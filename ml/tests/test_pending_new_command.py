import asyncio
import copy
import time

import pytest

from brain import comms
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.server import BrainServer
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


def run(coro):
    return asyncio.run(coro)


class CapturingTracer(Tracer):
    def finish(self, outcome):
        self.last = copy.deepcopy(self.current)
        super().finish(outcome)


def make_orch(tmp_path, engine=None, server=None):
    return Orchestrator(
        server or FakeServer(), Catalog.load(),
        CapturingTracer(tmp_path / "traces"), engine=engine)


def pending_orch(tmp_path, engine=None, server=None):
    orch = make_orch(tmp_path, engine=engine, server=server)
    goal = "Open notes and write a template about my day"
    orch._pending_task = {"goal": goal, "t": time.time()}
    resumed = []

    async def plan(goal, trace, answer=None):
        resumed.append((goal, answer))
        return "resumed"

    orch._planner_loop = plan
    return orch, goal, resumed


@pytest.mark.parametrize("use_engine", [False, True])
def test_message_supersedes_pending_planner_task(
        tmp_path, monkeypatch, use_engine):
    engine = FakeEngine(default=("ANSWER", 0.99)) if use_engine else None
    orch, goal, resumed = pending_orch(tmp_path, engine=engine)
    started = []

    async def start(_orch, message, text):
        started.append((message, text))
        return "message"

    monkeypatch.setattr(comms, "start", start)
    text = "Text Caleb that I'll be there in ten"

    result = run(orch.handle_utterance(text))

    assert result["outcome"] == "message"
    assert resumed == []
    assert started and started[0][1] == text
    assert orch._pending_task is None
    pending = next(
        decision["pending_superseded"]
        for decision in orch.tracer.last["decisions"]
        if "pending_superseded" in decision)
    assert pending == {
        "kinds": ["pending_task"], "by": "message", "goal": goal}


@pytest.mark.parametrize("text,ctx,expected", [
    ("draft an email to Caleb about tomorrow", {"app": "Mail"},
     "draft_email"),
    ("calculate 4 plus 5", None, "calculator"),
    ("go to YouTube", None, "site"),
    ("open Notes and play music", None, "compound"),
    ("open Safari", None, "route:open_app"),
])
def test_new_command_classifies_explicit_request_types(
        tmp_path, text, ctx, expected):
    orch = make_orch(tmp_path)

    assert run(orch._new_command(text, ctx)) == expected


@pytest.mark.parametrize("default", [
    ("open_app", 0.99), ("send_message", 0.99),
])
@pytest.mark.parametrize("text", [
    "yes", "no", "the second one", "Caleb Kawano", "Caleb", "50", "ten",
    "continue", "send it to the work one", "Volume 50",
])
def test_answers_resume_pending_task_without_routing(tmp_path, default, text):
    engine = FakeEngine(default=default)
    orch, goal, resumed = pending_orch(tmp_path, engine=engine)

    result = run(orch.handle_utterance(text))

    assert result["outcome"] == "resumed"
    assert resumed == [(goal, text)]
    assert engine.route_calls == []


def test_confident_router_command_reuses_route_for_normal_path(tmp_path):
    text = "play some music"
    engine = FakeEngine(
        routes={text: ("play_music", 0.9)},
        argmap={("play_music", text): {"query": "music"}})
    orch, _, resumed = pending_orch(tmp_path, engine=engine)

    result = run(orch.handle_utterance(text))

    assert result["outcome"] == "ok"
    assert resumed == []
    assert engine.route_calls == [text]
    assert orch._pending_task is None
    assert any(
        decision.get("pending_superseded", {}).get("by") == "router:play_music"
        for decision in orch.tracer.last["decisions"])


