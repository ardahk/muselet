import asyncio

import pytest

from brain.tools import compose_text
from test_first_use_fixes import _compose_orch


def observation(app, window="Draft", label="Body"):
    return {"app": app, "window": window, "focused_ref": 1,
            "elements": [{"ref": 1, "role": "textarea", "label": label}]}


@pytest.mark.parametrize("obs", [
    observation("Messages"), observation("Mail"), observation("Slack"),
    observation("Microsoft Outlook"), observation("Safari", "Gmail"),
    observation("Google Chrome", "LinkedIn", "Message"),
    observation("Unknown", "Compose"), observation("Unknown", label="Subject"),
    observation("Unknown", label="To:"),
])
@pytest.mark.parametrize("target", ["focused", "document"])
@pytest.mark.parametrize("yes", [True, False])
def test_planner28_composer_requires_preview_before_typing(monkeypatch, obs, target, yes):
    orch = _compose_orch("A short generated draft", monkeypatch)
    orch.server.observe = lambda: obs
    orch.server.confirm_yes = yes
    original = orch._run_skill

    async def type_after_confirm(*args):
        assert orch.server.confirms == ['Type this draft: "A short generated draft"?']
        return await original(*args)

    orch._run_skill = type_after_confirm
    result = asyncio.run(compose_text.run(orch, {"target": target}, "write a reply"))
    assert result == ("ok" if yes else "cancelled")
    assert orch.server.confirms == ['Type this draft: "A short generated draft"?']
    assert len(orch.skills_called) == int(yes)
    if yes:
        assert orch.skills_called[0][:2] == (
            "type_text", {"text": "A short generated draft"})


@pytest.mark.parametrize("app", ["Notes", "TextEdit", "Pages"])
@pytest.mark.parametrize("target", ["focused", "document"])
def test_planner28_documents_type_without_confirm(monkeypatch, app, target):
    orch = _compose_orch("Draft text", monkeypatch)
    orch._ctx = {"app": "Messages", "focused": 'textarea "Message"'}
    orch.server.observe = lambda: observation(app, "My document", "Document body")
    assert asyncio.run(compose_text.run(
        orch, {"target": target}, "write about sending email")) == "ok"
    assert orch.server.confirms == []
    assert orch.skills_called[0][0] == "type_text"


@pytest.mark.parametrize("obs", [None, {}, {"ok": False}, "error"])
@pytest.mark.parametrize("yes", [True, False])
def test_planner28_missing_observation_in_composer_still_confirms(monkeypatch, obs, yes):
    orch = _compose_orch("Draft text", monkeypatch)
    orch._ctx = {"app": "Mail"}
    orch.server.confirm_yes = yes

    def observe():
        if obs == "error":
            raise RuntimeError("observation unavailable")
        return obs

    orch.server.observe = observe
    result = asyncio.run(compose_text.run(orch, {"target": "focused"}, "draft"))
    assert result == ("ok" if yes else "cancelled")
    assert orch.server.confirms == ['Type this draft: "Draft text"?']
    assert len(orch.skills_called) == int(yes)


def test_planner28_missing_observation_uses_last_composer_window(monkeypatch):
    orch = _compose_orch("Draft text", monkeypatch)
    orch._ctx = {"app": "Safari"}
    orch._last_obs = observation("Safari", "Gmail")
    orch.server.observe = lambda: None
    asyncio.run(compose_text.run(orch, {"target": "focused"}, "draft"))
    assert len(orch.server.confirms) == 1


@pytest.mark.parametrize("app", ["Notes", "TextEdit", "Pages"])
def test_planner28_missing_document_observation_does_not_confirm(monkeypatch, app):
    orch = _compose_orch("Draft text", monkeypatch)
    orch._ctx = {"app": app, "focused": 'textarea "Document body"'}
    orch._last_obs = observation("Mail")
    orch.server.observe = lambda: None
    assert asyncio.run(compose_text.run(orch, {"target": "document"}, "draft")) == "ok"
    assert orch.server.confirms == []
    assert len(orch.skills_called) == 1


def test_planner28_focused_context_label_identifies_composer(monkeypatch):
    orch = _compose_orch("Draft text", monkeypatch)
    orch._ctx = {"app": "Safari", "focused": 'textarea "Reply"'}
    orch.server.observe = lambda: {"app": "Safari"}
    asyncio.run(compose_text.run(orch, {"target": "focused"}, "draft"))
    assert len(orch.server.confirms) == 1


def test_planner28_composer_strips_trailing_returns_at_typing_boundary(monkeypatch):
    orch = _compose_orch("Line one\nLine two", monkeypatch)
    orch.server.observe = lambda: observation("Messages")
    monkeypatch.setattr(compose_text, "_cap_words", lambda text: text + "\r\n\r\n")
    assert asyncio.run(compose_text.run(orch, {"target": "document"}, "draft")) == "ok"
    assert orch.skills_called[0][1]["text"] == "Line one\nLine two"
    assert "\n" not in orch.server.confirms[0] and "\r" not in orch.server.confirms[0]


def test_planner28_preview_is_short(monkeypatch):
    orch = _compose_orch("x" * 200 + " extra words " * 50, monkeypatch)
    orch.server.observe = lambda: observation("Mail")
    asyncio.run(compose_text.run(orch, {"target": "focused"}, "draft"))
    assert len(orch.server.confirms[0]) < 110
    assert "…" in orch.server.confirms[0]


def test_planner28_confirm_timeout_never_types(monkeypatch):
    orch = _compose_orch("Draft text", monkeypatch)
    orch.server.observe = lambda: observation("Mail")
    orch.server.confirm_raises = True
    assert asyncio.run(compose_text.run(orch, {"target": "focused"}, "draft")) == "cancelled"
    assert orch.skills_called == []


@pytest.mark.parametrize("text", ["", "<think>hidden</think>"])
def test_planner28_empty_generation_never_confirms_or_types(monkeypatch, text):
    orch = _compose_orch(text, monkeypatch)
    orch._ctx = {"app": "Messages"}
    assert asyncio.run(compose_text.run(orch, {"target": "focused"}, "draft")) == "failed"
    assert orch.server.confirms == [] and orch.skills_called == []
