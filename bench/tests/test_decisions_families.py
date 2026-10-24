import random
from datetime import date

import pytest

from bench.systemone.schema import parse_request
from training.decisions.families import GENERATORS, counting, multi_hop, numeric, probability, temporal


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
