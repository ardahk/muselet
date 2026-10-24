"""Missing required args: fallback table, then slot filling (task 1)."""

import asyncio
import json

import pytest

from brain import slots
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer

from fakes import FakeEngine, FakeServer


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tracer(tmp_path):
    return Tracer(tmp_path / "traces")


def _orch(tracer, engine=None, server=None):
    return Orchestrator(server or FakeServer(), Catalog.load(), tracer,
                        engine=engine)


def _traces(tracer):
    return [json.loads(ln) for f in tracer.dir.glob("*.jsonl")
            for ln in f.read_text().splitlines()]


# ---------- fallback table ----------

def test_note_body_from_title():
    a = slots.fill_defaults("new_note", {"title": "buy milk"},
                            "make a new note that says buy milk")
    assert a == {"title": "buy milk", "body": "buy milk"}


def test_note_title_is_first_six_words_of_body():
    a = slots.fill_defaults(
        "new_note", {"title": "pick up the kids from school at five today"}, "")
    assert a["body"] == "pick up the kids from school at five today"
    assert a["title"] == "pick up the kids from school"


def test_note_body_from_utterance_when_no_args():
    a = slots.fill_defaults("new_note", {}, "make a note that says call the bank")
    assert a["body"] == "call the bank" and a["title"] == "call the bank"


def test_note_without_any_content_stays_missing():
    assert "body" not in slots.fill_defaults("new_note", {}, "make a new note")


def test_note_with_body_untouched():
    a = {"title": "Groceries", "body": "eggs and milk"}
    assert slots.fill_defaults("new_note", a, "x") == a


@pytest.mark.parametrize("utt,args,title", [
    ("remind me to call mom tomorrow at 5pm", {"due": "tomorrow at 5pm"},
     "call mom"),
    ("remind me tomorrow at 9 to water the plants", {"due": "tomorrow at 9"},
     "water the plants"),
    ("remind me to pay rent on friday", {}, "pay rent"),
    ("create a reminder to stretch in 20 minutes", {}, "stretch"),
    ("don't let me forget to email Sam tonight", {}, "email Sam"),
])
def test_reminder_title_from_utterance(utt, args, title):
    out = slots.fill_defaults("create_reminder", args, utt)
    assert out["title"] == title


@pytest.mark.parametrize("utt,args,title", [
    ("schedule dentist appointment tomorrow at 3pm",
     {"start": "tomorrow at 3pm"}, "dentist appointment"),
    ("add an event called team lunch on friday at noon", {}, "team lunch"),
    ("create an event for project review next monday at 10am",
     {"start": "next monday at 10am"}, "project review"),
])
def test_event_title_from_utterance(utt, args, title):
    assert slots.fill_defaults("create_event", args, utt)["title"] == title


def test_reminder_title_kept_when_present():
    a = {"title": "Call mom", "due": "tomorrow"}
    assert slots.fill_defaults("create_reminder", a, "remind me tomorrow") == a


def test_reminder_only_datetime_leaves_title_missing():
    assert "title" not in slots.fill_defaults(
        "create_reminder", {"due": "tomorrow at 5"}, "remind me tomorrow at 5")


def test_other_skills_never_guessed():
    assert slots.fill_defaults("send_message", {"to": "Mom"},
                               "text mom") == {"to": "Mom"}


@pytest.mark.parametrize("skill,arg,typ,q", [
    ("new_note", "body", "string", "What should the note say?"),
    ("send_message", "to", "contact", "Who should I text?"),
    ("create_event", "start", "datetime", "When?"),
    ("start_timer", "duration", "duration", "For how long?"),
    ("open_app", "app", "app", "Which app?"),
])
def test_questions_are_natural_and_short(skill, arg, typ, q):
    assert slots.question(skill, arg, typ) == q


def test_every_required_arg_has_short_question():
    cat = Catalog.load()
    for name, spec in cat.skills.items():
        for a in spec.get("args", []):
            if a.get("required"):
                q = slots.question(name, a["name"], a.get("type"))
                assert len(q.split()) <= 12 and q.endswith("?"), (name, q)


@pytest.mark.parametrize("text,typ,want", [
    ("it should say buy milk", "string", "buy milk"),
    ("Um, to Mom.", "contact", "Mom"),
    ("at 5 pm tomorrow", "datetime", "5 pm tomorrow"),
    ("to the store and back", "string", "to the store and back"),
])
def test_clean_answer(text, typ, want):
    assert slots.clean_answer(text, typ) == want


# ---------- orchestrator ----------

def test_live_failure_note_with_title_only(tracer):
    """'make a new note that says buy milk' -> ARGS gave only title."""
    eng = FakeEngine({"make a new note that says buy milk": ("new_note", 0.97)},
                     {("new_note", "make a new note that says buy milk"):
                      {"title": "buy milk"}})
    o = _orch(tracer, eng)
    assert run(o.handle_utterance("make a new note that says buy milk")) == \
        {"outcome": "ok"}
    assert o.server.skills() == [{"name": "new_note", "args": {
        "title": "buy milk", "body": "buy milk"}}]


