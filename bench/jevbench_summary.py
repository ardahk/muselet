"""Summarize JevBench result JSONL using its pinned metric implementations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def summarize(jevbench: Path, pairs: list[tuple[str, Path, Path]]) -> dict:
    sys.path.insert(0, str(jevbench))
    from jevbench.metrics import brier_score, ece_top_label, latency_summary
    from jevbench.tasks import load_jsonl

    summary = {}
    all_rows = []
    for name, task_file, result_file in pairs:
        tasks = {task.id: task for task in load_jsonl(str(task_file))}
        rows = [json.loads(line) for line in result_file.read_text().splitlines() if line.strip()]
        all_rows.extend((name, row, tasks[row["task_id"]]) for row in rows)
        summary[name] = _score(rows, tasks, brier_score, ece_top_label, latency_summary)
    summary["total"] = _score(
        [row for _, row, _ in all_rows],
        {task.id: task for _, _, task in all_rows},
        brier_score, ece_top_label, latency_summary,
    )
    return summary


def _score(rows, tasks, brier_score, ece_top_label, latency_summary):
    scorable = [row for row in rows if tasks[row["task_id"]].expected is not None]
    correct = [bool(row.get("valid") and row.get("correct")) for row in scorable]
    briers, calibration = [], []
    for row in scorable:
        if not row.get("valid") or not isinstance(row.get("probs"), dict):
            continue
        task = tasks[row["task_id"]]
        expected = str(task.expected)
        labels = task.labels if task.question["type"] != "noul" else ["no", "yes"]
        try:
            briers.append(brier_score(row["probs"], expected, labels))
            confidence = max(float(row["probs"].get(label, 0.0)) for label in labels)
            calibration.append((confidence, bool(row.get("correct"))))
        except (KeyError, TypeError, ValueError):
            continue
    return {
        "n": len(rows),
        "scorable": len(scorable),
        "accuracy": sum(correct) / len(correct) if correct else None,
        "brier": sum(briers) / len(briers) if briers else None,
        "ece": ece_top_label(calibration)["ece"] if calibration else None,
        "valid_distributions": len(calibration),
        "latency": latency_summary([row.get("latency_s") for row in rows]),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jevbench-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.jevbench_dir / "datasets" / "public"
    pairs = [
        (split, root / f"{split}.jsonl", args.run_dir / split / "results.jsonl")
        for split in ("original", "easy", "hard")
    ]
    result = summarize(args.jevbench_dir, pairs)
    (args.run_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
