"""Wire-level HandsKit/Brain proxy used by live benchmark runners."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.server import ServerConnection

SAFETY_BLOCKED_ERROR = "blocked by bench safety guard"
SAFETY_SCRIPT_PATTERNS = (
    re.compile(r"\bsend(?:ing)?\b", re.IGNORECASE),
    re.compile(r"\binvit(?:e|es|ed|ing|ation)\b", re.IGNORECASE),
    re.compile(r"\battendees?\b", re.IGNORECASE),
)
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.IGNORECASE)


def _catalog_confirm_skills() -> set[str]:
    catalog_path = Path(__file__).resolve().parents[2] / "skills" / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        str(skill.get("name"))
        for skill in catalog.get("skills", [])
        if skill.get("risk") == "confirm"
    }


_CONFIRM_SKILLS = _catalog_confirm_skills()


def _decode(raw: str | bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _wall_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class CaseCapture:
    case_id: str = ""
    confirm_reply: bool | None = None
    frames: list[dict[str, Any]] = field(default_factory=list)
    utterance_monotonic: float | None = None
    utterance_wall: str | None = None
    first_action_monotonic: float | None = None
    terminal_monotonic: float | None = None
    confirm_count: int = 0
    confirm_cancelled: bool = False
    confirm_asked_unexpectedly: bool = False
    safety_blocked: bool = False
    safety_blocks: list[dict[str, Any]] = field(default_factory=list)
    active: bool = False
    utterance_event: asyncio.Event = field(default_factory=asyncio.Event)
    first_action_event: asyncio.Event = field(default_factory=asyncio.Event)
    terminal_event: asyncio.Event = field(default_factory=asyncio.Event)

    def record(self, direction: str, raw: str | bytes) -> dict[str, Any] | None:
        now = time.monotonic()
        frame = _decode(raw)
        self.frames.append({
            "direction": direction,
            "monotonic": now,
            "wall_time": _wall_time(),
            "frame": frame if frame is not None else repr(raw),
        })
        return frame

    def as_dict(self) -> dict[str, Any]:
        elapsed = None
        if self.utterance_monotonic is not None and self.first_action_monotonic is not None:
            elapsed = max(0.0, self.first_action_monotonic - self.utterance_monotonic)
        return {
            "case_id": self.case_id,
            "utterance_wall": self.utterance_wall,
            "first_action_latency_s": elapsed,
            "confirm_count": self.confirm_count,
            "confirm_cancelled": self.confirm_cancelled,
            "confirm_asked_unexpectedly": self.confirm_asked_unexpectedly,
            "safety_blocked": self.safety_blocked,
            "safety_blocks": list(self.safety_blocks),
            "frames": list(self.frames),
        }


class BenchProxy:
    """One-client-at-a-time WS proxy with runner-controlled script RPCs."""

    def __init__(
        self,
        brain_url: str = "ws://127.0.0.1:8765",
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        safety_guard: bool = True,
    ):
        parsed = urlsplit(brain_url)
        if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
            raise ValueError(f"invalid brain WebSocket URL: {brain_url!r}")
        self.brain_url = brain_url
        self.host = host
        self.port = port
        self.safety_guard = safety_guard
        self._server = None
        self._hands: ServerConnection | None = None
        self._brain: ClientConnection | None = None
        self._connected = asyncio.Event()
        self._disconnected = asyncio.Event()
        self._disconnected.set()
        self._connection_lock = asyncio.Lock()
        self._pending_scripts: dict[str, asyncio.Future] = {}
        self._pending_rpcs: dict[str, asyncio.Future] = {}
        self._script_seq = 0
        self._allowed_confirm_skills: set[str] = set()
        self.capture = CaseCapture()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def start(self) -> "BenchProxy":
        if self._server is not None:
            return self
        self._server = await websockets.serve(
            self._handle_hands, self.host, self.port, max_size=None
        )
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for connection in (self._hands, self._brain):
            if connection is not None:
                await connection.close()
        self._hands = None
        self._brain = None
        self._connected.clear()
        self._disconnected.set()
        for future in (*self._pending_scripts.values(), *self._pending_rpcs.values()):
            if not future.done():
                future.set_exception(ConnectionError("proxy closed"))
        self._pending_scripts.clear()
        self._pending_rpcs.clear()

    async def __aenter__(self) -> "BenchProxy":
        return await self.start()

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def begin_case(
        self,
        case_id: str,
        confirm_reply: bool | None,
        *,
        allow_confirm_skills: set[str] | None = None,
    ) -> None:
        if self._hands is not None or self._brain is not None:
            raise RuntimeError("cannot begin a case while a HandsKit client is connected")
        self.capture = CaseCapture(case_id=case_id, confirm_reply=confirm_reply)
        self._allowed_confirm_skills = set(allow_confirm_skills or ())

    def _blocked_reason(self, frame: dict[str, Any]) -> str | None:
        if not self.safety_guard:
            return None
        method = frame.get("method")
        params = frame.get("params")
        if not isinstance(params, dict):
            params = {}
        if method == "skill":
            name = str(params.get("name", ""))
            if name in {"send_message", "compose_email"}:
                return "communications skill"
            if name in _CONFIRM_SKILLS and name not in getattr(
                self, "_allowed_confirm_skills", set()
            ):
                return "confirm-risk skill"
            if name == "create_event":
                args = params.get("args")
                if isinstance(args, dict):
                    for key, value in args.items():
                        if re.search(r"attendee|invitee|e-?mail", str(key), re.IGNORECASE):
                            return "event attendee or email arguments"
                        if isinstance(value, str) and _EMAIL_PATTERN.search(value):
                            return "event email argument"
        if method == "act" and params.get("op") == "script":
            code = str(params.get("code", ""))
            if any(pattern.search(code) for pattern in SAFETY_SCRIPT_PATTERNS):
                return "suspicious script"
        return None

    async def _block_rpc(self, brain: ClientConnection, frame: dict[str, Any], reason: str) -> None:
        request_id = str(frame.get("id", ""))
        self.capture.safety_blocked = True
        block = {"id": request_id, "reason": reason, "method": frame.get("method")}
        self.capture.safety_blocks.append(block)
        response = {
            "t": "rpc_result",
            "id": request_id,
            "ok": False,
            "error": SAFETY_BLOCKED_ERROR,
        }
        self.capture.frames.append({
            "direction": "proxy_to_brain",
            "monotonic": time.monotonic(),
            "wall_time": _wall_time(),
            "frame": response,
            "safety_blocked": True,
            "reason": reason,
        })
        await brain.send(json.dumps(response))

    async def wait_connected(self, timeout: float = 20) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def wait_disconnected(self, timeout: float = 10) -> None:
        await asyncio.wait_for(self._disconnected.wait(), timeout)

    def mark_utterance_finished(self) -> None:
        self.capture.active = False
        if self.capture.terminal_monotonic is None:
            self.capture.terminal_monotonic = time.monotonic()
            self.capture.terminal_event.set()

    async def wait_for_utterance(self, timeout: float = 20) -> None:
        await asyncio.wait_for(self.capture.utterance_event.wait(), timeout)

    async def wait_for_first_action(self, timeout: float | None = None) -> bool:
        if self.capture.first_action_event.is_set():
            return True
        try:
            if timeout is None:
                await self.capture.first_action_event.wait()
            else:
                await asyncio.wait_for(self.capture.first_action_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def wait_for_terminal(self, timeout: float | None = None) -> bool:
        if self.capture.terminal_event.is_set():
            return True
        try:
            if timeout is None:
                await self.capture.terminal_event.wait()
            else:
                await asyncio.wait_for(self.capture.terminal_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def run_script(
        self,
        lang: str,
        code: str,
        timeout: float = 20,
        *,
        allow_inflight: bool = False,
    ) -> dict[str, Any]:
        if lang not in ("applescript", "jxa", "shell"):
            raise ValueError(f"unsupported script language {lang!r}")
        if self.capture.active and not allow_inflight:
            raise RuntimeError("script RPC is only allowed between utterances")
        await self.wait_connected(timeout)
        hands = self._hands
        if hands is None:
            raise ConnectionError("HandsKit client disconnected")
        self._script_seq += 1
        request_id = f"bench-{self._script_seq}"
        future = asyncio.get_running_loop().create_future()
        self._pending_scripts[request_id] = future
        request = {
            "t": "rpc",
            "id": request_id,
            "method": "act",
            "params": {"op": "script", "lang": lang, "code": code},
        }
        self.capture.frames.append({
            "direction": "runner_to_hands",
            "monotonic": time.monotonic(),
            "wall_time": _wall_time(),
            "frame": request,
        })
        try:
            await hands.send(json.dumps(request, ensure_ascii=False))
            reply = await asyncio.wait_for(future, timeout)
        finally:
            self._pending_scripts.pop(request_id, None)
        result = reply.get("result")
        if not isinstance(result, dict):
            result = {}
        result.setdefault("ok", bool(reply.get("ok")))
        if not result["ok"]:
            raise RuntimeError(str(result.get("error") or reply.get("error") or "script RPC failed"))
        return result

    async def run_skill(
        self,
        name: str,
        args: dict[str, Any],
        timeout: float = 20,
        *,
        allow_inflight: bool = False,
    ) -> dict[str, Any]:
        if self.capture.active and not allow_inflight:
            raise RuntimeError("skill RPC is only allowed between utterances")
        await self.wait_connected(timeout)
        hands = self._hands
        if hands is None:
            raise ConnectionError("HandsKit client disconnected")
        self._script_seq += 1
        request_id = f"bench-{self._script_seq}"
        future = asyncio.get_running_loop().create_future()
        self._pending_rpcs[request_id] = future
        request = {
            "t": "rpc",
            "id": request_id,
            "method": "skill",
            "params": {"name": name, "args": args},
        }
        self.capture.frames.append({
            "direction": "runner_to_hands",
            "monotonic": time.monotonic(),
            "wall_time": _wall_time(),
            "frame": request,
        })
        try:
            await hands.send(json.dumps(request, ensure_ascii=False))
            reply = await asyncio.wait_for(future, timeout)
        finally:
            self._pending_rpcs.pop(request_id, None)
        result = reply.get("result")
        if not isinstance(result, dict):
            result = {}
        result.setdefault("ok", bool(reply.get("ok")))
        if not result["ok"]:
            raise RuntimeError(str(result.get("error") or reply.get("error") or "skill RPC failed"))
        return result

    def snapshot(self) -> dict[str, Any]:
        return self.capture.as_dict()

    async def _handle_hands(self, hands: ServerConnection) -> None:
        async with self._connection_lock:
            if self._hands is not None:
                await hands.close(1013, "benchmark proxy handles one HandsKit client at a time")
                return
            self._hands = hands
            self._disconnected.clear()
            brain = None
            try:
                brain = await websockets.connect(self.brain_url, max_size=None)
                self._brain = brain
                self._connected.set()
                await self._forward_pair(hands, brain)
            except (OSError, websockets.WebSocketException) as exc:
                self.capture.frames.append({
                    "direction": "proxy_error",
                    "monotonic": time.monotonic(),
                    "wall_time": _wall_time(),
                    "frame": {"error": str(exc)},
                })
            finally:
                self._connected.clear()
                self._hands = None
                self._brain = None
                self._disconnected.set()
                for future in (*self._pending_scripts.values(), *self._pending_rpcs.values()):
                    if not future.done():
                        future.set_exception(ConnectionError("HandsKit disconnected"))
                self._pending_scripts.clear()
                self._pending_rpcs.clear()
                if brain is not None:
                    await brain.close()

    async def _forward_pair(
        self, hands: ServerConnection, brain: ClientConnection
    ) -> None:
        tasks = (
            asyncio.create_task(self._hands_to_brain(hands, brain)),
            asyncio.create_task(self._brain_to_hands(brain, hands)),
        )
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                exception = task.exception()
                if exception is not None:
                    raise exception
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _hands_to_brain(
        self, hands: ServerConnection, brain: ClientConnection
    ) -> None:
        async for raw in hands:
            frame = self.capture.record("hands_to_brain", raw)
            if frame is None:
                await brain.send(raw)
                continue
            if frame.get("t") == "rpc_result":
                request_id = str(frame.get("id", ""))
                future = self._pending_scripts.get(request_id) or self._pending_rpcs.get(request_id)
                if future is not None:
                    if not future.done():
                        future.set_result(frame)
                    continue
            if frame.get("t") == "utterance" and frame.get("final", True):
                self.capture.utterance_monotonic = time.monotonic()
                self.capture.utterance_wall = _wall_time()
                self.capture.active = True
                self.capture.utterance_event.set()
            await brain.send(raw)

    async def _brain_to_hands(
        self, brain: ClientConnection, hands: ServerConnection
    ) -> None:
        async for raw in brain:
            frame = self.capture.record("brain_to_hands", raw)
            if frame is None:
                await hands.send(raw)
                continue
            if frame.get("t") == "confirm":
                self.capture.confirm_count += 1
                reply = self.capture.confirm_reply
                if reply is None:
                    self.capture.confirm_asked_unexpectedly = True
                    reply = False
                response = {
                    "t": "confirm_reply",
                    "id": frame.get("id"),
                    "yes": reply,
                }
                self.capture.frames.append({
                    "direction": "proxy_to_brain",
                    "monotonic": time.monotonic(),
                    "wall_time": _wall_time(),
                    "frame": response,
                })
                await brain.send(json.dumps(response))
                continue
            if frame.get("t") == "confirm_cancel":
                self.capture.confirm_cancelled = True
                if self.capture.terminal_monotonic is None:
                    self.capture.terminal_monotonic = time.monotonic()
                    self.capture.active = False
                    self.capture.terminal_event.set()
                self.capture.frames.append({
                    "direction": "proxy_observation",
                    "monotonic": time.monotonic(),
                    "wall_time": _wall_time(),
                    "frame": {"t": "confirm_cancel", "id": frame.get("id")},
                })
            if frame.get("t") == "rpc":
                method = frame.get("method")
                request_id = str(frame.get("id", ""))
                reason = self._blocked_reason(frame)
                if reason:
                    await self._block_rpc(brain, frame, reason)
                    continue
                if method in ("act", "skill") and not request_id.startswith("bench-"):
                    params = frame.get("params")
                    params = params if isinstance(params, dict) else {}
                    is_ocr = method == "ocr" or (
                        method == "act" and str(params.get("op", "")).casefold() == "ocr"
                    )
                    if not is_ocr and self.capture.first_action_monotonic is None:
                        self.capture.first_action_monotonic = time.monotonic()
                        self.capture.first_action_event.set()
            if frame.get("t") == "ui" and frame.get("mascot") in (
                "success", "confused", "sleeping"
            ):
                if self.capture.terminal_monotonic is None:
                    self.capture.terminal_monotonic = time.monotonic()
                    self.capture.active = False
                    self.capture.terminal_event.set()
            await hands.send(raw)
