"""Router check on the Mac: parity with training, then a tuned-vs-tuned comparison.

  1. render parity   runtime RouteRenderer tokens/choice_pos == training tokens, per parity row
  2. logit parity    runtime DecisionEngine probs vs the Tinker sampler's probs (argmax agreement, max |dp|)
                     (only meaningful for the trained model the parity file came from; skip with --no-logit-parity)
  3. tau fit         on the parity rows (cloud A's held-out val items = dev), per model: the gate
                     "p_top < tau -> MULTI_STEP" that maximizes dev macro-F1 (ties: higher accuracy, then lower tau)
  4. route_v1        ungated top-1, and accuracy / macro-F1 at the model's own dev-fitted tau

  uv run --project ml python evals/router_check.py --model models/route-4b-main-mlx4 --parity P --tag trained_main
  uv run --project ml python evals/router_check.py --model mlx-community/Qwen3.5-4B-4bit --parity P --tag base \
      --no-logit-parity
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "src"))

TAUS = [0.0, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8]


def norm_ctx(ctx: dict) -> dict:
    return {k: (v if v is not None else "none") if k != "online" else v for k, v in (ctx or {}).items()}


def gated(rows, tau):
    """rows: (gold, top, p_top) -> accuracy, macro-F1 over gold labels."""
    pairs = [(g, t if p >= tau else "MULTI_STEP") for g, t, p in rows]
    acc = sum(g == p for g, p in pairs) / len(pairs)
    f1s = []
    for lab in sorted({g for g, _ in pairs}):
        tp = sum(g == lab and p == lab for g, p in pairs)
        fp = sum(g != lab and p == lab for g, p in pairs)
        fn = sum(g == lab and p != lab for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0)
    return acc, sum(f1s) / len(f1s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--parity", required=True)
    ap.add_argument("--cases", default=str(ROOT / "evals" / "route_v1.jsonl"))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--no-logit-parity", action="store_true")
    a = ap.parse_args()

    from brain.catalog import Catalog
    from brain.decision import DecisionEngine
    eng = DecisionEngine(a.model, Catalog.load())
    par = [json.loads(x) for x in open(a.parity) if x.strip()]
    par = [r for r in par if r.get("kind") != "header" and "tokens" in r]

    render_ok, render_bad = 0, []
    agree, dps, dev_rows = 0, [], []
    t0 = time.time()
    for r in par:
        ctx = norm_ctx(r.get("context"))
        rend = eng.route_renderer.render(eng._route_decision(r["utterance"], ctx))
        same = rend.tokens[: rend.choice_pos] == r["tokens"][: r["choice_pos"]] and rend.choice_pos == r["choice_pos"]
        render_ok += same
        if not same and len(render_bad) < 5:
            k = next((i for i, (x, y) in enumerate(zip(rend.tokens, r["tokens"])) if x != y),
                     min(len(rend.tokens), len(r["tokens"])))
            render_bad.append({"utterance": r["utterance"], "first_diff": k,
                               "ours": eng.tokenizer.decode(rend.tokens[max(0, k - 5): k + 15]),
                               "theirs": eng.tokenizer.decode(r["tokens"][max(0, k - 5): k + 15])})
        res = eng.route(r["utterance"], ctx)
        dev_rows.append((r["label"], res.top, res.p_top))
        if not a.no_logit_parity:
            tp = r.get("tinker_probs") or r.get("probs") or {}
            if tp:
                labs = [x for x in tp if x in res.probs]
                agree += max(labs, key=lambda x: res.probs[x]) == max(labs, key=lambda x: tp[x])
                dps.append(max(abs(res.probs[x] - tp[x]) for x in labs))
    n = len(par)

    fits = []
    for tau in TAUS:
        acc, f1 = gated(dev_rows, tau)
        fits.append((f1, acc, -tau, tau))
    best = max(fits)
    tau = best[3]

    cases = [json.loads(x) for x in open(a.cases) if x.strip()]
    v1, ms = [], []
    for c in cases:
        res = eng.route(c["utterance"], c.get("ctx", {}))
        v1.append((c["label"], res.top, res.p_top))
        ms.append(res.ms["route_ms"])
    acc_v1, f1_v1 = gated(v1, tau)
    acc_def, f1_def = gated(v1, 0.55)
    out = {
        "tag": a.tag, "model": a.model, "parity_file": a.parity, "n_parity": n,
        "render_parity": round(render_ok / n, 4), "render_mismatches": render_bad,
        "logit_argmax_agreement": None if a.no_logit_parity or not dps else round(agree / len(dps), 4),
        "logit_max_abs_dp_mean": None if not dps else round(statistics.mean(dps), 4),
        "logit_max_abs_dp_max": None if not dps else round(max(dps), 4),
        "dev_ungated_top1": round(sum(g == t for g, t, _ in dev_rows) / n, 4),
        "dev_tau_grid": [{"tau": t, "macro_f1": round(f, 4), "acc": round(ac, 4)} for f, ac, _, t in fits],
        "tau_fitted": tau,
        "route_v1": {"n": len(cases), "ungated_top1": round(sum(g == t for g, t, _ in v1) / len(v1), 4),
                     "acc_at_fitted_tau": round(acc_v1, 4), "macro_f1_at_fitted_tau": round(f1_v1, 4),
                     "acc_at_0.55": round(acc_def, 4), "macro_f1_at_0.55": round(f1_def, 4),
                     "route_ms_p50": round(statistics.median(ms), 1),
                     "route_ms_p95": round(sorted(ms)[int(0.95 * (len(ms) - 1))], 1)},
        "sec": round(time.time() - t0, 1),
    }
    d = ROOT / "runs" / "router"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{a.tag}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
