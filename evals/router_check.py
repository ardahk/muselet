"""Router check on the Mac (MLX, free): fit tau on val, then route_v1_clean / route_v2, tuned vs tuned.

--set (each run writes runs/router/<router>_<set>.json; --set val must run first for every router):
  val             it3 held-out val (val_route.jsonl, 1396 = it2's val split + it3 additions; rows that occur in it2's
                  train are dropped for every router). Tau grid fit, the only place tau is ever fitted: the gate
                  "p_top < tau -> MULTI_STEP" maximizing macro-F1 (ties: accuracy, then lower tau). Also ARGS exact on
                  val_args.jsonl (983, gold skill given). Rows whose gold label the router cannot emit are excluded.
  route_v1_clean  103 cases; route_v2 955 cases (labelled under catalog v3), also on the v2-catalog subset (labels it2
                  can emit). Both at the tau fitted on val for that router (or --tau); ungated top-1, per-label, ECE.
  parity          parity_300.jsonl: runtime render == training render, MLX top-1 vs Tinker sampler top-1 (target
                  >= 0.99) and |dp|; meaningful for --router it3 only.
val_route.jsonl, val_args.jsonl and parity_300.jsonl ship with jonsnov/muselet-route-4b-it3-mlx4 (--data-dir).

  uv run --project ml python evals/router_check.py --router it3 --set parity
  for r in it2 it3; do for s in val route_v1_clean route_v2; do
    uv run --project ml python evals/router_check.py --router $r --set $s; done; done
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "src"))

TAUS = [0.0, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]
V2 = ROOT / "skills" / "catalog.json"
V3 = ROOT / "training" / "artifacts" / "catalog_v3.json"
ROUTERS = {  # name -> (model, catalog the router was trained on, serve_brain.sh default tau)
    "it2": ("models/route-4b-it2-mlx4", V2, 0.65),
    "it3": ("models/route-4b-it3-mlx4", V3, 0.65),
    "base": ("mlx-community/Qwen3.5-4B-4bit", V2, 0.20),
}
CASES = {"route_v1_clean": ROOT / "evals" / "route_v1_clean.jsonl", "route_v2": ROOT / "evals" / "route_v2.jsonl"}
OUT = ROOT / "runs" / "router"


def load(p):
    return [json.loads(x) for x in open(p) if x.strip()]


def ctx_of(r: dict) -> dict:
    c = r.get("context", r.get("ctx")) or {}
    return {k: ("none" if v is None and k != "online" else v) for k, v in c.items()}


def gated(rows, tau):
    """rows: (gold, top, p_top) -> accuracy, macro-F1 over gold labels, per-label accuracy."""
    pairs = [(g, t if p >= tau else "MULTI_STEP") for g, t, p in rows]
    acc = sum(g == p for g, p in pairs) / len(pairs)
    f1s, per = [], {}
    for lab in sorted({g for g, _ in pairs}):
        tp = sum(g == lab and p == lab for g, p in pairs)
        fp = sum(g != lab and p == lab for g, p in pairs)
        fn = sum(g == lab and p != lab for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0)
        per[lab] = {"n": tp + fn, "acc": round(rc, 4)}
    return acc, sum(f1s) / len(f1s), per


def ece(rows, bins=15):
    """Expected calibration error of p_top vs ungated top-1 correctness."""
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        it = [(p, g == t) for g, t, p in rows if lo <= p < hi or (b == bins - 1 and p == 1)]
        if it:
            e += len(it) / len(rows) * abs(sum(c for _, c in it) / len(it) - sum(p for p, _ in it) / len(it))
    return round(e, 4)


def summary(rows, tau):
    acc, f1, per = gated(rows, tau)
    return {"n": len(rows), "ungated_top1": round(sum(g == t for g, t, _ in rows) / len(rows), 4),
            "acc": round(acc, 4), "macro_f1": round(f1, 4), "ece_15": ece(rows), "per_label": per}


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1) if xs else None


def norm_args(d: dict) -> dict:
    return {k: v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v).strip().lower()
            for k, v in d.items() if k not in ("ms", "_raw")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True, help="it2 | it3 | base | a model path (then pass --catalog)")
    ap.add_argument("--set", required=True, choices=["val", "route_v1_clean", "route_v2", "parity"])
    ap.add_argument("--catalog", help="route catalog (default: the router's training catalog)")
    ap.add_argument("--data-dir", default=str(ROOT / ROUTERS["it3"][0]),
                    help="dir with val_route.jsonl, val_args.jsonl, parity_300.jsonl (the it3 HF repo)")
    ap.add_argument("--tau", type=float, help="override the val-fitted tau (route sets only)")
    ap.add_argument("--args-model", help="ARGS model (default: the router itself, as tools/serve_brain.sh)")
    ap.add_argument("--limit", type=int, help="first N rows only (smoke runs)")
    ap.add_argument("--tag", help="output name (default <router>_<set>)")
    a = ap.parse_args()

    from brain.catalog import Catalog
    from brain.cli import _resolve_model
    from brain.decision import DecisionEngine, catalog_options
    model, cat_path, _ = ROUTERS.get(a.router, (a.router, V2, None))
    cat = Catalog.load(a.catalog or cat_path)
    tag = a.tag or f"{Path(a.router).name}_{a.set}"
    data = Path(a.data_dir)
    if a.set != "val" and a.set != "parity" and a.tau is None:
        fit = OUT / f"{Path(a.router).name}_val.json"
        if not fit.exists():
            sys.exit(f"no val fit at {fit}: run --set val first (tau is never fitted on eval sets) or pass --tau")
        tau = json.loads(fit.read_text())["tau_fitted"]
    else:
        tau = a.tau
    eng = DecisionEngine(_resolve_model(model), cat,
                         args_model_path=_resolve_model(a.args_model) if a.args_model else None)
    names = {n for n, _ in catalog_options(cat)}
    out = {"tag": tag, "router": a.router, "model": model, "catalog": str(cat_path if not a.catalog else a.catalog),
           "catalog_version": cat.version, "set": a.set, "args_model": eng.args_model_path}
    t0 = time.time()

    def route_rows(cases):
        rows, ms = [], []
        for c in cases:
            res = eng.route(c["utterance"], ctx_of(c))
            rows.append((c["label"], res.top, res.p_top))
            ms.append(res.ms["route_ms"])
        return rows, ms

    if a.set == "parity":
        par = [r for r in load(data / "parity_300.jsonl") if "tokens" in r][: a.limit]
        ok, bad, agree, dps, rows = 0, [], 0, [], []
        for r in par:
            ctx = ctx_of(r)
            rend = eng.route_renderer.render(eng._route_decision(r["utterance"], ctx))
            same = rend.choice_pos == r["choice_pos"] and rend.tokens[: rend.choice_pos] == r["tokens"][: r["choice_pos"]]
            ok += same
            if not same and len(bad) < 5:
                bad.append(r["utterance"])
            res = eng.route(r["utterance"], ctx)
            rows.append((r["label"], res.top, res.p_top))
            tp = r["tinker_probs"]
            labs = [x for x in tp if x in res.probs]
            agree += max(labs, key=res.probs.get) == max(labs, key=tp.get)
            dps.append(max(abs(res.probs[x] - tp[x]) for x in labs))
        out.update({"n": len(par), "render_parity": round(ok / len(par), 4), "render_mismatches": bad,
                    "top1_agreement": round(agree / len(par), 4), "target": 0.99,
                    "max_abs_dp_mean": round(statistics.mean(dps), 4), "max_abs_dp_max": round(max(dps), 4),
                    "mlx_top1_vs_gold": round(sum(g == t for g, t, _ in rows) / len(rows), 4),
                    "tinker_top1_vs_gold": round(sum(max(r["tinker_probs"], key=r["tinker_probs"].get) == r["label"]
                                                     for r in par) / len(par), 4)})
    elif a.set == "val":
        val = load(data / "val_route.jsonl")
        keep = [r for r in val if not r.get("in_it2_train") and r["label"] in names][: a.limit]
        rows, ms = route_rows(keep)
        fits = [(f, ac, -t, t) for t in TAUS for ac, f, _ in [gated(rows, t)]]
        tau = max(fits)[3]
        out.update({"n_file": len(val), "n_excluded_not_in_catalog": sum(r["label"] not in names for r in val),
                    "n_excluded_in_it2_train": sum(bool(r.get("in_it2_train")) for r in val),
                    "tau_grid": [{"tau": t, "macro_f1": round(f, 4), "acc": round(ac, 4)} for f, ac, _, t in fits],
                    "tau_fitted": tau, "route": summary(rows, tau),
                    "route_ms_p50": pct(ms, 0.5), "route_ms_p95": pct(ms, 0.95)})
        va = [r for r in load(data / "val_args.jsonl") if not r.get("in_it2_train") and r["skill"] in names][: a.limit]
        hits = raw_hits = 0
        ams = []
        for r in va:
            ext = eng.args(r["skill"], r["utterance"], ctx_of(r))
            argn = {x["name"] for x in (cat.get(r["skill"]) or {}).get("args", [])}
            gold = DecisionEngine._parse_args_line(r["target"], argn)
            hits += norm_args(ext) == norm_args(gold)
            raw_hits += ext["_raw"].strip() == r["target"].strip()
            ams.append(ext["ms"]["args_ms"])
        out["args_val"] = {"n": len(va), "exact": round(hits / len(va), 4) if va else None,
                           "raw_string_exact": round(raw_hits / len(va), 4) if va else None,
                           "args_ms_p50": pct(ams, 0.5)}
    else:
        cases = load(CASES[a.set])[: a.limit]
        rows, ms = route_rows(cases)
        out.update({"tau": tau, "tau_source": "--tau" if a.tau is not None else "val fit",
                    "route": summary(rows, tau), "route_ms_p50": pct(ms, 0.5), "route_ms_p95": pct(ms, 0.95)})
        if a.set == "route_v2":
            v2 = {n for n, _ in catalog_options(Catalog.load(V2))}
            sub = [r for c, r in zip(cases, rows) if c["label"] in v2]
            out["route_v2_catalog_subset"] = summary(sub, tau)
        # ARGS end-to-end as cli.eval_route scores it (same coercion and match rules), at the fitted tau
        from brain.orchestrator import Orchestrator
        orch = Orchestrator.__new__(Orchestrator)
        orch.catalog = cat

        def args_match(got: dict, gold: dict) -> bool:
            if set(got) != set(gold):
                return False
            for k, gv in gold.items():
                v = got[k]
                if isinstance(gv, (int, float)) and isinstance(v, (int, float)):
                    if v != gv:
                        return False
                elif str(v).strip().lower() != str(gv).strip().lower():
                    return False
            return True

        e2e_n = scored = hits = 0
        for c, (gold, top, p) in zip(cases, rows):
            if not c.get("args"):
                continue
            e2e_n += 1
            if (top if p >= tau else "MULTI_STEP") != gold:
                continue
            ext = eng.args(gold, c["utterance"], ctx_of(c))
            got = {k: v for k, v in ext.items() if k not in ("ms", "_raw", "missing")}
            got = Orchestrator._coerce_args(orch, gold, got, utterance=c["utterance"])
            got = {k: got[k] for k in c["args"] if k in got}
            scored += 1
            hits += args_match(got, c["args"])
        out["args_e2e"] = {"n_with_args": e2e_n, "n_scored": scored,
                           "args_exact": round(hits / scored, 4) if scored else None,
                           "e2e_exact": round(hits / e2e_n, 4) if e2e_n else None}
    out["sec"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{tag}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("tau_grid",)}, indent=1))


if __name__ == "__main__":
    main()
