from __future__ import annotations

import json
import random
import re
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

from .templates import TEMPLATES

ROOT = Path(__file__).resolve().parents[3]
PHRASEBANK_PATH = Path(__file__).resolve().parent / "phrasebank.json"
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PHRASEBANK: dict[str, dict[str, list[str]]] | None = None


def load_phrasebank(path: Path = PHRASEBANK_PATH) -> dict[str, dict[str, list[str]]]:
    global _PHRASEBANK
    if _PHRASEBANK is None:
        _PHRASEBANK = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return _PHRASEBANK


def phrase(family: str, template: str, rng: random.Random, **values) -> str:
    bank = load_phrasebank().get(family, {})
    variants = [template, *bank.get(template, [])]
    selected = rng.choice(variants)
    for key, value in values.items():
        selected = selected.replace("{" + key + "}", str(value))
    return selected


def sample_kinds(rng: random.Random, count: int) -> list[str]:
    if not 2 <= count <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    kinds = [rng.choice(("choice", "noul", "score")) for _ in range(count)]
    return kinds


def decimal_text(value: Decimal, places: int = 2, prefix: str = "") -> str:
    quantum = Decimal(1).scaleb(-places)
    rendered = f"{value.quantize(quantum):,.{places}f}"
    return f"{rendered}%" if prefix == "%" else f"{prefix}{rendered}"


def amount_score(rng: random.Random, value: Decimal, *, places: int = 2, prefix: str = "$",
                 metric: str = "The result") -> tuple[str, list[str]]:
    count = rng.randint(3, 6)
    if value < 0:
        raise ValueError("score-band values cannot be negative")
    granularity = (
        Decimal("1") if places == 0 or prefix == "%"
        else Decimal("5") if value < 100
        else Decimal("10") if value < 500
        else Decimal("25") if value < 2000
        else Decimal("50") if value < 10000
        else Decimal("100")
    )
    precision = max(0, -granularity.as_tuple().exponent)
    cutfmt = lambda item: decimal_text(item, precision, prefix)
    boundary_case = value > 0 and rng.random() < 0.15
    if value == 0:
        target = 0
        cuts = [granularity * index for index in range(1, count)]
    elif boundary_case:
        edge = rng.randrange(1, count)
        target = edge
        below = [value - granularity * distance
                 for distance in rng.sample(range(2, 12), edge - 1)]
        above = [value + granularity * distance
                 for distance in rng.sample(range(2, 12), count - edge - 1)]
        cuts = sorted([*below, value, *above])
    else:
        target = rng.randrange(count)
        percentage_distance = abs(value) * Decimal("0.03")
        units = (percentage_distance / granularity).to_integral_value(rounding=ROUND_CEILING)
        minimum_distance = max(granularity * 2, granularity * units)
        below = [value - minimum_distance * distance
                 for distance in rng.sample(range(1, 12), target)]
        above = [value + minimum_distance * distance
                 for distance in rng.sample(range(1, 12), count - target - 1)]
        cuts = sorted(below + above)
    levels = []
    for index in range(count):
        if index == 0:
            levels.append(f"{metric} is >= {cutfmt(cuts[0] - granularity)} and < {cutfmt(cuts[0])}.")
        elif index == count - 1:
            levels.append(f"{metric} is >= {cutfmt(cuts[-1])}.")
        else:
            levels.append(f"{metric} is >= {cutfmt(cuts[index - 1])} and < {cutfmt(cuts[index])}.")
    return str(target), levels


def integer_score(rng: random.Random, value: int, *, metric: str = "The result") -> tuple[str, list[str]]:
    return amount_score(rng, Decimal(value), places=0, prefix="", metric=metric)


