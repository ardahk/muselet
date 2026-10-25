"""start_timer copy per backend; Clock AX failures fall back to Muselet's timer
silently, with no setup hint (docs/CLOCK_TIMERS.md)."""

import asyncio

import pytest

from brain import replies
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer

from fakes import FakeServer

AX_VERIFIED = {"backend": "clock_ax", "verified": True, "seconds": 600}
AX_UNVERIFIED = {"backend": "clock_ax", "verified": False, "seconds": 600}
AX_FAILED = {"backend": "muselet", "fallback_reason": "wheel_s_stuck",
             "clock_ax_reason": "wheel_s_stuck", "seconds": 600, "timer_id": "timer-def"}
AX_UNAVAILABLE = {"backend": "muselet", "fallback_reason": "clock_ax_unavailable",
                  "clock_ax_reason": "clock_ax_unavailable", "seconds": 600}
AX_START_UNVERIFIED = {"backend": "muselet", "fallback_reason": "start_unverified",
                       "clock_ax_reason": "start_unverified", "verified": False, "seconds": 600}

TIMER = [{"op": "skill", "name": "start_timer", "args": {"duration": "600"}}]


# The five AX_* backends are covered end to end (same strings) by
# test_only_the_timer_reply_no_setup_hint below.
@pytest.mark.parametrize("result,want", [
    ({"backend": "clock_ax", "seconds": 5400}, "Timer set for 1 hour 30 minutes"),
    ({"backend": "muselet", "seconds": 90}, "Timer set for 1 minute 30 seconds"),
    ({"backend": "clock_ax", "seconds": 1}, "Timer set for 1 second"),
    (None, "Timer set for 10 minutes"),          # old HandsKit: no backend
])
def test_timer_bubble_by_backend(result, want):
    text = replies.success_text("start_timer", {"duration": "600"}, result)
    assert text == want
    assert len(text.split()) <= 12


def _orch(tmp_path, results):
    it = iter(results)
    server = FakeServer(handlers={
        "skill": lambda p: {"ok": True, "result": next(it), "ms": 1}})
    return Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces")), server


@pytest.mark.parametrize("result,want", [
    (AX_VERIFIED, "Timer set in Clock for 10 minutes"),
    (AX_UNVERIFIED, "Timer set for 10 minutes"),
    (AX_FAILED, "Timer set for 10 minutes in Muselet"),
    (AX_UNAVAILABLE, "Timer set for 10 minutes in Muselet"),
    (AX_START_UNVERIFIED, "Timer set for 10 minutes in Muselet"),
])
def test_only_the_timer_reply_no_setup_hint(tmp_path, result, want):
    o, server = _orch(tmp_path, [result, result])

    async def go():
        out = [await o.execute_actions(TIMER) for _ in range(2)]
        await asyncio.sleep(0.02)
        return out
    assert asyncio.run(go()) == ["ok", "ok"]
    assert server.said == [want] * 2
