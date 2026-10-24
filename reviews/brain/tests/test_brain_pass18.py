"""Pass-18 repros. Run from a checkout of the named branch:
PYTHONPATH=ml/src:ml/tests pytest reviews/brain/tests/test_brain_pass18.py"""
import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator, abs_level
from brain.server import BrainServer
from brain.traces import Tracer
from fakes import FakeEngine
from test_orchestrator import FakeHands
from test_planner_loop import _up, run

try:
    from brain import calc
    HAS_RESULT = hasattr(calc, "result")
except ImportError:
    HAS_RESULT = False


@pytest.mark.skipif(not HAS_RESULT, reason="cloud/hobby-gaps only")
@pytest.mark.parametrize("text", [
    "move 2 files from Downloads to folder 3",
    "close 2 tabs out of 5",
    "play 2 songs from track 7",
    "reply to Sam: meeting moved from 3 to 4",
])
def test_brain20_commands_not_hijacked_by_calc(text):
    """cloud/hobby-gaps bdcb2c4: calc.result() runs before the engine route."""
    hands = FakeHands()
    server = BrainServer(port=0)
    eng = FakeEngine(default=("MULTI_STEP", 0.9))
    orch = Orchestrator(server, Catalog.load(), Tracer(), engine=eng)

    async def go():
        server.port = 9971
        await _up(server, hands, orch, 9971)
        await orch.handle_utterance(text)
        await hands.close(); await server.close()
    run(go())
    says = [m.get("text") for m in hands.messages if m.get("t") == "say"]
    assert eng.route_calls, f"router never ran; mascot said {says}"


def test_brain16_percent_after_direction_is_relative():
    """cloud/brain-4 dbc699d regression: main gives None for these."""
    assert abs_level("turn up the volume 20%") is None
    assert abs_level("turn up the volume 5 percent") is None
    assert abs_level("turn the brightness up 3 notches at 9 pm") is None
