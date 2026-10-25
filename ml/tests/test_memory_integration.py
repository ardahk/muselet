"""Memory integration tests with local fakes only."""

import asyncio
import json
import time

from brain.catalog import Catalog
from brain.memory import WorkingMemory
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


def test_wikipedia_followup_opens_focused_site_without_second_route(tmp_path):
    async def run():
        engine = FakeEngine(
            routes={"open wikipedia": ("open_url", 0.99)},
            argmap={("open_url", "open wikipedia"): {
                "url": "https://en.wikipedia.org/"}})
        server = FakeServer()
        tracer = Tracer(tmp_path / "traces")
        orch = Orchestrator(server, Catalog.load(), tracer, engine=engine)
        orch.memory = WorkingMemory()

        first = await orch.handle_utterance("open wikipedia", {"app": "Zen"})
        second = await orch.handle_utterance(
            "search for history", {"app": "Zen"})

        assert first["outcome"] == "ok"
        assert second["outcome"] == "ok"
        assert engine.route_calls == ["open wikipedia"]
        skills = server.skills()
        assert [call["name"] for call in skills] == ["open_url", "open_url"]
        assert skills[-1]["args"]["url"] == (
            "https://en.wikipedia.org/w/index.php?search=history")

        trace_file = next((tmp_path / "traces").glob("*.jsonl"))
        records = [json.loads(line) for line in
                   trace_file.read_text().splitlines()]
        memory = [item["memory.followup"]
                  for item in records[1]["decisions"]
                  if "memory.followup" in item]
        assert memory and memory[0]["path"] == "rule"
        return None

    asyncio.run(run())


def test_disabled_memory_routes_followup_normally(tmp_path):
    async def run():
        engine = FakeEngine(
            routes={"search for history": ("web_search", 0.99)},
            argmap={("web_search", "search for history"): {
                "query": "history"}})
        server = FakeServer()
        tracer = Tracer(tmp_path / "traces")
        orch = Orchestrator(server, Catalog.load(), tracer, engine=engine)
        orch.memory = WorkingMemory()
        orch.memory_enabled = False

        result = await orch.handle_utterance(
            "search for history", {"app": "Zen"})

        assert result["outcome"] == "ok"
        assert engine.route_calls == ["search for history"]
        assert server.skills()[-1]["name"] == "web_search"
        assert server.skills()[-1]["args"]["query"] == "history"
        record = json.loads(next((tmp_path / "traces").glob("*.jsonl"))
                            .read_text().splitlines()[0])
        assert not any("memory.followup" in item
                       for item in record["decisions"])

    asyncio.run(run())


def test_memory_ask_does_not_create_planner_pending_task(tmp_path):
    async def run():
        server = FakeServer()
        orch = Orchestrator(
            server, Catalog.load(), Tracer(tmp_path / "traces"))
        orch.memory = WorkingMemory()
        orch.memory.record(
            "move window left", "move window left", "window_layout",
            {"layout": "left"}, True, {"app": "Finder"},
            t=time.time())

        result = await orch.handle_utterance("undo", {"app": "Finder"})

        assert result["outcome"] == "awaiting_user"
        assert orch._pending_task is None

    asyncio.run(run())
