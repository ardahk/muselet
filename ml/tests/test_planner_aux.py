import asyncio
import time

import pytest

from brain import cli
from brain.catalog import Catalog
from brain.memory import MemoryStore, WorkingMemory
from brain.orchestrator import Orchestrator
from brain.tools import compose_text, draft_email
from brain.traces import Tracer
from fakes import FakeServer, SyncWorker


class _TextModel:
    def __init__(self, answer="the save dialog is still open",
                 completion="open the second budget spreadsheet",
                 probabilities=None):
        self.answer = answer
        self.completion = completion
        self.probabilities = probabilities or {"true": 0.99, "false": 0.01}
        self.generate_calls = []
        self.complete_calls = []
        self.decide_calls = []

    def generate(self, *args, **kwargs):
        self.generate_calls.append((args, kwargs))
        return self.answer

    def complete(self, *args, **kwargs):
        self.complete_calls.append((args, kwargs))
        return self.completion

    def decide(self, *args, **kwargs):
        self.decide_calls.append((args, kwargs))
        return self.probabilities


def _orch(tmp_path, server=None):
    return Orchestrator(
        server or FakeServer(), Catalog.load(),
        Tracer(tmp_path / "traces"),
        longterm_store=MemoryStore(path=tmp_path / "memory.sqlite"))


def _run(coro):
    return asyncio.run(coro)


