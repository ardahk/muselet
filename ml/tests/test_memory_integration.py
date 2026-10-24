"""Memory integration tests with local fakes only."""

import asyncio
import json
import time

from brain.catalog import Catalog
from brain.memory import MemoryStore, WorkingMemory, apply_longterm, eval_adapter
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


def test_longterm_substitution_is_comms_only_and_eval_none_is_unchanged():
    rows = [{"type": "person", "key": "mom", "value": "Jane Kim"}]
    assert apply_longterm("open_app Mom", rows) == "open_app Mom"
    assert apply_longterm("send a message to Mom", rows) == \
        "send a message to Jane Kim"

    history = []
    ctx = {"app": "Messages", "t": 10}
    baseline = eval_adapter("send a message to Mom", ctx, history)
    explicit_none = eval_adapter(
        "send a message to Mom", ctx, history, longterm=None)
    assert {key: baseline[key] for key in ("text", "changed", "path", "ask")} \
        == {key: explicit_none[key]
            for key in ("text", "changed", "path", "ask")}
    recalled = eval_adapter(
        "send a message to Mom", ctx, history, longterm=rows)
    assert "Jane Kim" in recalled["text"]


def test_memory_request_delete_and_clear_protocol_shape(tmp_path):
    async def run():
        store = MemoryStore(tmp_path / "memory.db")
        store.upsert("fact", "tea", "green tea")
        orch = Orchestrator(
            FakeServer(), Catalog.load(), Tracer(tmp_path / "traces"),
            longterm_store=store)
        listed = orch.memory_request({"op": "list"})
        assert set(listed["items"][0]) == {
            "id", "type", "key", "value", "created"}
        assert len(orch.memory_request({"op": "search", "q": "tea"})["items"]) == 1
        orch.memory_request({"op": "delete", "id": listed["items"][0]["id"]})
        assert orch.memory_request({"op": "list"})["items"] == []
        store.close()

    asyncio.run(run())


def test_voice_forget_requires_confirmation_and_supports_last_turn_ids(tmp_path):
    async def run():
        store = MemoryStore(tmp_path / "memory.db")
        store.upsert("fact", "tea", "green tea")
        server = FakeServer()
        orch = Orchestrator(
            server, Catalog.load(), Tracer(tmp_path / "traces"),
            longterm_store=store)
        orch.memory = WorkingMemory()

        server.confirm_yes = False
        await orch.handle_utterance("forget about tea", {"app": "Finder"})
        assert server.confirms[-1] == "Forget green tea?"
        assert len(store.list()) == 1

        server.confirm_yes = True
        await orch.handle_utterance("forget about tea", {"app": "Finder"})
        assert server.said[-1] == "Forgotten."
        assert store.list() == []

        row = store.upsert("fact", "tea", "green tea")
        orch._last_memory_ids = [row["id"]]
        await orch.handle_utterance("forget that", {"app": "Finder"})
        assert server.said[-1] == "Forgotten."
        assert store.list() == []

        await orch.handle_utterance("forget about tea", {"app": "Finder"})
        assert server.said[-1] == "I don't have anything about that."

        store.upsert("fact", "tea", "green tea")
        await orch.handle_utterance("forget everything", {"app": "Finder"})
        assert server.confirms[-1] == "Forget everything?"
        assert server.said[-1] == "Forgotten."
        assert store.list() == []
        store.close()

    asyncio.run(run())


def test_voice_recall_speaks_rendered_memory(tmp_path):
    async def run():
        store = MemoryStore(tmp_path / "memory.db")
        store.upsert("fact", "tea", "green tea", now=1)
        server = FakeServer()
        orch = Orchestrator(
            server, Catalog.load(), Tracer(tmp_path / "traces"),
            longterm_store=store)
        orch.memory = WorkingMemory()
        await orch.handle_utterance(
            "what do you remember about tea", {"app": "Finder"})
        assert server.said[-1] == "Memory: fact tea = green tea"
        store.close()

    asyncio.run(run())
