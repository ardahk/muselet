from training.decisions.paraphrase import validate_paraphrase


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
