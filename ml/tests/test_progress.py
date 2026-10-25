"""Planner progress phrases for the mascot bubble (ui-progress)."""

import asyncio

from brain.progress import MAX_WORDS, site_name, step_phrase

ELS = [
    {"ref": 12, "role": "textfield", "label": "Search"},
    {"ref": 40, "role": "link", "label": "Jazz Classics... Relaxing Jazz Piano"},
    {"ref": 41, "role": "link", "label": "Lo-fi Beats - 24/7 Radio"},
    {"ref": 7, "role": "securetextfield", "label": "Wi-Fi"},
    {"ref": 8, "role": "textfield", "label": "Password"},
    {"ref": 9, "role": "textarea", "label": "Message body"},
    {"ref": 3, "role": "button", "label": ""},
]


def test_examples_from_brief():
    assert step_phrase({"op": "type", "ref": 12, "text": "jazz", "enter": True},
                       ELS) == "Typing jazz"
    assert step_phrase({"op": "press", "ref": 40}, ELS) == "Clicking Jazz Classics"
    assert step_phrase({"op": "url", "url": "https://www.youtube.com/results?q=x"},
                       ELS) == "Opening YouTube"
    assert step_phrase({"op": "open", "name": "Maps"}, ELS) == "Opening Maps"
    assert step_phrase({"op": "script", "lang": "jxa",
                        "code": "document.querySelector('video').paused"},
                       ELS) == "Checking playback"


def test_labels_are_trimmed_at_separators():
    assert step_phrase({"op": "press", "ref": 41}, ELS) == "Clicking Lo-fi Beats"
    assert step_phrase({"op": "press", "ref": 3}, ELS) == "Clicking"
    assert step_phrase({"op": "press", "ref": 999}, ELS) == "Clicking"
    assert step_phrase({"op": "press", "ref": 40}, None) == "Clicking"


def test_secrets_and_long_bodies_never_echoed():
    assert step_phrase({"op": "type", "ref": 8, "text": "hunter2"}, ELS) == "Typing"
    assert step_phrase({"op": "type", "ref": 7, "text": "hunter2"}, ELS) == "Typing"
    assert step_phrase({"op": "type", "ref": 12, "text": "sk4f9a8b7c6d5e4f3"},
                       ELS) == "Typing"
    body = "Hey Mom, running late tonight, see you at eight"
    phrase = step_phrase({"op": "type", "ref": 9, "text": body}, ELS)
    assert phrase == "Typing in Message body"
    assert "Mom" not in phrase
    assert step_phrase({"op": "skill", "name": "type_text",
                        "args": {"text": body}}, ELS) == "Typing"


def test_terminal_ops_have_no_phrase():
    for a in ({"op": "done", "summary": "x"}, {"op": "ask", "question": "x"},
              {"op": "confirm", "summary": "x"}, {"op": "refuse", "reason": "x"},
              None):
        assert step_phrase(a, ELS) is None


def test_other_ops_and_word_cap():
    assert step_phrase({"op": "keys", "combo": "cmd+l"}) == "Going to the address bar"
    assert step_phrase({"op": "keys", "combo": "return"}) == "Pressing Return"
    assert step_phrase({"op": "keys", "combo": "cmd+shift+n"}) == "Pressing ⌘⇧N"
    assert step_phrase({"op": "scroll", "ref": 1, "direction": "down"}) == "Scrolling down"
    assert step_phrase({"op": "wait", "ms": 500}) == "Waiting for the page"
    assert step_phrase({"op": "script", "lang": "shell", "code": "ls"}) == \
        "Running a quick script"
    assert step_phrase({"op": "skill", "name": "open_app",
                        "args": {"name": "Numbers"}}) == "Opening Numbers"
    assert step_phrase({"op": "skill", "name": "set_brightness",
                        "args": {"level": 50}}) == "Set brightness"
    assert step_phrase({"op": "click", "target": "Play"}) == "Clicking Play"
    long = {"op": "type", "ref": 12, "text": "a b c d e f g h i j k"}
    assert len(step_phrase(long, ELS).split()) <= MAX_WORDS


def test_site_names():
    assert site_name("https://mail.google.com/x") == "Gmail"
    assert site_name("github.com/ardahk") == "GitHub"
    assert site_name("https://en.wikipedia.org/wiki/Jazz") == "Wikipedia"
    assert site_name("https://www.reddit.com/r/jazz") == "Reddit"
    assert site_name("") == ""


def test_show_step_sends_acting_bubble():
    from brain.orchestrator import Orchestrator, _DeferredServer

    sent = []

    class Srv:
        async def ui(self, mascot, bubble=None, ms=None):
            sent.append((mascot, bubble))

    o = Orchestrator.__new__(Orchestrator)
    o.server = Srv()
    o._last_obs = {"elements": ELS}
    asyncio.run(o._show_step({"op": "press", "ref": 40}))
    asyncio.run(o._show_step({"op": "done", "summary": "ok"}))
    assert sent == [("acting", "Clicking Jazz Classics")]
    o.server = _DeferredServer(Srv())
    asyncio.run(o._show_step({"op": "press", "ref": 40}))
    assert sent == [("acting", "Clicking Jazz Classics")]
