"""Hands CLI process lifecycle shared by live and replay benchmarks."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any


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
        self._client_seq = 0

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
        await self._start_client()
        await self.proxy.wait_connected()

    async def start_utterance(self, utterance: str) -> None:
        await self._stop_client()
        await self.proxy.wait_disconnected()
        await self._start_client(utterance)
        await self.proxy.wait_for_utterance()

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

    async def prepare_for_cleanup(self) -> None:
        if self.proxy.capture.active:
            await self._stop_client()
            self.proxy.mark_utterance_finished()
            await self.proxy.wait_disconnected()
            await self.start_scripts()

    async def stop(self) -> None:
        await self._stop_client()

    async def _start_client(self, utterance: str | None = None) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._client_seq += 1
        log_path = self.log_dir / f"{self.case_id}-client-{self._client_seq}.log"
        self.log = log_path.open("w", encoding="utf-8")
        command = [self.hands_bin, "serve", "--url", self.proxy.url]
        if utterance is not None:
            command.extend(["--utterance", utterance])
        try:
            self.process = subprocess.Popen(
                command,
                cwd=self.cwd,
                env=os.environ.copy(),
                stdout=self.log,
                stderr=subprocess.STDOUT,
            )
        except Exception:
            self.log.close()
            self.log = None
            raise

    async def _stop_client(self) -> None:
        process, log = self.process, self.log
        self.process = None
        self.log = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, timeout=5)
        if log is not None:
            log.close()
        if process is not None:
            try:
                await self.proxy.wait_disconnected(timeout=5)
            except asyncio.TimeoutError:
                pass
