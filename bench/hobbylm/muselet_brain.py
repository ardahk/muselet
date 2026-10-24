"""Run the repository Brain server for a macOS HobbyLM replay."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/src"))

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.server import BrainServer
from brain.traces import Tracer


async def serve(port: int):
    tracer = Tracer()
    server = BrainServer(port=port)
    await server.start()
    orchestrator = Orchestrator(server, Catalog.load(), tracer)

    async def on_utterance(text: str, final: bool):
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
    args = parser.parse_args(argv)
    asyncio.run(serve(args.port))


if __name__ == "__main__":
    raise SystemExit(main())
