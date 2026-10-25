"""BrainServer: origin checks, protocol frames, confirm / config / memory
round trips (no orchestrator)."""

import asyncio

import pytest
import websockets
from websockets.exceptions import InvalidStatus

from brain import protocol
from brain.server import BrainServer


@pytest.mark.parametrize("origin", [
    "https://attacker.example", "http://localhost:3000",
    "http://127.0.0.1", "null", "", "localhost-native",
])
def test_browser_origins_rejected_before_dispatch(origin):
    async def scenario():
        server = BrainServer(port=0)
        calls = []

        async def utterance(*args):
            calls.append(args)

        server.on_utterance = utterance
        await server.start()
        try:
            with pytest.raises(InvalidStatus) as rejected:
                async with websockets.connect(
                        f"ws://127.0.0.1:{server.port}", origin=origin):
                    pytest.fail("browser handshake accepted")
            assert rejected.value.response.status_code == 403
            assert not server.connected
            assert not calls
        finally:
            await server.close()
    asyncio.run(scenario())


def test_native_no_origin_can_connect_and_confirm():
    async def scenario():
        server = BrainServer(port=0)
        await server.start()
        try:
            async with websockets.connect(f"ws://127.0.0.1:{server.port}") as native:
                await server.wait_connected()
                confirm = asyncio.create_task(server.ask_confirm("Send?"))
                message = protocol.parse(await native.recv())
                with pytest.raises(InvalidStatus):
                    async with websockets.connect(
                            f"ws://127.0.0.1:{server.port}", origin="https://attacker.example"):
                        pytest.fail("browser handshake accepted")
                assert server.connected and not confirm.done()
                await native.send(protocol.encode({"t": "confirm_reply",
                                                   "id": message["id"], "yes": True}))
                assert await confirm is True
        finally:
            await server.close()
    asyncio.run(scenario())


# ---------- protocol frames + confirm_cancel (ux-1) ----------

def test_protocol_ui_ms_and_confirm_cancel():
    assert protocol.ui("success", ms=212.4) == {"t": "ui", "mascot": "success",
                                               "ms": 212}
    assert "ms" not in protocol.ui("thinking")
    assert protocol.confirm_cancel("c1") == {"t": "confirm_cancel", "id": "c1"}


def test_confirm_timeout_sends_confirm_cancel():
    srv, sent = BrainServer(port=0), []

    async def send(m):
        sent.append(m)
    srv.send = send
    with pytest.raises(RuntimeError):
        asyncio.run(srv.ask_confirm("Send it?", timeout=0.01))
    assert sent[0]["t"] == "confirm"
    assert sent[1] == {"t": "confirm_cancel", "id": sent[0]["id"]}


def test_confirm_cancelled_task_sends_confirm_cancel():
    srv, sent = BrainServer(port=0), []

    async def send(m):
        sent.append(m)
    srv.send = send

    async def go():
        t = asyncio.create_task(srv.ask_confirm("Send it?"))
        await asyncio.sleep(0.01)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    asyncio.run(go())
    assert [m["t"] for m in sent] == ["confirm", "confirm_cancel"]


# ---------- config / memory frames ----------

def test_server_config_frame_ack(monkeypatch):
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


def test_server_memory_frame_reply(monkeypatch):
    async def go():
        server = BrainServer(port=0)
        sent = []

        async def send(msg):
            sent.append(msg)

        async def memory(msg):
            assert msg == {"t": "memory", "op": "list"}
            return {"items": [{
                "id": 1, "type": "fact", "key": "tea",
                "value": "green", "created": 1.0}]}

        monkeypatch.setattr(server, "send", send)
        server.on_memory = memory
        server._start_memory({"t": "memory", "op": "list"})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return sent

    assert asyncio.run(go()) == [{
        "t": "memory", "items": [{
            "id": 1, "type": "fact", "key": "tea",
            "value": "green", "created": 1.0}]}]
