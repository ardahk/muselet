"""brain trace-stats over a committed fixture (task 4)."""

import json
import subprocess
import sys
from pathlib import Path

from brain import tracestats

FIX = Path(__file__).parent / "fixtures" / "traces_small.jsonl"


def test_pct_nearest_rank():
    assert tracestats.pct([], 50) is None
    assert tracestats.pct([5], 95) == 5
    xs = list(range(1, 101))
    assert tracestats.pct(xs, 50) == 50 and tracestats.pct(xs, 95) == 95
    assert tracestats.pct([1, 2, 3, 4], 50) == 2


def test_load_skips_bad_lines_and_filters_since(tmp_path):
    assert len(tracestats.load(FIX)) == 7
    assert len(tracestats.load(FIX, "2026-10-24")) == 5
    assert len(tracestats.load(FIX, "2026-10-24T09:05:30")) == 2
    (tmp_path / "a.jsonl").write_text(FIX.read_text())
    assert len(tracestats.load(tmp_path)) == 7       # directory of files


def test_overall_metrics():
    rep = tracestats.stats(tracestats.load(FIX))
    a = rep["all"]
    assert rep["n"] == 7 and a["n"] == 7
    assert a["route_ms"] == {"p50": 55.0, "p95": 70.0, "n": 5}
    assert a["args_ms"] == {"p50": 35.0, "p95": 40.0, "n": 3}
    assert a["release_to_first_action_ms"]["n"] == 4
    assert a["release_to_first_action_ms"]["p50"] == 150.0
    assert a["planner_ttft_ms"] == {"p50": 300.0, "p95": 300.0, "n": 1}
    assert a["decode_tok_s"]["p50"] == 50.0
    assert a["total_ms"]["p95"] == 2401.0


def test_spec_hit_and_slot_fill():
    rep = tracestats.stats(tracestats.load(FIX))
    assert rep["spec_n"] == 5 and rep["spec_hit_rate"] == 0.6
    assert rep["slot_fill"] == 2


def test_grouping():
    rep = tracestats.stats(tracestats.load(FIX))
    assert set(rep["by_outcome"]) == {"ok", "awaiting_user", "fallback"}
    assert rep["by_outcome"]["ok"]["n"] == 5
    assert set(rep["by_label"]) == {"set_volume", "send_message", "MULTI_STEP",
                                    "ANSWER", "fallback", "none"}
    sv = rep["by_label"]["set_volume"]
    assert sv["n"] == 2 and sv["route_ms"]["p95"] == 70.0


def test_report_text():
    txt = tracestats.format_report(tracestats.stats(tracestats.load(FIX)))
    assert "traces: 7" in txt and "slot_fill: 2" in txt
    assert "set_volume" in txt and "awaiting_user" in txt


def test_cli(tmp_path):
    src = Path(__file__).parents[1] / "src"
    out = subprocess.run(
        [sys.executable, "-m", "brain.cli", "trace-stats", "--path", str(FIX),
         "--since", "2026-10-24", "--json"], capture_output=True, text=True,
        env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"}, check=True)
    rep = json.loads(out.stdout)
    assert rep["n"] == 5 and rep["slot_fill"] == 2