@pytest.mark.parametrize("label,p_top", [
    ("change_volume", 0.3), ("ASK", 0.99), ("ANSWER", 0.99),
])
def test_low_confidence_ask_and_answer_routes_resume_pending(
        tmp_path, label, p_top):
    text = "turn the volume up"
    engine = FakeEngine(routes={text: (label, p_top)})
    orch, goal, resumed = pending_orch(tmp_path, engine=engine)

    result = run(orch.handle_utterance(text))

    assert result["outcome"] == "resumed"
    assert resumed == [(goal, text)]
    assert engine.route_calls == [text]
    assert orch._pending_task is None


@pytest.mark.parametrize("text,expected", [
    ("Text Caleb that I'll be there in ten", "message"),
    ("10 minutes", "slot"),
])
def test_duration_slot_only_superseded_by_new_command(
        tmp_path, monkeypatch, text, expected):
    orch = make_orch(tmp_path)
    orch._slot = {
        "skill": "start_timer", "args": {}, "missing": ["duration"],
        "t": time.time(), "utterance": "start a timer",
    }
    started = []

    async def start(_orch, message, utterance):
        started.append((message, utterance))
        return "message"

    monkeypatch.setattr(comms, "start", start)
    result = run(orch.handle_utterance(text))

    if expected == "message":
        assert result["outcome"] == "message"
        assert started and started[0][1] == text
        assert orch._slot is None
        assert any(
            decision.get("pending_superseded", {}).get("kinds") == ["slot"]
            for decision in orch.tracer.last["decisions"])
    else:
        assert result["outcome"] == "ok"
        assert started == []
        assert orch._slot is None
        skill = next(params for method, params in orch.server.rpcs
                     if method == "skill")
        assert skill["name"] == "start_timer"
        assert skill["args"]["duration"] == 600


def contact(name, value, label="mobile"):
    return {
        "id": name, "name": name,
        "handles": [{"kind": "phone", "value": value, "label": label}],
    }


def make_comms_orch(tmp_path):
    matches = [
        contact("Arda Hoke", "+15550005551"),
        contact("Arda Smith", "+15550005552", "home"),
    ]
    server = FakeServer(handlers={
        "messages_people": lambda _: {"people": []},
        "contacts_search": lambda _: {"matches": matches},
        "messages_compose": lambda _: {
            "ok": True, "frontmost": True, "body_visible": True},
        "messages_send": lambda _: {"ok": True, "sent": True},
    })
    return make_orch(tmp_path, server=server)


def test_choose_pending_superseded_by_router_command(tmp_path):
    text = "turn the volume up"
    engine = FakeEngine(
        routes={text: ("change_volume", 0.95)},
        argmap={("change_volume", text): {"delta": 10}})
    orch = make_comms_orch(tmp_path)
    orch.engine = engine
    assert run(comms.send_message(orch, "Arda", "hi")) == "awaiting_user"

    result = run(orch.handle_utterance(text))

    assert result["outcome"] == "ok"
    assert orch._comms is None
    assert engine.route_calls == [text]
    assert any(
        decision.get("pending_superseded", {}).get("kinds") == ["comms"]
        for decision in orch.tracer.last["decisions"])
    assert any(params.get("name") == "change_volume"
               for params in orch.server.skills())


def test_second_choice_answer_still_selects_second_contact(tmp_path):
    orch = make_comms_orch(tmp_path)
    assert run(comms.send_message(orch, "Arda", "hi")) == "awaiting_user"

    result = run(orch.handle_utterance("the second one"))

    assert result["outcome"] == "ok"
    assert orch._comms is None
    composed = next(params for method, params in orch.server.rpcs
                    if method == "messages_compose")
    assert composed["handle"] == "+15550005552"


