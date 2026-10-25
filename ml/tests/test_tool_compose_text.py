import asyncio
from types import SimpleNamespace

import pytest

from brain.orchestrator import Orchestrator
from brain.tools import compose_text
from brain.tools.compose_text import _cap_words, _title
from fakes import FakeEngine, FakeServer, SyncWorker


class _FakePlanner:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.text


def _compose_orch(text, monkeypatch, error=None):
    from brain import planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: SyncWorker())
    server = FakeServer()
    planner = _FakePlanner(text)
    orch = SimpleNamespace(
        planner=planner, planner_escalate=None, server=server,
        tracer=SimpleNamespace(current={"decisions": []}),
        _last_action_error=error, _pending_task=None, ui_ended=[],
        skills_called=[])

    async def run_skill(name, args, utterance, trace):
        orch.skills_called.append((name, args, utterance))
        orch._last_action_error = error
        return "failed" if error else "ok"

    async def end_ui(mascot):
        orch.ui_ended.append(mascot)

    orch._run_skill = run_skill
    orch._end_ui = end_ui
    return orch


# ---------- compose_text: notes / focused / document targets ----------

def test_compose_postprocessing():
    out = _cap_words("\n".join(f"word{i}" for i in range(151)))
    assert len(out.split()) <= 150
    assert _title("my day", "A useful title\nbody") == "A useful title"
    assert _title("my day", "- one\n- two") == "My Day"


def test_compose_text_note_path_caps_and_verifies(monkeypatch):
    from brain.tools.compose_text import SYSTEM, run

    generated = "My useful title\n" + " ".join(f"word{i}" for i in range(160))
    orch = _compose_orch(generated, monkeypatch)
    outcome = asyncio.run(run(orch, {"topic": "my day"}, "write a note"))
    assert outcome == "ok"
    name, args, utterance = orch.skills_called[0]
    assert name == "new_note" and utterance == "write a note"
    assert args["title"] == "My useful title"
    assert len(args["body"].split()) <= 150
    assert orch.planner.calls[0][0] == (
        SYSTEM, "Topic: my day\nRequest: write a note")
    assert ("verify", {"expect": 'appears "My useful title"'}) in \
        orch.server.rpcs
    assert orch.server.said[-1] == "Wrote it in Notes"


@pytest.mark.parametrize("error,expected", [
    (None, "ok"),
    ("no_text_target", "awaiting_user"),
])
def test_compose_text_focused_path(monkeypatch, error, expected):
    from brain.tools.compose_text import run

    orch = _compose_orch("Draft text", monkeypatch, error=error)
    outcome = asyncio.run(run(
        orch, {"topic": "my day", "target": "focused"}, "draft my day"))
    assert outcome == expected
    assert orch.skills_called[0][0] == "type_text"
    if error:
        assert orch.server.said[-1] == \
            "Click where it should go, then say continue."
        assert orch._pending_task["goal"] == "draft my day"
    else:
        assert orch.server.said[-1] == "Wrote it"


@pytest.mark.parametrize("target,skill", [("document", "type_text"), ("notes", "new_note")])
def test_compose_text_v3_targets(monkeypatch, target, skill):
    from brain.tools.compose_text import run

    orch = _compose_orch("Draft text", monkeypatch)
    asyncio.run(run(orch, {"topic": "my day", "target": target}, "draft my day"))
    assert orch.skills_called[0][0] == skill


def test_compose_text_dispatches_through_tools_run(monkeypatch):
    from brain import tools

    orch = _compose_orch("Text", monkeypatch)
    assert asyncio.run(tools.run(
        orch, "compose_text", {"topic": "my day", "target": "note"},
        "write about my day")) == "ok"
    assert orch.skills_called[0][0] == "new_note"


# ---------- notes pre-route: write X in Notes skips the router ----------

@pytest.mark.parametrize("text,topic", [
    ("Open notes and write a template about my day so I can fill it out",
     "a template about my day so I can fill it out"),
    ("write a poem in my notes", "a poem"),
    ("make a list on the notes", "a list"),
    ("create a template into notes", "a template"),
    ("draft a plan in a notes", "a plan"),
    ("Open notes, and write a template about my day", "a template about my day"),
    ("open the notes and make a list", "a list"),
    ("open notes app and create a template", "a template"),
    ("open the notes app, then draft a plan", "a plan"),
    ("open up notes and write a poem", "a poem"),
    ("open up the notes app, and then write a poem", "a poem"),
    ("write a poem in my notes app", "a poem"),
    ("write a poem in apple notes", "a poem"),
    ("Draft a plan in Apple Notes app.", "a plan"),
])
def test_notes_preroute_native_rpc(text, topic):
    class Writer:
        def generate(self, system, user, **kwargs):
            assert f"Topic: {topic}" in user
            return "My day\nMood: ____\nHighlights: ____"

    engine = FakeEngine()
    server = FakeServer()
    orch = Orchestrator(server, engine=engine)
    orch.planner = Writer()
    assert asyncio.run(orch.handle_utterance(text))["outcome"] == "ok"
    assert engine.route_calls == []
    assert server.skills() == [{"name": "new_note", "args": {
        "title": "My day", "body": "My day\nMood: ____\nHighlights: ____"}}]
    assert server.confirms == []
    assert not any(m == "act" for m, _ in server.rpcs)


@pytest.mark.parametrize("text", ["", "open notes", "notes about X in TextEdit",
                                       "write notes about X in TextEdit",
                                       "open notes and write", "write in notes",
                                       "write hello in textedit", "open the notes app",
                                       "open up notes", "open notes,",
                                       "write a poem in apple notes in textedit"])
def test_notes_preroute_does_not_overmatch(text):
    from brain.tools.compose_text import parse_request
    assert parse_request(text) is None


@pytest.mark.parametrize("generated", ["", RuntimeError("generation failed")])
def test_notes_preroute_generation_failure(generated):
    class Writer:
        def generate(self, *args, **kwargs):
            if isinstance(generated, Exception):
                raise generated
            return generated

    server = FakeServer()
    orch = Orchestrator(server, engine=FakeEngine())
    orch.planner = Writer()
    assert asyncio.run(orch.handle_utterance("write a poem in notes"))["outcome"] == "failed"
    assert server.skills() == []
    assert server.confirms == []


# ---------- planner-28: composer windows preview before typing ----------

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
