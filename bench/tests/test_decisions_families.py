import asyncio
import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import date

import pytest

from bench.systemone.schema import parse_request
from training.decisions.author import AUTHOR_SCHEMA, _parse_item, author_items
from training.decisions.families import GENERATORS, counting, multi_hop, numeric, probability, temporal
from training.decisions.families.core import choice_question, count_phrase
from training.decisions.paraphrase import validate_paraphrase


def test_temporal_hand_checked_gold_helpers():
    holidays = {date(2024, 1, 1)}
    assert temporal.business_days_after(date(2023, 12, 29), 1, holidays) == date(2024, 1, 2)
    assert temporal.prorate_monthly(290, 2024, 2, 29) == 290
    assert temporal.prorate_monthly(280, 2023, 2, 28) == 280
    assert temporal.late_days(date(2024, 4, 2), date(2024, 4, 2), inclusive_deadline=True) == 0
    assert temporal.late_days(date(2024, 4, 2), date(2024, 4, 2), inclusive_deadline=False) == 1


def test_numeric_counting_multihop_and_probability_hand_calculations():
    assert numeric.fee_after_discount(100, 10, 5) == 94.5
    assert counting.count_eligible([
        {"active": True, "region": "north", "days": 3},
        {"active": True, "region": "south", "days": 5},
        {"active": False, "region": "north", "days": 4},
    ]) == 1
    assert multi_hop.lookup_sla("T", {"T": {"customer": "C"}}, {"C": {"plan": "gold"}},
                                {"gold": {"sla_hours": 24}}) == 24
    assert multi_hop.resolve_response_hours(
        "T", {"T": {"account": "A"}}, {"A": {"contract": "C", "region": "North"}},
        {"C": {"plan": "Priority"}}, {"Priority": 30}, {"North": 5},
    ) == 35
    assert probability.posterior_positive(0.1, 0.9, 0.08) == pytest.approx(0.5555555556)
    assert probability.expected_value(0.5, 100, 20) == 30


@pytest.mark.parametrize("family,generate", sorted(GENERATORS.items()))
def test_generated_records_are_valid_systemone_requests(family, generate):
    item = generate(random.Random(1901), "mixed", 3, ["choice", "noul", "score"])
    request = parse_request({"state": item["state"], "questions": item["questions"]})
    assert len(request.questions) == 3
    assert set(item["gold"]) == set(item["questions"])
    assert {q.type for q in request.questions.values()} == {"choice", "noul", "score"}
    assert all(answer in request.questions[qid].options for qid, answer in item["gold"].items())
    if family == "long_policy":
        assert len(item["state"].split()) >= 1400


def test_choice_gold_position_is_uniform_within_each_option_count():
    rng = random.Random(814)
    options = {f"result_{i}": f"Result {i} is the outcome under the stated rule." for i in range(26)}
    observed = defaultdict(Counter)
    for _ in range(8000):
        question, gold = choice_question(rng, "Which result applies?", "result_0", options)
        criteria = question["criteria"]
        observed[len(criteria)][list(criteria).index(gold)] += 1

    for option_count, counts in observed.items():
        if option_count > 12 or sum(counts.values()) < 100:
            continue
        expected = sum(counts.values()) / option_count
        assert all(abs(counts[position] - expected) < expected * 0.35
                   for position in range(option_count))


@pytest.mark.parametrize("family,generate", sorted(GENERATORS.items()))
def test_generated_criteria_are_question_specific_and_articles_are_grammatical(family, generate):
    item = generate(random.Random(1902), "mixed", 3, ["choice", "noul", "score"])
    descriptions = []
    for question in item["questions"].values():
        criteria = question["criteria"]
        descriptions.extend(criteria if isinstance(criteria, list) else criteria.values())
    assert all("the stated condition is satisfied" not in text.lower() for text in descriptions)
    assert all("the stated condition is not satisfied" not in text.lower() for text in descriptions)
    assert "a insurance" not in item["state"].lower()
    assert "a education" not in item["state"].lower()
    assert "a it operations" not in item["state"].lower()