def round_bands(
    value: Decimal,
    unit: str,
    step_choices: list[Decimal],
    rng: random.Random,
    levels: tuple[int, int] = (3, 6),
    boundary_rate: float = 0.15,
) -> tuple[list[str], int]:
    if not step_choices or any(step <= 0 for step in step_choices):
        raise ValueError("step_choices must contain positive steps")
    if levels[0] < 2 or levels[1] < levels[0]:
        raise ValueError("levels must be an increasing range of at least two levels")
    if not 0 <= boundary_rate <= 1:
        raise ValueError("boundary_rate must be between zero and one")

    step = rng.choice(step_choices)
    count = rng.randint(*levels)
    boundary = rng.random() < boundary_rate and count > 1
    if boundary:
        gold_index = rng.randrange(1, count)
        below_count = gold_index - 1
        above_count = count - gold_index - 1
        lower_margin = max(step, (abs(value) * Decimal("0.03") / step).to_integral_value(
            rounding=ROUND_CEILING) * step)
        lower_edge = ((value - lower_margin) / step).to_integral_value(
            rounding=ROUND_FLOOR) * step
        upper_edge = ((value + lower_margin) / step).to_integral_value(
            rounding=ROUND_CEILING) * step
        below = []
        edge = lower_edge
        for _ in range(below_count):
            below.append(edge)
            edge -= step * rng.randint(1, 3)
        above = []
        edge = upper_edge
        for _ in range(above_count):
            above.append(edge)
            edge += step * rng.randint(1, 3)
        cuts = sorted([*below, value, *above])
    else:
        if count == 1:
            gold_index = 0
        else:
            gold_weights = [1 / count]
            remainder = 1 / count - boundary_rate / (count - 1)
            gold_weights.extend([remainder] * (count - 1))
            gold_index = rng.choices(range(count), weights=gold_weights, k=1)[0]
        margin = max(step, (abs(value) * Decimal("0.03") / step).to_integral_value(
            rounding=ROUND_CEILING) * step)
        below_edge = ((value - margin) / step).to_integral_value(rounding=ROUND_FLOOR) * step
        above_edge = ((value + margin) / step).to_integral_value(rounding=ROUND_CEILING) * step
        below = []
        edge = below_edge
        for _ in range(gold_index):
            below.append(edge)
            edge -= step * rng.randint(1, 3)
        above = []
        edge = above_edge
        for _ in range(count - gold_index - 1):
            above.append(edge)
            edge += step * rng.randint(1, 3)
        cuts = sorted([*below, *above])

    precision = min(
        2, max(0, -step.as_tuple().exponent, -value.as_tuple().exponent)
    )

    def render(number: Decimal) -> str:
        text = f"{number:,.{precision}f}"
        if unit == "$":
            return f"${text}"
        if unit == "%":
            return f"{text}%"
        return f"{text} {unit}".strip()

    criteria = []
    for index in range(count):
        if index == 0:
            criteria.append(f"The result is less than {render(cuts[0])}.")
        elif index == count - 1:
            criteria.append(f"The result is at least {render(cuts[-1])}.")
        else:
            criteria.append(
                f"The result is at least {render(cuts[index - 1])} but less than {render(cuts[index])}."
            )
    return criteria, gold_index


def choice_options(
    rng: random.Random,
    qid: str,
    answer: str,
    descriptions: dict[str, str],
    *,
    minimum: int = 2,
    maximum: int = 12,
) -> dict[str, str]:
    if answer not in descriptions:
        raise ValueError(f"missing gold key {answer}")
    desired = min(
        len(descriptions),
        26 if len(descriptions) >= 13 and rng.random() < 0.05 else rng.randint(minimum, maximum),
    )
    distractors = [(key, text) for key, text in descriptions.items() if key != answer]
    selected = rng.sample(distractors, desired - 1)
    gold_row = (answer, descriptions[answer])
    position = rng.randrange(desired)
    rows = [*selected[:position], gold_row, *selected[position:]]
    return {key: text for key, text in rows}


def _score_surface(rng: random.Random, gold: str, levels: list[str]) -> str:
    return str(rng.choice([str(index) for index in range(len(levels)) if str(index) != gold]))


