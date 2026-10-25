import asyncio
import json
import time

import pytest

from brain.agentic import hint
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


class FakePlanner:
    def __init__(self, turns):
        self.turns = turns
        self.user_msgs = []

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, **kwargs):
        idx = min(len(self.user_msgs), len(self.turns) - 1)
        self.user_msgs.append({
            "goal": goal, "observation": observation,
            "last_batch": last_batch, "hint": hint})
        for line in self.turns[idx]:
            if not cancel.is_set():
                time.sleep(0.005)
                loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": self.turns[idx], "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("skill,args,want", [
    ("start_timer", {"duration": "10 minutes", "label": "tea"},
     "use the Clock app's Timers tab; duration 10 minutes; label tea"),
    ("create_event", {
        "title": "Lunch", "start": "tomorrow", "end": "later",
        "location": "Cafe"},
     "use the Calendar app; new event titled Lunch; starts tomorrow; "
     "end later; location Cafe"),
    ("create_reminder", {"title": "Call Sam", "due": "tomorrow"},
     "use the Reminders app; reminder Call Sam; due tomorrow"),
    ("new_note", {"title": "List", "body": "milk", "ms": 4, "_raw": "x"},
     "use the Notes app; new note titled List; text: milk"),
    ("compose_text", {"topic": "packing", "target": "Notes"},
     "use the Notes app (or Notes); write a new note about packing"),
    ("play_music", {"query": "jazz"},
     "use the Music app; play jazz"),
    ("todays_agenda", {}, "use the Calendar app; read today's events back to the user"),
    ("send_message", {"to": "Caleb", "body": "hi"},
     "use the Messages app; recipient Caleb; message: hi; "
     "ask to confirm before sending"),
    ("compose_email", {"to": "Sam", "subject": "Hi", "body": "Hello"},
     "use the Mail app; to Sam; subject Hi; body: Hello; "
     "leave it as a draft, don't send"),
    ("draft_email", {"to": "Sam", "about": "schedule"},
     "the email is open in the browser/Mail; write a draft reply to Sam "
     "about schedule in the reply box; don't send"),
    ("premiere_command", {"command": "play_toggle", "ms": 2},
     "use Adobe Premiere Pro; command play_toggle"),
])
def test_agentic_hints(skill, args, want):
    assert hint(skill, args) == want


_MESSAGE_OBS = {
    "epoch": 1, "app": "Messages", "window": "New Message",
    "focused_ref": 2,
    "elements": [
        {"ref": 2, "role": "textfield", "label": "Message"},
        {"ref": 3, "role": "button", "label": "Send"},
    ],
    "text": ('app: Messages | window: "New Message" | focused: #2\n'
             '#2 textfield "Message"\n#3 button "Send"'),
    "ax_ms": 1,
}


@pytest.mark.parametrize("action", [
    'type #2 "I\'ll be there in ten" enter',
    "press #3",
])
def test_agentic_message_confirmation_names_recipient_and_blocks_send(
        tmp_path, action):
    goal = "text Caleb that I'll be there in ten"
    planner = FakePlanner([[action], ['done "message drafted"']])
    server = FakeServer(observe=lambda: _MESSAGE_OBS)
    server.confirm_yes = False
    tracer = Tracer(tmp_path / "traces")
    orch = Orchestrator(server, Catalog.load(), tracer,
                        engine=FakeEngine())
    orch.agentic_apps = True
    orch.planner = planner
    orch.verify_done = False

    _run(orch.handle_utterance(goal))

    assert planner.user_msgs[0]["hint"] and \
        "Messages" in planner.user_msgs[0]["hint"] and \
        "Caleb" in planner.user_msgs[0]["hint"]
    assert server.confirms and all("Caleb" in summary
                                  for summary in server.confirms)
    assert not [params for method, params in server.rpcs
                if method == "act"]
    trace_path = next((tmp_path / "traces").glob("*.jsonl"))
    trace = json.loads(trace_path.read_text().splitlines()[-1])
    assert trace["agentic_app"] == {
        "skill": "send_message",
        "args": {"to": "Caleb", "body": "I'll be there in ten"},
    }


