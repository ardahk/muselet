import asyncio, sys
sys.path.insert(0, "bench"); sys.path.insert(0, ".")
import websockets
from bench.harness.proxy import BenchProxy
async def main():
    brains = []
    async def brain(ws):
        brains.append(ws)
        async for m in ws: pass
    srv = await websockets.serve(brain, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    p = await BenchProxy(f"ws://127.0.0.1:{port}").start()
    a = await websockets.connect(p.url)   # stale client: open, never closed
    await asyncio.sleep(0.3)
    try:
        await p.wait_disconnected(0.5)
    except asyncio.TimeoutError:
        print("A latched: wait_disconnected timeout")
    ok = await p.release_slot(2.0)
    print("release_slot ->", ok)
    if not ok:
        await p.force_release()
    print("after force: slot_released", p._slot_released(), "forced", p.forced_releases, "lock", p._connection_lock.locked())
    await asyncio.sleep(0.5)
    print("0.5s later: lock", p._connection_lock.locked(), "A close_code", a.close_code)
    b = await websockets.connect(p.url)
    await asyncio.sleep(1.0)
    print("B: brains", len(brains), "hands is B", p._hands is not None, "slot_released", p._slot_released())
    await b.close(); await asyncio.sleep(0.5)
    try:
        await p.wait_disconnected(1.0); print("B close -> slot freed")
    except asyncio.TimeoutError:
        print("B close -> TIMEOUT")
asyncio.run(main())
