import asyncio, sys
sys.path.insert(0, '.')
import websockets
from bench.harness.proxy import BenchProxy
async def brain_handler(ws):
    try:
        async for _ in ws: pass
    except Exception: pass
async def main():
    bsrv = await websockets.serve(brain_handler, "127.0.0.1", 0)
    bport = bsrv.sockets[0].getsockname()[1]
    p = BenchProxy(f"ws://127.0.0.1:{bport}")
    await p.start()
    a = await websockets.connect(p.url)        # stale client that never closes
    await p.wait_connected(5)
    ha = p._hands
    b = await websockets.connect(p.url)        # new client
    await asyncio.sleep(3)
    print("hands is A:", p._hands is ha, "| A open:", a.state.name, "| B open:", b.state.name, "| lock held:", p._connection_lock.locked())
    try:
        await asyncio.wait_for(b.send('{"t":"hello"}'), 1); print("B send ok (buffered)")
    except Exception as e: print("B send err", e)
    await a.close(); await asyncio.sleep(1)
    print("after A closes: hands is B?", p._hands is not None and p._hands is not ha)
    await b.close(); await p.close(); bsrv.close()
asyncio.run(main())
