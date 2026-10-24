"""Pass-19 repros. Run from a checkout of the named branch:
PYTHONPATH=ml/src:ml/tests pytest reviews/brain/tests/test_brain_pass19.py"""
import inspect
import pathlib

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.server import BrainServer
from brain.traces import Tracer
from fakes import FakeEngine
from test_orchestrator import FakeHands
from test_planner_loop import _up, run


@pytest.mark.parametrize("text,skill,args", [
    ("turn the volume all the way up", "set_volume", {"level": 100}),
    ("turn the brightness all the way down", "set_brightness", {"level": 0}),
])
def test_brain23_all_the_way_stays_absolute(text, skill, args):
    """cloud/hobby-gaps 929b931: _run_skill overwrites the model's level."""
    hands = FakeHands()
    server = BrainServer(port=0)
    eng = FakeEngine(routes={text: (skill, 0.97)},
                     argmap={(skill, text): {k: str(v) for k, v in args.items()}})
    orch = Orchestrator(server, Catalog.load(), Tracer(), engine=eng)

    async def go():
        server.port = 9972
        await _up(server, hands, orch, 9972)
        await orch.handle_utterance(text)
        await hands.close(); await server.close()
    run(go())
    sent = [m["params"] for m in hands.messages
            if m.get("t") == "rpc" and m.get("method") == "skill"]
    assert sent and sent[0]["name"] == skill and sent[0]["args"] == args, sent


def test_brain22_history_format_matches_fewshot():
    """cloud/brain-4 dfb66a3: default history 'dsl' but few-shot uses '[ok] x'."""
    from brain import dsl, planner
    hist = inspect.signature(planner.Planner.__init__).parameters["history"].default
    fs = planner.few_shot_text(planner.FEWSHOT_PATH) or ""
    if hist == "dsl":
        assert "\n[ok] " not in fs, "few-shot teaches [ok] lines, history sends '-> ok'"
        assert dsl.action_line("press #4 -> ok", set()) is None, \
            "an echoed history line parses as an executable action"
