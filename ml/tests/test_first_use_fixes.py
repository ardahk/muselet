import asyncio
import time
from types import SimpleNamespace

import pytest

from brain.catalog import Catalog
from brain.decision import RouteRenderer, catalog_options
from brain.orchestrator import Orchestrator
from brain.planner import Planner
from brain.sites import fix_url, normalize_name
from brain.tools.compose_text import _cap_words, _title
from brain.traces import Tracer
from fakes import FakeServer


def test_site_aliases_and_urls():
    assert normalize_name("The Google Docs website") == "googledocs"
    assert fix_url("gmail/inbox?x=1") == "https://mail.google.com/inbox?x=1"
    assert fix_url("https://github.com/a#b") == "https://github.com/a#b"
    assert fix_url("example/path") == "https://example.com/path"
    assert fix_url("localhost:3000/a") == "https://localhost:3000/a"
    assert fix_url("127.0.0.1:3000/a") == "https://127.0.0.1:3000/a"
    assert fix_url("[::1]:3000/a") == "https://[::1]:3000/a"


def test_catalog_url_coercion():
    cat = Catalog({"skills": [{
        "name": "go", "args": [{"name": "url", "type": "url",
                                  "required": True}]
    }]})
    assert cat.validate_args("go", {"url": "gmail"})["url"] == \
        "https://mail.google.com"


def test_hidden_router_skill_is_not_an_option():
    visible = Catalog({"skills": [
        {"name": "a", "description": "A"},
        {"name": "hidden", "description": "H", "router": False},
    ]})
    assert catalog_options(visible) == [("a", "A")]
    assert visible.get("hidden") is not None


def test_hidden_router_skill_does_not_change_route_question():
    base = Catalog({"skills": [
        {"name": "a", "description": "A"},
    ], "special_options": [{"name": "ASK", "description": "Ask"}]})
    with_hidden = Catalog({"skills": [
        {"name": "a", "description": "A"},
        {"name": "hidden", "description": "H", "router": False},
    ], "special_options": [{"name": "ASK", "description": "Ask"}]})
    left, right = RouteRenderer.__new__(RouteRenderer), \
        RouteRenderer.__new__(RouteRenderer)
    left._options, right._options = catalog_options(base), \
        catalog_options(with_hidden)
    utterance, ctx = "write a short note", {"app": "Notes"}
    assert left.decision(utterance, ctx).text == \
        right.decision(utterance, ctx).text
    assert left.decision(utterance, ctx).choices == \
        right.decision(utterance, ctx).choices


def test_login_hint_is_opt_in():
    planner = Planner.__new__(Planner)
    base = planner.user_message("sign in", 'window: "Home"', None)
    hinted = planner.user_message("sign in", 'window: "Login"', None,
                                  login_page=True)
    assert base == 'Goal: "sign in"\nwindow: "Home"'
    assert "Login page: ask the user to sign in" not in base
    assert "Login page: ask the user to sign in" in hinted


def test_signin_gate_requires_exact_text_and_tracks_pending():
    orch = Orchestrator.__new__(Orchestrator)
    orch._last_obs = {"focused_ref": 3, "elements": [
        {"ref": 3, "role": "textfield", "label": "Email or phone"}]}
    orch._ctx = {"focused": "none"}
    orch._current_goal = "open Gmail"
    orch._utterance = "open Gmail"
    orch._answer_history = []
    orch._pending_task = None
    trace = {}
    assert not orch._signin_gate("hello", trace=trace, goal="open Gmail")
    assert trace["signin_gate"] == "Email or phone"
    assert orch._pending_task["goal"] == "open Gmail"
    orch._answer_history.append("sign in with jo@x.com")
    assert orch._signin_gate("jo@x.com", goal="open Gmail")
    orch._last_obs["elements"] = [
        {"ref": 3, "role": "textarea", "label": "Note body"}]
    assert orch._signin_gate("ordinary note text", goal="write a note")


