"""evals/planner_think_report.py: pre-registered ship rule and run-file loading (no model)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))
import planner_think_report as R  # noqa: E402


def _rows(n, n_pass, ms, think=0):
    return [{"pass": i < n_pass, "plan_ms": ms, "retrieval_ms": 1.0, "think_tokens": think} for i in range(n)]


def _st(mean, p50):
    return {"holdout_mean": mean, "p50_ms": p50}


def test_decide_gates_and_ties():
    best, notes = R.decide({"a": _st(0.70, 2000), "b": _st(0.70, 1500), "c": _st(0.80, 3500), "d": _st(0.66, 900)})
    assert best == "b"
    assert "c: FAIL (step p50 3500 ms > 3000)" in notes
    assert "d: FAIL (holdout mean 0.660 < 0.672)" in notes
    assert R.decide({"x": _st(0.672, 3000)})[0] == "x"
    assert R.decide({"y": _st(0.671, 100)}) == (None, ["y: FAIL (holdout mean 0.671 < 0.672)"])
    assert R.decide({"lo": _st(0.70, 100), "hi": _st(0.75, 2900)})[0] == "hi"


def test_load_and_stats(tmp_path, capsys):
    def put(name, rows):
        (tmp_path / f"think-{name}.json").write_text(json.dumps({"summary": {}, "rows": rows}))
    put("4b-t512-qwen-all-v1holdout", _rows(10, 7, 1000, 300))
    put("4b-t512-qwen-all-v1holdout2", _rows(10, 8, 2000, 300))
    put("4b-t512-qwen-all-v2holdout", _rows(20, 10, 3000, 300))
    put("4b-t512-qwen-all-v1tune", _rows(4, 4, 9000))
    put("4b-t0-greedy-all-v1holdout", _rows(10, 6, 100))
    stats = R.load(tmp_path, "think")
    assert list(stats) == ["4b-t512-qwen-all"] and "skip 4b-t0-greedy-all" in capsys.readouterr().out
    st = stats["4b-t512-qwen-all"]
    assert round(st["holdout_mean"], 3) == round((0.7 + 0.8 + 0.5) / 3, 3)
    assert st["p50_ms"] == 2501.0 and st["p95_ms"] == 3001.0     # holdout rows only, tune excluded
    assert st["rates"]["v1-tune"] == 1.0 and st["think_tokens_mean"] == 300
