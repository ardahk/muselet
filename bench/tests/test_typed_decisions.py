import ast
import inspect
import json
import runpy
import textwrap
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as parquet
import pytest

from bench import typed_decisions


def _score_gold():
    return {
        "type": "score",
        "probabilities": {"0": 0.1, "1": 0.3, "2": 0.4, "3": 0.2},
    }


def test_normalize_noul_value_and_score_it():
    gold = {
        "type": "noul",
        "probabilities": {"false": 0.1, "true": 0.9},
    }

    normalized, tag = typed_decisions.normalize_answer({"noul": 0.8}, gold)

    assert tag == "noul_from_value"
    assert normalized["probabilities"]["false"] == pytest.approx(0.2)
    assert normalized["probabilities"]["true"] == 0.8
    assert typed_decisions.score_one(normalized, gold)[0] is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.79, "1"), (2.5, "3"), (-1, "0"), (7, "3")],
)
def test_normalize_score_value_rounds_half_up_and_clamps(value, expected):
    normalized, tag = typed_decisions.normalize_answer({"score": value}, _score_gold())

    assert tag == "score_onehot_from_value"
    assert normalized["probabilities"] == {
        level: 1.0 if level == expected else 0.0
        for level in _score_gold()["probabilities"]
    }


def test_normalized_score_is_scored_correctly():
    gold = _score_gold()
    normalized, tag = typed_decisions.normalize_answer({"score": 2}, gold)

    assert tag == "score_onehot_from_value"
    assert typed_decisions.score_one(normalized, gold)[0] is True


def test_existing_probabilities_are_returned_unchanged():
    pred = {"probabilities": {"A": 0.8, "B": 0.2}}

    normalized, tag = typed_decisions.normalize_answer(
        pred,
        {"type": "choice", "probabilities": {"A": 1.0, "B": 0.0}},
    )

    assert normalized is pred
    assert tag is None


def test_missing_answer_remains_uniform():
    pred = {"probabilities": {}}
    gold = {
        "type": "noul",
        "probabilities": {"false": 0.0, "true": 1.0},
    }

    normalized, tag = typed_decisions.normalize_answer(pred, gold)

    assert normalized is pred
    assert tag is None
    assert typed_decisions.score_one(normalized, gold)[0] is False


def test_main_normalizes_brain_serve_answers_and_records_counts(tmp_path, monkeypatch, capsys):
    rows = []
    for index in range(2):
        rows.append(
            {
                "id": f"case-{index}",
                "state": json.dumps({"app": "test"}),
                "questions": json.dumps(
                    {
                        "noul_q": {"type": "noul"},
                        "score_q": {"type": "score"},
                        "choice_q": {"type": "choice"},
                    }
                ),
                "gold": json.dumps(
                    {
                        "noul_q": {
                            "type": "noul",
                            "probabilities": {"false": 0.1, "true": 0.9},
                        },
                        "score_q": {
                            "type": "score",
                            "probabilities": {
                                "0": 0.1,
                                "1": 0.6,
                                "2": 0.2,
                                "3": 0.1,
                            },
                        },
                        "choice_q": {
                            "type": "choice",
                            "probabilities": {"A": 0.7, "B": 0.3},
                        },
                    }
                ),
            }
        )
    parquet_path = tmp_path / "two-cases.parquet"
    parquet.write_table(pa.Table.from_pylist(rows), parquet_path)
    monkeypatch.setattr(
        typed_decisions,
        "_post",
        lambda _url, _payload: {
            "answers": {
                "noul_q": {"type": "noul", "noul": 0.8},
                "score_q": {"type": "score", "score": 0.79},
                "choice_q": {"probabilities": {"A": 0.9, "B": 0.1}},
            }
        },
    )

    assert typed_decisions.main(
        ["--parquet", str(parquet_path), "--out-root", str(tmp_path)]
    ) == 0

    output = capsys.readouterr().out
    printed_lines = output.strip().splitlines()
    printed_summary = json.loads("\n".join(printed_lines[:-1]))
    run_dir = Path(printed_lines[-1])
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    expected_counts = {
        "noul_from_value": 2,
        "score_onehot_from_value": 2,
    }
    assert summary["normalized_answers"] == expected_counts
    assert printed_summary["normalized_answers"] == expected_counts
    assert summary["n_decisions"] == 6
    for prediction in predictions:
        assert prediction["scores"]["noul_q"]["normalized"] == "noul_from_value"
        assert prediction["scores"]["score_q"]["normalized"] == "score_onehot_from_value"
        assert prediction["scores"]["choice_q"]["normalized"] is None


def _without_docstring(function_source):
    function = ast.parse(textwrap.dedent(function_source)).body[0]
    if (
        function.body
        and isinstance(function.body[0], ast.Expr)
        and isinstance(function.body[0].value, ast.Constant)
        and isinstance(function.body[0].value.value, str)
    ):
        function.body.pop(0)
    return ast.dump(function, include_attributes=False)


def test_score_one_matches_pinned_upstream_source_ignoring_docstring():
    upstream_path = Path("/home/ubuntu/ext/td/bench/score_with_jobs.py")
    if not upstream_path.is_file():
        pytest.skip(f"upstream scorer is unavailable: {upstream_path}")

    upstream = runpy.run_path(str(upstream_path))

    assert _without_docstring(inspect.getsource(typed_decisions.score_one)) == (
        _without_docstring(inspect.getsource(upstream["score_one"]))
    )
