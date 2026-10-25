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


def test_numbers_sort_controls_describe_the_picker_not_grid_selection():
    hints = [hint for hint in load_hints() if hint.id == "numbers"]
    text = render_hints(hints)
    assert "Add a Column... is the sort-key picker" in text
    assert "selecting a grid header does NOT add a sort rule" in text
    assert "Sort Now applies the rules" in text


def test_numbers_formula_facts_preserve_the_source_and_derive_real_ranges():
    hints = [hint for hint in load_hints() if hint.id == "numbers"]
    text = render_hints(hints)
    assert "SORTBY(array, key-array, sort-order)" in text
    assert "-1 for descending" in text
    assert "sorted COPY into empty cells" in text
    assert "observed source ranges excluding headers" in text
    assert "A1:E121" not in text
