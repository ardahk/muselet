import random
import re
from collections import Counter, defaultdict
from decimal import Decimal

from training.decisions.gen_codegold.common import round_bands, score_level_for
from training.decisions.gen_codegold.families import cg_counting


def _generate(seed):
    rng = random.Random(seed)
    return cg_counting.generate(rng, rng.randint(2, 5))


def test_counting_independent_text_verifier_recomputes_500_seeds():
    for seed in range(500):
        record = _generate(seed)
        assert cg_counting.verify_rendered(record), f"independent verifier rejected seed {seed}"
        assert 2 <= len(record["questions"]) <= 5
        assert len({question["instructions"] for question in record["questions"].values()}) == len(
            record["questions"]
        )


def test_counting_d9_distributions_and_surface_constraints():
    records = [_generate(seed + 10_000) for seed in range(2_000)]
    included_notes = []
    note_positions = Counter()
    choice_positions = defaultdict(Counter)
    score_levels = defaultdict(Counter)
    noul_answers = []

    for record in records:
        state = record["state"]
        tokens = len(state) // 4
        assert 600 <= tokens <= 2_500
        assert "schema" not in state.lower()
        assert not re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", state)
        rows, *_ = cg_counting._read_export(state)
        assert 25 <= len(rows) <= 60
        instructions = [question["instructions"] for question in record["questions"].values()]
        assert len(instructions) == len(set(instructions))

        staff_note = record["_meta"]["staff_note"]
        if staff_note["included"]:
            included_notes.append(staff_note["correct"])
            note_positions[staff_note["position"]] += 1
        else:
            assert staff_note["correct"] is None
            assert staff_note["position"] is None

        for qid, question in record["questions"].items():
            criteria = question["criteria"]
            assert not any(re.match(rf"^{re.escape(qid)}_", key) for key in criteria) if isinstance(
                criteria, dict
            ) else True
            assert not any("candidate" in str(key).lower() for key in criteria)
            assert not any("candidate" in str(value).lower() for value in criteria.values()) if isinstance(
                criteria, dict
            ) else True
            if question["type"] == "choice":
                assert 2 <= len(criteria) <= 26
                assert record["gold"][qid] in criteria
                choice_positions[len(criteria)][list(criteria).index(record["gold"][qid])] += 1
            elif question["type"] == "score":
                assert record["gold"][qid].isdigit()
                assert int(record["gold"][qid]) < len(criteria)
                score_levels[len(criteria)][record["gold"][qid]] += 1
                for level in criteria:
                    for number in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level):
                        if "." in number:
                            assert len(number.rsplit(".", 1)[1]) <= 2
            else:
                noul_answers.append(record["gold"][qid])

    note_rate = sum(note is True for note in included_notes) / len(included_notes)
    assert 0.60 <= len(included_notes) / len(records) <= 0.70
    assert 0.25 <= note_rate <= 0.35
    assert len(note_positions) >= 3
    assert 0.45 <= noul_answers.count("true") / len(noul_answers) <= 0.55

    for positions in choice_positions.values():
        if sum(positions.values()) >= 30:
            assert len(positions) > 1
            assert max(positions.values()) / min(positions.values()) < 2.0
    for count, distribution in score_levels.items():
        observed = [distribution[str(index)] for index in range(count)]
        assert min(observed) > 0
        assert max(observed) / min(observed) < 1.8


def test_counting_round_bands_have_rounded_edges_and_uniform_gold():
    rng = random.Random(40_401)
    value = Decimal("877.37")
    gold_counts = Counter()
    boundary_count = 0
    for _ in range(2_000):
        criteria, gold_index = round_bands(
            value, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50")],
            rng, levels=(5, 5), boundary_rate=0.15,
        )
        assert len(criteria) == 5
        assert score_level_for(value, criteria) == str(gold_index)
        edges = {
            Decimal(token.replace(",", ""))
            for level in criteria
            for token in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level)
        }
        if value in edges:
            boundary_count += 1
        else:
            assert min(abs(value - edge) for edge in edges) >= value * Decimal("0.02")
        for level in criteria:
            for number in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level):
                if "." in number:
                    assert len(number.rsplit(".", 1)[1]) <= 2
        gold_counts[gold_index] += 1

    assert 0.12 <= boundary_count / 2_000 <= 0.18
    assert max(gold_counts.values()) / min(gold_counts.values()) < 1.2
