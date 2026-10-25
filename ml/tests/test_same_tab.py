"""Same-tab navigation and browser page-task routing."""

import asyncio
import time

from brain.catalog import Catalog
from brain.memory import WorkingMemory
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


class FakePlanner:
    def __init__(self, turns):
        self.turns = turns
        self.calls = []

    def plan(self, goal, observation, last_batch, lines_out, loop,
             cancel, hint=None, script_output=None, recent=None):
        index = min(len(self.calls), len(self.turns) - 1)
        self.calls.append({"goal": goal, "hint": hint})
        lines = self.turns[index]
        for line in lines:
            if cancel.is_set():
                break
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
            time.sleep(0.02)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1.0, "decode_tok_s": 20.0,
                "tokens": 12, "plan_ms": 10.0}


def _orch(tmp_path, *, server=None, engine=None, planner=None):
    server = server or FakeServer()
    orch = Orchestrator(
        server, Catalog.load(), Tracer(tmp_path / "traces"), engine=engine)
    orch.memory = WorkingMemory()
    orch.planner = planner
    return orch


def _run(coro):
    return asyncio.run(coro)


def _skills(server):
    return [call for call in server.rpcs if call[0] == "skill"]


def test_wikipedia_followup_uses_current_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"navigate to wikipedia": ("open_url", 0.99)},
            argmap={("open_url", "navigate to wikipedia"): {
                "url": "https://en.wikipedia.org/"}})
        server = FakeServer()
        orch = Orchestrator(
            server, Catalog.load(), Tracer(tmp_path / "traces"),
            engine=engine)
        orch.memory = WorkingMemory()

        first = await orch.handle_utterance(
            "navigate to wikipedia", {"app": "Zen"})
        second = await orch.handle_utterance(
            "search for history",
            {"app": "Zen", "url": "https://en.wikipedia.org/"})

        assert first["outcome"] == "ok"
        assert second["outcome"] == "ok"
        assert engine.route_calls == ["navigate to wikipedia"]
        skills = _skills(server)
        assert [params["args"]["same_tab"] for _, params in skills] == [
            True, True]
        assert [params["args"]["browser"] for _, params in skills] == [
            "Zen", "Zen"]
        assert skills[-1][1]["args"]["url"] == (
            "https://en.wikipedia.org/w/index.php?search=history")

    _run(go())


def test_new_tab_request_does_not_set_same_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"open youtube in a new tab": ("open_url", 0.99)},
            argmap={("open_url", "open youtube in a new tab"): {
                "url": "https://youtube.com/"}})
        server = FakeServer()
        orch = _orch(tmp_path, server=server, engine=engine)

        result = await orch.handle_utterance(
            "open youtube in a new tab", {"app": "Zen"})

        assert result["outcome"] == "ok"
        assert "same_tab" not in _skills(server)[0][1]["args"]

    _run(go())


def test_non_browser_frontmost_does_not_set_same_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"open wikipedia": ("open_url", 0.99)},
            argmap={("open_url", "open wikipedia"): {
                "url": "https://en.wikipedia.org/"}})
        server = FakeServer()
        orch = _orch(tmp_path, server=server, engine=engine)

        result = await orch.handle_utterance(
            "open wikipedia", {"app": "Finder"})

        assert result["outcome"] == "ok"
        assert "same_tab" not in _skills(server)[0][1]["args"]

    _run(go())


def test_requested_other_browser_does_not_set_same_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"open wikipedia in safari": ("open_url", 0.99)},
            argmap={("open_url", "open wikipedia in safari"): {
                "url": "https://en.wikipedia.org/", "browser": "Safari"}})
        server = FakeServer()
        orch = _orch(tmp_path, server=server, engine=engine)

        result = await orch.handle_utterance(
            "open wikipedia in safari", {"app": "Zen"})

        assert result["outcome"] == "ok"
        assert "same_tab" not in _skills(server)[0][1]["args"]

    _run(go())


def test_web_search_only_reuses_search_engine_pages(tmp_path):
    async def route(url, path):
        engine = FakeEngine(
            routes={"search for history": ("web_search", 0.99)},
            argmap={("web_search", "search for history"): {
            "query": "history"}})
        server = FakeServer()
        orch = _orch(tmp_path / path, server=server, engine=engine)
        orch.memory_enabled = False
        result = await orch.handle_utterance(
            "search for history", {"app": "Zen", "url": url})
        assert result["outcome"] == "ok"
        return _skills(server)[0][1]["args"]

    async def go():
        article = await route(
            "https://en.wikipedia.org/wiki/History", "article")
        google = await route(
            "https://www.google.com/search?q=a", "google")
        return article, google

    article_args, google_args = _run(go())
    assert "same_tab" not in article_args
    assert google_args["same_tab"] is True
    assert google_args["browser"] == "Zen"


def test_page_task_uses_planner_and_planner_url_navigates_same_tab(tmp_path):
    async def go():
        engine = FakeEngine()
        server = FakeServer()
        planner = FakePlanner([
            ['url "https://www.amazon.com/s?k=chicken"'],
            ['done "searched"'],
        ])
        orch = _orch(tmp_path, server=server, engine=engine, planner=planner)

        result = await orch.handle_utterance(
            "add some chicken to my cart",
            {"app": "Google Chrome", "url": "https://www.amazon.com/"})

        assert result["outcome"] == "ok"
        assert engine.route_calls == []
        assert planner.calls[0]["hint"] and "amazon.com" in planner.calls[0]["hint"]
        skills = _skills(server)
        assert len(skills) == 1
        assert skills[0][1]["name"] == "open_url"
        assert skills[0][1]["args"]["same_tab"] is True
        assert skills[0][1]["args"]["browser"] == "Google Chrome"
        assert not any(method == "act" and params.get("op") == "url"
                       for method, params in server.rpcs)

    _run(go())


def test_result_and_video_page_tasks_use_planner(tmp_path):
    async def run_case(utterance, url, name):
        engine = FakeEngine()
        planner = FakePlanner([['done "done"']])
        orch = _orch(tmp_path / name, engine=engine, planner=planner)
        result = await orch.handle_utterance(
            utterance, {"app": "Zen", "url": url})
        assert result["outcome"] == "ok"
        assert engine.route_calls == []
        assert len(planner.calls) == 1

    async def go():
        await run_case("click the first result",
                       "https://www.google.com/search?q=history", "google")
        await run_case("play the first video",
                       "https://www.youtube.com/results?search_query=history",
                       "youtube")

    _run(go())


def test_page_task_for_different_site_uses_engine(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"add chicken to my walmart cart": ("web_search", 0.99)},
            argmap={("web_search", "add chicken to my walmart cart"): {
                "query": "chicken walmart"}})
        planner = FakePlanner([['done "done"']])
        server = FakeServer()
        orch = _orch(
            tmp_path, server=server, engine=engine, planner=planner)

        result = await orch.handle_utterance(
            "add chicken to my walmart cart",
            {"app": "Google Chrome", "url": "https://www.amazon.com/"})

        assert result["outcome"] == "ok"
        assert engine.route_calls == ["add chicken to my walmart cart"]
        assert planner.calls == []
        assert "same_tab" not in _skills(server)[0][1]["args"]

    _run(go())


def test_compound_collection_disables_same_tab(tmp_path):
    orch = _orch(tmp_path)
    orch._ctx["app"] = "Zen"
    orch._collect = []
    args = {"url": "https://en.wikipedia.org/"}
    result = orch._same_tab_args(
        "open_url", args, "open wikipedia", {"decisions": []})
    assert result is args
    assert "same_tab" not in result