def test_count_phrase_fixes_singular_plural_across_counting_states():
    assert count_phrase(1, "open day") == "1 open day"
    assert count_phrase(2, "open day") == "2 open days"
    for seed in range(300):
        item = counting.generate(random.Random(seed), "mixed", 3, ["choice", "noul", "score"])
        assert "1 open days" not in item["state"]
        assert not re.search(r"\b[2-9] open day\b", item["state"])


def _gold_surface(value: str) -> str | None:
    if value.startswith("date_"):
        return "-".join(value.split("_")[1:])
    if value.startswith("utc_"):
        values = value.split("_")[1:]
        return f"{values[0]}-{values[1]}-{values[2]} {values[3]}:{values[4]} UTC"
    if value.startswith("usd_"):
        whole, cents = value.removeprefix("usd_").rsplit("_", 1)
        return f"${whole}.{cents}"
    if value.startswith("count_"):
        return f"{value.removeprefix('count_')} eligible referrals"
    if value.startswith("hours_"):
        return f"{value.removeprefix('hours_')} hours"
    if value.startswith("posterior_"):
        number = float(value.removeprefix("posterior_").replace("_", "."))
        return f"{number:.2%}"
    return None


@pytest.mark.parametrize("family,generate", sorted(GENERATORS.items()))
def test_computed_gold_surfaces_and_intermediate_facts_are_not_leaked(family, generate):
    item = generate(random.Random(2401), "mixed", 3, ["choice", "noul", "score"])
    for qid, answer in item["gold"].items():
        surface = _gold_surface(answer)
        if surface:
            assert surface.lower() not in item["state"].lower(), (family, qid, surface)
    forbidden = [value.lower() for value in item["_leak_audit"]["intermediate_values"]]
    for question in item["questions"].values():
        descriptions = question["criteria"]
        descriptions = descriptions.values() if isinstance(descriptions, dict) else descriptions
        for description in descriptions:
            lowered = description.lower()
            assert all(value not in lowered for value in forbidden), (family, description, forbidden)


def test_counting_distractors_stay_within_the_observed_row_range():
    item = counting.generate(random.Random(2402), "mixed", 3, ["choice", "noul", "score"])
    rows = [line for line in item["state"].splitlines() if "R-" in line]
    question = next(q for q in item["questions"].values() if q["type"] == "choice")
    values = [int(key.removeprefix("count_")) for key in question["criteria"]]
    assert rows
    assert all(0 <= value <= len(rows) for value in values)


def test_multi_hop_uses_multiple_similar_entities_and_separate_registers():
    item = multi_hop.generate(random.Random(2403), "mixed", 3, ["choice", "noul", "score"])
    assert sum(line.startswith("| INC-41") for line in item["state"].splitlines()) == 5
    assert sum(line.startswith("| AGR-31") for line in item["state"].splitlines()) == 5
    assert "customer operations email" in item["state"].lower()
    assert "linked platinum entitlement" not in item["state"].lower()
    choice = next(q for q in item["questions"].values() if q["type"] == "choice")
    assert all("plan" not in description.lower() for description in choice["criteria"].values())


def test_question_count_draw_is_uniform_and_separate_from_answer_generation():
    count_rng, answer_rng = random.Random(2404), random.Random(2405)
    counts, numeric_answers = [], []
    for _ in range(600):
        count = count_rng.randint(1, 6)
        item = numeric.generate(answer_rng, "mixed", count, ["choice", "noul", "score"])
        counts.append(len(item["questions"]))
        numeric_answers.append(float(next(iter(item["gold"].values())).removeprefix("usd_").replace("_", ".")))
    assert min(counts) == 1 and max(counts) == 6
    assert abs(sum(counts) / len(counts) - 3.5) < 0.15
    mean_count = sum(counts) / len(counts)
    mean_answer = sum(numeric_answers) / len(numeric_answers)
    covariance = sum((count - mean_count) * (answer - mean_answer)
                     for count, answer in zip(counts, numeric_answers)) / len(counts)
    var_count = sum((count - mean_count) ** 2 for count in counts) / len(counts)
    var_answer = sum((answer - mean_answer) ** 2 for answer in numeric_answers) / len(counts)
    correlation = covariance / math.sqrt(var_count * var_answer)
    assert abs(correlation) < 0.15


