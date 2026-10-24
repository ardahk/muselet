"""Stdlib implementation of DeskMind Brain's System One wire types."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

MAX_CHOICE_OPTIONS = 255
MIN_SCORE_LEVELS = 2
MAX_SCORE_LEVELS = 10
NOUL_OPTIONS = ("false", "true")
_STATE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProtocolError(ValueError):
    def __init__(self, message: str, *, field: str | None = None, code: str = "invalid_request"):
        super().__init__(message)
        self.code = code
        self.field = field


@dataclass(frozen=True)
class Question:
    qid: str
    type: str
    instructions: Any
    criteria: Any
    options: list[str]
    descriptions: dict[str, Any]


@dataclass(frozen=True)
class Request:
    state: Any
    model: str
    questions: dict[str, Question]
    identity: dict[str, Any]


def _fail(message: str, field: str) -> None:
    raise ProtocolError(message, field=field)


def _question(qid: str, raw: Any) -> Question:
    prefix = f"questions.{qid}"
    if not isinstance(raw, dict):
        _fail("question must be an object", prefix)
    kind = raw.get("type")
    if kind not in ("choice", "score", "noul"):
        _fail("type must be one of choice, score, noul", f"{prefix}.type")
    if "instructions" not in raw:
        _fail("field required", f"{prefix}.instructions")

    criteria = raw.get("criteria")
    descriptions: dict[str, Any] = {}
    if kind == "choice":
        if isinstance(criteria, list):
            ordered: dict[str, Any] = {}
            for index, entry in enumerate(criteria):
                field = f"{prefix}.criteria.{index}"
                if not isinstance(entry, dict) or set(entry) != {"key", "description"}:
                    _fail('choice criteria entries must be {"key", "description"}', field)
                key = entry["key"]
                if not isinstance(key, str) or not key:
                    _fail("choice criteria key must be a non-empty string", f"{field}.key")
                if key in ordered:
                    _fail(f"duplicate choice criteria key: {key!r}", f"{field}.key")
                ordered[key] = entry["description"]
            criteria = ordered
        if not isinstance(criteria, dict) or not 1 <= len(criteria) <= MAX_CHOICE_OPTIONS:
            _fail(
                f"choice criteria must be a map or a list with 1..{MAX_CHOICE_OPTIONS} options",
                f"{prefix}.criteria",
            )
        options = list(criteria)
        descriptions = dict(criteria)
    elif kind == "score":
        if not isinstance(criteria, list) or not MIN_SCORE_LEVELS <= len(criteria) <= MAX_SCORE_LEVELS:
            _fail(
                f"score criteria must be a list of {MIN_SCORE_LEVELS}..{MAX_SCORE_LEVELS} levels",
                f"{prefix}.criteria",
            )
        options = [str(i) for i in range(len(criteria))]
        descriptions = dict(zip(options, criteria))
    else:
        options = list(NOUL_OPTIONS)
        if isinstance(criteria, dict):
            descriptions = {key: criteria[key] for key in options if key in criteria}

    return Question(qid, kind, raw["instructions"], criteria, options, descriptions)


def parse_request(payload: Any) -> Request:
    """Validate and normalize a request without losing criterion order."""
    if not isinstance(payload, dict):
        _fail("request must be a JSON object", "$")
    if "state" not in payload:
        _fail("field required", "state")
    model = payload.get("model", "deskmind-brain-local")
    if not isinstance(model, str):
        _fail("model must be a string", "model")
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, dict):
        _fail("questions must be an object", "questions")
    questions = {qid: _question(qid, raw) for qid, raw in raw_questions.items()}

    identity: dict[str, Any] = {}
    for key in ("request_id", "session_id", "observation_id"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                _fail(f"{key} must be a non-empty string or null", key)
            identity[key] = value
    step = payload.get("step")
    if step is not None:
        if isinstance(step, bool) or not isinstance(step, int) or step < 1:
            _fail("step must be an integer >= 1", "step")
        identity["step"] = step
    digest = payload.get("state_digest")
    if digest is not None:
        if not isinstance(digest, str) or not _STATE_DIGEST.fullmatch(digest):
            _fail("state_digest must match sha256:<64 lowercase hex characters>", "state_digest")
        identity["state_digest"] = digest
    return Request(payload["state"], model, questions, identity)


def normalize(dist: dict[str, float], options: list[str]) -> dict[str, float]:
    values = [max(float(dist.get(option, 0.0)), 0.0) for option in options]
    total = sum(values)
    if total <= 0:
        return {option: 1.0 / len(options) for option in options}
    return {option: value / total for option, value in zip(options, values)}


def choice_confidence(dist: dict[str, float]) -> float:
    count = len(dist)
    if count <= 1:
        return 1.0
    return (count * max(dist.values()) - 1.0) / (count - 1)


def score_value(dist: dict[str, float]) -> float:
    return sum(int(level) * probability for level, probability in dist.items())


def score_confidence(dist: dict[str, float]) -> float:
    count = len(dist)
    if count <= 1:
        return 1.0
    mean = score_value(dist)
    mad = sum(probability * abs(int(level) - mean) for level, probability in dist.items())
    return max(0.0, 1.0 - 2.0 * mad / (count - 1))


def build_answer(question: Question | dict[str, Any], dist: dict[str, float]) -> dict[str, Any]:
    """Convert an option distribution to the upstream answer shape."""
    if isinstance(question, Question):
        kind, options, descriptions = question.type, question.options, question.descriptions
    else:
        kind = question["type"]
        options = list(question["options"])
        descriptions = question.get("descriptions", {})
    probs = normalize(dist, options)
    if kind == "noul":
        p_true = probs["true"]
        return {"type": "noul", "noul": p_true, "probabilities": {"false": probs["false"], "true": p_true}}
    if kind == "choice":
        return {
            "type": "choice",
            "choice": max(probs, key=probs.__getitem__),
            "probabilities": probs,
            "confidence": choice_confidence(probs),
        }
    return {
        "type": "score",
        "score": score_value(probs),
        "legend": {level: descriptions.get(level) for level in options},
        "probabilities": probs,
        "confidence": score_confidence(probs),
    }


def from_answer(question: Question, answer: dict[str, Any]) -> dict[str, float]:
    """Parse an answer like DeskMind/JevBench/Typed Decisions do."""
    options = question.options
    if question.type == "noul":
        p = float(answer["noul"])
        if math.isnan(p):
            raise ValueError("noul is NaN")
        p = min(max(p, 0.0), 1.0)
        return {"false": 1.0 - p, "true": p}
    probabilities = answer.get("probabilities")
    if probabilities:
        return normalize({str(key): value for key, value in probabilities.items()}, options)
    value = str(answer.get("choice") if question.type == "choice" else round(float(answer["score"])))
    return normalize({value: 1.0}, options)
