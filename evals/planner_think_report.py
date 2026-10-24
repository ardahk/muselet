"""Planner thinking-mode matrix: table + pre-registered ship decision from saved offline runs.

Run files: runs/planner_offline/<prefix>-<config>-<set>.json, set in v1tune | v1holdout | v1holdout2 | v2holdout
(v1tune optional, reference only), e.g. think-4b-t512-qwen-all-v2holdout.json.
Rule (pre-registered, cloud/builder_planner_think.md): a config ships if its unweighted mean pass over the three
holdouts is >= SHIPPED + 0.03 (= .672) and its per-step p50 (median plan_ms + retrieval_ms over all holdout rows)
is <= 3000 ms. Among passing configs the highest holdout mean wins; ties go to the lower p50. None -> keep think=0.

  uv run --project ml python evals/planner_think_report.py --prefix think
"""

import argparse
import json
import statistics
from pathlib import Path

FILE_SETS = {"v1tune": "v1-tune", "v1holdout": "v1-holdout", "v1holdout2": "v1-holdout2", "v2holdout": "v2-holdout"}
HOLDOUTS = ("v1-holdout", "v1-holdout2", "v2-holdout")
SHIPPED = 0.642
GAIN = 0.03
P50_MAX_MS = 3000.0


def step_ms(row: dict) -> float:
    return row["plan_ms"] + row.get("retrieval_ms", 0.0)


def config_stats(sets: dict[str, list[dict]]) -> dict:
    """sets[set_name] = run rows. Requires the three holdouts."""
    rates = {s: sum(r["pass"] for r in rows) / len(rows) for s, rows in sets.items()}
    ho_rows = [r for s in HOLDOUTS for r in sets[s]]
    ms = sorted(step_ms(r) for r in ho_rows)
    return {"rates": rates, "n_pass": {s: sum(r["pass"] for r in rows) for s, rows in sets.items()},
            "n": {s: len(rows) for s, rows in sets.items()},
            "holdout_mean": statistics.mean(rates[s] for s in HOLDOUTS),
            "p50_ms": statistics.median(ms), "p95_ms": ms[int(0.95 * (len(ms) - 1))],
            "think_tokens_mean": statistics.mean(r.get("think_tokens", 0) for r in ho_rows)}


def decide(stats: dict[str, dict]) -> tuple[str | None, list[str]]:
    notes, ok = [], {}
    for cfg, st in sorted(stats.items()):
        why = []
        if st["holdout_mean"] < SHIPPED + GAIN - 1e-9:
            why.append(f"holdout mean {st['holdout_mean']:.3f} < {SHIPPED + GAIN:.3f}")
        if st["p50_ms"] > P50_MAX_MS:
            why.append(f"step p50 {st['p50_ms']:.0f} ms > {P50_MAX_MS:.0f}")
        notes.append(f"{cfg}: " + ("PASS" if not why else "FAIL (" + "; ".join(why) + ")"))
        if not why:
            ok[cfg] = st
    if not ok:
        return None, notes
    return min(ok, key=lambda c: (-round(ok[c]["holdout_mean"], 9), ok[c]["p50_ms"])), notes


def load(runs_dir: Path, prefix: str) -> dict[str, dict]:
    found: dict[str, dict[str, list[dict]]] = {}
    for path in sorted(runs_dir.glob(f"{prefix}-*.json")):
        stem = path.stem[len(prefix) + 1:]
        for tag, set_name in FILE_SETS.items():
            if stem.endswith("-" + tag) and not (tag == "v1holdout" and stem.endswith("-v1holdout2")):
                found.setdefault(stem[:-len(tag) - 1], {})[set_name] = json.loads(path.read_text())["rows"]
                break
    out = {}
    for cfg, sets in found.items():
        if missing := [s for s in HOLDOUTS if not sets.get(s)]:
            print(f"skip {cfg}: missing {', '.join(missing)}")
            continue
        out[cfg] = config_stats(sets)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="think")
    ap.add_argument("--runs-dir", type=Path, default=Path(__file__).resolve().parents[1] / "runs" / "planner_offline")
    a = ap.parse_args(argv)
    stats = load(a.runs_dir, a.prefix)
    if not stats:
        ap.error(f"no complete configs for prefix {a.prefix!r} in {a.runs_dir}")
    print("| config | v1-tune | v1-holdout | v1-holdout2 | v2-holdout | holdout mean | step p50 ms | step p95 ms "
          "| think tokens mean |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for cfg, st in sorted(stats.items()):
        cells = [f"{st['n_pass'][s]}/{st['n'][s]} ({st['rates'][s]:.3f})" if s in st["rates"] else "-"
                 for s in FILE_SETS.values()]
        print(f"| {cfg} | " + " | ".join(cells) + f" | {st['holdout_mean']:.3f} | {st['p50_ms']:.0f} | "
              f"{st['p95_ms']:.0f} | {st['think_tokens_mean']:.1f} |")
    best, notes = decide(stats)
    print(f"DECISION: ship {best}" if best else "DECISION: keep think=0 (no config passes)")
    for n in notes:
        print(n)


if __name__ == "__main__":
    main()
