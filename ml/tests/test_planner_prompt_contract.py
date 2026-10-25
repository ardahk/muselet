"""The planner chooses app actions without prewritten finance recipes."""

from brain.app_hints import load_hints, render_hints
from brain.planner import PROMPT_PATH


def test_system_prompt_does_not_force_removed_app_tools_or_schemas():
    text = PROMPT_PATH.read_text()
    assert "skill finance_review" not in text
    assert "skill premiere_command" not in text
    assert "A1:E121" not in text
    assert "Transactions::" not in text
    assert "set value of cell" not in text
    assert "never invent a schema" in text
    assert "Read with `get`" in text
    assert "current goal only" in text


def test_numbers_cheat_sheet_exposes_reads_and_native_sort_not_a_workflow():
    hints = [hint for hint in load_hints() if hint.id == "numbers"]
    text = render_hints(hints)
    assert "get formatted value" in text
    assert "sort aTable by column n of aTable direction descending" in text
    assert "transaction values" in text
    assert "skill finance_review" not in text
    assert "finance_review tool" not in text