def test_signin_gate_accepts_answer_from_resumed_task():
    async def go():
        orch = Orchestrator(FakeServer(), Catalog.load(), Tracer())
        orch._last_obs = {"focused_ref": 3, "elements": [
            {"ref": 3, "role": "textfield", "label": "Email or phone"}]}
        orch._pending_task = {"goal": "sign in to Gmail", "t": time.time()}

        async def resume(goal, trace, answer=None, **kwargs):
            assert goal == "sign in to Gmail"
            assert answer == "jo@x.com"
            assert orch._answer_history == ["jo@x.com"]
            assert orch._signin_gate(answer, goal=goal, trace=trace)
            return "ok"

        orch._planner_loop = resume
        return await orch.handle_utterance("jo@x.com")

    assert asyncio.run(go())["outcome"] == "ok"


@pytest.mark.parametrize("utterance,typed,expected", [
    ("open Gmail", "hello to my new coworkers", "awaiting_user"),
    ("sign in with jo@x.com", "jo@x.com", "ok"),
])
def test_signin_gate_on_native_type_text(utterance, typed, expected, tmp_path):
    async def go():
        server = FakeServer()
        orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "trace"))
        orch._last_obs = {"focused_ref": 3, "elements": [
            {"ref": 3, "role": "textfield", "label": "Email or phone"}]}
        orch._utterance = utterance
        outcome = await orch._run_skill(
            "type_text", {"text": typed}, utterance, {"decisions": []})
        return outcome, server

    outcome, server = asyncio.run(go())
    assert outcome == expected
    assert ("Please sign in first, then tell me to continue." in server.said) \
        == (expected == "awaiting_user")
    assert bool(server.skills()) == (expected == "ok")


@pytest.mark.parametrize("text", [
    "\n".join(f"word{i}" for i in range(151)),
    "<think>hidden</think>Visible text",
])
def test_compose_postprocessing(text):
    out = _cap_words(text.replace("<think>hidden</think>", ""))
    assert len(out.split()) <= 150
    assert _title("my day", "A useful title\nbody") == "A useful title"
    assert _title("my day", "- one\n- two") == "My Day"


class _FakeWorker:
    async def submit_async(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


class _FakePlanner:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.text


def _compose_orch(text, monkeypatch, error=None):
    from brain import planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: _FakeWorker())
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


def test_compose_text_dispatches_through_tools_run(monkeypatch):
    from brain import tools

    orch = _compose_orch("Text", monkeypatch)
    assert asyncio.run(tools.run(
        orch, "compose_text", {"topic": "my day", "target": "note"},
        "write about my day")) == "ok"
    assert orch.skills_called[0][0] == "new_note"


@pytest.mark.parametrize("memory,pressure,reason", [
    (32 * 1024 ** 3, 60, "needs 48 GB RAM"),
    (64 * 1024 ** 3, 30, "memory pressure"),
])
def test_escalation_refuses_insufficient_memory(memory, pressure, reason):
    orch = Orchestrator(FakeServer(), Catalog.load())
    orch.planner = object()
    values = {"hw.memsize": memory, "kern.memorystatus_level": pressure}
    orch._sysctl_reader = values.__getitem__
    result = asyncio.run(orch.set_escalation(True))
    assert result == {"loaded": False, "reason": reason}
    assert orch.planner_escalate is None


def test_escalation_loads_once_and_unloads():
    orch = Orchestrator(FakeServer(), Catalog.load())
    orch.planner = object()
    orch._sysctl_reader = lambda name: {
        "hw.memsize": 64 * 1024 ** 3,
        "kern.memorystatus_level": 60,
    }[name]
    calls = []
    planner = object()
    orch._escalate_loader = lambda *args, **kwargs: (
        calls.append((args, kwargs)) or planner)
    async def go():
        first = await orch.set_escalation(True)
        second = await orch.set_escalation(True)
        await orch.set_escalation(False)
        return first, second
    first, second = asyncio.run(go())
    assert first == second == {"loaded": True}
    assert len(calls) == 1
    assert calls[0][1]["tag"] == "planner-escalate"
    assert orch.planner_escalate is None


def test_escalation_refuses_without_base_planner():
    orch = Orchestrator(FakeServer(), Catalog.load())
    assert asyncio.run(orch.set_escalation(True)) == {
        "loaded": False, "reason": "no planner"}


def test_server_config_frame_ack(monkeypatch):
    from brain.server import BrainServer

    async def go():
        server = BrainServer(port=0)
        sent = []

        async def send(msg):
            sent.append(msg)

        async def config(msg):
            return {"loaded": True}

        monkeypatch.setattr(server, "send", send)
        server.on_config = config
        server._start_config({"t": "config", "escalate_planner": True})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return sent

    sent = asyncio.run(go())
    assert sent == [{
        "t": "config_ack", "escalate_planner": True, "loaded": True}]


