"""brain review pass 43 repros. Run from repo root:
PYTHONPATH=ml/src:ml/tests pytest reviews/brain/tests/test_brain_pass43.py"""
import asyncio

import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.planner import worker
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


@pytest.mark.parametrize("code", [
    'tell application "Finder"\nif exists file "a.txt" of desktop then empty\nend tell',
    'tell application "Finder" to if (count of windows) > 0 then empty trash',
    'tell application "System Events" to if exists process "Safari" then restart',
    'tell application "System Events" to if exists process "Music" then shut down',
    'tell application "System Events" to if exists process "Mail" then log out',
    'tell application "Finder" to eject (get every disk whose ejectable is true)',
])
def test_brain39_session_ending_scripts_need_confirm(code):
    # restart / shut down / log out / empty trash discard unsaved work or data
    assert Orchestrator.script_needs_confirm(Orchestrator, "applescript", code)


def test_brain40_final_text_not_replaced_by_partial_args(tmp_path):
    eng = FakeEngine(
        {"type hello world": ("type_text", 0.97),
         "type hello, world.": ("type_text", 0.97)},
        {("type_text", "type hello world"): {"text": "hello world"},
         ("type_text", "Type Hello, world."): {"text": "Hello, world."}})
    o = Orchestrator(FakeServer(), Catalog.load(), Tracer(tmp_path / "t"),
                     engine=eng)
    o._speculative_route("type hello world")
    worker().submit(lambda: None).result(5)
    asyncio.run(o.handle_utterance("Type Hello, world."))
    typed = [s["args"].get("text") for s in o.server.skills()
             if s["name"] == "type_text"]
    # final ASR text adds case + punctuation; partial-derived args must not win
    assert typed == ["Hello, world."], (typed, eng.args_calls)