@pytest.mark.parametrize("skill,text,args", [
    ("start_timer", "set a timer", {"duration": "10 minutes"}),
    ("new_note", "write a note", {"title": "Groceries", "body": "milk"}),
    ("play_music", "play jazz", {"query": "jazz"}),
])
@pytest.mark.parametrize("enabled", [True, False])
def test_top_skill_routes_to_planner_only_when_enabled(
        tmp_path, skill, text, args, enabled):
    engine = FakeEngine(
        routes={text: (skill, 0.99)},
        argmap={(skill, text): args})
    server = FakeServer()
    planner = FakePlanner([['done "finished"']])
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"),
                        engine=engine)
    orch.agentic_apps = enabled
    orch.planner = planner
    orch.verify_done = False

    result = _run(orch._engine_route(text, {"decisions": []}))

    assert result == "ok"
    if enabled:
        assert planner.user_msgs
        assert not server.skills()
    else:
        assert not planner.user_msgs
        assert [call["name"] for call in server.skills()] == [skill]


def test_disabled_app_skill_replans_without_strike_or_recovery(tmp_path):
    planner = FakePlanner([
        ['skill start_timer duration="10 minutes"'],
        ["press #1"],
        ['done "finished"'],
    ])
    server = FakeServer()
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"))
    orch.agentic_apps = True
    orch.planner = planner

    result = _run(orch._planner_loop(
        "start a timer", {"decisions": []}))

    assert result == "ok"
    assert len(planner.user_msgs) >= 3
    failed_batch = planner.user_msgs[1]["last_batch"]
    assert any("skill disabled: operate the app's UI" in line
               for line in failed_batch)
    assert not [call for call in server.skills()
                if call["name"] == "start_timer"]
    assert orch._recover_round == 0


def test_agentic_message_is_not_used_for_longterm_memory(
        tmp_path, monkeypatch):
    from brain.memory import policy

    goal = "text Caleb that I'll be there in ten"
    planner = FakePlanner([["press #1"], ['done "finished"']])
    server = FakeServer(observe=lambda: _MESSAGE_OBS)
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"),
                        engine=FakeEngine())
    orch.agentic_apps = True
    orch.planner = planner
    orch.verify_done = False
    seen = []
    monkeypatch.setattr(
        policy, "extract_writes",
        lambda text, **kwargs: seen.append(text) or [])
    orch._persist_memory_writes = lambda writes: None

    _run(orch.handle_utterance(goal))

    assert seen == [""]


def test_agentic_message_auto_done_waits_before_sending(tmp_path):
    state = dict(_MESSAGE_OBS)

    def act(params):
        if params.get("op") == "type":
            state["text"] = (
                'app: Messages | window: "New Message" | focused: #2\n'
                '#2 textfield "Message" value="hi there caleb"\n'
                '#3 button "Send"')
            return {
                "ok": True, "act_ms": 1, "epoch": 2,
                "diff_text": '~ #2 value="hi there caleb"',
                "observed": state["text"],
            }
        return {"ok": True, "act_ms": 1, "epoch": 2}

    planner = FakePlanner([[
        'type #2 "hi there caleb"',
        'confirm "Text Caleb: hi there caleb?"',
        "press #3",
    ]])
    server = FakeServer(act=act, observe=lambda: state)
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"),
                        engine=FakeEngine())
    orch.agentic_apps = True
    orch.planner = planner
    trace = {"decisions": []}

    result = _run(orch._agentic_route(
        "send_message", {"to": "Caleb", "body": "hi there caleb"},
        "text Caleb that hi there caleb", trace))

    assert result == "awaiting_user"
    assert not [params for method, params in server.rpcs
                if method == "act" and params.get("op") == "press"]
    auto_done = [d for d in trace["decisions"] if "auto_done" in d]
    assert auto_done == [{
        "auto_done": "confirm summary=Text Caleb: hi there caleb?",
        "turn": 0,
        "kind": "message",
    }]
    assert server.said == ["Message is ready; press Send when you want"]