def test_site_and_browser_skill_rewrites():
    async def go():
        server = FakeServer()
        orch = Orchestrator(server, Catalog.load())
        trace = {"decisions": []}
        result = await orch._run_skill(
            "open_app", {"app": "Gmail"}, "navigate to gmail", trace)
        assert result == "ok"
        gmail = server.skills()[-1]
        assert gmail["name"] == "open_url"
        assert gmail["args"]["url"] == "https://mail.google.com"
        assert trace["site_switch"] == ["gmail", "mail.google.com"]

        server.apps = {"running": ["Slack.app"], "installed": []}
        orch._apps = None
        orch._utterance = "open Slack"
        await orch._run_skill("open_app", {"app": "Slack"}, "open Slack",
                              {"decisions": []})
        assert server.skills()[-1]["name"] == "open_app"

        await orch._run_skill("open_app", {"app": "Safari"},
                              "search for cats", {"decisions": []})
        browser = server.skills()[-1]
        assert browser["name"] == "open_url"
        assert browser["args"]["url"] == "https://www.google.com"

        trace = {"decisions": []}
        orch._utterance = "open Safari"
        await orch._run_skill("open_app", {"app": "Safari"},
                              "open Safari", trace)
        assert server.skills()[-1]["name"] == "open_app"
        assert "browser_rewrite" not in trace

        orch._utterance = "open Chrome"
        await orch._run_skill("open_app", {"app": "Google Chrome"},
                              "open Chrome", {"decisions": []})
        assert server.skills()[-1]["name"] == "open_app"
    asyncio.run(go())


def test_planner_open_site_rewrites_to_url():
    async def go():
        server = FakeServer()
        orch = Orchestrator(server, Catalog.load())
        orch._current_goal = "navigate to gmail"
        result = await orch._exec_action({"op": "open", "name": "gmail"})
        assert result["status"] == "ok"
        assert server.rpcs[-1] == (
            "act", {"url": "https://mail.google.com", "op": "url"})
        assert orch._last_url == "https://mail.google.com"
    asyncio.run(go())


class _StreamingFakePlanner:
    def __init__(self, turns):
        self.turns = turns
        self.calls = 0
        self.login_hints = []
        self.history = "dsl"

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, script_output=None, login_page=False):
        self.login_hints.append(login_page)
        lines = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        for line in lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1, "decode_tok_s": 1,
                "tokens": 1}


def test_planner_loop_passes_login_page_hint(tmp_path):
    async def go():
        server = FakeServer(observe=lambda: {
            "epoch": 1, "app": "Chrome", "window": "Sign in",
            "focused_ref": None, "elements": [],
            "text": "app: Chrome | window: Sign in | Password",
            "ax_ms": 1})
        orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"))
        planner = _StreamingFakePlanner([['done "ok"', 'expect title~"Sign in"']])
        orch.planner = planner
        outcome = await orch._planner_loop("continue", {"decisions": []})
        return outcome, planner

    outcome, planner = asyncio.run(go())
    assert outcome == "ok"
    assert planner.login_hints == [True]


def test_identical_noop_presses_trip_loop_guard(tmp_path):
    async def go():
        server = FakeServer(act=lambda p: {
            "ok": True, "epoch": 2, "diff_text": ""}, observe=lambda: {
                "epoch": 1, "app": "Notes", "window": "Notes",
                "focused_ref": None, "elements": [
                    {"ref": 1, "role": "button", "label": "New Note",
                     "frame": [0, 0, 20, 20]}],
                "text": 'app: Notes | window: "Notes"\n'
                        '#1 button "New Note"', "ax_ms": 1})
        orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"))
        orch.planner = _StreamingFakePlanner([
            ["press #1", "press #1", "press #1"],
        ])
        outcome = await orch._planner_loop("make a new note", {
            "decisions": []})
        return outcome, server, orch

    outcome, server, orch = asyncio.run(go())
    assert outcome == "awaiting_user"
    assert server.said[-1] == "I'm stuck on that, can you help?"
    assert len([1 for method, params in server.rpcs
                if method == "act" and params.get("op") == "press"]) == 4
