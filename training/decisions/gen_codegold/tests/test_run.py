from types import SimpleNamespace

from training.decisions.gen_codegold import run
from training.decisions.gen_codegold.run import (
    _paraphrase_targets,
    _pending_label_questions,
    _preserved_marker_count,
)


def test_paraphrase_target_rates_are_50_percent_states_and_40_percent_questions():
    records = [
        {
            "id": f"state-{index}",
            "_meta": {"prose_sections": ["A prose section."]},
            "questions": {f"q{question}": {} for question in range(3)},
        }
        for index in range(100)
    ]

    selected_states, selected_questions = _paraphrase_targets(records, 17)

    assert len(selected_states) == 50
    assert len(selected_questions) == 120
    assert _paraphrase_targets(records, 17) == (selected_states, selected_questions)


def test_preserved_marker_count_identifies_complex_sections():
    assert _preserved_marker_count("A plain sentence.") == 0
    assert _preserved_marker_count(", ".join("$100.00" for _ in range(16))) == 16


def test_label_resume_tracks_completed_questions_even_without_kept_state():
    records = [
        {"id": "state-1", "questions": {"q1": {}, "q2": {}}},
        {"id": "state-2", "questions": {"q1": {}}},
    ]
    partial = [{"id": "state-1", "qid": "q1"}]

    pending = _pending_label_questions(records, partial)
    assert [(item["id"], qid) for item, qid, _ in pending] == [
        ("state-1", "q2"),
        ("state-2", "q1"),
    ]
    assert _pending_label_questions(
        records,
        [
            {"id": "state-1", "qid": "q1"},
            {"id": "state-1", "qid": "q2"},
            {"id": "state-2", "qid": "q1"},
        ],
    ) == []


def test_ledger_scopes_budget_to_round_and_project_total(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "COST_PATH", tmp_path / "costs.jsonl")
    ledger = run._ledger(SimpleNamespace(run="full", budget=33.0))

    assert ledger.run == "codegold"
    assert ledger.round_id == "full"
    assert ledger.budget == 33.0
    assert ledger.cumulative_budget == 68.0