def finish_record(
    rng: random.Random,
    family: str,
    schema: str,
    base_state: str,
    specs: list[tuple[str, str, str, object]],
    *,
    facts: dict,
    traps: list[str],
    narrative: str | None = None,
    note: tuple[str, bool] | None = None,
    intermediate_values: list[str] | None = None,
    approx_tokens: int | None = None,
) -> dict:
    questions, gold, surface = {}, {}, {}
    for index, (kind, instructions, answer, criteria) in enumerate(specs, start=1):
        qid = f"q{index}"
        if kind == "choice":
            picked = choice_options(rng, qid, answer, dict(criteria))
            question = {"type": "choice", "instructions": instructions, "criteria": picked}
            wrong = [key for key in picked if key != answer]
            surfaced = rng.choice(wrong)
        elif kind == "noul":
            question = {"type": "noul", "instructions": instructions, "criteria": dict(criteria)}
            surfaced = "false" if answer == "true" else "true"
        elif kind == "score":
            levels = list(criteria)
            question = {"type": "score", "instructions": instructions, "criteria": levels}
            surfaced = _score_surface(rng, answer, levels)
        else:
            raise ValueError(f"unsupported question type: {kind}")
        questions[qid] = question
        gold[qid] = answer
        surface[qid] = surfaced

    state = base_state.rstrip()
    note_text, note_correct = (note if note is not None else ("", None))
    note_position = None
    if note_text:
        sections = state.split("\n\n")
        note_position = rng.randrange(len(sections) + 1)
        sections.insert(note_position, note_text)
        state = "\n\n".join(sections)
    calculated_tokens = len(state) // 4
    return {
        "id": f"{family}-{rng.getrandbits(48):012x}",
        "family": family,
        "source": "code",
        "license": "synthetic",
        "generator": f"gen_codegold/{family}@v1",
        "state": state,
        "questions": questions,
        "gold": gold,
        "gold_basis": {qid: "code" for qid in questions},
        "teacher": {},
        "teacher_samples": {},
        "target": {},
        "_leak_audit": {"intermediate_values": list(intermediate_values or [])},
        "_meta": {
            "surface": surface,
            "traps": sorted(set(traps)),
            "schema": schema,
            "approx_tokens": approx_tokens if approx_tokens is not None else calculated_tokens,
            "facts": facts,
            "narrative_section": note_text,
            "staff_note": {"included": bool(note_text), "correct": note_correct,
                           "position": note_position},
        },
    }


def key_for_value(stem: str, value, *, places: int = 0) -> str:
    value_text = str(value)
    if isinstance(value, Decimal):
        value_text = f"{value:.{places}f}"
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value_text).strip("_").lower()
    return f"{stem}_{cleaned}"


def render_facts(facts: dict) -> str:
    omitted = {"schema", "review_note", "surface_note", "staff_note", "eligible_use"}
    lines = []

    def label(key):
        return re.sub(r"\s+", " ", key.replace("_", " ").replace("-", " ")).strip().capitalize()

    def emit(value, depth=0, name=None):
        indent = "  " * depth
        if name is not None:
            lines.append(f"{indent}{label(name)}:")
            indent += "  "
        if isinstance(value, dict):
            for key, child in value.items():
                if key in omitted or key.startswith("_"):
                    continue
                emit(child, depth + (name is not None), key)
        elif isinstance(value, list):
            for index, child in enumerate(value, 1):
                emit(child, depth + 1, f"record {index}")
        elif isinstance(value, bool):
            lines.append(f"{indent}{'Yes' if value else 'No'}")
        else:
            lines.append(f"{indent}{value}")

    emit(facts)
    return "\n".join(lines)


def score_level_for(value: Decimal | int | float, criteria: list[str]) -> str | None:
    import re

    parsed_value = Decimal(str(value))
    number = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
    for index, description in enumerate(criteria):
        values = [Decimal(token.replace(",", "")) for token in number.findall(description)]
        if ("and <" in description or "less than" in description.lower()) and len(values) >= 2:
            if values[0] <= parsed_value < values[1]:
                return str(index)
        elif "less than" in description.lower() and len(values) == 1:
            if parsed_value < values[0]:
                return str(index)
        elif values and parsed_value >= values[0]:
            return str(index)
    return None


def distinct_choices(stem: str, values, answer, description, *, minimum: int = 26) -> tuple[str, dict[str, str]]:
    values = list(dict.fromkeys(values))
    if answer not in values:
        values.insert(0, answer)
    offset = 1
    while len(values) < minimum:
        candidate = answer - offset if isinstance(answer, int) else None
        if candidate is None or candidate in values:
            candidate = answer + offset
        if candidate not in values:
            values.append(candidate)
        offset += 1
    return key_for_value(stem, answer), {
        key_for_value(stem, value): description(value) for value in values[:minimum]
    }


def append_phrase_section(text: str, section: str, content: str) -> str:
    return f"{text.rstrip()}\n\n{section.upper()}\n{content}"
