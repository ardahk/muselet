"""WebSocket server on ws://127.0.0.1:8765 — one app connection."""

import asyncio
import itertools
import logging

import websockets

from . import protocol

log = logging.getLogger("brain.server")


class BrainServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._ws = None
        self._server = None
        self._seq = itertools.count(1)
        self._pending: dict[str, asyncio.Future] = {}
        self._confirms: dict[str, asyncio.Future] = {}
        self._connected = asyncio.Event()
        self._utterance_task: asyncio.Task | None = None
        self.on_utterance = None      # async cb(text, final)
        self.on_hello = None          # async cb(screens)
        self.on_cancel = None         # async cb()

    async def start(self):
        self._server = await websockets.serve(self._handler, self.host, self.port)
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]
        log.info("brain ws listening on ws://%s:%d", self.host, self.port)

    async def close(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def wait_connected(self, timeout: float = 30):
        await asyncio.wait_for(self._connected.wait(), timeout)

    def cancel_utterance(self):
        """Cancel the currently running utterance task, if any."""
        if self._utterance_task and not self._utterance_task.done():
            self._utterance_task.cancel()

    def _start_utterance(self, text: str):
        """One utterance at a time: cancel any in-flight task, then start."""
        self.cancel_utterance()
        if self.on_utterance is None:
            return

        async def runner():
            try:
                await self.on_utterance(text, True)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("utterance handler failed")

        self._utterance_task = asyncio.get_running_loop().create_task(runner())

    async def _handler(self, ws):
        if self._ws is not None:
            log.warning("second app connection rejected")
            await ws.close(1013, "only one app connection")
            return
        self._ws = ws
        self._connected.set()
        log.info("app connected")
        try:
            async for raw in ws:
                try:
                    msg = protocol.parse(raw)
                except Exception:
                    log.warning("bad frame: %r", raw[:80])
                    continue
                t = msg.get("t")
                if t == "rpc_result":
                    fut = self._pending.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                elif t == "confirm_reply":
                    fut = self._confirms.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(bool(msg.get("yes")))
                elif t == "hello":
                    log.info("hello: %s", msg)
                    if self.on_hello:
                        await self.on_hello(msg.get("screens", []))
                elif t == "utterance":
                    # Run handling as a task so the receive loop keeps
                    # reading rpc_result frames (avoids deadlock).
                    if msg.get("final"):
                        self._start_utterance(msg.get("text", ""))
                elif t == "cancel":
                    self.cancel_utterance()
                    if self.on_cancel:
                        await self.on_cancel()
        finally:
            log.info("app disconnected")
            self._ws = None
            self._connected.clear()
            self.cancel_utterance()
            for f in self._pending.values():
                if not f.done():
                    f.set_result({"t": "rpc_result", "ok": False,
                                  "error": "app disconnected"})
            self._pending.clear()

    async def send(self, msg: dict):
        ws = self._ws
        if ws is None:
            raise ConnectionError("app not connected")
        await ws.send(protocol.encode(msg))

    async def rpc(self, method: str, params: dict, timeout: float = 30):
        """Send an rpc and await the correlated rpc_result.

        Returns the result payload (a dict with "ok" merged in for act/skill/
        verify results) whenever the app produced one — including failures
        that carry a result. Raises RuntimeError only on timeout, disconnect,
        or a result-less error (unknown method, bad params)."""
        rid = f"r{next(self._seq)}"
        fut = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self.send(protocol.rpc(rid, method, params))
        try:
            reply = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"rpc {method} timed out")
        finally:
            self._pending.pop(rid, None)
        if reply.get("ok"):
            res = reply.get("result")
            if isinstance(res, dict):
                res.setdefault("ok", True)
            return res
        if reply.get("result") is not None:
            res = reply["result"]
            if isinstance(res, dict):
                res.setdefault("ok", False)
            return res
        raise RuntimeError(reply.get("error", "rpc failed"))

    async def ask_confirm(self, summary: str, timeout: float = 120) -> bool:
        """Send {"t":"confirm"} and wait for confirm_reply."""
        cid = f"c{next(self._seq)}"
        fut = asyncio.get_running_loop().create_future()
        self._confirms[cid] = fut
        await self.send(protocol.confirm(cid, summary))
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._confirms.pop(cid, None)
            raise RuntimeError("confirm timed out")

    async def say(self, text: str):
        await self.send(protocol.say(text))

    async def ui(self, mascot: str, bubble: str | None = None):
        await self.send(protocol.ui(mascot, bubble))
