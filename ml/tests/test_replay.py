"""Offline trace replay (brain.replay): the harness itself, plus the seven
user-test failures of 2026-10-24 as regressions (evals/replay/)."""
import asyncio
import json
from pathlib import Path

import pytest

from brain import replay

ROOT = Path(__file__).resolve().parents[2]
USER_CASES = replay.load(ROOT / "evals/replay/user_2026-10-24.jsonl")
ZEN = {"app": "Zen", "focused": "none", "selection": False, "online": True,
       "url": "https://www.google.com/", "window_title": "Google"}


def _case(turn, **kw):
    return {"id": "t", "apps": {"running": [], "installed": ["TextEdit"]},
            "turns": [turn], **kw}


def _timer_turn(**kw):
    return dict({"utterance": "set a timer for 2 minutes", "ctx": ZEN,
                 "route": {"set a timer for 2 minutes": {"start_timer": 0.98}},
                 "args": {"start_timer": {"duration": "2 minutes"}},
                 "rpc": [{"method": "skill", "match": {"name": "start_timer"},
                          "result": {"backend": "clock_ax", "seconds": 120,
                                     "verified": True}}]}, **kw)


def test_recorded_hands_answers_only_what_was_recorded():
    r = replay.run_case(_case(_timer_turn(
        expect=[{"rpc": {"method": "skill", "name": "start_timer",
                         "args": {"duration": 120}}}])))
    assert r["passed"], r
    turn = _timer_turn()
    turn["rpc"][0]["match"]["name"] = "open_app"    # recording no longer matches
    r = replay.run_case(_case(turn))
    assert not r["passed"]
    assert "unrecorded" in r["turns"][0]["failures"][0]


def test_unrecorded_route_is_a_divergence_not_a_guess():
    turn = _timer_turn(route={})
    r = replay.run_case(_case(turn))
    assert not r["passed"]
    assert "route 'set a timer for 2 minutes'" in r["turns"][0]["failures"][0]


def test_said_none_forbids_claims_and_precondition_skips():
    r = replay.run_case(_case(_timer_turn(precondition=True,
                                          expect=[{"said_none": "(?i)timer"}])))
    assert r.get("skipped") and not r["passed"]


def test_from_trace_round_trips_a_recorded_turn(tmp_path):
    """Replay -> trace -> from_trace -> replay gives the same RPCs."""
    case = _case(_timer_turn())
    r1 = asyncio.run(replay.replay_case(case, tmp_path))
    rows = [json.loads(l) for p in (tmp_path / "traces").glob("*.jsonl")
            for l in p.read_text().splitlines()]
    assert rows and rows[-1]["ctx"]["app"] == "Zen"
    drafted = replay.from_trace(rows[-1:])
    drafted["apps"] = case["apps"]
    t = drafted["turns"][0]
    assert t["route"] == {"set a timer for 2 minutes": {"start_timer": 0.98}}
    assert t["args"] == {"start_timer": {"duration": "2 minutes"}}
    r2 = replay.run_case(drafted)
    assert r2["passed"], r2
    assert r2["turns"][0]["sent"] == r1["turns"][0]["sent"]


@pytest.mark.parametrize("case", USER_CASES, ids=[c["id"] for c in USER_CASES])
def test_user_failure_regression(case):
    """Each case encodes the behaviour the user expected. `fails_on_main`
    marks it strict-xfail until the fix lane lands: the fixing PR deletes
    the key (XPASS fails CI until it does)."""
    r = replay.run_case(case)
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    failures = [f for t in r["turns"] for f in t["failures"]]
    if case.get("fails_on_main"):
        if r["passed"]:
            pytest.fail(f"XPASS: {case['id']} now passes; delete fails_on_main "
                        f"(fixed by {case.get('fixed_by')})")
        pytest.xfail(f"{case.get('fixed_by')}: {failures[0][:200]}")
    assert r["passed"], failures
