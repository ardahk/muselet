"""Tiny websocket server for exercising the Muselet Bridge plugin (UXP panels can only be clients).

Usage:  python premiere/test_server.py                # interactive: type `cmd {json args}` lines
        python premiere/test_server.py --script        # send a fixed read-only smoke test, then exit
Requires: websockets (already a brain dependency).
"""

import argparse
import asyncio
import itertools
import json
import sys

import websockets

SMOKE = [
    ("ping", {}),
    ("sequence_info", {}),
    ("move_playhead", {"seconds": 2.5}),
    ("add_marker", {"name": "muselet test"}),
    ("razor_at_playhead", {}),
    ("undo", {}),
    ("bogus", {}),
]

ids = itertools.count(1)


async def call(ws, cmd, args):
    req = {"id": f"r{next(ids)}", "cmd": cmd, "args": args}
    await ws.send(json.dumps(req))
    while True:
        reply = json.loads(await ws.recv())
        if reply.get("id") == req["id"]:
            return reply
        print("<<", json.dumps(reply))


async def session(ws, script: bool, done: asyncio.Event):
    hello = json.loads(await ws.recv())
    print("connected:", json.dumps(hello))
    if script:
        failures = 0
        for cmd, args in SMOKE:
            reply = await call(ws, cmd, args)
            print(f">> {cmd} {json.dumps(args)}\n<< {json.dumps(reply)}")
            failures += not reply.get("ok") and reply.get("error") not in ("not_supported",) and cmd != "bogus"
        print("smoke failures:", failures)
        done.set()
        return
    loop = asyncio.get_running_loop()
    while True:
        line = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        if not line:
            continue
        cmd, _, rest = line.partition(" ")
        reply = await call(ws, cmd, json.loads(rest) if rest else {})
        print(json.dumps(reply, indent=2))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--script", action="store_true")
    a = ap.parse_args()
    done = asyncio.Event()
    async with websockets.serve(lambda ws: session(ws, a.script, done), "127.0.0.1", a.port):
        print(f"listening on ws://127.0.0.1:{a.port}; load/reload the Muselet Bridge panel in Premiere")
        await (done.wait() if a.script else asyncio.Future())


if __name__ == "__main__":
    asyncio.run(main())
