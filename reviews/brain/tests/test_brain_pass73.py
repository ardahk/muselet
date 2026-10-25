"""brain-55 (wip/local 422399a, mac/fix-thinking b43270d): _timer_control_intent runs first in _engine_route and claims any utterance with 'timer' plus stop/cancel/pause/resume, and bare it/this/that within 10 min of a timer, sending it to a Clock planner loop."""
import time
import pytest
from brain.orchestrator import Orchestrator


def _orch(recent_timer=False):
    if not hasattr(Orchestrator, "_timer_control_intent"):
        pytest.skip("no _timer_control_intent on this branch")
    o = Orchestrator.__new__(Orchestrator)
    o._ctx = {"app": "Spotify"}
    o._last_timer_at = time.time() - 60 if recent_timer else 0
    return o


@pytest.mark.parametrize("text", [
    "set a 10 minute timer to stop the oven",
    "start a timer and pause my music",
])
def test_timer_requests_are_not_timer_controls(text):
    assert _orch()._timer_control_intent(text) is None


@pytest.mark.parametrize("text", [
    "stop playing this song",
    "pause this video",
])
def test_media_pronouns_after_a_timer_are_not_timer_controls(text):
    assert _orch(recent_timer=True)._timer_control_intent(text) is None
