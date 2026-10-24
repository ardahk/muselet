"""planner-20 repro: fail, fail, then a standalone `done` -> the harness's own
done-rejection is the 3rd 'failed turn' and the loop guard returns
awaiting_user ("I'm stuck") instead of letting the planner re-confirm done.
Run from ml/: PYTHONPATH=src:tests python -m pytest <this file>
(stubs mlx so it runs on Linux; FakePlanner never touches the model)."""
import sys, types, importlib.abc, importlib.machinery


class _Any:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return _Any()
    def __getattr__(self, n): return _Any()
    def __mro_entries__(self, bases): return (object,)


class _Mod(types.ModuleType):
    __path__ = []
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return _Any()


class _Stub(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    ROOTS = ("mlx", "mlx_lm", "mlx_vlm", "tinker", "tinker_cookbook", "torch", "transformers")
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in self.ROOTS:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
    def create_module(self, spec): return _Mod(spec.name)
    def exec_module(self, m): pass


sys.meta_path.insert(0, _Stub())

import asyncio
from brain import protocol
from test_orchestrator import FakeHands
from test_planner_loop import FakePlanner, _mk, _up, run, trace_for


def test_fail_fail_done_is_not_stuck():
    hands = FakeHands()
    planner = FakePlanner([
        ["press #1", 'expect appears "A"'],
        ["press #2", 'expect appears "B"'],
        ['done "recovered"'],
        ['done "recovered"'],
    ])
    server, orch = _mk(0, planner, hands)
    orig = FakeHands.reply
    n = {"v": 0}

    async def reply(self, msg):
        if msg["method"] == "verify":
            n["v"] += 1
            return protocol.rpc_result(msg["id"], True,
                                       {"ok": n["v"] > 2, "observed": "x"})
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)

    async def go():
        server.port = 9941
        await _up(server, hands, orch, 9941)
        out = await orch._planner_loop("do it", trace_for(orch))
        await hands.close(); await server.close()
        return out
    out = run(go())
    assert out != "awaiting_user", (out, planner.calls)