def test_paraphrase_preserves_numbers_dates_names_identifiers_and_conditions():
    original = (
        "Mina Patel filed CLM-2048 on 2026-03-10 at 09:14. The $5,000 ceiling is inclusive; "
        "at least 3 records must be active."
    )
    paraphrased = (
        "On 2026-03-10 at 09:14, Mina Patel filed CLM-2048. The $5,000 ceiling remains inclusive, "
        "and at least 3 records must be active."
    )
    assert validate_paraphrase(original, paraphrased)


def test_paraphrase_rejects_changed_date_number_name_identifier_or_condition():
    original = (
        "Mina Patel filed CLM-2048 on 2026-03-10. The $5,000 ceiling is inclusive; "
        "at least 3 records must be active."
    )
    changed_date = (
        "Mina Patel filed CLM-2048 on 2026-03-11. The $5,000 ceiling is inclusive; "
        "at least 3 records must be active."
    )
    changed_condition = (
        "Mina Patel filed CLM-2048 on 2026-03-10. The $5,000 ceiling is exclusive; "
        "at least 3 records must be active."
    )
    assert not validate_paraphrase(original, changed_date)
    assert not validate_paraphrase(original, changed_condition)
    assert not validate_paraphrase(
        "Request from Avery Chen: invoice INV-4207 is due on 2026-04-15 for $125.00.",
        "Avery Chen sent invoice INV-4207 for $150.00, due 2026-04-15.",
    )


def test_author_schema_normalizes_choice_lists_booleans_and_score_levels():
    payload = {
        "state": "A request is being reviewed.",
        "questions": [
            {"type": "choice", "instructions": "Which route applies?",
             "criteria": [{"key": "standard", "description": "Use the standard route."},
                          {"key": "urgent", "description": "Use the urgent route."},
                          {"key": "review", "description": "Request a review."},
                          {"key": "hold", "description": "Place the request on hold."}],
             "answer": "standard", "rationale": "The route rule selects standard."},
            {"type": "noul", "instructions": "Is review required?",
             "criteria": {"false": "Review is not required.", "true": "Review is required."},
             "answer": True, "rationale": "The request meets the review trigger."},
            {"type": "score", "instructions": "Which urgency level applies?",
             "criteria": ["Low urgency.", "Moderate urgency.", "High urgency."],
             "answer": 1, "rationale": "The stated deadline is in the middle band."},
        ],
    }
    item = _parse_item(json.dumps(payload), random.Random(2410), "routing")
    assert item["authored_answer"] == {"q1": "standard", "q2": "true", "q3": "1"}
    assert isinstance(item["questions"]["q1"]["criteria"], dict)
    assert AUTHOR_SCHEMA["properties"]["questions"]["minItems"] == 3
    assert AUTHOR_SCHEMA["properties"]["questions"]["maxItems"] == 6
    score_schema = AUTHOR_SCHEMA["properties"]["questions"]["items"]["anyOf"][2]
    assert score_schema["properties"]["criteria"]["minItems"] == 3
    assert score_schema["properties"]["criteria"]["maxItems"] == 6


def test_author_model_mix_is_80_20_and_uses_strict_schema():
    choice = {"type": "choice", "instructions": "Which route applies?",
              "criteria": [{"key": key, "description": f"Choose {key}."}
                           for key in ("a", "b", "c", "d")],
              "answer": "a", "rationale": "The rule selects a."}
    response = json.dumps({"state": "A self-contained state.", "questions": [choice] * 5})

    class FakeClient:
        unavailable_models = {}

        def __init__(self):
            self.models = []

        async def generate(self, model, prompt, ledger, **kwargs):
            self.models.append(model)
            assert kwargs["response_schema"] is AUTHOR_SCHEMA
            assert kwargs["max_output_tokens"] == 8000
            return response, {}

    client = FakeClient()
    items, rejected = asyncio.run(author_items(20, random.Random(2411), client, object()))
    assert not rejected
    assert len(items) == 20
    assert Counter(client.models) == {"gpt-5.4-mini": 16, "claude-sonnet-5-5": 4}
