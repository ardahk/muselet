"""Write the 2% generation sample report: 30 random items per label (SPEC 1.8 step 3)."""

from __future__ import annotations

import argparse
import collections
import json
import random
from pathlib import Path

from muselet_train.catalog import option_names
from muselet_train.gen import DATA, _load

REPO = Path(__file__).resolve().parents[3]


def ctx_line(c: dict) -> str:
    return (f"app={c['app']} | focused={c['focused']} | selection={'yes' if c['selection'] else 'no'} | "
            f"online={'yes' if c['online'] else 'no'} | last_action={c['last_action'] or 'none'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--per-label", type=int, default=30)
    a = ap.parse_args()
    rng = random.Random(0)
    route = _load(a.run, "route.jsonl")
    args = {(x["utterance"], x["src"]): x["target"] for x in _load(a.run, "args.jsonl")}
    stats = json.loads((DATA / a.run / "stats.json").read_text())
    usage = json.loads((DATA / a.run / "usage.json").read_text())
    by = collections.defaultdict(list)
    for r in route:
        by[r["label"]].append(r)
    picked = []
    L = [f"# Phase 1 generation: 2% sample (`{a.run}`)\n",
         f"Route items kept: {len(route)}; ARGS items: {stats['args']}. "
         f"{a.per_label} random items per label below (`*` = from a G3 context pair).\n",
         "## Token usage\n", "| model | calls | input tok | output tok |", "|---|---|---|---|"]
    L += [f"| `{m}` | {u['calls']} | {u['input']:,} | {u['output']:,} |" for m, u in usage.items()]
    L += ["", "## Rejects\n", "| label / reason | n |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in stats["rejects"].items()]
    L += ["", "## Kept per label\n", "| label | n |", "|---|---|"]
    L += [f"| {lab} | {len(by[lab])} |" for lab in option_names()]
    for lab in option_names():
        xs = rng.sample(by[lab], min(a.per_label, len(by[lab])))
        picked += xs
        L += ["", f"## {lab} ({len(by[lab])} kept)\n", "| request | args / nearest_skill | context |", "|---|---|---|"]
        for x in xs:
            extra = args.get((x["utterance"], x["src"])) if "args" in x else (
                f"nearest={x['nearest_skill']}" if "nearest_skill" in x else "")
            t = x["utterance"].replace("|", "\\|")
            L.append(f"| {'*' if x.get('g3') else ''}{t} | `{extra or ''}` | {ctx_line(x['context']).replace('|', '¦')} |")
    (REPO / "training/reports").mkdir(parents=True, exist_ok=True)
    (REPO / f"training/reports/gen_{a.run}.md").write_text("\n".join(L) + "\n")
    (REPO / f"training/artifacts/gen_{a.run}_picked.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in picked))
    print("wrote", len(picked))


if __name__ == "__main__":
    main()
