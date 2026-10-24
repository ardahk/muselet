"""App `config` frame -> `config_ack` (35B planner fallback toggle)."""

import asyncio
import json
from types import SimpleNamespace

import websockets

from brain.cli import apply_config
from brain.server import BrainServer


def test_apply_config_toggles_resident_escalate():
    resident = object()
    orch = SimpleNamespace(planner_escalate=resident)
    off = apply_config(orch, resident, {"t": "config", "escalate_planner": False})
    assert off == {"ok": True, "escalate_planner": False, "reason": "off"}
    assert orch.planner_escalate is None
    on = apply_config(orch, resident, {"t": "config", "escalate_planner": True})
    assert on == {"ok": True, "escalate_planner": True, "reason": "loaded"}
    assert orch.planner_escalate is resident


def test_apply_config_not_loaded():
    orch = SimpleNamespace(planner_escalate=None)
    ack = apply_config(orch, None, {"t": "config", "escalate_planner": True})
    assert ack["ok"] is False and ack["escalate_planner"] is False
    assert "ESCALATE=1" in ack["reason"]
    assert orch.planner_escalate is None


def _roundtrip(server_setup) -> dict:
    async def go():
        server = BrainServer(port=0)
        server_setup(server)
        await server.start()
        async with websockets.connect(f"ws://127.0.0.1:{server.port}") as ws:
            await ws.send(json.dumps({"t": "config", "escalate_planner": True}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), 5))
        await server.close()
        return reply
    return asyncio.run(go())


def test_server_replies_config_ack():
    async def on_config(msg):
        return {"ok": True, "escalate_planner": msg["escalate_planner"], "reason": "loaded"}
    reply = _roundtrip(lambda s: setattr(s, "on_config", on_config))
    assert reply == {"t": "config_ack", "ok": True, "escalate_planner": True, "reason": "loaded"}


def test_server_config_without_handler():
    reply = _roundtrip(lambda s: None)
    assert reply["t"] == "config_ack" and reply["ok"] is False
