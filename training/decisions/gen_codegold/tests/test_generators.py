from __future__ import annotations

import random
import re
from collections import Counter, defaultdict

import pytest

from bench.systemone.schema import parse_request
from training.decisions.build import _chi_square_position, _leak_errors
from training.decisions.gen_codegold import FAMILIES
from training.decisions.gen_codegold.families import GENERATORS
from training.decisions.gen_codegold.families import (
    cg_counting, cg_long_policy, cg_multi_hop, cg_numeric,
    cg_probability, cg_temporal, cg_trap,
)

MODULES = {
    "cg_counting": cg_counting, "cg_multi_hop": cg_multi_hop,
    "cg_long_policy": cg_long_policy, "cg_temporal": cg_temporal,
    "cg_numeric": cg_numeric, "cg_probability": cg_probability, "cg_trap": cg_trap,
}


def _record(family, seed):
    rng = random.Random(seed)
    return GENERATORS[family](rng, rng.randint(2, 5))


@pytest.mark.parametrize("family", FAMILIES)
def test_generators_validate_schema_and_independent_gold(family):
    verifier = MODULES[family].verify_rendered
    for seed in range(200):
        record = _record(family, seed)
        assert 2 <= len(record["questions"]) <= 5
        parse_request({"state": record["state"], "questions": record["questions"]})
        assert set(record["gold"]) == set(record["questions"])
        assert set(record["gold_basis"].values()) == {"code"}
        assert record["_meta"]["traps"]
        assert set(record["_meta"]["surface"]) == set(record["questions"])
        assert not _leak_errors(record)
        for qid, question in record["questions"].items():
            kind, criteria = question["type"], question["criteria"]
            if kind == "choice":
                assert 2 <= len(criteria) <= 26
                assert len(criteria) == len(set(criteria))
                assert record["gold"][qid] in criteria
            elif kind == "score":
                assert 3 <= len(criteria) <= 6
                assert record["gold"][qid] in {str(i) for i in range(len(criteria))}
                if family == "cg_counting":
                    assert all("less than" in band.lower() for band in criteria[:-1])
                    assert "at least" in criteria[-1].lower()
                else:
                    assert all(">=" in band and "<" in band for band in criteria[:-1])
                    assert ">=" in criteria[-1] and "<" not in criteria[-1]
            else:
                assert set(criteria) == {"false", "true"}
                assert record["gold"][qid] in criteria
    assert all(verifier(_record(family, seed)) for seed in range(200))


@pytest.mark.parametrize("family", FAMILIES)
def test_generator_distributions(family):
    rng = random.Random(880_123 + FAMILIES.index(family))
    records, noul, score, option_counts = [], Counter(), defaultdict(Counter), Counter()
    tokens = []
    for _ in range(2000):
        record = GENERATORS[family](rng, rng.randint(2, 5))
        records.append(record)
        tokens.append(record["_meta"]["approx_tokens"])
        for qid, question in record["questions"].items():
            if question["type"] == "noul":
                noul[record["gold"][qid]] += 1
            elif question["type"] == "score":
                count = len(question["criteria"])
                score[count][record["gold"][qid]] += 1
            else:
                option_counts[len(question["criteria"])] += 1

    true_share = noul["true"] / sum(noul.values())
    assert 0.45 <= true_share <= 0.55
    assert _chi_square_position(records)[-1] > 0.05
    assert option_counts
    assert all(2 <= option_count <= 26 for option_count in option_counts)
    for count, levels in score.items():
        total = sum(levels.values())
        expected = total / count
        assert set(levels) == {str(i) for i in range(count)}
        assert all(0.5 * expected <= levels[str(i)] <= 1.5 * expected for i in range(count))
    if family == "cg_long_policy":
        assert min(tokens) >= 2000
        assert max(tokens) <= 6000
        assert max(tokens) - min(tokens) >= 1000


def test_word_level_distance_is_bounded():
    from training.decisions.gen_codegold.decontam2 import _within_one

    assert _within_one(("alpha", "beta"), ("alpha", "gamma"))
    assert _within_one(("alpha", "beta"), ("alpha", "beta", "gamma"))
    assert not _within_one(("alpha", "beta"), ("gamma", "delta"))
