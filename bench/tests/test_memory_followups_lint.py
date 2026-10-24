import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals.memory_followups_lint import lint


def _row():
    return {
        "id": "mf-0001",
        "split": "tune",
        "category": "site_search",
        "longterm": [],
        "turns": [
            {
                "utterance": "Search for the page.",
                "ctx": {
                    "app": "Finder", "focused": "none", "selection": False, "online": True,
                    "url": "", "window_title": "Finder", "t": 0,
                },
                "outcome": {"skill": "planner", "args": {"goal": "Search for the page."}, "ok": True},
                "expect": {"type": "unchanged"},
            },
            {
                "utterance": "Try again.",
                "ctx": {
                    "app": "Finder", "focused": "none", "selection": False, "online": True,
                    "url": "", "window_title": "Finder", "t": 1,
                },
                "outcome": {"skill": "ASK", "args": {"question": "Which page?"}, "ok": True},
                "expect": {"type": "not_resolved"},
            },
        ],
    }


def _row_problems(rows):
    return [problem for problem in lint(rows) if not problem.startswith("dataset:")]


def test_real_eval_file_lints():
    path = ROOT / "evals" / "memory_followups.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert lint(rows) == []


def test_minimal_synthetic_row_passes_per_row_checks():
    assert _row_problems([_row()]) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda row: row["turns"][0]["outcome"].update(skill="missing_skill", args={}), "unknown skill"),
        (lambda row: row["turns"][0]["outcome"].update(
            skill="set_volume", args={"level": 50, "extra": 1}), "unknown argument"),
        (lambda row: row["turns"][0]["outcome"].update(
            skill="window_layout", args={"layout": "diagonal"}), "invalid value"),
        (lambda row: row["turns"][0]["outcome"].update(skill="set_volume", args={}), "missing required argument"),
        (lambda row: row["turns"][0].update(expect={"type": "rewrite", "all": [[]], "none": []}), "all must"),
        (lambda row: row["turns"][0].update(expect={"type": "rewrite", "all": [], "none": []}), "all must"),
        (lambda row: row["turns"][0]["ctx"].update(extra="value"), "ctx keys"),
        (lambda row: row["turns"][1]["ctx"].update(t=0), "strictly increasing"),
        (lambda row: row["turns"][0]["ctx"].update(url="https://example.com"), "url must be empty"),
        (lambda row: row.update(split="validation"), "split must"),
    ],
)
def test_mutations_are_rejected(mutate, expected):
    row = copy.deepcopy(_row())
    mutate(row)
    assert any(expected in problem for problem in _row_problems([row]))


def test_duplicate_id_is_rejected():
    rows = [_row(), copy.deepcopy(_row())]
    assert any("duplicate id" in problem for problem in _row_problems(rows))