def test_memory_rewrite_uses_aux_complete(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    planner = _TextModel()
    aux = _TextModel()
    orch = _orch(tmp_path)
    orch.longterm_enabled = False
    orch.planner = planner
    orch.planner_aux = aux
    orch.memory = WorkingMemory()
    orch.memory.record(
        "search for history", "search for history", "web_search",
        {"query": "history"}, True, {"app": "Safari"}, t=time.time())

    result = _run(orch._memory_followup("the other one", {"decisions": []}))

    assert result.reason == "llm-invalid"
    assert len(aux.complete_calls) == 1
    assert planner.complete_calls == []


def test_fallback_answer_uses_aux_generate(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    planner = _TextModel(answer="planner answer")
    aux = _TextModel(answer="aux answer")
    orch = _orch(tmp_path)
    orch.planner = planner
    orch.planner_aux = aux

    assert _run(orch._answer("What is the capital of France?", {
        "decisions": []})) == "ok"

    assert aux.generate_calls[0][0][0] == "Answer in at most 12 words."
    assert planner.generate_calls == []


def test_verify_missing_text_uses_aux_generate(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    planner = _TextModel(answer="planner text")
    aux = _TextModel(answer="the save dialog is still open")
    orch = _orch(tmp_path)
    orch.planner = planner
    orch.planner_aux = aux

    answer = _run(orch._missing_text("save the file", [], "empty"))

    assert answer == "the save dialog is still open"
    assert len(aux.generate_calls) == 1
    assert planner.generate_calls == []


def test_verify_done_uses_aux_decide(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    planner = _TextModel()
    aux = _TextModel()
    orch = _orch(tmp_path, FakeServer(observe=lambda: {
        "epoch": 1, "app": "Finder", "window": "Saved",
        "elements": [], "text": "The file is saved. " * 20}))
    orch.planner = planner
    orch.planner_aux = aux

    result = _run(orch._verify_done(
        "save the file", [], {"decisions": []}))

    assert result[0] is True
    assert len(aux.decide_calls) == 1
    assert planner.decide_calls == []


def test_escalation_planner_owns_verify_text_and_decide(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    planner = _TextModel()
    aux = _TextModel()
    escalation = _TextModel()
    orch = _orch(tmp_path, FakeServer(observe=lambda: {
        "epoch": 1, "app": "Finder", "window": "Saved",
        "elements": [], "text": "The file is saved. " * 20}))
    orch.planner = planner
    orch.planner_aux = aux
    orch.planner_escalate = escalation
    orch._active_planner = escalation

    answer = _run(orch._missing_text("save the file", [], "empty"))
    result = _run(orch._verify_done(
        "save the file", [], {"decisions": []}))

    assert answer == "the save dialog is still open"
    assert result[0] is True
    assert len(escalation.generate_calls) == 1
    assert len(escalation.decide_calls) == 1
    assert aux.generate_calls == [] and aux.decide_calls == []
    assert planner.generate_calls == [] and planner.decide_calls == []


def test_web_question_and_answer_use_aux_when_planner_is_absent(
        tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    question = "look up when the golden gate bridge opened"
    page = ('app: Safari | window: "Search"\n' +
            "The Golden Gate Bridge opened in 1937. " * 15)
    server = FakeServer(observe=lambda: {
        "epoch": 3, "app": "Safari", "window": "Search",
        "elements": [], "text": page, "ax_ms": 1})
    aux = _TextModel(answer="May 27, 1937")
    orch = _orch(tmp_path, server)
    orch.planner = None
    orch.planner_aux = aux
    orch._ctx = {"online": True}
    orch.WEB_RICH_CHARS = 200
    orch.tracer.begin(question)

    assert orch._web_question(question)
    assert _run(orch._web_answer(question, {"decisions": []})) == "ok"

    assert server.said[-1] == "May 27, 1937"
    assert len(aux.generate_calls) == 1


def test_compose_text_uses_aux_and_falls_back_to_planner(
        monkeypatch):
    from test_tool_compose_text import _compose_orch

    aux = _TextModel(answer="An excellent draft\nA short note.")
    orch = _compose_orch("Planner text", monkeypatch)
    orch.planner_aux = aux
    result = _run(compose_text.run(
        orch, {"topic": "project update"}, "write a note about the project"))

    assert result == "ok"
    assert len(aux.generate_calls) == 1
    assert orch.planner.calls == []

    fallback = _compose_orch("Planner draft", monkeypatch)
    fallback.planner_aux = None
    assert _run(compose_text.run(
        fallback, {"topic": "project update"}, "write a note")) == "ok"
    assert len(fallback.planner.calls) == 1


def test_draft_email_uses_aux_generate(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: SyncWorker())
    monkeypatch.setattr(draft_email, "user_name", lambda: None)
    obs = {"epoch": 1, "app": "Mail", "window": "Inbox", "elements": []}
    orch = _orch(tmp_path, FakeServer(observe=lambda: obs))
    planner = _TextModel(answer="planner draft")
    aux = _TextModel(answer="Thanks for reaching out.")
    orch.planner = planner
    orch.planner_aux = aux

    result = _run(draft_email.run(
        orch, {"to": "ada@example.com", "about": "hello"},
        "draft an email"))

    assert result == "ok"
    assert len(aux.generate_calls) == 1
    assert planner.generate_calls == []


def test_text_model_falls_back_to_planner_without_aux(tmp_path):
    planner = _TextModel()
    orch = _orch(tmp_path)
    orch.planner = planner
    orch.planner_aux = None

    assert orch._text_model() is planner
    assert orch._text_model(planner) is planner


def test_cli_aux_default_and_run_cmd_forwarding(monkeypatch):
    args, parser = cli.build_parser(["serve"])
    assert args.planner_aux_model == "mlx-community/Qwen3.5-4B-4bit"
    captured = {}

    async def fake_serve(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda model: model)
    cli.run_cmd(args, parser)

    assert captured["planner_aux_model"] == \
        "mlx-community/Qwen3.5-4B-4bit"


@pytest.mark.parametrize(("aux_value", "expected_count", "shared"), [
    ("planner", 1, True),
    ("same", 1, True),
    ("aux-model", 2, False),
])
def test_serve_aux_shares_or_constructs_separate_model(
        monkeypatch, aux_value, expected_count, shared):
    captured = {}

    class Server:
        def __init__(self, port):
            self.port = port

        async def start(self):
            pass

        async def close(self):
            pass

    class Orch:
        def __init__(self, *args, **kwargs):
            self.grounder_cfg = {}
            captured["orch"] = self

        def _schedule_warm_planner(self, planner, tag="planner"):
            pass

        async def handle_utterance(self, text, ctx=None):
            raise asyncio.CancelledError

    made = []

    def make_planner(path, engine, opts=None, tag="planner"):
        planner = _TextModel()
        made.append((path, opts, tag, planner))
        return planner

    async def inputs():
        yield "stop"

    monkeypatch.setattr(cli, "BrainServer", Server)
    monkeypatch.setattr(cli, "Orchestrator", Orch)
    monkeypatch.setattr(cli, "_resolve_model",
                        lambda value: "main" if value == "same" else value)
    monkeypatch.setattr(cli, "make_planner", make_planner)
    monkeypatch.setattr(cli, "_stdin_lines", inputs)

    _run(cli.serve(
        planner_model="main", planner_aux_model=aux_value,
            planner_blind="planner"))

    orch = captured["orch"]
    assert len(made) == expected_count
    if shared:
        assert orch.planner_aux is orch.planner
    else:
        assert orch.planner_aux is made[1][3]
        assert made[1][:3] == (
            "aux-model", {"few_shot": None, "constrain": False},
            "planner-aux")


def test_serve_leaves_aux_unset_without_planner(monkeypatch):
    captured = {}

    class Server:
        def __init__(self, port):
            self.port = port

        async def start(self):
            pass

        async def close(self):
            pass

    class Orch:
        def __init__(self, *args, **kwargs):
            self.grounder_cfg = {}
            captured["orch"] = self

        def _schedule_warm_planner(self, planner, tag="planner"):
            pass

        async def handle_utterance(self, text, ctx=None):
            raise asyncio.CancelledError

    async def inputs():
        yield "stop"

    monkeypatch.setattr(cli, "BrainServer", Server)
    monkeypatch.setattr(cli, "Orchestrator", Orch)
    monkeypatch.setattr(cli, "_resolve_model",
                        lambda value: None if value == "none" else value)
    monkeypatch.setattr(cli, "make_planner",
                        lambda *args, **kwargs: pytest.fail(
                            "no planner should be built"))
    monkeypatch.setattr(cli, "_stdin_lines", inputs)

    _run(cli.serve(
        planner_model="none", planner_aux_model="aux-model"))

    assert captured["orch"].planner is None
    assert captured["orch"].planner_aux is None
