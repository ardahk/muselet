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
