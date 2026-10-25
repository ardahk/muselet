"""Regression tests for brain-9 live-run fixes."""

import asyncio
import json
import time
from concurrent.futures import Future

import pytest

from brain.catalog import Catalog
from brain.decision import DecisionEngine
from brain.orchestrator import Orchestrator, _content_words, named_browser
from brain.planner import catalog_desc
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer
from test_brain8_live_fixes import FakePlanner


class InlineWorker:
    async def submit_async(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


def _orch(tmp_path, text, routes=None, args=None, planner=None,
          server=None):
    server = server or FakeServer()
    orch = Orchestrator(
        server, Catalog.load(), Tracer(tmp_path / "traces"),
        engine=FakeEngine(routes or {}, args or {}))
    orch.planner = planner
    return orch, server


def _web_settings(orch):
    orch.WEB_AX_WINDOW_S = 0.002
    orch.WEB_PAGE_CAP_S = 0.04
    orch.WEB_PAGE_POLL_S = 0.001
    orch.WEB_PAGE_MIN_S = 0.005
    orch.WEB_RICH_CHARS = 1500


def _trace_for(orch, question):
    return orch.tracer.begin(question)


def _web_answer_decision(trace):
    return next(d["web_answer"] for d in trace["decisions"]
                if "web_answer" in d)


def test_hidden_browser_args_stay_out_of_catalog_prompts():
    catalog = Catalog.load()
    engine = DecisionEngine.__new__(DecisionEngine)
    engine.catalog = catalog
    signature = lambda name: DecisionEngine.arg_signature(engine, name)
    assert signature("open_url") == "url:url required"
    assert signature("web_search") == "query:string required"
    lines = catalog_desc(catalog, signature).splitlines()
    expected = {
        "open_url": "open_url(url:url required): Open a URL in the default browser.",
        "web_search": "web_search(query:string required): Search the web for a query in the default browser.",
    }
    assert {line.split("(", 1)[0]: line for line in lines
            if line.startswith(("open_url(", "web_search("))} == expected
    assert catalog.validate_args("open_url", {
        "url": "https://example.com", "browser": "Safari"})["browser"] == "Safari"


def test_named_browser_aliases_and_context():
    assert named_browser("open this in Safari") == "Safari"
    assert named_browser("search for ramen in GOOGLE CHROME") == "Google Chrome"
    assert named_browser("use Chrome") == "Google Chrome"
    assert named_browser("open Firefox") == "Firefox"
    assert named_browser("using Microsoft Edge") == "Microsoft Edge"
    assert named_browser("open Brave Browser") == "Brave Browser"
    assert named_browser("search zen browser") == "Zen"
    assert named_browser("open with the Arc browser") == "Arc"
    assert named_browser("look it up in edge") == "Microsoft Edge"
    assert named_browser("use Brave") == "Brave Browser"
    assert named_browser("open a tab in Zen browser") == "Zen"
    assert named_browser("launch Vivaldi") == "Vivaldi"
    assert named_browser(
        "open in Arc, then use the Edge browser, then open Arc") == "Arc"
    assert named_browser("search for brave new world") is None
    assert named_browser("search for zen meditation") is None
    assert named_browser("look up opera tickets") is None


def test_planner_open_then_web_search_preserves_requested_browser(
        tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    text = "search for flights to tokyo in safari"
    planner = FakePlanner([
        ['open "Safari"', 'skill web_search query="flights to Tokyo"'],
        ['done "ok"'],
    ])
    orch, server = _orch(
        tmp_path, text, routes={text: ("MULTI_STEP", 0.95)},
        planner=planner)
    asyncio.run(orch.handle_utterance(text))

    assert [p for m, p in server.rpcs if m == "skill"] == [{
        "name": "web_search",
        "args": {"query": "flights to Tokyo", "browser": "Safari"},
    }], server.rpcs
    open_rpc = next((i for i, (m, p) in enumerate(server.rpcs)
                     if m == "act" and p.get("op") == "open" and
                     p.get("name") == "Safari"), None)
    skill_rpc = next((i for i, (m, p) in enumerate(server.rpcs)
                      if m == "skill" and p.get("name") == "web_search"),
                     None)
    assert open_rpc is not None and skill_rpc is not None and \
        open_rpc < skill_rpc, server.rpcs


def test_planner_url_act_receives_named_browser(tmp_path):
    orch, server = _orch(tmp_path, "open example.com in chrome")
    orch._current_goal = "open example.com in chrome"
    result = asyncio.run(orch._exec_action({
        "op": "url", "url": "https://example.com"}))
    assert result["status"] == "ok"
    assert next(p for m, p in server.rpcs if m == "act")["browser"] == \
        "Google Chrome"


@pytest.mark.parametrize(("text", "skill", "args", "browser"), [
    ("search for ramen in chrome", "web_search", {"query": "ramen"},
     "Google Chrome"),
    ("open github in arc", "open_url", {"url": "https://github.com"}, "Arc"),
    ("search for flights to tokyo", "web_search",
     {"query": "flights to tokyo"}, None),
])
def test_router_fast_path_browser_args(tmp_path, monkeypatch, text, skill,
                                       args, browser):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    orch, server = _orch(
        tmp_path, text, {text: (skill, 0.95)}, {(skill, text): args})
    asyncio.run(orch.handle_utterance(text))
    rpc_args = next(p["args"] for m, p in server.rpcs
                    if m == "skill" and p["name"] == skill)
    if browser is None:
        assert "browser" not in rpc_args
    else:
        assert rpc_args["browser"] == browser


def test_execute_actions_url_receives_named_browser(tmp_path):
    orch, server = _orch(tmp_path, "open example.com using the edge browser")
    orch._current_goal = "open example.com using the edge browser"
    assert asyncio.run(orch.execute_actions([{
        "op": "url", "url": "https://example.com"}])) == "ok"
    assert next(p for m, p in server.rpcs if m == "act")["browser"] == \
        "Microsoft Edge"


def test_web_answer_waits_for_rich_ax_without_ocr(tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    thin = "The bridge opened in 1937. " + ("x" * 192)
    rich = "The bridge opened in 1937. " + ("details " * 220)
    observations = iter([
        {"text": thin, "web_ax_pending": False},
        {"text": rich, "web_ax_pending": False},
    ])
    server = FakeServer(observe=lambda: next(observations))
    planner = FakePlanner(answer=lambda system, user: "1937")
    orch, server = _orch(tmp_path, "when did the bridge open",
                         planner=planner, server=server)
    _web_settings(orch)
    trace = _trace_for(orch, "when did the bridge open")

    asyncio.run(orch._web_answer("when did the bridge open", trace))

    assert server.said[-1] == "1937"
    assert not any(method == "ocr" for method, _ in server.rpcs)
    decision = _web_answer_decision(trace)
    assert decision["samples"] == 2 and decision["ocr"] is False


def test_stable_thin_ax_uses_ocr_for_answer(tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    thin = "Search results are loading."
    server = FakeServer(
        observe=lambda: {"text": thin, "web_ax_pending": False},
        handlers={
            "screenshot": lambda _: {"path": "screen.png"},
            "ocr": lambda _: {"text": "The bridge opened in 1937."},
        })
    planner = FakePlanner(answer=lambda system, user: (
        "1937" if "1937" in user else "NOT_FOUND"))
    orch, server = _orch(tmp_path, "when did the bridge open",
                         planner=planner, server=server)
    _web_settings(orch)
    trace = _trace_for(orch, "when did the bridge open")

    asyncio.run(orch._web_answer("when did the bridge open", trace))

    assert server.said[-1] == "1937"
    assert _web_answer_decision(trace)["ocr"] == "ocr"


def test_long_ax_without_question_words_still_runs_ocr(tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    ax = "unrelated " * 170
    server = FakeServer(
        observe=lambda: {"text": ax, "web_ax_pending": False},
        handlers={
            "screenshot": lambda _: {"path": "screen.png"},
            "ocr": lambda _: {"text": "visible screen text " * 120},
        })
    orch, server = _orch(
        tmp_path, "what is the", planner=FakePlanner(answer="NOT_FOUND"),
        server=server)
    _web_settings(orch)
    trace = _trace_for(orch, "what is the")

    asyncio.run(orch._web_answer("what is the", trace))

    assert any(method == "ocr" for method, _ in server.rpcs)
    assert _web_answer_decision(trace)["ocr"] == "ocr"


def test_web_answer_combines_ax_and_ocr_when_both_match(tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    server = FakeServer(
        observe=lambda: {
            "text": "AX mentions the bridge. " + "more " * 200,
            "web_ax_pending": False,
        },
        handlers={
            "screenshot": lambda _: {"path": "screen.png"},
            "ocr": lambda _: {"text": "OCR also shows the bridge."},
        })
    planner = FakePlanner(answer=lambda system, user: "1937")
    orch, server = _orch(tmp_path, "when did the bridge open",
                         planner=planner, server=server)
    _web_settings(orch)
    trace = _trace_for(orch, "when did the bridge open")

    asyncio.run(orch._web_answer("when did the bridge open", trace))

    user = planner.generates[-1][1]
    assert "\n--- screen text (OCR) ---\n" in user
    assert "AX mentions the bridge." in user
    assert "OCR also shows the bridge." in user
    assert _web_answer_decision(trace)["ocr"] == "both"


def test_web_answer_pending_observations_stop_at_cap(tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    server = FakeServer(observe=lambda: {
        "text": "Loading", "web_ax_pending": True})
    orch, server = _orch(tmp_path, "when did the bridge open",
                         planner=FakePlanner(answer="NOT_FOUND"), server=server)
    _web_settings(orch)
    orch.WEB_AX_WINDOW_S = 0.002
    orch.WEB_PAGE_CAP_S = 0.02
    trace = _trace_for(orch, "when did the bridge open")
    started = time.perf_counter()

    asyncio.run(orch._web_answer("when did the bridge open", trace))

    assert time.perf_counter() - started < 0.5
    assert _web_answer_decision(trace)["wait_ms"] < 100
    assert _web_answer_decision(trace)["samples"] >= 2


def test_warm_planner_records_event_and_swallows_failure(
        tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    orch, _ = _orch(tmp_path, "warm")

    class WarmPlanner:
        model_path = "fake/model"

        def warm(self):
            return {"warm_ms": 42.0, "prefix_ms": 1.0,
                    "constraint_ms": 2.0, "retrieval_ms": 3.0,
                    "decode_ms": 4.0}

    asyncio.run(orch.warm_planner(WarmPlanner()))
    rows = [json.loads(line) for path in orch.tracer.dir.glob("*.jsonl")
            for line in path.read_text().splitlines()]
    assert rows[-1]["event"] == "planner.warm"
    assert rows[-1]["warm_ms"] == 42.0
    assert rows[-1]["model"] == "fake/model"

    class BrokenPlanner:
        def warm(self):
            raise RuntimeError("warm failed")

    asyncio.run(orch.warm_planner(BrokenPlanner()))


def test_successful_escalation_load_schedules_planner_warm(
        tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    orch, _ = _orch(tmp_path, "escalate")
    orch.planner = object()
    orch._sysctl_reader = lambda name: {
        "hw.memsize": 64 * 1024 ** 3,
        "kern.memorystatus_level": 50,
    }[name]
    warmed = []

    class EscalationPlanner:
        model_path = "fake/escalation"

        def warm(self):
            warmed.append(True)
            return {"warm_ms": 5.0}

    planner = EscalationPlanner()
    orch._escalate_loader = lambda *args, **kwargs: planner

    async def enable_and_warm():
        result = await orch.set_escalation(True)
        await asyncio.gather(*list(orch._warm_tasks))
        return result

    result = asyncio.run(enable_and_warm())

    assert result == {"loaded": True}
    assert orch.planner_escalate is planner
    assert warmed


def test_question_content_words_exclude_command_words():
    assert _content_words("when did the bridge open") == {"bridge", "open"}
    assert _content_words("what is the") == set()
