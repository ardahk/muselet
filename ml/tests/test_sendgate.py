import asyncio

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.sendgate import enter_sends
from brain.traces import Tracer
from fakes import FakeServer


def run(coro):
    return asyncio.run(coro)


def _orch(tmp_path):
    server = FakeServer()
    return Orchestrator(server, Catalog.load(), Tracer(tmp_path / "trace")), server


@pytest.mark.parametrize("app", [
    "Discord", "WhatsApp", "Microsoft Teams", "Teams", "Telegram", "Signal",
    "Messenger", "WeChat", "Zoom", "Skype", "Google Chat", "Messages", "Mail",
    "Slack",
])
def test_enter_sends_supported_composer_app_names(app):
    assert enter_sends(app, None, None, None)


@pytest.mark.parametrize("bundle_id", [
    "com.hnc.Discord", "net.whatsapp.WhatsApp", "com.microsoft.teams2",
    "com.microsoft.teams", "ru.keepcoder.Telegram", "org.telegram.desktop",
    "org.whispersystems.signal-desktop", "com.facebook.archon",
    "com.tencent.xinWeChat", "us.zoom.xos", "com.skype.skype",
    "com.apple.MobileSMS", "com.apple.mail", "com.tinyspeck.slackmacgap",
])
def test_enter_sends_supported_bundle_ids(bundle_id):
    assert enter_sends(bundle_id, None, None, None)


@pytest.mark.parametrize("title", [
    "Gmail - Inbox", "Discord | General", "WhatsApp Web",
])
def test_enter_sends_browser_window_titles(title):
    assert enter_sends("Google Chrome", title, None, None)


@pytest.mark.parametrize(("role", "label"), [
    ("textarea", "Write a reply…"),
    ("textfield", "Message #general"),
    ("combobox", "Add a comment"),
])
def test_enter_sends_generic_composer_fields(role, label):
    assert enter_sends("TextEdit", "Untitled", role, label)


@pytest.mark.parametrize(("app", "window", "role", "label"), [
    ("Finder", "Recents", "textfield", "Search"),
    ("Safari", "Start Page", "textfield", "Search"),
    ("Google Chrome", "Amazon", "textfield", "Address and search bar"),
    ("Numbers", "Budget", "textfield", "A1"),
    ("Numbers", "Budget", "cell", "Cell B2"),
    ("Gmail Settings", "TextEdit", "textfield", "Search"),
])
def test_enter_sends_ignores_non_composer_fields(app, window, role, label):
    assert not enter_sends(app, window, role, label)


@pytest.mark.parametrize("combo", ["return", "enter", "cmd+return", "keypad_enter"])
def test_keys_enter_confirms_for_focused_message_field(tmp_path, combo):
    orch, server = _orch(tmp_path)
    orch._last_obs = {
        "app": "TextEdit", "window": "Untitled", "focused_ref": 4,
        "elements": [{"ref": 4, "role": "textarea",
                      "label": "Write a reply…"}],
    }

    result = run(orch._exec_action({"op": "keys", "combo": combo}))

    assert result["status"] == "ok"
    assert server.confirms == [f"Press {combo} in TextEdit?"]


def test_keys_enter_uses_context_focus_when_observation_ref_is_missing(tmp_path):
    orch, server = _orch(tmp_path)
    orch._last_obs = {
        "app": "TextEdit", "window": "Untitled", "focused_ref": None,
        "elements": [],
    }
    orch._ctx["focused"] = 'textarea "Write a reply…"'

    result = run(orch._exec_action({"op": "keys", "combo": "return"}))

    assert result["status"] == "ok"
    assert len(server.confirms) == 1


def test_type_enter_uses_the_referenced_element(tmp_path):
    orch, server = _orch(tmp_path)
    orch._last_obs = {
        "app": "TextEdit", "window": "Untitled", "focused_ref": None,
        "elements": [{"ref": 12, "role": "combobox",
                      "label": "Add a comment"}],
    }

    result = run(orch._exec_action({
        "op": "type", "ref": 12, "text": "hello", "enter": True,
    }))

    assert result["status"] == "ok"
    assert len(server.confirms) == 1


def test_textedit_body_enter_does_not_confirm(tmp_path):
    orch, server = _orch(tmp_path)
    orch._last_obs = {
        "app": "TextEdit", "window": "Untitled", "focused_ref": 4,
        "elements": [{"ref": 4, "role": "textarea", "label": "Body"}],
    }

    result = run(orch._exec_action({"op": "keys", "combo": "return"}))

    assert result["status"] == "ok"
    assert server.confirms == []


def test_declined_type_enter_is_cancelled_without_act(tmp_path):
    orch, server = _orch(tmp_path)
    server.confirm_yes = False
    orch._last_obs = {
        "app": "Notes", "window": "Untitled", "focused_ref": 2,
        "elements": [{"ref": 2, "role": "textfield",
                      "label": "Message #general"}],
    }

    result = run(orch._exec_action({
        "op": "type", "ref": 2, "text": "hello", "enter": True,
    }))

    assert result["status"] == "cancelled"
    assert server.confirms
    assert "act" not in server.methods()


def test_zen_browser_web_composer_counts():
    """The user's default browser is Zen: a Gmail/Slack tab there is a composer."""
    from brain.sendgate import is_composer_app
    assert is_composer_app("Zen", "Inbox - Gmail")
    assert is_composer_app("Zen Browser", "general | Slack")
    assert not is_composer_app("Zen", "Wikipedia")
