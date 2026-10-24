import asyncio
import json

import pytest
import websockets

from bench.harness.proxy import BenchProxy


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


async def drain_queue(queue):
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items
