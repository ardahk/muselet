"""Memory integration tests with local fakes only."""

import asyncio
import json
import time

from brain.catalog import Catalog
from brain.memory import (
    MemoryStore, WorkingMemory, apply_longterm, eval_adapter, resolve,
)
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


def test_llm_gate_and_invalid_reasons_are_recorded_in_followup_trace(
        tmp_path, monkeypatch):
    class _ImmediateWorker:
        async def submit_async(self, fn, *args):
            return fn(*args)

    class _Planner:
        response = ""
        calls = 0

        def complete(self, _prompt, _tokens):
            self.calls += 1
            return self.response

    monkeypatch.setattr("brain.planner.worker", _ImmediateWorker)

    async def run():
        planner = _Planner()
        orch = Orchestrator(
            FakeServer(), Catalog.load(), Tracer(tmp_path / "traces"),
            longterm_store=MemoryStore(path=tmp_path / "memory.sqlite"))
        orch.longterm_enabled = False
        orch.planner = planner
        orch.memory = WorkingMemory()
        orch.memory.record(
            "open Finder", "open Finder", "open_app", {"app": "Finder"},
            True, {"app": "Finder"}, t=time.time())

        trace = {"decisions": []}
        gated = await orch._memory_followup(
            "search for best podcasts", trace)
        assert gated.reason == "llm-gated"
        assert planner.calls == 0
        assert trace["decisions"][-1]["memory.followup"]["reason"] == \
            "llm-gated"

        orch.memory = WorkingMemory()
        orch.memory.record(
            "search for history", "search for history", "web_search",
            {"query": "history"}, True, {"app": "Safari"}, t=time.time())
        planner.response = "open the second budget spreadsheet"
        trace = {"decisions": []}
        invalid = await orch._memory_followup("the other one", trace)
        assert invalid.reason == "llm-invalid"
        assert trace["decisions"][-1]["memory.followup"]["reason"] == \
            "llm-invalid"
        assert planner.calls == 1

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


def test_longterm_substitution_normalizes_keys_and_values():
    ctx = {"app": "Finder", "t": 10}
    wm = WorkingMemory()
    cases = [
        ("draft an email to the caterer asking about vegetarian options",
         {"type": "contact", "key": "the caterer",
          "value": "Rosa Delgado (rosa@example.com)"},
         "draft an email to Rosa Delgado asking about vegetarian options"),
        ("open my b roll folder",
         {"type": "folder", "key": "b-roll folder",
          "value": "~/Movies/Projects/B-Roll"},
         "open ~/Movies/Projects/B-Roll"),
        ("pull up the ci dashboard",
         {"type": "site", "key": "ci dashboard",
          "value": "https://ci.example.com/wavetable"},
         "open https://ci.example.com/wavetable"),
        ("start my practise timer",
         {"type": "preference", "key": "practice timer",
          "value": "25 minutes"},
         "start a 25 minutes timer"),
        ("put on my codeing music",
         {"type": "preference", "key": "coding music",
          "value": "Tycho"},
         "put on Tycho"),
        ("play my warm up playlist",
         {"type": "preference", "key": "warmup playlist",
          "value": "Scales and Arpeggios"},
         "play Scales and Arpeggios"),
    ]
    for utterance, row, expected in cases:
        result = resolve(utterance, wm, ctx, 10, longterm=[row])
        assert result.path == "rule"
        assert result.text == expected


def test_longterm_substitution_limits_count_and_single_word_matches():
    ctx = {"app": "Music", "t": 10}
    wm = WorkingMemory()
    rows = [
        {"type": "preference", "key": "coding music", "value": "Tycho"},
        {"type": "preference", "key": "focus music", "value": "Brown noise"},
        {"type": "preference", "key": "music", "value": "Jazz"},
    ]
    result = resolve(
        "play my codeing music and my focus music and music", wm, ctx, 10,
        longterm=rows)
    assert result.text == "play Tycho and Brown noise and music"
    assert resolve(
        "play music", wm, ctx, 10, longterm=[rows[-1]]).changed is False
    assert resolve(
        "play my music", wm, ctx, 10, longterm=[rows[-1]]).text == "play Jazz"
    file_in_email = resolve(
        "email my cousin saying the invite is ready", wm, ctx, 10,
        longterm=[{"type": "file", "key": "invite",
                   "value": "~/Documents/Invite.pages"}])
    assert file_in_email.changed is False


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


def test_forget_everything_wipes_memories_workflows_and_plan_bank(
        tmp_path, monkeypatch):
    from brain.plan_bank import Demo, PlanBank

    async def run():
        db_path = tmp_path / "memory.db"
        workflows_path = tmp_path / "workflows.jsonl"
        monkeypatch.setenv("MUSELET_MEMORY_DB", str(db_path))
        store = MemoryStore(db_path)
        fact = store.upsert("fact", "tea", "green tea")
        store.upsert("workflow", "morning routine", "open calendar")
        workflows_path.write_text(
            json.dumps({"goal": "open calendar", "source": "memory"}) + "\n",
            encoding="utf-8")
        server = FakeServer()
        orch = Orchestrator(
            server, Catalog.load(), Tracer(tmp_path / "traces"),
            longterm_store=store)

        def plan_bank():
            class Planner:
                pass

            planner = Planner()
            planner.plan_bank = PlanBank([
                Demo("Open Calendar", "Finder", "user", "app: Finder",
                     ["open Calendar"], source="memory"),
                Demo("Open Notes", "Finder", "v2-tune", "app: Finder",
                     ["open Notes"], source="v2"),
            ])
            return planner

        orch.planner = plan_bank()
        orch._last_memory_ids = [fact["id"]]
        assert orch.memory_request({"op": "clear"}) == {"items": []}
        assert store.list() == []
        assert not workflows_path.exists()
        assert [demo.source for demo in orch.planner.plan_bank.demos] == ["v2"]
        assert orch._last_memory_ids == []

        store.upsert("fact", "tea", "green tea")
        store.upsert("workflow", "morning routine", "open calendar")
        workflows_path.write_text(
            json.dumps({"goal": "open calendar", "source": "memory"}) + "\n",
            encoding="utf-8")
        orch.planner = plan_bank()
        orch._last_memory_ids = [1]
        orch.memory = WorkingMemory()
        server.confirm_yes = True
        await orch.handle_utterance("forget everything", {"app": "Finder"})
        assert store.list() == []
        assert not workflows_path.exists()
        assert [demo.source for demo in orch.planner.plan_bank.demos] == ["v2"]
        assert orch._last_memory_ids == []
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
