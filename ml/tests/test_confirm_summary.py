"""Confirm summaries name the object and stay <= 12 words (task 6)."""

import asyncio

import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer


@pytest.fixture
def orch(tmp_path):
    o = Orchestrator(FakeServer(), Catalog.load(), Tracer(tmp_path / "t"))
    o._last_obs = {"app": "Messages", "elements": [
        {"ref": 3, "label": "Send"}, {"ref": 5, "label": "Delete conversation"}]}
    return o


def summ(o, a):
    return asyncio.run(o._confirm_summary(a))


@pytest.mark.parametrize("a,want", [
    ({"op": "skill", "name": "send_message",
      "args": {"to": "Mom", "body": "running ten minutes late, start without me"}},
     'Text Mom: "running ten minutes late, start without me"?'),
    ({"op": "skill", "name": "compose_email",
      "args": {"to": "Sam Lee", "body": "Here are the Q3 numbers"}},
     'Email Sam Lee: "Here are the Q3 numbers"?'),
    ({"op": "skill", "name": "move_to_trash",
      "args": {"path": "/Users/a/Downloads/report final.pdf"}},
     "Move /Users/a/Downloads/report final.pdf to Trash?"),
    ({"op": "skill", "name": "quit_app", "args": {"app": "Keynote"}},
     "Quit Keynote?"),
    ({"op": "skill", "name": "empty_trash", "args": {}},
     "Empty the Trash permanently?"),
    ({"op": "press", "ref": 5}, 'Press "Delete conversation" in Messages?'),
    ({"op": "keys", "combo": "cmd+return"}, "Press cmd+return in Messages?"),
    ({"op": "type", "ref": 3, "text": "see you at 8", "enter": True},
     'Type "see you at 8" and send in Messages?'),
    ({"op": "script", "lang": "applescript",
      "code": 'tell application "Finder" to delete file "x"'},
     "Run AppleScript on Finder?"),
    ({"op": "script", "lang": "shell", "code": "rm -rf ~/tmp/build"},
     'Run shell command "rm -rf ~/tmp/build"?'),
])
def test_summary_names_object(orch, a, want):
    assert summ(orch, a) == want


@pytest.mark.parametrize("a", [
    {"op": "skill", "name": "send_message", "args": {
        "to": "Mom", "body": " ".join(f"w{i}" for i in range(40))}},
    {"op": "skill", "name": "send_message", "args": {
        "to": "Dr Anne Marie Jones Smith of the Clinic", "body": "hi there you"}},
    {"op": "skill", "name": "compose_email", "args": {
        "to": "x@y.com", "body": "a b c d e f g h i j k l m n o p"}},
    {"op": "type", "text": "one two three four five six seven eight nine",
     "enter": True},
    {"op": "confirm", "summary": " ".join(["word"] * 30)},
    {"op": "skill", "name": "move_to_trash", "args": {
        "path": "/a/" + " ".join(["long"] * 20) + ".txt"}},
    {"op": "skill", "name": "open_url", "args": {"url": "https://x.com"}},
])
def test_summary_at_most_12_words(orch, a):
    s = summ(orch, a)
    assert len(s.split()) <= 12 and s.endswith("?"), s


def test_long_body_shows_first_words(orch):
    s = summ(orch, {"op": "skill", "name": "send_message", "args": {
        "to": "Mom", "body": "I will be home around nine tonight because the "
                             "train is delayed again"}})
    assert s.startswith('Text Mom: "I will be home around nine tonight')
    assert s.endswith('…"?') and len(s.split()) <= 12


def test_skill_confirm_uses_object_summary(orch):
    asyncio.run(orch.execute_actions([{"op": "skill", "name": "compose_email",
                                       "args": {"to": "Mom", "body": "hi"}}]))
    assert orch.server.confirms == ['Email Mom: "hi"?']


def test_trash_confirm_names_file(orch):
    asyncio.run(orch.execute_actions([{"op": "skill", "name": "move_to_trash",
                                       "args": {"path": "~/Desktop/old.key"}}]))
    assert orch.server.confirms == ["Move ~/Desktop/old.key to Trash?"]


def test_script_confirm_names_app(orch):
    asyncio.run(orch.execute_actions([{
        "op": "script", "lang": "applescript",
        "code": 'tell application "Mail" to send'}]))
    assert orch.server.confirms == ["Run AppleScript on Mail?"]
