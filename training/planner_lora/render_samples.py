"""Render deterministic planner LoRA samples for token-level parity tests."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import common

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "planner_lora_render_samples.jsonl"
TOKENIZER = "mlx-community/Qwen3.5-4B-4bit"


def _multiline_script(demo: dict) -> bool:
    completion = demo.get("completion", "")
    return bool(re.search(r'(?ms)^script\b[^\n]*""".*?\n.*?"""', completion))


def select_samples(demos: list[dict], count: int = 20) -> list[dict]:
    ordered = sorted(demos, key=lambda demo: demo["id"])
    if len(ordered) < count:
        raise ValueError(f"need {count} demos, found {len(ordered)}")

    selected: list[dict] = []

    def force(predicate, number: int = 1):
        for demo in ordered:
            if predicate(demo) and demo not in selected:
                selected.append(demo)
                number -= 1
                if number == 0:
                    break

    force(lambda demo: demo["state"].get("last_batch") is not None, 2)
    force(lambda demo: demo["state"].get("script_output") is not None)
    force(lambda demo: common.login_page(demo["state"]))
    force(_multiline_script)

    remaining = [demo for demo in ordered if demo not in selected]
    selected.extend(random.Random(0).sample(remaining, count - len(selected)))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demos",
        help="local demos.jsonl.gz; defaults to the pinned Hugging Face dataset",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    demos = common.load_demos(args.demos)
    planner = common.make_planner()
    rows = [
        {
            "id": demo["id"],
            "state": {
                key: demo["state"].get(key)
                for key in ("goal", "observation", "last_batch", "script_output")
            },
            "completion": demo["completion"],
            **common.render(planner, demo["state"], demo["completion"]),
        }
        for demo in select_samples(demos)
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "meta": {
            "demos": f"{common.DEMOS_REPO}@{common.DEMOS_REV}",
            "tokenizer": TOKENIZER,
            "few_shot": None,
            "retrieval_k": 0,
        }
    }
    with args.output.open("w") as output:
        output.write(json.dumps(header, ensure_ascii=False) + "\n")
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
