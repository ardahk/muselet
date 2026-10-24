"""Scorer for evals/memory_followups.jsonl (lead-owned; pre-registered before any results were seen).

Each turn is resolved by `brain.memory.eval_adapter(utterance, ctx, history, longterm, llm)` with teacher forcing:
`history` holds the earlier turns' gold `{utterance, ctx, outcome}`, never the resolver's own outputs.

Grading per turn (`expect.type`):
  unchanged     pass iff the text is routed as said: not changed and no ask.
  rewrite       pass iff changed, not an ask, every `all` group has an alternative in the resolved text, and no `none`
                term occurs (case-insensitive substrings on the URL-unquoted text).
  not_resolved  pass iff no referent was invented: unchanged or an ask.
`changed` counts only when the resolved text differs from the utterance (case/whitespace-insensitive).

Ship rules (holdout split; latency is gated separately in-brain, the wall ms here is a proxy):
  phase 1 (`--mode rules|llm`):  rewrite accuracy over non-`longterm` categories >= 0.85 AND false-rewrite <= 0.02
  phase 2 (`--longterm`):        rewrite accuracy over all categories >= 0.85 AND false-rewrite <= 0.02
  false-rewrite = share of `unchanged` turns (all categories) that were changed. Any adapter exception fails ship.
Holdout runs print aggregates only; per-turn records go to runs/memory_eval/ (gitignored).

  uv run --project ml python evals/memory_eval.py --split tune --mode rules
  uv run --project ml python evals/memory_eval.py --split holdout --mode llm --llm-model mlx-community/Qwen3.5-4B-4bit
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote_plus

ROOT = Path(__file__).resolve().parents[1]
GATE_ACC, GATE_FALSE = 0.85, 0.02


def norm(s: str) -> str:
    return " ".join(unquote_plus(s or "").lower().split())


def grade(expect: dict, utterance: str, res: dict) -> bool:
    changed = bool(res.get("changed")) and norm(res.get("text", "")) != norm(utterance)
    ask = res.get("path") == "ask"
    kind = expect["type"]
    if kind == "unchanged":
        return not changed and not ask
    if kind == "not_resolved":
        return not changed or ask
    if kind == "rewrite":
        if not changed or ask:
            return False
        text = norm(res.get("text", ""))
        return (all(any(norm(a) in text for a in group) for group in expect["all"])
                and not any(norm(t) in text for t in expect.get("none", [])))
    raise ValueError(f"unknown expect type {kind!r}")


def pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2)


def make_llm(model: str):
    from brain.catalog import Catalog
    from brain.planner import Planner
    planner = Planner(model, Catalog.load())
    return lambda prompt, max_tokens: planner.complete(prompt, max_tokens)


def run(items: list[dict], adapter, llm, longterm: bool) -> list[dict]:
    records = []
    for seq in items:
        turns = seq["turns"]
        for i, turn in enumerate(turns):
            history = [{"utterance": t["utterance"], "ctx": t["ctx"], "outcome": t["outcome"]} for t in turns[:i]]
            t0 = time.perf_counter()
            try:
                res, err = adapter(turn["utterance"], turn["ctx"], history,
                                   seq.get("longterm") if longterm else None, llm), None
            except Exception as e:  # a crash fails the turn, never the run
                res, err = {"text": turn["utterance"], "changed": False, "path": "error"}, repr(e)
            wall = (time.perf_counter() - t0) * 1000
            records.append({"id": seq["id"], "turn": i, "category": seq["category"], "split": seq["split"],
                            "expect": turn["expect"]["type"], "utterance": turn["utterance"],
                            "text": res.get("text"), "path": res.get("path"), "changed": res.get("changed"),
                            "pass": err is None and grade(turn["expect"], turn["utterance"], res),
                            "wall_ms": round(wall, 3), "ms": res.get("ms"), "error": err})
    return records


def summarize(records: list[dict], longterm: bool) -> dict:
    def rate(rs, key=lambda r: r["pass"]):
        return round(sum(map(key, rs)) / len(rs), 4) if rs else None

    rw = [r for r in records if r["expect"] == "rewrite"]
    rw_scope = rw if longterm else [r for r in rw if r["category"] != "longterm"]
    unch = [r for r in records if r["expect"] == "unchanged"]
    nr = [r for r in records if r["expect"] == "not_resolved"]
    acc = rate(rw_scope)
    false = rate(unch, key=lambda r: r["error"] is None and not r["pass"] and r["path"] != "ask")
    errors = sum(r["error"] is not None for r in records)
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    by_path = defaultdict(list)
    for r in records:
        by_path[r["path"]].append(r["wall_ms"])
    return {
        "turns": len(records), "errors": errors,
        "rewrite_acc": acc, "rewrite_n": len(rw_scope), "rewrite_scope": "all" if longterm else "non-longterm",
        "rewrite_acc_all": rate(rw), "false_rewrite": false, "unchanged_n": len(unch),
        "spurious_ask": rate(unch, key=lambda r: r["path"] == "ask"),
        "not_resolved_acc": rate(nr), "not_resolved_n": len(nr),
        "by_category": {c: {"n": len(rs), "pass": rate(rs),
                            "rewrite": rate([r for r in rs if r["expect"] == "rewrite"])}
                        for c, rs in sorted(by_cat.items())},
        "wall_ms": {p or "none": {"n": len(v), "p50": pct(v, .5), "p95": pct(v, .95)} for p, v in by_path.items()},
        "fast_path_wall_ms_p50": pct([r["wall_ms"] for r in unch if r["path"] in (None, "none")], .5),
        "ship": bool(errors == 0 and acc is not None and false is not None
                     and acc >= GATE_ACC and false <= GATE_FALSE),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "evals/memory_followups.jsonl")
    ap.add_argument("--split", choices=["tune", "holdout", "all"], default="tune")
    ap.add_argument("--mode", choices=["none", "rules", "llm"], default="rules",
                    help="none = identity baseline, rules = adapter without LLM, llm = adapter with --llm-model")
    ap.add_argument("--llm-model", default="mlx-community/Qwen3.5-4B-4bit")
    ap.add_argument("--longterm", action="store_true", help="pass the seeded long-term memories (phase 2)")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args(argv)

    items = [json.loads(line) for line in args.data.read_text().splitlines() if line.strip()]
    if args.split != "all":
        items = [s for s in items if s["split"] == args.split]
    if args.mode == "none":
        def adapter(utterance, *_):
            return {"text": utterance, "changed": False, "path": "none"}
        llm = None
    else:
        from brain.memory import eval_adapter as adapter
        llm = make_llm(args.llm_model) if args.mode == "llm" else None

    records = run(items, adapter, llm, args.longterm)
    summary = {"split": args.split, "mode": args.mode, "longterm": args.longterm,
               "llm_model": args.llm_model if args.mode == "llm" else None,
               "sequences": len(items), **summarize(records, args.longterm)}
    tag = args.tag or f"{args.split}_{args.mode}{'_lt' if args.longterm else ''}"
    out = ROOT / "runs/memory_eval" / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{tag}.json").write_text(json.dumps(summary, indent=1))
    with open(out / f"{tag}.records.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(json.dumps(summary, indent=1))
    if args.split == "tune":
        for r in records:
            if not r["pass"]:
                print(f"FAIL {r['id']}#{r['turn']} [{r['category']}/{r['expect']}] {r['utterance']!r} -> "
                      f"{r['path']}: {r['text']!r} {r['error'] or ''}", file=sys.stderr)
    print(f"wrote {out / tag}.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
