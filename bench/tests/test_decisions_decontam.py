import training.decisions.decontam as decontam_module
from training.decisions.build import _write_jsonl, split_stage
from training.decisions.families import CODE_FAMILIES


def test_decontam_reports_reference_overlaps_before_and_after(monkeypatch, tmp_path):
    matched_text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike"
    monkeypatch.setattr(
        decontam_module,
        "load_reference_sets",
        lambda root: {
            "synthetic_eval": {
                "text_grams": decontam_module.grams(matched_text),
                "option_sets": {frozenset(("a", "b"))},
                "reference_rows": 1,
                "reference_questions": 1,
            }
        },
    )
    records = [
        {
            "id": "text-overlap",
            "family": "numeric",
            "source": "code",
            "state": matched_text,
            "questions": {
                "q1": {"type": "noul", "instructions": "Is this true?", "criteria": {}},
            },
        },
        {
            "id": "option-overlap",
            "family": "numeric",
            "source": "code",
            "state": "A distinct synthetic state.",
            "questions": {
                "q1": {"type": "choice", "instructions": "Choose.", "criteria": {"a": "A", "b": "B"}},
            },
        },
        {
            "id": "clean",
            "family": "numeric",
            "source": "code",
            "state": "Another distinct synthetic state.",
            "questions": {
                "q1": {"type": "choice", "instructions": "Choose.", "criteria": {"left": "Left", "right": "Right"}},
            },
        },
    ]

    kept, report = decontam_module.decontam(records, tmp_path)

    assert [row["id"] for row in kept] == ["clean"]
    counts = report["per_reference"]["synthetic_eval"]
    assert counts["before"] == {"word_13gram_rows": 1, "option_set_questions": 1}
    assert counts["after"] == {"word_13gram_rows": 0, "option_set_questions": 0}
    assert counts["examples"]["word_13gram"][0]["record_id"] == "text-overlap"
    assert counts["examples"]["option_sets"][0]["record_id"] == "option-overlap"
    assert report["remaining_overlaps"] == {"word_13gram": 0, "option_sets": 0}


def test_full_split_is_state_disjoint_and_has_every_code_family(tmp_path):
    rows = [
        {
            "id": f"{family}-{index}",
            "family": family,
            "source": "code",
            "questions": {},
        }
        for family in CODE_FAMILIES
        for index in range(20)
    ]
    _write_jsonl(tmp_path / "records_decontam.jsonl", rows)

    train, dev = split_stage(tmp_path, seed=19)

    train_ids = {row["id"] for row in train}
    dev_ids = {row["id"] for row in dev}
    assert train_ids.isdisjoint(dev_ids)
    assert {row["family"] for row in dev} == set(CODE_FAMILIES)
    assert len(dev) == len(CODE_FAMILIES)
