"""Before/after report for evals/open_ended.jsonl live runs.

uv run --project ml python evals/open_ended_report.py runs/bench/live/<before> runs/bench/live/<after>
Reads each run's results.jsonl (rows carry the brain trace). Pass = strict_pass over executed cases
(not skipped / harness_timeout); step latency = planner `turn_ms` (plan + execute one batch).
"""
import json
import math
import sys
from pathlib import Path


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def load(run: Path) -> list[dict]:
    return [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines() if line.strip()]


def turns(trace):
    return [d for d in (trace or {}).get("decisions", []) if isinstance(d, dict) and "planner_turn" in d]


def stats(rows: list[dict]) -> dict:
    ex = [r for r in rows if r.get("status") not in ("skipped", "harness_timeout") and not r.get("ungradable")]
    steps = [float(t["turn_ms"]) for r in ex for t in turns(r.get("trace")) if t.get("turn_ms") is not None]
    sec = lambda key: [float(r[key]) for r in ex if r.get(key) is not None]
    return {
        "executed": len(ex), "passed": sum(bool(r.get("strict_pass")) for r in ex),
        "skipped": sorted({f"{r.get('id')}:{r.get('skip_reason')}" for r in rows if r.get("status") == "skipped"}),
        "step_p50_ms": pct(steps, .5), "step_p95_ms": pct(steps, .95), "steps": len(steps),
        "first_action_p50_s": pct(sec("first_action_latency_s"), .5),
        "completion_p50_s": pct(sec("utterance_latency_s"), .5),
        "open_ended_routed": sum(bool((r.get("trace") or {}).get("open_ended")) for r in ex),
        "false_done": sum(bool(r.get("false_done")) for r in ex),
        "by_id": {r.get("id"): bool(r.get("strict_pass")) for r in ex},
    }


def fmt(v, nd=0):
    return "-" if v is None else f"{v:.{nd}f}"


def main(argv):
    runs = [Path(a) for a in argv]
    if not runs:
        sys.exit(__doc__)
    res = [stats(load(r)) for r in runs]
    print("| run | pass | rate | step p50 ms | step p95 ms | steps | first action p50 s | completion p50 s | open_ended routed | false done |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for run, s in zip(runs, res):
        rate = s["passed"] / s["executed"] if s["executed"] else None
        print(f"| {run.name} | {s['passed']}/{s['executed']} | {fmt(rate, 3)} | {fmt(s['step_p50_ms'])} | "
              f"{fmt(s['step_p95_ms'])} | {s['steps']} | {fmt(s['first_action_p50_s'], 2)} | "
              f"{fmt(s['completion_p50_s'], 2)} | {s['open_ended_routed']} | {s['false_done']} |")
    ids = sorted({i for s in res for i in s["by_id"]})
    print("\n| case | " + " | ".join(r.name for r in runs) + " |\n|---|" + "---|" * len(runs))
    for i in ids:
        print(f"| {i} | " + " | ".join({True: "pass", False: "FAIL", None: "skip"}[s["by_id"].get(i)] for s in res) + " |")
    for run, s in zip(runs, res):
        if s["skipped"]:
            print(f"\nskipped in {run.name}: " + ", ".join(s["skipped"]))


if __name__ == "__main__":
    main(sys.argv[1:])
