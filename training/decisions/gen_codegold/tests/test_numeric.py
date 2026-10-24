import random
import re
from collections import Counter

from training.decisions.gen_codegold.families import cg_numeric


def _generate(seed):
    rng = random.Random(seed)
    return cg_numeric.generate(rng, rng.randint(2, 5))


def _neutralized(text):
    text = re.sub(r"\$[\d,]+(?:\.\d{1,2})?", "<value>", text)
    text = re.sub(r"\b\d+(?:,\d{3})*(?:\.\d+)?%?\b", "<value>", text)
    text = re.sub(r"\b(?:Base|Standard|Elevated|Priority)\b", "<value>", text)
    text = re.sub(r"\b(?:Yes|No)\b", "<value>", text)
    return text


def test_numeric_independently_reparses_chained_calculations():
    for seed in range(500):
        record = _generate(seed + 200_000)
        assert cg_numeric.verify_rendered(record), f"verifier rejected seed {seed}"
        assert 300 <= record["_meta"]["approx_tokens"] <= 1_500
        assert record["_meta"]["hop_count"] in (2, 3)
        quantities = list(record["_meta"]["quantity_kinds"].values())
        assert len(quantities) == len(set(quantities))
        assert len(record["_meta"]["facts"]["fx"]) >= 6
        assert len(record["_meta"]["facts"]["tiers"]) == 4
        assert "marginal" in record["state"].lower()
        assert "superseded" not in record["state"].lower()
        assert not re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", record["state"])
        assert "schema" not in record["state"].lower()


def test_numeric_neutral_options_and_mistake_derived_notes():
    note_correct = []
    modes = Counter()
    comparisons = Counter()
    for seed in range(2_000):
        record = _generate(seed + 220_000)
        state = record["state"]
        mode = record["_meta"]["facts"]["mode"]
        modes[mode] += 1
        comparisons[record["_meta"]["facts"]["comparison"]] += 1
        if mode == "fee threshold":
            assert re.search(r"Fee test: (?:at least|strictly greater than)", state)
        else:
            assert "Rate review: compare the relative change" in state
        for question in record["questions"].values():
            if question["type"] != "choice":
                continue
            assert len({_neutralized(text) for text in question["criteria"].values()}) == 1
            assert not any(
                phrase in text.lower()
                for text in question["criteria"].values()
                for phrase in ("using the old rate", "applying one rate", "because the")
            )
        for qid, question in record["questions"].items():
            if question["type"] == "choice":
                provenance = record["_meta"]["option_provenance"][qid]
                assert set(question["criteria"]) <= set(provenance)
        note = record["_meta"]["narrative_section"]
        if note:
            assert note.startswith("Mira (finance): I get ")
            assert not any(word in note.lower() for word in ("superseded", "slice", "conversion rule"))
            note_correct.append(record["_meta"]["staff_note"]["correct"])
    assert all(value > 0 for value in modes.values())
    assert set(comparisons) == {"at least", "strictly greater than"}
    assert 0.25 <= sum(value is True for value in note_correct) / len(note_correct) <= 0.35
    assert 0.60 <= len(note_correct) / 2_000 <= 0.70


def test_numeric_generates_exact_threshold_boundaries_for_both_comparators():
    exact = Counter()
    threshold_states = 0
    for seed in range(2_000):
        record = _generate(seed + 240_000)
        document = cg_numeric._read_state(record["state"])
        if document["mode"].lower() != "fee threshold":
            continue
        threshold_states += 1
        _, _, fee, *_ = cg_numeric._calculate(document)
        if fee == document["threshold"]:
            exact[document["comparison"]] += 1

    assert 0.12 <= sum(exact.values()) / 2_000 <= 0.18
    assert set(exact) == {"at least", "strictly greater than"}
    assert threshold_states > 800
