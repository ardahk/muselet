from __future__ import annotations

import random

DOMAINS = (
    "insurance", "healthcare administration", "logistics", "IT operations", "retail",
    "education", "travel", "finance", "human resources", "property management",
    "customer support", "public services", "procurement", "software operations",
)
NAMES = (
    "Avery Chen", "Mina Patel", "Jordan Reyes", "Theo Brooks", "Nadia Ali", "Eli Morgan",
    "Priya Shah", "Luis Romero", "Grace Kim", "Omar Haddad", "Sofia Laurent",
    "Noah Williams", "Iris Nakamura", "Caleb Foster", "Amara Okafor", "Ravi Desai",
)


def choose_domain(rng: random.Random, domain: str) -> str:
    return domain if domain != "mixed" else rng.choice(DOMAINS)


def article(noun: str) -> str:
    return "an" if noun[:1].lower() in "aeiou" else "a"


def count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def near_miss_values(answer, mistake_values, *, minimum: int = 5, lower=None, upper=None, step=1):
    values = []

    def add(value):
        if lower is not None and value < lower:
            return
        if upper is not None and value > upper:
            return
        if value not in values:
            values.append(value)

    add(answer)
    for value in mistake_values:
        add(value)
    radius = 1
    while len(values) < minimum:
        add(answer - radius * step)
        add(answer + radius * step)
        radius += 1
    return values


def choice_question(rng: random.Random, instructions: str, answer: str, options: dict[str, str]) -> dict:
    options = dict(options)
    if answer not in options:
        raise ValueError("choice answer missing from options")
    if len(options) < 2:
        raise ValueError("choice questions require at least two plausible options")
    requested = 26 if rng.random() < 0.05 else rng.randint(2, 12)
    requested = min(requested, len(options))
    answer_row = (answer, options.pop(answer))
    distractors = rng.sample(list(options.items()), requested - 1)
    position = rng.randrange(requested)
    items = [*distractors[:position], answer_row, *distractors[position:]]
    return {"type": "choice", "instructions": instructions, "criteria": dict(items)}, answer


def make_question(rng: random.Random, qid: str, kind: str, instructions: str, answer: str,
                  choices: dict[str, str] | None = None, levels: list[str] | None = None):
    if kind == "choice":
        if choices is None:
            raise ValueError("choice questions require question-specific option descriptions")
        question, gold = choice_question(rng, instructions, answer, choices)
    elif kind == "noul":
        if choices is None or set(choices) != {"false", "true"}:
            raise ValueError("noul questions require question-specific false/true descriptions")
        if answer not in choices:
            raise ValueError("noul answer must be false or true")
        gold = answer
        criteria = list(choices.items())
        rng.shuffle(criteria)
        question = {"type": "noul", "instructions": instructions, "criteria": dict(criteria)}
    elif kind == "score":
        if not levels or answer not in {str(i) for i in range(len(levels))}:
            raise ValueError("invalid score levels or answer")
        question, gold = {"type": "score", "instructions": instructions, "criteria": levels}, answer
    else:
        raise ValueError(f"unknown decision type {kind}")
    return qid, question, gold


def record(rng: random.Random, family: str, domain: str, state: str, questions: list[tuple],
           intermediate_values: tuple[str, ...] = ()) -> dict:
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
        "_leak_audit": {"intermediate_values": list(intermediate_values)},
    }


def question_specs(types: list[str], n_questions: int):
    if not types or n_questions < 1:
        raise ValueError("types and n_questions must be non-empty")
    return [types[i % len(types)] for i in range(n_questions)]
