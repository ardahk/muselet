import asyncio
import json

import pytest
import websockets

from bench.harness.proxy import BenchProxy, SAFETY_BLOCKED_ERROR


def test_proxy_forwards_frames_consumes_script_rpc_and_measures_first_action():
    async def scenario():
        brain_frames = asyncio.Queue()
        brain_ws = asyncio.Queue()

        async def brain_handler(ws):
            brain_ws.put_nowait(ws)
            async for raw in ws:
                brain_frames.put_nowait(json.loads(raw))

        async with websockets.serve(brain_handler, "127.0.0.1", 0) as brain_server:
            brain_port = brain_server.sockets[0].getsockname()[1]
            async with BenchProxy(f"ws://127.0.0.1:{brain_port}") as proxy:
                await proxy.begin_case("proxy-test", False)

                async def hands_client():
                    async with websockets.connect(proxy.url) as hands:
                        await hands.send(json.dumps({"t": "hello", "screens": []}))
                        await proxy.wait_connected()
                        script = asyncio.create_task(
                            proxy.run_script("shell", "printf runner-script")
                        )
                        injected = json.loads(await asyncio.wait_for(hands.recv(), 1))
                        assert injected["id"] == "bench-1"
                        await hands.send(json.dumps({
                            "t": "rpc_result",
                            "id": injected["id"],
                            "ok": True,
                            "result": {"ok": True, "output": "runner-script"},
                        }))
                        assert (await script)["output"] == "runner-script"

                        await hands.send(json.dumps({
                            "t": "utterance", "id": "u1", "text": "check", "final": True,
                        }))
                        while True:
                            raw = await hands.recv()
                            frame = json.loads(raw)
                            if frame.get("t") == "rpc":
                                await hands.send(json.dumps({
                                    "t": "rpc_result", "id": frame["id"], "ok": True,
                                    "result": {"ok": True},
                                }))
                            elif frame.get("t") == "ui":
                                break

                client = asyncio.create_task(hands_client())
                assert (await asyncio.wait_for(brain_frames.get(), 1))["t"] == "hello"
                assert (await asyncio.wait_for(brain_frames.get(), 1))["t"] == "utterance"
                assert not proxy.capture.first_action_event.is_set()
                brain = await asyncio.wait_for(brain_ws.get(), 1)
                await brain.send(json.dumps({
                    "t": "rpc", "id": "r-observe", "method": "observe", "params": {},
                }))
                assert (await asyncio.wait_for(brain_frames.get(), 1))["t"] == "rpc_result"
                assert not proxy.capture.first_action_event.is_set()
                await brain.send(json.dumps({
                    "t": "rpc", "id": "r-act", "method": "act", "params": {"op": "press"},
                }))
                assert (await asyncio.wait_for(brain_frames.get(), 1))["id"] == "r-act"
                assert await proxy.wait_for_first_action(1)
                await brain.send(json.dumps({"t": "ui", "mascot": "success"}))
                await asyncio.wait_for(client, 1)
                snapshot = proxy.snapshot()
                assert snapshot["first_action_latency_s"] is not None
                assert not any(
                    f.get("id", "").startswith("bench-")
                    for f in await drain_queue(brain_frames)
                )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("confirm_reply", "expected", "unexpected"),
    [(True, True, False), (False, False, False), (None, False, True)],
)
def test_proxy_confirm_replies_are_intercepted(confirm_reply, expected, unexpected):
    async def scenario():
        confirm_result = asyncio.Future()
        brain_ws = asyncio.Queue()

        async def brain_handler(ws):
            brain_ws.put_nowait(ws)
            async for raw in ws:
                frame = json.loads(raw)
                if frame.get("t") == "confirm_reply":
                    confirm_result.set_result(frame)

        async with websockets.serve(brain_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with BenchProxy(f"ws://127.0.0.1:{port}") as proxy:
                await proxy.begin_case("confirm", confirm_reply)

                async def hands_client():
                    async with websockets.connect(proxy.url) as hands:
                        await hands.send(json.dumps({"t": "hello"}))
                        await proxy.wait_connected()
                        await hands.send(json.dumps({
                            "t": "utterance", "id": "u1", "text": "confirm", "final": True,
                        }))
                        await asyncio.sleep(0.2)

                client = asyncio.create_task(hands_client())
                brain = await asyncio.wait_for(brain_ws.get(), 1)
                await brain.send(json.dumps({"t": "confirm", "id": "c1", "summary": "Send?"}))
                reply = await asyncio.wait_for(confirm_result, 1)
                assert reply == {"t": "confirm_reply", "id": "c1", "yes": expected}
                assert proxy.capture.confirm_asked_unexpectedly is unexpected
                await client

    asyncio.run(scenario())


def test_proxy_confirm_cancel_ends_confirmation_wait():
    async def scenario():
        brain_ws = asyncio.Queue()

        async def brain_handler(ws):
            brain_ws.put_nowait(ws)
            async for _raw in ws:
                pass

        async with websockets.serve(brain_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with BenchProxy(f"ws://127.0.0.1:{port}") as proxy:
                await proxy.begin_case("confirm-cancel", False)
                async def hands_client():
                    async with websockets.connect(proxy.url) as hands:
                        await hands.send(json.dumps({"t": "hello"}))
                        await proxy.wait_connected()
                        await asyncio.sleep(1)

                client = asyncio.create_task(hands_client())
                brain = await asyncio.wait_for(brain_ws.get(), 1)
                await brain.send(json.dumps({"t": "confirm_cancel", "id": "c1"}))
                await asyncio.wait_for(proxy.capture.terminal_event.wait(), 1)
                snapshot = proxy.snapshot()
                assert snapshot["confirm_cancelled"] is True
                assert snapshot["frames"][-1]["frame"]["t"] == "confirm_cancel"
                client.cancel()

    asyncio.run(scenario())


def test_safety_guard_returns_failures_without_forwarding_blocked_rpcs():
    blocked_requests = [
        {"method": "skill", "params": {"name": "send_message", "args": {}}},
        {"method": "skill", "params": {"name": "compose_email", "args": {}}},
        {"method": "skill", "params": {"name": "move_to_trash", "args": {}}},
        {"method": "skill", "params": {"name": "create_event", "args": {"attendee": "Alex"}}},
        {"method": "skill", "params": {"name": "create_event", "args": {"invitee": "Alex"}}},
        {"method": "skill", "params": {"name": "create_event", "args": {"email": "a@example.com"}}},
        {"method": "skill", "params": {"name": "create_event", "args": {"notes": "a@example.com"}}},
        {"method": "act", "params": {"op": "script", "code": "send message"}},
        {"method": "act", "params": {"op": "script", "code": "invite Alex"}},
        {"method": "act", "params": {"op": "script", "code": "list attendees"}},
    ]

    async def scenario():
        incoming = asyncio.Queue()
        brain_ws = asyncio.Queue()
        hands_received = asyncio.Queue()
        stop = asyncio.Event()

        async def brain_handler(ws):
            brain_ws.put_nowait(ws)
            async for raw in ws:
                incoming.put_nowait(json.loads(raw))

        async with websockets.serve(brain_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with BenchProxy(f"ws://127.0.0.1:{port}") as proxy:
                await proxy.begin_case("safety", False)

                async def hands_client():
                    async with websockets.connect(proxy.url) as hands:
                        await hands.send(json.dumps({"t": "hello"}))
                        await proxy.wait_connected()
                        await hands.send(json.dumps({
                            "t": "utterance", "id": "u1", "text": "blocked", "final": True,
                        }))
                        while not stop.is_set():
                            try:
                                raw = await asyncio.wait_for(hands.recv(), 0.02)
                            except asyncio.TimeoutError:
                                continue
                            hands_received.put_nowait(json.loads(raw))

                client = asyncio.create_task(hands_client())
                brain = await asyncio.wait_for(brain_ws.get(), 1)
                assert (await asyncio.wait_for(incoming.get(), 1))["t"] == "hello"
                assert (await asyncio.wait_for(incoming.get(), 1))["t"] == "utterance"
                for index, request in enumerate(blocked_requests):
                    request_id = f"unsafe-{index}"
                    await brain.send(json.dumps({
                        "t": "rpc", "id": request_id, **request,
                    }))
                    response = await asyncio.wait_for(incoming.get(), 1)
                    assert response == {
                        "t": "rpc_result", "id": request_id, "ok": False,
                        "error": SAFETY_BLOCKED_ERROR,
                    }
                await asyncio.sleep(0.05)
                stop.set()
                await asyncio.wait_for(client, 1)
                assert hands_received.empty()
                capture = proxy.snapshot()
                assert capture["safety_blocked"] is True
                assert len(capture["safety_blocks"]) == len(blocked_requests)

    asyncio.run(scenario())


async def drain_queue(queue):
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def test_close_bounded_aborts_peer_that_never_answers():
    from bench.harness.proxy import _close_bounded

    class Transport:
        def __init__(self):
            self.aborted = False

        def abort(self):
            self.aborted = True

    class HangingConnection:
        def __init__(self):
            self.transport = Transport()

        async def close(self):
            await asyncio.sleep(60)

    async def scenario():
        connection = HangingConnection()
        started = asyncio.get_running_loop().time()
        await _close_bounded(connection, timeout=0.05)
        assert asyncio.get_running_loop().time() - started < 10
        assert connection.transport.aborted

    asyncio.run(scenario())


