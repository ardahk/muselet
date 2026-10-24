"""Hands CLI process lifecycle shared by live and replay benchmarks."""

from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from bench.harness.core import HarnessTimeout


CLIENT_PROCESSES: set[subprocess.Popen] = set()


@lru_cache(maxsize=None)
def serve_timeout_supported(hands_bin: str) -> bool:
    try:
        result = subprocess.run(
            [hands_bin, "serve", "--help"],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "--timeout" in (result.stdout or "") + (result.stderr or "")


async def _terminate_process(process: subprocess.Popen, grace: float = 2.0) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            await asyncio.to_thread(process.wait, timeout=grace)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait, timeout=grace)
    CLIENT_PROCESSES.discard(process)


async def kill_registered_clients() -> None:
    for process in tuple(CLIENT_PROCESSES):
        await _terminate_process(process)


async def release_slot_for_case(proxy: Any) -> bool:
    try:
        if await proxy.release_slot(5.0):
            return True
    except Exception:
        pass
    await kill_registered_clients()
    try:
        return await proxy.release_slot(5.0)
    except Exception:
        return False


def _serve_summary(path: Path | None, exit_code: int | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    summary = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("t") == "serve_summary":
            summary = record
    if summary is not None:
        summary["exit_code"] = exit_code
    return summary


class HandsRuntime:
    def __init__(
        self,
        proxy: Any,
        hands_bin: str,
        log_dir: Path,
        case_id: str,
        *,
        cwd: Path | None = None,
    ):
        self.proxy = proxy
        self.hands_bin = hands_bin
        self.log_dir = log_dir
        self.case_id = case_id
        self.cwd = cwd
        self.process: subprocess.Popen | None = None
        self.log = None
        self.log_path: Path | None = None
        self._client_seq = 0
        self.hands_serve_timeout_flag = serve_timeout_supported(hands_bin)
        self.hands_serve_summary: dict[str, Any] | None = None

    @property
    def utterance_monotonic(self) -> float | None:
        return self.proxy.capture.utterance_monotonic

    @property
    def first_action_monotonic(self) -> float | None:
        return self.proxy.capture.first_action_monotonic

    @property
    def terminal_monotonic(self) -> float | None:
        return self.proxy.capture.terminal_monotonic

    def snapshot(self) -> dict[str, Any]:
        return self.proxy.snapshot()

    def mark_utterance_finished(self) -> None:
        self.proxy.mark_utterance_finished()

    async def start_scripts(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        await self._release_before_start("start_scripts")
        await self._start_client()
        await self._wait_for("wait_connected", self.proxy.wait_connected)

    async def start_utterance(self, utterance: str, timeout_s: float = 30) -> None:
        await self._stop_client()
        await self._wait_for("wait_disconnected", self.proxy.wait_disconnected)
        await self._release_before_start("start_utterance")
        await self._start_client(utterance, timeout_s=timeout_s)
        await self._wait_for("wait_for_utterance", self.proxy.wait_for_utterance)

    async def start_turns(self, utterances: list[str], timeout_s: float = 30) -> None:
        """One HandsKit client sends every turn on one WebSocket; the proxy gates each."""
        await self._stop_client()
        await self._wait_for("wait_disconnected", self.proxy.wait_disconnected)
        await self._release_before_start("start_turns")
        self.proxy.gate_turns()
        await self._start_client(list(utterances), timeout_s=timeout_s)
        await self._wait_for("wait_for_utterance", self.proxy.wait_for_utterance)

    def begin_turn(self, confirm_reply: bool | None) -> None:
        self.proxy.begin_turn(confirm_reply)

    async def wait_next_turn(self, timeout_s: float = 20) -> bool:
        return await self.proxy.wait_for_held_utterance(timeout_s)

    async def send_next_turn(self) -> None:
        if not await self.proxy.release_held_utterance():
            raise RuntimeError("no held utterance to send")
        await self._wait_for("wait_for_utterance", self.proxy.wait_for_utterance)

    async def _wait_for(self, stage: str, wait, *args, **kwargs):
        try:
            return await wait(*args, **kwargs)
        except asyncio.TimeoutError as exc:
            slot_released = await self.recover()
            raise HarnessTimeout(stage, slot_released) from exc

    async def _release_before_start(self, stage: str) -> None:
        if await self.proxy.release_slot(5.0):
            return
        slot_released = await self.recover()
        if not slot_released:
            raise HarnessTimeout(stage, False)

    async def recover(self) -> bool:
        await self._terminate_client()
        return await self.proxy.release_slot(5.0)

    async def run_script(
        self, lang: str, code: str, *, allow_inflight: bool = False
    ) -> dict[str, Any]:
        if self.process is None or self.process.poll() is not None:
            await self.start_scripts()
        return await self.proxy.run_script(
            lang, code, allow_inflight=allow_inflight
        )

    async def run_skill(
        self, name: str, args: dict[str, Any], *, allow_inflight: bool = False
    ) -> dict[str, Any]:
        if self.process is None or self.process.poll() is not None:
            await self.start_scripts()
        return await self.proxy.run_skill(
            name, args, allow_inflight=allow_inflight
        )

    async def run_rpc(
        self, method: str, params: dict[str, Any], *, allow_inflight: bool = False
    ) -> dict[str, Any]:
        if self.process is None or self.process.poll() is not None:
            await self.start_scripts()
        return await self.proxy.run_rpc(
            method, params, allow_inflight=allow_inflight
        )

    async def prepare_for_cleanup(self) -> None:
        if self.proxy.capture.active:
            await self._stop_client()
            self.proxy.mark_utterance_finished()
            await self._wait_for("wait_disconnected", self.proxy.wait_disconnected)
            await self.start_scripts()

    async def stop(self) -> None:
        await self._terminate_client()
        await self.proxy.release_slot(5.0)

    async def _start_client(
        self, utterance: str | list[str] | None = None, *, timeout_s: float = 30
    ) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._client_seq += 1
        log_path = self.log_dir / f"{self.case_id}-client-{self._client_seq}.log"
        self.log = log_path.open("w", encoding="utf-8")
        self.log_path = log_path
        command = [self.hands_bin, "serve", "--url", self.proxy.url]
        if utterance is not None:
            for text in [utterance] if isinstance(utterance, str) else utterance:
                command.extend(["--utterance", text])
            self.hands_serve_timeout_flag = serve_timeout_supported(self.hands_bin)
            if self.hands_serve_timeout_flag:
                command.extend(["--timeout", str(math.ceil(timeout_s) + 15)])
        try:
            self.process = subprocess.Popen(
                command,
                cwd=self.cwd,
                env=os.environ.copy(),
                stdout=self.log,
                stderr=subprocess.STDOUT,
            )
            CLIENT_PROCESSES.add(self.process)
        except Exception:
            self.log.close()
            self.log = None
            self.log_path = None
            raise

    async def _stop_client(self) -> None:
        await self._terminate_client()

    async def _terminate_client(self) -> None:
        process, log = self.process, self.log
        self.process = None
        self.log = None
        if process is not None:
            await _terminate_process(process)
        if log is not None:
            log.close()
        if process is not None:
            self.hands_serve_summary = _serve_summary(
                self.log_path, process.poll()
            ) or self.hands_serve_summary
        self.log_path = None
