"""Compare planner retrieval ablations using saved offline benchmark runs."""

import argparse
import json
import statistics
from pathlib import Path

from statistics import mean

SETS = ("v1-tune", "v1-holdout", "v1-holdout2", "v2-holdout")
HOLDOUTS = SETS[1:]
FILE_SETS = {
    "v1tune": "v1-tune",
    "v1holdout": "v1-holdout",
    "v1holdout2": "v1-holdout2",
    "v2holdout": "v2-holdout",
}


def decide(res: dict) -> tuple[int, list[str]]:
    """res[k][set] = {"n", "n_pass", "ttft_ms_p50"}; k=0 required. Pre-registered rule: ship k>0 only if the
    unweighted mean pass rate over the 3 holdouts gains >= 0.03 over k=0, no set (all 4) loses more than 1
    passing scenario, and TTFT p50 rises by <= 150 ms on every set. Several k pass -> highest gain, tie -> smaller k."""
    def rate(r, s):
        return r[s]["n_pass"] / r[s]["n"]
    base, notes, ok = res[0], [], {}
    for k in (1, 2):
        if k not in res:
            continue
        r = res[k]
        gain = mean(rate(r, s) for s in HOLDOUTS) - mean(rate(base, s) for s in HOLDOUTS)
        why = []
        if gain < 0.03 - 1e-9:
            why.append(f"holdout gain {gain:+.3f} < +0.030")
        drops = {s: base[s]["n_pass"] - r[s]["n_pass"] for s in SETS}
        if bad := [s for s in SETS if drops[s] > 1]:
            why.append("drop > 1 scenario: " + ", ".join(f"{s} -{drops[s]}" for s in bad))
        dt = {s: r[s]["ttft_ms_p50"] - base[s]["ttft_ms_p50"] for s in SETS}
        if slow := [s for s in SETS if dt[s] > 150]:
            why.append("TTFT p50 > +150 ms: " + ", ".join(f"{s} +{dt[s]:.0f}" for s in slow))
        notes.append(f"k={k}: gain {gain:+.3f} -> " + ("PASS" if not why else "FAIL (" + "; ".join(why) + ")"))
        if not why:
            ok[k] = gain
    if not ok:
        return 0, notes
    best = max(ok.values())
    return min(k for k, g in ok.items() if g >= best - 1e-9), notes


def _row_stats(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("benchmark run has no rows")
    return {
        "n": len(rows),
        "n_pass": sum(row["pass"] for row in rows),
        "ttft_ms_p50": statistics.median(row["ttft_ms"] for row in rows),
        "prompt_tokens_mean": statistics.mean(row["prompt_tokens"] for row in rows),
        "dynamic_tokens_mean": statistics.mean(row["dynamic_tokens"] for row in rows),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="ret")
    parser.add_argument("--runs-dir", type=Path, default=Path(__file__).resolve().parents[1] / "runs" / "planner_offline")
    args = parser.parse_args(argv)
    results = {}
    for k in (0, 1, 2):
        current = {}
        missing = []
        for tag, set_name in FILE_SETS.items():
            path = args.runs_dir / f"{args.prefix}-k{k}-{tag}.json"
            if not path.is_file():
                missing.append(tag)
                continue
            data = json.loads(path.read_text())
            current[set_name] = _row_stats(data["rows"])
        if k == 0 and missing:
            parser.error(f"missing required k=0 run(s): {', '.join(missing)}")
        if k > 0 and missing:
            continue
        results[k] = current

    print("| k | set | pass rate | n_pass/n | prompt tokens mean | dynamic tokens mean | TTFT p50 ms |")
    print("|---:|---|---:|---:|---:|---:|---:|")
    for k in sorted(results):
        for set_name in SETS:
            row = results[k][set_name]
            print(f"| {k} | {set_name} | {row['n_pass'] / row['n']:.3f} | "
                  f"{row['n_pass']}/{row['n']} | {row['prompt_tokens_mean']:.1f} | "
                  f"{row['dynamic_tokens_mean']:.1f} | {row['ttft_ms_p50']:.1f} |")
    decision, notes = decide(results)
    if decision:
        print(f"DECISION: ship retrieval_k={decision}")
    else:
        print("DECISION: keep retrieval_k=0")
    for note in notes:
        print(note)


if __name__ == "__main__":
    main()
