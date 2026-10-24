"""Integration test: real WebSocket, fake hands client."""

import asyncio
import json

import pytest
import websockets

from brain import protocol
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.server import BrainServer
from brain.traces import Tracer


class FakeHands:
    """A fake app-side hands client. Records every rpc, replies canned."""

    def __init__(self):
        self.ws = None
        self.rpcs: list[dict] = []
        self.messages: list[dict] = []
        self.task = None
        self.act_results = {}        # op -> result dict
        self.skill_fail = {}         # name -> error
        self.confirm_delay = 0.0
        self.confirm_yes = True
        self.sent_confirm_replies: list[str] = []

    async def connect(self, port: int):
        self.ws = await websockets.connect(f"ws://127.0.0.1:{port}")
        await self.ws.send(json.dumps(protocol.hello(
            [{"id": 1, "frame": [0, 0, 1512, 982], "scale": 2.0}])))
        self.task = asyncio.create_task(self._loop())

    async def close(self):
        if self.task:
            self.task.cancel()
        if self.ws:
            await self.ws.close()

    async def _loop(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            self.messages.append(msg)
            t = msg.get("t")
            if t == "rpc":
                self.rpcs.append(msg)
                reply = await self.reply(msg)
                await self.ws.send(json.dumps(reply))
            elif t == "confirm":
                async def answer(cid=msg["id"]):
                    if self.confirm_delay:
                        await asyncio.sleep(self.confirm_delay)
                    self.sent_confirm_replies.append(cid)
                    await self.ws.send(json.dumps(
                        protocol.confirm_reply(cid, self.confirm_yes)))
                asyncio.create_task(answer())

    async def reply(self, msg: dict) -> dict:
        rid, method, params = msg["id"], msg["method"], msg.get("params", {})
        if method == "observe":
            return protocol.rpc_result(rid, True, {
                "epoch": 1, "app": "Finder", "window": "Recents",
                "focused_ref": 4, "elements": [], "text": "obs", "ax_ms": 5})
        if method == "act":
            op = params.get("op")
            res = self.act_results.get(op, {
                "ok": True, "act_ms": 1, "settle_ms": 1, "epoch": 2})
            return protocol.rpc_result(rid, res.get("ok", True), res,
                                       res.get("error"))
        if method == "skill":
            name = params.get("name")
            if name in self.skill_fail:
                return protocol.rpc_result(rid, False, None,
                                           self.skill_fail[name])
            return protocol.rpc_result(rid, True,
                                       {"ok": True, "result": {}, "ms": 1})
        if method == "verify":
            return protocol.rpc_result(rid, True, {"ok": True, "observed": "x"})
        return protocol.rpc_result(rid, False, None, "unknown")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tracer(tmp_path):
    return Tracer(tmp_path / "traces")


def test_batch_execution_order(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        actions = [
            {"op": "wait", "ms": 1},
            {"op": "keys", "combo": "cmd+n"},
            {"op": "skill", "name": "mute", "args": {"on": True}},
            {"op": "done", "summary": "finished"},
        ]
        ok = await orch.execute_actions(actions)
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return ok, fake
    ok, fake = run(go())
    assert ok == "ok"
    # keys (act) + skill rpc; wait/done handled brain-side; "done" ends batch
    methods = [(m["method"], m["params"].get("op", m["params"].get("name")))
               for m in fake.rpcs]
    assert ("act", "keys") in methods
    assert ("skill", "mute") in methods
    # done was last -> nothing after it
    says = [m for m in fake.messages if m.get("t") == "say"]
    assert says and says[-1]["text"] == "finished"


def test_stop_on_failed_expect(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        fake.act_results["press"] = {"ok": False,
                                     "error": "expect_failed: window"}
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        actions = [
            {"op": "press", "ref": 4, "expect": 'title~"Recents"'},
            {"op": "keys", "combo": "cmd+n"},   # must never be sent
        ]
        ok = await orch.execute_actions(actions)
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return ok, fake
    ok, fake = run(go())
    assert ok == "failed"
    acts = [r for r in fake.rpcs if r["method"] == "act"]
    assert len(acts) == 1
    assert acts[0]["params"]["op"] == "press"
    # the expect string is forwarded to hands
    assert acts[0]["params"].get("expect") == 'title~"Recents"'


def test_confirm_flow_blocks_until_reply(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        fake.confirm_delay = 0.25     # reply yes after 250 ms
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        actions = [{"op": "skill", "name": "move_to_trash",
                    "args": {"path": "/tmp/definitely-not-real-xyz"}}]
        t0 = asyncio.get_running_loop().time()
        ok = await orch.execute_actions(actions)
        elapsed = asyncio.get_running_loop().time() - t0
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return ok, fake, elapsed
    ok, fake, elapsed = run(go())
    assert ok == "ok"
    # the confirm frame went out before the skill rpc, and the rpc waited
    kinds = [m.get("t") for m in fake.messages]
    assert kinds.index("confirm") < kinds.index("rpc")
    assert elapsed >= 0.25
    assert len(fake.sent_confirm_replies) == 1
    # confirmed flag reached the skill call
    skill_rpc = [m for m in fake.rpcs if m["method"] == "skill"][0]
    assert skill_rpc["params"]["args"]["confirmed"] is True
    assert skill_rpc["params"]["name"] == "move_to_trash"


def test_confirm_denied_cancels(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        fake.confirm_yes = False
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        ok = await orch.execute_actions(
            [{"op": "skill", "name": "compose_email",
              "args": {"to": "nobody", "body": "x"}}])
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return ok, fake
    ok, fake = run(go())
    assert ok == "cancelled"
    # confirm was asked but the skill rpc was never sent
    assert any(m.get("t") == "confirm" for m in fake.messages)
    assert not any(m["method"] == "skill" for m in fake.rpcs)


def test_utterance_routing_volume(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        await orch.handle_utterance("set volume to 30")
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return fake
    fake = run(go())
    skill = [m for m in fake.rpcs if m["method"] == "skill"]
    assert len(skill) == 1
    assert skill[0]["params"] == {"name": "set_volume",
                                "args": {"level": 30}}


def test_utterance_frame_over_ws(tracer):
    """A final utterance arriving over WS must get its rpc_results back.

    On the old code (on_utterance awaited inside the receive loop) this
    deadlocks: the handler can't read rpc_result while handling."""
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)

        async def cb(text, final, ctx=None):
            await orch.handle_utterance(text, ctx)
        server.on_utterance = cb
        await fake.ws.send(json.dumps(
            protocol.utterance("u1", "set volume to 40", True)))
        await asyncio.sleep(1.5)
        await fake.close()
        await server.close()
        return fake
    fake = run(go())
    skill = [m for m in fake.rpcs if m["method"] == "skill"]
    assert len(skill) == 1
    assert skill[0]["params"]["args"]["level"] == 40


def test_utterance_frame_cancel(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        fake.confirm_delay = 10.0       # confirm blocks forever-ish
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        server.on_utterance = lambda text, final, ctx=None: \
            orch.handle_utterance(text, ctx)
        await fake.ws.send(json.dumps(
            protocol.utterance("u1", "trash file x", True)))
        # router won't match -> fallback; use a direct batch for determinism:
        task = asyncio.get_running_loop().create_task(
            orch.execute_actions(
                [{"op": "skill", "name": "move_to_trash",
                  "args": {"path": "/tmp/x"}}]))
        await asyncio.sleep(0.3)
        server.cancel_utterance()   # 'cancel' frame would do the same
        task.cancel()
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return True
    assert run(go())


def test_script_confirm_policy():
    script_needs_confirm = Orchestrator.__new__(Orchestrator).script_needs_confirm
    assert script_needs_confirm("shell", "echo hi")
    assert script_needs_confirm("applescript", 'tell app "Finder" to empty trash')
    assert script_needs_confirm("jxa", "Application('Mail').quit()")
    assert not script_needs_confirm("applescript", 'tell app "Finder" to get name of window 1')
    assert not script_needs_confirm("jxa", "Application('Safari').get()")


def test_utterance_fallback_says(tracer):
    async def go():
        server = BrainServer(port=0)
        await server.start()
        fake = FakeHands()
        await fake.connect(server.port)
        await server.wait_connected(5)
        orch = Orchestrator(server, Catalog.load(), tracer)
        await orch.handle_utterance("recompile the kernel please")
        await asyncio.sleep(0.1)
        await fake.close()
        await server.close()
        return fake
    fake = run(go())
    # fallback: observe then say "I can't do that yet"
    assert any(m["method"] == "observe" for m in fake.rpcs)
    assert any(m.get("t") == "say" and "can't do that" in m["text"]
               for m in fake.messages)
