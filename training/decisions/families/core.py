from __future__ import annotations

import random

DOMAINS = (
    "insurance", "healthcare administration", "logistics", "IT operations",
    "retail", "education", "travel", "finance", "human resources",
)
NAMES = ("Avery Chen", "Mina Patel", "Jordan Reyes", "Theo Brooks", "Nadia Ali", "Eli Morgan")


def choose_domain(rng: random.Random, domain: str) -> str:
    return domain if domain != "mixed" else rng.choice(DOMAINS)


def choice_question(rng: random.Random, instructions: str, answer: str, options: dict[str, str]) -> dict:
    options = dict(options)
    if answer not in options:
        raise ValueError("choice answer missing from options")
    requested = rng.randint(13, 26) if rng.random() < 0.05 else rng.randint(2, 12)
    while len(options) < requested:
        index = len(options) + 1
        key = f"alternate_{index:02d}"
        options[key] = f"Use the alternate procedure {index}, which does not satisfy the stated conditions."
    items = list(options.items())
    rng.shuffle(items)
    return {"type": "choice", "instructions": instructions, "criteria": dict(items)}, answer


def make_question(rng: random.Random, qid: str, kind: str, instructions: str, answer: str,
                  choices: dict[str, str] | None = None, levels: list[str] | None = None):
    if kind == "choice":
        options = choices or {
            answer: "This action follows the stated facts and rules.",
            "defer": "Defer the decision until more information is available.",
            "reject": "Reject the request under the stated rules.",
        }
        question, gold = choice_question(rng, instructions, answer, options)
    elif kind == "noul":
        gold = answer
        criteria = [("false", "The stated condition is not satisfied."),
                    ("true", "The stated condition is satisfied.")]
        rng.shuffle(criteria)
        question = {"type": "noul", "instructions": instructions, "criteria": dict(criteria)}
    elif kind == "score":
        if not levels or answer not in {str(i) for i in range(len(levels))}:
            raise ValueError("invalid score levels or answer")
        question, gold = {"type": "score", "instructions": instructions, "criteria": levels}, answer
    else:
        raise ValueError(f"unknown decision type {kind}")
    return qid, question, gold


def record(rng: random.Random, family: str, domain: str, state: str, questions: list[tuple]) -> dict:
    built = [make_question(rng, f"q{i + 1}", kind, text, answer, choices, levels)
             for i, (kind, text, answer, choices, levels) in enumerate(questions)]
    return {
        "id": f"{family}-{rng.getrandbits(48):012x}",
        "family": family,
        "source": "synthetic-code",
        "license": "synthetic",
        "state": state,
        "questions": {qid: question for qid, question, _ in built},
        "gold": {qid: answer for qid, _, answer in built},
        "gold_basis": {qid: "code" for qid, _, _ in built},
        "teacher": {},
        "target": {},
    }


def question_specs(types: list[str], n_questions: int):
    if not types or n_questions < 1:
        raise ValueError("types and n_questions must be non-empty")
    return [types[i % len(types)] for i in range(n_questions)]