def test_server_accepts_only_recognized_confirm_interrupt():
    async def scenario():
        server = BrainServer()
        frames = []
        confirm_seen = asyncio.Event()
        cancel_seen = asyncio.Event()
        new_seen = asyncio.Event()
        said = []

        async def send(frame):
            frames.append(frame)
            if frame["t"] == "confirm":
                confirm_seen.set()
            elif frame["t"] == "confirm_cancel":
                cancel_seen.set()

        async def utterance(text, final, ctx):
            if text == "pending":
                await server.ask_confirm("Send?")
                said.append("SENT")
            else:
                new_seen.set()

        async def interrupt(text, ctx):
            return text == "turn the volume up"

        server.send = send
        server.on_utterance = utterance
        server.on_confirm_interrupt = interrupt
        server._start_utterance("pending")
        await confirm_seen.wait()
        confirm_id = next(frame["id"] for frame in frames
                          if frame["t"] == "confirm")

        server._start_utterance("turn the volume up")
        await new_seen.wait()
        await cancel_seen.wait()
        await server._utterance_task

        assert {"t": "confirm_cancel", "id": confirm_id} in frames
        assert "SENT" not in said
        assert [frame["t"] for frame in frames].count("confirm") == 1

    run(scenario())


def test_server_ignores_unrecognized_utterance_during_confirm():
    async def scenario():
        server = BrainServer()
        frames = []
        confirm_seen = asyncio.Event()
        checked = asyncio.Event()
        said = []

        async def send(frame):
            frames.append(frame)
            if frame["t"] == "confirm":
                confirm_seen.set()

        async def utterance(text, final, ctx):
            await server.ask_confirm("Send?")
            said.append("SENT")

        async def interrupt(text, ctx):
            checked.set()
            return False

        server.send = send
        server.on_utterance = utterance
        server.on_confirm_interrupt = interrupt
        server._start_utterance("pending")
        await confirm_seen.wait()
        confirm_id = next(frame["id"] for frame in frames
                          if frame["t"] == "confirm")
        task = server._utterance_task

        server._start_utterance("uh what")
        await checked.wait()

        assert not task.done()
        assert confirm_id in server._confirms
        assert not server._confirms[confirm_id].done()
        assert not any(frame["t"] == "confirm_cancel" for frame in frames)
        server._confirms[confirm_id].set_result(True)
        await task
        assert said == ["SENT"]

    run(scenario())


def test_confirm_interrupt_cancels_message_before_send(tmp_path):
    async def scenario():
        server = BrainServer()
        frames = []
        rpc_calls = []
        confirm_seen = asyncio.Event()
        cancel_seen = asyncio.Event()
        skill_seen = asyncio.Event()
        text = "turn the volume up"
        engine = FakeEngine(
            routes={text: ("change_volume", 0.95)},
            argmap={("change_volume", text): {"delta": 10}})
        orch = make_orch(tmp_path, engine=engine, server=server)

        async def send(frame):
            frames.append(frame)
            if frame["t"] == "confirm":
                confirm_seen.set()
            elif frame["t"] == "confirm_cancel":
                cancel_seen.set()

        async def rpc(method, params, timeout=30):
            rpc_calls.append((method, params))
            if method == "messages_people":
                return {"people": [contact("Caleb", "+15551234567")]}
            if method == "messages_compose":
                return {"ok": True, "frontmost": True,
                        "body_visible": True}
            if method == "skill":
                skill_seen.set()
                return {"ok": True, "act_ms": 1}
            if method == "messages_send":
                return {"ok": True, "sent": True}
            return {"ok": True}

        async def utterance(utterance_text, final, ctx):
            await orch.handle_utterance(utterance_text, ctx)

        server.send = send
        server.rpc = rpc
        server.on_utterance = utterance
        server.on_confirm_interrupt = orch.confirm_interrupt
        server._start_utterance(
            "Text Caleb that I'll be there in ten")
        await confirm_seen.wait()

        server._start_utterance(text)
        await cancel_seen.wait()
        await skill_seen.wait()
        await server._utterance_task

        assert "messages_send" not in [method for method, _ in rpc_calls]
        assert not any(frame.get("text") == "Left it as a draft"
                       for frame in frames)
        assert any(
            decision.get("confirm_superseded") == "router:change_volume"
            for decision in orch.tracer.last["decisions"])
        assert any(frame["t"] == "confirm_cancel" for frame in frames)

    run(scenario())
