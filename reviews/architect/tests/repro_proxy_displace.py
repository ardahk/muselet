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
    print("after A: hands is set", p._hands is not None, "brains", len(brains))
    b = await websockets.connect(p.url)
    await asyncio.sleep(2.0)
    print("after B 2s: brains", len(brains), "A closed", a.close_code, "lock locked", p._connection_lock.locked())
    try:
        await asyncio.wait_for(p.wait_disconnected(0.5), 1)
    except Exception as e: print("wait_disconnected:", type(e).__name__)
asyncio.run(main())
