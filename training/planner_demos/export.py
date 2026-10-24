"""Assemble the HF dataset folder (<dir>/hf) from build_states / teachers / keep outputs.

  ~/venvs/demos/bin/python training/planner_demos/export.py --dir ~/data/planner_demos
  ~/venvs/demos/bin/python training/planner_demos/upload.py --dir ~/data/planner_demos/hf --repo jonsnov/muselet-planner-demos-v1
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402
import teachers  # noqa: E402

README = """---
license: other
private: true
---
# muselet-planner-demos-v1

Teacher demonstrations for the Muselet System-2 planner (DSL action batches over a macOS accessibility tree).

- `demos.jsonl.gz` ({kept} rows): chat datums. `messages` = system (prompts/planner_system.md with the skill catalog,
  **no few-shot block**) + user (runtime `Planner.user_message`, DSL history) + assistant (the kept batch). Also
  `completion`, `target_model`, `other_reply`, raw `state` fields (goal, observation, last_batch, script_output,
  accept_first, reject_any, confirm_before).
- `bank.jsonl.gz` ({bank} rows): retrieval demo bank (goal, app, category, observation header, passing batch; < 400
  Qwen3.5 tokens each) for dynamic 1-2-shot examples.
- `states.jsonl.gz` ({states} rows): every state sent to the teachers (v2-tune + synthetic), with its grader fields.
- `replies.jsonl.gz`: raw teacher replies + usage. `meta.json`: counts, pass rates, rejection reasons, spend.

Keep rule: both teachers (gpt-5.6-sol reasoning=medium, claude-opus-5-5) pass the state's grader (evals/planner_offline.grade,
runtime and strict) and neither reply overwrites existing field text; target = the shorter passing reply.
Sources: evals/planner_scenarios_v2.jsonl v2-tune only plus synthetic states from training/planner_demos/states_*.py;
goals gated (exact / 13-gram / short edit<=1) against v2-holdout, v1 tune/holdout/holdout2, live_t1 and evals/external
(HobbyLM sealed r1-r4 etc., DeskMind). Code: ardahk/muselet@{commit} training/planner_demos/.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path.home() / "data" / "planner_demos")
    a = ap.parse_args()
    built, hf = a.dir / "built", a.dir / "hf"
    hf.mkdir(exist_ok=True)
    for n in ("demos.jsonl.gz", "bank.jsonl.gz"):
        shutil.copy(built / n, hf / n)
    for n in ("states.jsonl", "replies.jsonl"):
        with open(a.dir / n, "rb") as src, gzip.open(hf / f"{n}.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
    stats = json.loads((built / "keep_stats.json").read_text())
    sr = json.loads((a.dir / "states_report.json").read_text())
    commit = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"name": "muselet-planner-demos-v1", "teachers": teachers.MODELS, "openai_reasoning_effort": "medium",
            "system_prompt_sha256": hashlib.sha256(render.SYSTEM.encode()).hexdigest(), "few_shot": False, "history": "dsl",
            "states": sr["kept_total"], "states_report": sr, "keep": stats, "spend": teachers.spend(a.dir), "code_commit": commit}
    (hf / "meta.json").write_text(json.dumps(meta, indent=1))
    (hf / "README.md").write_text(README.format(kept=stats["kept"], bank=stats["bank"], states=sr["kept_total"], commit=commit))
    print(json.dumps({"kept": stats["kept"], "bank": stats["bank"], "states": sr["kept_total"],
                      "usd": meta["spend"]["total_usd"]}, indent=1))


if __name__ == "__main__":
    main()
