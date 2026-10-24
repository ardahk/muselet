import random
import re
from collections import Counter

from training.decisions.gen_codegold.families import cg_multi_hop


def _generate(seed):
    rng = random.Random(seed)
    return cg_multi_hop.generate(rng, rng.randint(2, 5))


def _neutralized(text):
    text = re.sub(r"\$[\d,]+(?:\.\d{1,2})?", "<value>", text)
    text = re.sub(r"\bVN-\d+\b", "<entity>", text)
    text = re.sub(r"\b[A-Z]{3}\b", "<value>", text)
    text = re.sub(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", "<value>", text)
    text = re.sub(r"\b(?:Review|Manager|Director|Executive)\b", "<value>", text)
    return text


def test_multi_hop_independently_reparses_three_hops():
    for seed in range(500):
        record = _generate(seed + 100_000)
        assert cg_multi_hop.verify_rendered(record), f"verifier rejected seed {seed}"
        assert 600 <= record["_meta"]["approx_tokens"] <= 2_500
        assert record["_meta"]["hop_count"] == 3
        assert len(record["_meta"]["facts"]["entities"]) >= 6
        assert len(record["_meta"]["facts"]["agreements"]) >= 8
        assert len(record["_meta"]["facts"]["rates"]) >= 8
        assert len(record["_meta"]["facts"]["matrix"]) >= 4
        assert any(
            row["Status"] in {"Superseded", "Archived"}
            for row in record["_meta"]["facts"]["agreements"]
        )
        assert "replaced" in record["state"].lower()
        quantities = list(record["_meta"]["quantity_kinds"].values())
        assert len(quantities) == len(set(quantities))
        assert not re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", record["state"])
        assert "schema" not in record["state"].lower()


def test_multi_hop_neutral_options_and_family_notes():
    note_correct = []
    for seed in range(2_000):
        record = _generate(seed + 120_000)
        for qid, question in record["questions"].items():
            if question["type"] != "choice":
                continue
            provenance = record["_meta"]["option_provenance"][qid]
            assert set(question["criteria"]) <= set(provenance)
            assert len({_neutralized(text) for text in question["criteria"].values()}) == 1
            assert not any(
                phrase in text.lower()
                for text in question["criteria"].values()
                for phrase in ("using the old", "if the reviewer", "after applying", "because the")
            )
        note = record["_meta"]["narrative_section"]
        if note:
            assert note.startswith("Mira (procurement): I get $")
            assert "superseded" not in note.lower()
            note_correct.append(record["_meta"]["staff_note"]["correct"])
    assert 0.25 <= sum(value is True for value in note_correct) / len(note_correct) <= 0.35
    assert 0.60 <= len(note_correct) / 2_000 <= 0.70
