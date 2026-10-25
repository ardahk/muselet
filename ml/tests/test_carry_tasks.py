import asyncio
import re
import time

import pytest
from brain import carry, dsl
from brain.app_hints import match_hints, render_hints
from brain.catalog import Catalog
from brain.finish import criterion, evidence, progress_kind
from brain.orchestrator import Orchestrator
from brain.planner import Planner
from brain.tools import compose_text
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer

WEATHER = "Look up the weather in Tokyo and text it to Caleb"
SUSHI = ("Find a highly rated sushi place nearby in Maps and text the "
         "address to Caleb")
SUMMARY = "Summarize this article into a new note"
PACKING = "Make a packing list for a 3-day trip to Tokyo in Notes"


class NotesPlanner:
    def __init__(self, turns):
        self.turns = turns
        self.calls = []

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, notes=None, **kwargs):
        idx = min(len(self.calls), len(self.turns) - 1)
        self.calls.append({"goal": goal, "hint": hint, "notes": notes,
                           "last_batch": last_batch})
        for line in self.turns[idx]:
            if not cancel.is_set():
                time.sleep(0.005)
                loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": self.turns[idx], "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}


def _obs(text, app="Messages", window="New Message", focused=2):
    elements = [{"ref": int(r), "role": role, "label": label}
                for r, role, label in re.findall(
                    r'(?m)^#(\d+) (\w+) "([^"]*)"', text)]
    return {"epoch": 1, "app": app, "window": window, "focused_ref": focused,
            "elements": elements, "ax_ms": 1,
            "text": f'app: {app} | window: "{window}" | focused: #{focused}\n'
                    + text}


_DRAFT_EMPTY = '#2 textfield "Message"\n#3 button "Send"'


def _orch(tmp_path, planner, act=None, state=None, engine=None):
    state = state if state is not None else {"obs": _obs(_DRAFT_EMPTY)}
    server = FakeServer(act=act, observe=lambda: state["obs"])
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"),
                        engine=engine or FakeEngine())
    orch.agentic_apps = True
    orch.planner = planner
    orch.verify_done = False
    return orch, server


def test_carry_parse_exact_sentences():
    assert carry.parse(WEATHER) == {
        "kind": "relay", "lookup": "Look up the weather in Tokyo",
        "obj": "it", "to": "Caleb"}
    assert carry.parse(SUSHI) == {
        "kind": "relay",
        "lookup": "Find a highly rated sushi place nearby in Maps",
        "obj": "address", "to": "Caleb"}
    assert carry.parse(SUMMARY) == {"kind": "summary_note",
                                    "source": "article"}
    # packing list is a plain compose_text note (one app), not a carry task
    assert carry.parse(PACKING) is None
    assert compose_text.parse_request(PACKING)["target"] == "note"
    for text in ("text Caleb that I'll be there in ten",
                 "look up the weather in Tokyo", "send it", "find sushi"):
        assert carry.parse(text) is None


@pytest.mark.parametrize("text,kind", [
    (WEATHER, "relay"), (SUSHI, "relay"), (SUMMARY, "summary_note")])
def test_carry_finish_criterion_and_progress(text, kind):
    crit = criterion(text)
    assert crit[0] == kind
    assert progress_kind(text, None)[0] == kind
    if kind == "relay":
        assert crit[1] == "Caleb"
        assert "Messages draft to Caleb" in crit[2]
        assert "confirm" in crit[2] and "not sent" in crit[2]
    else:
        assert "new note" in crit[2]


def test_relay_evidence_needs_carried_value_and_confirm():
    notes = ["Tokyo: sunny +18°C"]
    draft = _obs('#2 textfield "Message" value="Tokyo is 18°C and sunny"')
    assert evidence("relay", "Caleb", draft, args={"notes": notes},
                    confirmed=True)
    assert not evidence("relay", "Caleb", draft, args={"notes": notes})
    wrong = _obs('#2 textfield "Message" value="Tokyo is nice today"')
    assert not evidence("relay", "Caleb", wrong, args={"notes": notes},
                        confirmed=True)
    other_app = _obs('#2 textfield "Message" value="18°C"', app="Notes")
    assert not evidence("relay", "Caleb", other_app, args={"notes": notes},
                        confirmed=True)
    addr = _obs('#2 textfield "Message" value="Sushi Kanda, 1-2-3 Ginza"')
    assert evidence("relay", "Caleb", addr, confirmed=True,
                    args={"notes": ["Sushi Kanda, 1-2-3 Ginza, Chuo City"]})


def test_summary_note_evidence_needs_notes_body():
    body = " ".join(["word"] * 20)
    ok = _obs(f'#5 textarea "Body" value="{body}"', app="Notes",
              window="Notes", focused=5)
    assert evidence("summary_note", "", ok)
    assert not evidence("summary_note", "", _obs(
        '#5 textarea "Body" value="Title"', app="Notes", window="Notes",
        focused=5))


