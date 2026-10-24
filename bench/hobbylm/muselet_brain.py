"""Run the existing Muselet brain with a benchmark-only first-RPC timestamp hook."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/src"))

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.server import BrainServer
from brain.traces import Tracer


class BenchmarkTracer(Tracer):
    def __init__(self, timing_file: Path, first_action_file: Path):
        super().__init__()
        self.timing_file = timing_file
        self.first_action_file = first_action_file
        self.started = None
        self.first_action_recorded = False

    def begin(self, utterance: str):
        self.first_action_recorded = False
        try:
            timing = json.loads(self.timing_file.read_text(encoding="utf-8"))
            self.started = float(timing["sent_monotonic"])
        except (OSError, ValueError, KeyError, TypeError):
            self.started = time.monotonic()
        return super().begin(utterance)

    def first_action(self, method: str, params: dict):
        if self.started is None or self.first_action_recorded:
            return
        self.first_action_recorded = True
        event = {
            "utterance": (self.current or {}).get("utterance"),
            "method": method,
            "skill": params.get("name"),
            "latency_s": max(0.0, time.monotonic() - self.started),
        }
        self.first_action_file.parent.mkdir(parents=True, exist_ok=True)
        with self.first_action_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")


async def serve(port: int, timing_file: Path, first_action_file: Path):
    tracer = BenchmarkTracer(timing_file, first_action_file)
    original_rpc = BrainServer.rpc

    async def measured_rpc(server, method, params, timeout=30):
        if method in ("act", "skill"):
            tracer.first_action(method, params)
        return await original_rpc(server, method, params, timeout=timeout)

    BrainServer.rpc = measured_rpc
    server = BrainServer(port=port)
    await server.start()
    orchestrator = Orchestrator(server, Catalog.load(), tracer)

    async def on_utterance(text: str, final: bool):
        server._bench_tracer = tracer
        await orchestrator.handle_utterance(text)

    server.on_utterance = on_utterance
    print(f"benchmark brain listening on ws://127.0.0.1:{server.port}", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await server.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timing-file", type=Path, required=True)
    parser.add_argument("--first-action-file", type=Path, required=True)
    args = parser.parse_args(argv)
    asyncio.run(serve(args.port, args.timing_file, args.first_action_file))


if __name__ == "__main__":
    raise SystemExit(main())
