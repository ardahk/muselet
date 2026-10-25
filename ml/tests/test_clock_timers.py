"""start_timer copy per backend and the once-per-session setup hint
(docs/CLOCK_TIMERS.md)."""

import asyncio

import pytest

from brain import replies
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer

from fakes import FakeServer

CLOCK = {"backend": "clock", "seconds": 600, "label": None, "ms": 420.0,
         "timer_id": "timer-abc"}
MISSING = {"backend": "muselet", "fallback_reason": "shortcut_missing",
           "clock_ax_reason": "wheel_s_stuck", "seconds": 600, "timer_id": "timer-def"}
TIMEOUT = {"backend": "muselet", "fallback_reason": "shortcut_timeout",
           "seconds": 600, "timer_id": "timer-ghi"}
AX_VERIFIED = {"backend": "clock_ax", "verified": True, "seconds": 600}
AX_UNVERIFIED = {"backend": "clock_ax", "verified": False, "seconds": 600}
AX_FALLBACK_FIELDS = {"backend": "clock_ax", "verified": False,
                      "fallback_reason": "shortcut_missing",
                      "clock_ax_reason": "wheel_s_stuck", "seconds": 600}

TIMER = [{"op": "skill", "name": "start_timer", "args": {"duration": "600"}}]


@pytest.mark.parametrize("result,want", [
    (CLOCK, "Timer set in Clock for 10 minutes"),
    (AX_VERIFIED, "Timer set for 10 minutes"),
    (AX_UNVERIFIED, "Timer set for 10 minutes"),
    (MISSING, "Timer set for 10 minutes"),
    (TIMEOUT, "Timer set for 10 minutes"),
    ({"backend": "muselet", "fallback_reason": "clock_off", "seconds": 90},
     "Timer set for 1 minute 30 seconds"),
    ({"backend": "clock", "seconds": 5400}, "Timer set in Clock for 1 hour 30 minutes"),
    ({"backend": "clock", "seconds": 1}, "Timer set in Clock for 1 second"),
    (None, "Timer set for 10 minutes"),          # old HandsKit: no backend
])
def test_timer_bubble_by_backend(result, want):
    text = replies.success_text("start_timer", {"duration": "600"}, result)
    assert text == want
    assert len(text.split()) <= 12


def test_hint_is_short():
    assert len(replies.CLOCK_HINT.split()) <= 12


def _orch(tmp_path, results):
    it = iter(results)
    server = FakeServer(handlers={
        "skill": lambda p: {"ok": True, "result": next(it), "ms": 1}})
    o = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"))
    o.CLOCK_HINT_DELAY_S = 0
    return o, server


def _run_all(o, n):
    async def go():
        return [await o.execute_actions(TIMER) for _ in range(n)]
    return asyncio.run(go())


def test_missing_shortcut_hint_once_per_session(tmp_path):
    o, server = _orch(tmp_path, [MISSING, MISSING, MISSING])
    assert _run_all(o, 3) == ["ok"] * 3
    assert server.said.count(replies.CLOCK_HINT) == 1
    assert server.said[:2] == ["Timer set for 10 minutes", replies.CLOCK_HINT]
    assert server.said.count("Timer set for 10 minutes") == 3


@pytest.mark.parametrize("result", [
    CLOCK, TIMEOUT, AX_VERIFIED, AX_UNVERIFIED, AX_FALLBACK_FIELDS,
    {"backend": "muselet", "fallback_reason": "clock_off"},
])
def test_no_hint_unless_shortcut_missing(tmp_path, result):
    o, server = _orch(tmp_path, [result])
    _run_all(o, 1)
    assert replies.CLOCK_HINT not in server.said


def test_clock_success_bubble_through_orchestrator(tmp_path):
    o, server = _orch(tmp_path, [CLOCK])
    _run_all(o, 1)
    assert server.said == ["Timer set in Clock for 10 minutes"]


def test_delayed_hint_follows_reply(tmp_path):
    o, server = _orch(tmp_path, [MISSING])
    o.CLOCK_HINT_DELAY_S = 0.01

    async def go():
        await o.execute_actions(TIMER)
        await asyncio.sleep(0.05)
    asyncio.run(go())
    assert server.said == ["Timer set for 10 minutes", replies.CLOCK_HINT]


def test_delayed_hint_dropped_when_new_request_started(tmp_path):
    o, server = _orch(tmp_path, [MISSING])
    o.CLOCK_HINT_DELAY_S = 0.02

    async def go():
        await o.execute_actions(TIMER)
        o._t_final += 1.0                      # next utterance arrived
        await asyncio.sleep(0.06)
    asyncio.run(go())
    assert server.said == ["Timer set for 10 minutes"]
    assert o._clock_hint_said                  # still once per session
