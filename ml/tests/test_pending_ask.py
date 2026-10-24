import asyncio
import time

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


def make_orch(tmp_path, engine=None):
    orch = Orchestrator(FakeServer(), Catalog.load(), Tracer(tmp_path / "traces"),
                        engine=engine)
    orch._pending_task = {"goal": "move it", "t": time.time()}
    orch._answer_history = ["earlier answer"]
    resumed = []

    async def plan(goal, trace, answer=None):
        resumed.append((goal, answer))
        return "resumed"

    orch._planner_loop = plan
    return orch, resumed


@pytest.mark.parametrize("text,skill", [
    ("set the volume to 50", "set_volume"),
    ("set the volume to thirty percent", "set_volume"),
    ("open Safari", "open_app"),
    ("launch Notes", "open_app"),
    ("open my downloads", "open_folder"),
    ("turn on dark mode", "dark_mode"),
    ("unmute", "mute"),
    ("search for weather tomorrow", "web_search"),
    ("take a screenshot", "take_screenshot"),
])
@pytest.mark.parametrize("use_engine", [False, True])
def test_brain12_new_command_cancels_pending_ask(tmp_path, text, skill, use_engine):
    engine = FakeEngine(default=("ANSWER", 0.95)) if use_engine else None
    orch, resumed = make_orch(tmp_path, engine)
    routed = []
    if use_engine:
        async def route(text, trace):
            routed.append(text)
            return "routed"
        orch._engine_route = route

    result = asyncio.run(orch.handle_utterance(text))

    assert resumed == []
    assert orch._pending_task is None
    assert orch._answer_history == []
    if use_engine:
        assert result["outcome"] == "routed"
        assert routed == [text]
    else:
        assert result["outcome"] == "ok"
        assert orch.server.skills()[0]["name"] == skill


@pytest.mark.parametrize("text", [
    "yes", "no", "the first one", "second", "Safari", "John Smith",
    "report.pdf", "Open Safari.txt", "~/Documents", "/Users/alex/Notes",
    '"open Safari"', "the blue one", "Volume 50", "a screenshot",
    "the search results", "maybe use the other folder", "50", "continue", "",
])
@pytest.mark.parametrize("use_engine", [False, True])
def test_brain12_answers_and_ambiguous_replies_resume(tmp_path, text, use_engine):
    engine = FakeEngine(default=("open_app", 0.99)) if use_engine else None
    orch, resumed = make_orch(tmp_path, engine)

    result = asyncio.run(orch.handle_utterance(text))

    assert result["outcome"] == "resumed"
    assert resumed == [("move it", text)]
    assert orch._answer_history == ["earlier answer", text]
    assert orch.server.methods() == []
    if engine:
        assert engine.route_calls == []


def test_brain12_unknown_command_remains_an_answer(tmp_path):
    orch, resumed = make_orch(tmp_path)
    asyncio.run(orch.handle_utterance("set it to the other one"))
    assert resumed == [("move it", "set it to the other one")]
