#!/usr/bin/env python3
"""One-time: make Muselet.app request macOS Automation/Calendar consent while the user is present.

Temporarily serves ws://127.0.0.1:8765 in place of the brain (stop the brain first). When the app connects, sends
harmless read-only RPCs that trigger each consent prompt, prints the results, and exits. Restart the brain after.
"""

import asyncio
import json

import websockets

STEPS = [
    ("Notes", "act", {"op": "script", "lang": "applescript", "code": 'tell application "Notes" to count folders'}),
    ("Calendar (automation)", "act", {"op": "script", "lang": "applescript",
                                      "code": 'tell application id "com.apple.iCal" to count calendars'}),
    ("Reminders (automation)", "act", {"op": "script", "lang": "applescript",
                                       "code": 'tell application "Reminders" to count lists'}),
    ("Numbers", "act", {"op": "script", "lang": "applescript",
                        "code": 'tell application id "com.apple.Numbers" to count documents'}),
    ("Finder", "act", {"op": "script", "lang": "applescript", "code": 'tell application "Finder" to count windows'}),
    ("System Events", "act", {"op": "script", "lang": "applescript",
                              "code": 'tell application "System Events" to count processes'}),
    ("Calendar (events access)", "skill", {"name": "todays_agenda", "args": {}}),
]


async def handler(ws):
    pending = {}
    loop = asyncio.get_running_loop()

    async def reader():
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("t") == "rpc_result" and msg.get("id") in pending:
                pending.pop(msg["id"]).set_result(msg)

    rt = asyncio.create_task(reader())
    for i, (name, method, params) in enumerate(STEPS):
        await ws.send(json.dumps({"t": "say", "text": f"Permission check: {name}"}))
        rid = f"tcc{i}"
        pending[rid] = loop.create_future()
        await ws.send(json.dumps({"t": "rpc", "id": rid, "method": method, "params": params}))
        try:
            res = await asyncio.wait_for(pending[rid], 120)
            print(f"{name:28} ok={res.get('ok')} {str(res.get('error') or '')[:120]}", flush=True)
        except asyncio.TimeoutError:
            pending.pop(rid, None)
            print(f"{name:28} TIMEOUT (prompt not answered?)", flush=True)
    await ws.send(json.dumps({"t": "say", "text": "Permissions checked. Thanks!"}))
    await ws.send(json.dumps({"t": "ui", "mascot": "success"}))
    rt.cancel()
    stop.set_result(None)


async def main():
    global stop
    stop = asyncio.get_running_loop().create_future()
    async with websockets.serve(handler, "127.0.0.1", 8765):
        print("waiting for Muselet.app to connect on :8765 ...", flush=True)
        await stop


if __name__ == "__main__":
    asyncio.run(main())
