"""Build evals/planner_scenarios_v2.jsonl from the hand-written category files (deterministic).

Split: per category, same-goal groups are assigned in definition order to the smaller split (validator checks 50/50).
  python3 evals/planner_v2_build.py && python3 evals/planner_v2_validate.py
"""

import collections
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from planner_v2_lib import SCENARIOS  # noqa: E402

CATEGORIES = ["single_step", "recovery", "done_gating", "ask", "confirm", "injection", "sign_in", "writing",
              "compound", "script"]


def build() -> list[dict]:
    SCENARIOS.clear()
    for c in CATEGORIES:
        if (HERE / f"planner_v2_cat_{c}.py").exists() or "--strict" in sys.argv:
            importlib.import_module(f"planner_v2_cat_{c}")
    # scenarios with the same goal in a category (e.g. a confirm case and its "-> yes" follow-up) form one group and
    # land in the same split; groups go, largest first then in definition order, to whichever split of the category is smaller
    groups = collections.defaultdict(list)
    for s in SCENARIOS:
        groups[(s["category"], s["goal"].lower().strip())].append(s)
    count = collections.defaultdict(collections.Counter)
    for (cat, _), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        split = "v2-tune" if count[cat]["v2-tune"] <= count[cat]["v2-holdout"] else "v2-holdout"
        for s in members:
            s["split"] = split
        count[cat][split] += len(members)
    return SCENARIOS


if __name__ == "__main__":
    rows = build()
    out = HERE / "planner_scenarios_v2.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {len(rows)} scenarios to {out}")
