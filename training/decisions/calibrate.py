from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _softmax(logits: list[float], temperature: float) -> list[float]:
    scaled = [value / temperature for value in logits]
    peak = max(scaled)
    values = [math.exp(value - peak) for value in scaled]
    total = sum(values)
    return [value / total for value in values]


def _ece(probabilities: list[list[float]], gold: list[int], bins: int = 15) -> float:
    groups = [[] for _ in range(bins)]
    for row, label in zip(probabilities, gold, strict=True):
        confidence = max(row)
        groups[min(int(confidence * bins), bins - 1)].append(
            (confidence, int(max(range(len(row)), key=row.__getitem__) == label))
        )
    n = max(1, len(gold))
    return sum(
        len(group) / n * abs(
            sum(confidence for confidence, _ in group) / len(group)
            - sum(correct for _, correct in group) / len(group)
        )
        for group in groups if group
    )


def _gold_index(row: dict) -> int:
    if "gold_index" in row:
        return int(row["gold_index"])
    gold = row["gold"]
    if isinstance(gold, int):
        return gold
    return row["labels"].index(gold)


def fit_temperatures(rows: list[dict]) -> dict[str, float]:
    if not rows:
        raise ValueError("calibration requires development predictions")
    grid = [math.exp(-2 + step * 0.05) for step in range(161)]

    def soft_loss(temperature: float) -> float:
        total = 0.0
        for row in rows:
            probs = _softmax(row["logits"], temperature)
            total -= sum(target * math.log(max(prob, 1e-12))
                         for target, prob in zip(row["target"], probs, strict=True))
        return total / len(rows)

    def hard_loss(temperature: float) -> float:
        probs = [_softmax(row["logits"], temperature) for row in rows]
        gold = [_gold_index(row) for row in rows]
        nll = -sum(math.log(max(prob[row_index], 1e-12))
                   for prob, row_index in zip(probs, gold, strict=True)) / len(rows)
        ece = _ece(probs, gold)
        return nll + ece

    return {
        "temperature_probs": min(grid, key=soft_loss),
        "temperature_conf": min(grid, key=hard_loss),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fit decision temperatures from dev-only logits.")
    parser.add_argument("--dev-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    rows = [json.loads(line) for line in args.dev_predictions.read_text().splitlines() if line.strip()]
    result = fit_temperatures(rows)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