def test_reminder_title_filled_then_executes(tracer):
    utt = "remind me to call mom tomorrow at 5pm"
    eng = FakeEngine({utt: ("create_reminder", 0.95)},
                     {("create_reminder", utt): {"due": "tomorrow at 5pm"}})
    o = _orch(tracer, eng)
    run(o.handle_utterance(utt))
    (call,) = o.server.skills()
    assert call["args"]["title"] == "call mom" and call["args"]["due"]


def test_slot_fill_asks_then_executes(tracer):
    eng = FakeEngine({"text mom": ("send_message", 0.95),
                      "i'm running late": ("ANSWER", 0.5)},
                     {("send_message", "text mom"): {"to": "Mom"}})
    o = _orch(tracer, eng)
    assert run(o.handle_utterance("text mom"))["outcome"] == "awaiting_user"
    assert o.server.said[-1] == "What should the message say?"
    assert o._slot["missing"] == ["body"] and not o.server.skills()
    assert run(o.handle_utterance("I'm running late"))["outcome"] == "ok"
    assert o.server.skills() == [{"name": "send_message", "args": {
        "to": "Mom", "body": "I'm running late", "confirmed": True}}]
    assert o.server.confirms == ['Text Mom: "I\'m running late"?']
    assert o._slot is None
    tr = _traces(tracer)
    assert [t.get("slot_fill") for t in tr] == [True, True]
    assert tr[0]["outcome"] == "awaiting_user"


def test_slot_fill_two_args_in_turn(tracer):
    eng = FakeEngine({"send a text": ("send_message", 0.95)}, {})
    o = _orch(tracer, eng)
    run(o.handle_utterance("send a text"))
    assert o.server.said[-1] == "Who should I text?"
    run(o.handle_utterance("to Dad"))
    assert o.server.said[-1] == "What should the message say?"
    run(o.handle_utterance("dinner at seven"))
    assert o.server.skills()[0]["args"]["to"] == "Dad"
    assert o.server.skills()[0]["args"]["body"] == "dinner at seven"


def test_slot_value_coerced_by_type(tracer):
    eng = FakeEngine({"set a timer": ("start_timer", 0.95)}, {})
    o = _orch(tracer, eng)
    run(o.handle_utterance("set a timer"))
    assert o.server.said[-1] == "For how long?"
    run(o.handle_utterance("ten minutes"))
    # parsed to seconds by code; catalog.validate_args stringifies durations
    assert o.server.skills() == [{"name": "start_timer",
                                  "args": {"duration": "600"}}]


def test_slot_invalid_value_reasks_then_gives_up(tracer):
    eng = FakeEngine({"set a timer": ("start_timer", 0.95)}, {})
    o = _orch(tracer, eng)
    run(o.handle_utterance("set a timer"))
    assert run(o.handle_utterance("banana"))["outcome"] == "awaiting_user"
    assert o.server.said[-1] == "For how long?"
    assert run(o.handle_utterance("banana"))["outcome"] == "failed"
    assert o._slot is None and not o.server.skills()


def test_confident_other_command_cancels_slot(tracer):
    eng = FakeEngine({"text mom": ("send_message", 0.95),
                      "mute": ("mute", 0.93)},
                     {("send_message", "text mom"): {"to": "Mom"},
                      ("mute", "mute"): {"on": "true"}})
    o = _orch(tracer, eng)
    run(o.handle_utterance("text mom"))
    run(o.handle_utterance("mute"))
    assert o._slot is None
    assert o.server.skills() == [{"name": "mute", "args": {"on": True}}]


def test_unconfident_other_skill_is_still_the_value(tracer):
    eng = FakeEngine({"make a note": ("new_note", 0.95),
                      "open the garage at noon": ("open_app", 0.6)}, {})
    o = _orch(tracer, eng)
    run(o.handle_utterance("make a note"))
    run(o.handle_utterance("open the garage at noon"))
    assert o.server.skills()[0]["args"]["body"] == "open the garage at noon"


def test_cancel_word_drops_slot(tracer):
    eng = FakeEngine({"make a note": ("new_note", 0.95)}, {})
    o = _orch(tracer, eng)
    run(o.handle_utterance("make a note"))
    assert run(o.handle_utterance("never mind"))["outcome"] == "cancelled"
    assert o._slot is None and not o.server.skills()


def test_slot_expires_after_60s(tracer):
    eng = FakeEngine({"make a note": ("new_note", 0.95),
                      "buy milk": ("ANSWER", 0.9)}, {})
    o = _orch(tracer, eng)
    run(o.handle_utterance("make a note"))
    o._slot["t"] -= 61
    run(o.handle_utterance("buy milk"))
    assert o._slot is None and not o.server.skills()


def test_slot_fill_regex_path(tracer):
    """no engine: execute_actions -> _skill also slot-fills."""
    o = _orch(tracer)
    out = run(o.execute_actions([{"op": "skill", "name": "send_message",
                                  "args": {"to": "Mom"}}]))
    assert out == "awaiting_user" and o._slot["missing"] == ["body"]
    run(o.handle_utterance("see you soon"))
    assert o.server.skills()[0]["args"]["body"] == "see you soon"
