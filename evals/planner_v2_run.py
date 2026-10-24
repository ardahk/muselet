"""Run the unchanged v1 planner bench (evals/planner_offline.py: Runner, knobs, grade) on the v2 scenarios.

  uv run --project ml python evals/planner_v2_run.py --v2-set v2-tune --model mlx-community/Qwen3.5-4B-4bit \
      --tag v2tune-base4b --constrain --done-alone --history dsl --system-extra prompts/planner_fewshot.md
  uv run --project ml python evals/planner_v2_run.py --v2-set v2-holdout --regrade <tag>
All other flags are planner_offline.py's; --set is fixed to `tune` internally (its scenario list is replaced).
Never tune on v2-holdout.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import planner_offline as po  # noqa: E402


def load(split: str | None) -> list[dict]:
    rows = [json.loads(x) for x in (HERE / "planner_scenarios_v2.jsonl").read_text().splitlines() if x.strip()]
    return [r for r in rows if split in (None, "all", r["split"])]


if __name__ == "__main__":
    argv = sys.argv[1:]
    split = "v2-tune"
    if "--v2-set" in argv:
        i = argv.index("--v2-set")
        split = argv[i + 1]
        del argv[i:i + 2]
        if split not in ("v2-tune", "v2-holdout", "all"):
            sys.exit("--v2-set must be v2-tune, v2-holdout or all")
    if "--set" in argv:
        sys.exit("use --v2-set (v2-tune | v2-holdout | all), not --set")
    scen = load(split)
    po.S[:] = scen
    po.TUNE[:] = load("all")          # regrade looks scenarios up by id here
    sys.argv = [sys.argv[0], *argv]
    po.main()
