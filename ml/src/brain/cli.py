"""brain serve — WS server + stdin REPL (each line = one final utterance)."""

import argparse
import asyncio
import sys

from .catalog import Catalog
from .orchestrator import Orchestrator
from .server import BrainServer
from .traces import Tracer


async def _stdin_lines():
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if line == "":
            return
        line = line.rstrip("\n")
        if line:
            yield line


async def serve(port: int = 8765):
    server = BrainServer(port=port)
    await server.start()
    orch = Orchestrator(server, Catalog.load(), Tracer())

    async def on_utt(text: str, final: bool):
        print(f"[utterance] {text}", flush=True)
        await orch.handle_utterance(text)

    server.on_utterance = on_utt
    print(f"brain listening on ws://127.0.0.1:{server.port}", flush=True)
    print("type an utterance + enter (headless mode)", flush=True)

    try:
        async for line in _stdin_lines():
            print(f"[stdin] {line}", flush=True)
            try:
                await orch.handle_utterance(line)
            except Exception as e:  # keep the REPL alive
                print(f"[error] {e!r}", flush=True)
        # stdin closed (e.g. daemon mode): keep serving WS clients
        print("[stdin closed] serving WS only", flush=True)
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.close()


def main():
    ap = argparse.ArgumentParser(prog="brain")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="run the WS server + stdin REPL")
    s.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.cmd == "serve":
        asyncio.run(serve(args.port))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