def test_note_op_parses_and_serializes():
    actions = dsl.parse('note "Tokyo: sunny +18°C"')
    assert actions == [{"op": "note", "text": "Tokyo: sunny +18°C"}]
    assert dsl.serialize(actions) == 'note "Tokyo: sunny +18°C"'


def test_scratch_renders_in_planner_prompt():
    msg = Planner.user_message(None, WEATHER, "OBS", None,
                               notes=["Tokyo: sunny +18°C"])
    assert "Scratch" in msg and "- Tokyo: sunny +18°C" in msg
    assert msg.index("Scratch") < msg.index("OBS")
    assert "- (none yet)" in Planner.user_message(None, WEATHER, "OBS",
                                                  None, notes=[])
    assert "Scratch" not in Planner.user_message(None, WEATHER, "OBS", None)


def test_add_note_is_tiny_and_bounded():
    notes = []
    carry.add_note(notes, "x" * 1000)
    assert len(notes[0]) == carry.NOTE_MAX
    for i in range(10):
        carry.add_note(notes, f"line {i}")
    assert len(notes) == carry.NOTES_KEPT and notes[-1] == "line 9"


@pytest.mark.parametrize("text", [WEATHER, SUSHI, SUMMARY])
def test_carry_utterance_reaches_planner_as_one_task(tmp_path, text,
                                                     monkeypatch):
    engine = FakeEngine(routes={"look up the weather in tokyo":
                                ("web_search", 0.99),
                                "text it to caleb": ("send_message", 0.99)})
    orch, _server = _orch(tmp_path, NotesPlanner([['done "x"']]),
                         engine=engine)
    calls = []

    async def fake_loop(goal, trace, hint=None, finish_criterion=None, **kw):
        calls.append((goal, hint, finish_criterion, dict(orch._carry or {})))
        return "ok"

    monkeypatch.setattr(orch, "_planner_loop", fake_loop)
    asyncio.run(orch.handle_utterance(text))
    assert len(calls) == 1
    goal, hint, finish, task = calls[0]
    assert goal == text and task == carry.parse(text)
    assert finish == carry.finish(task)
    assert engine.route_calls == []           # no skill + fragment split
    if task["kind"] == "relay":
        assert "Messages" in hint and "Caleb" in hint and "never send" in hint
    else:
        assert "Notes" in hint and "summary" in hint
    assert orch._carry is None


def test_weather_relay_carries_note_into_draft_and_never_sends(tmp_path):
    state = {"obs": _obs('#7 statictext "Tokyo: ☀️ +18°C"', app="Zen",
                         window="wttr.in", focused=7)}

    def act(params):
        if params.get("op") == "type":
            state["obs"] = _obs(
                '#2 textfield "Message" value="Tokyo is +18°C and sunny"\n'
                '#3 button "Send"')
            return {"ok": True, "act_ms": 1, "epoch": 2,
                    "diff_text": '~ #2 value="Tokyo is +18°C and sunny"',
                    "observed": state["obs"]["text"]}
        if params.get("op") == "open":
            state["obs"] = _obs(_DRAFT_EMPTY)
        return {"ok": True, "act_ms": 1, "epoch": 2}

    planner = NotesPlanner([
        ['note "Tokyo: sunny +18°C"', "open Messages"],
        ['type #2 "Tokyo is +18°C and sunny"',
         'confirm "Text Caleb: Tokyo is +18°C and sunny?"', "press #3"],
    ])
    orch, server = _orch(tmp_path, planner, act=act, state=state)
    result = asyncio.run(orch.handle_utterance(WEATHER))

    assert result["outcome"] == "awaiting_user"
    assert planner.calls[0]["notes"] == []
    assert planner.calls[1]["notes"] == ["Tokyo: sunny +18°C"]
    assert server.confirms
    assert not [p for m, p in server.rpcs
                if m == "act" and p.get("op") == "press"]
    assert "Message is ready; press Send when you want" in server.said


def test_relay_refuses_send_even_without_confirm(tmp_path):
    state = {"obs": _obs('#2 textfield "Message" value="18°C in Tokyo"\n'
                         '#3 button "Send"')}
    planner = NotesPlanner([["press #3"], ['refuse "stop"']])
    orch, server = _orch(tmp_path, planner, state=state)
    asyncio.run(orch.handle_utterance(WEATHER))
    assert not [p for m, p in server.rpcs
                if m == "act" and p.get("op") == "press"]
    assert "draft only" in " ".join(planner.calls[1]["last_batch"] or [])


@pytest.mark.parametrize("text,want", [
    (WEATHER, ["weather_stocks", "messages"]),
    (SUSHI, ["apple_maps", "messages"]),
])
def test_carry_app_hints(text, want):
    task = carry.parse(text)
    ids = [h.id for h in match_hints(text, route_hint=carry.hint(task), k=3)]
    for hid in want:
        assert hid in ids
    assert "notes" not in ids
    rendered = render_hints(match_hints(text, route_hint=carry.hint(task),
                                        k=3))
    assert 'note "' in rendered
