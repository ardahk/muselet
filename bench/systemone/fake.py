"""Deterministic, dependency-free backend for plumbing tests."""

from __future__ import annotations

import json
import math
import re
from typing import Any

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class FakeDecider:
    def decide(self, state: str, question: dict) -> dict[str, float]:
        context = set(_TOKEN.findall((state + " " + _text(question["instructions"])).casefold()))
        scores: list[tuple[str, float]] = []
        for option in question["options"]:
            description = question.get("descriptions", {}).get(option, "")
            words = set(_TOKEN.findall((option + " " + _text(description)).casefold()))
            overlap = len(context & words)
            scores.append((option, overlap / math.sqrt(max(len(context), 1) * max(len(words), 1))))
        maximum = max((score for _, score in scores), default=0.0)
        weights = [(option, math.exp((score - maximum) / 0.25)) for option, score in scores]
        total = sum(weight for _, weight in weights)
        return {option: weight / total for option, weight in weights}
