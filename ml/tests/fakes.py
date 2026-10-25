"""In-process fakes (no WebSocket): a server that records say/ui/confirm/rpc,
a scripted System-1 engine with the DecisionEngine route/args API, and small
shared helpers (planner/worker stand-ins, rpc/trace readers)."""

import asyncio
import copy
import inspect
import json
import threading
import time
from concurrent.futures import Future

from brain.catalog import Catalog
from brain.decision import RouteResult
from brain.orchestrator import Orchestrator
from brain.traces import Tracer


class FakeServer:
    def __init__(self, act=None, observe=None, apps=None, handlers=None,
                 confirm_raises=False):
        self.said: list[str] = []
        self.apps = apps or {"running": [], "installed": []}
        self.uis: list[str] = []
        self.ui_ms: list = []
        self.confirms: list[str] = []
        self.rpcs: list[tuple[str, dict]] = []
        self.confirm_yes = True
        self.confirm_raises = confirm_raises
        self.handlers = handlers or {}
        self.act = act or (lambda p: {"ok": True, "act_ms": 1, "epoch": 2})
        self.observe = observe or (lambda: {
            "epoch": 1, "app": "Finder", "window": "Recents",
            "focused_ref": 4, "elements": [],
            "text": 'app: Finder | window: "Recents" | focused: #4',
            "ax_ms": 1})

    async def say(self, text):
        self.said.append(text)

    async def ui(self, mascot, bubble=None, ms=None):
        self.uis.append(mascot)
        self.ui_ms.append(ms)

    async def ask_confirm(self, summary, timeout=120):
        self.confirms.append(summary)
        if self.confirm_raises:
            raise RuntimeError("timeout")
        return self.confirm_yes

    async def rpc(self, method, params, timeout=30):
        self.rpcs.append((method, params))
        if method in self.handlers:
            result = self.handlers[method](params)
            return await result if inspect.isawaitable(result) else result
        if method == "observe":
            return self.observe()
        if method == "act":
            return self.act(params)
        if method == "verify":
            return {"ok": True, "observed": "x"}
        if method == "apps":
            return self.apps() if callable(self.apps) else self.apps
        return {"ok": True, "result": {}, "ms": 1}

    def methods(self):
        return [m for m, _ in self.rpcs]

    def skills(self):
        return [p for m, p in self.rpcs if m == "skill"]


class FakeEngine:
    """routes: normalized text -> (label, p_top); argmap: (skill, text) ->
    raw ARGS dict. Records calls (thread-safe; runs on the MLX worker)."""

    def __init__(self, routes=None, argmap=None, default=("ANSWER", 0.9)):
        self.routes = routes or {}
        self.argmap = argmap or {}
        self.default = default
        self.route_calls: list[str] = []
        self.args_calls: list[tuple[str, str]] = []
        self.last_action = None
        self.gate: threading.Event | None = None   # block the next route

    def route(self, text, ctx):
        if self.gate is not None:
            g, self.gate = self.gate, None
            g.wait(5)
        self.route_calls.append(text)
        top, p = self.routes.get(" ".join(text.lower().split()), self.default)
        other = "ASK" if top != "ASK" else "ANSWER"
        return RouteResult(probs={top: p, other: round(1 - p, 3)}, top=top,
                           p_top=p, ms={"route_ms": 50.0})

    def args(self, skill, text, ctx):
        self.args_calls.append((skill, text))
        return dict(self.argmap.get((skill, " ".join(text.lower().split())), {}),
                    ms={"args_ms": 30.0}, _raw="raw")


def run(coro):
    return asyncio.run(coro)


def _skill_rpcs(server):
    return [(p["name"], p["args"]) for m, p in server.rpcs if m == "skill"]


def _acts(server):
    return [p for m, p in server.rpcs if m == "act"]


def _traces(tracer):
    return [json.loads(line) for path in tracer.dir.glob("*.jsonl")
            for line in path.read_text().splitlines()]


class CapturingTracer(Tracer):
    """Keeps a deep copy of the finished trace as `.last`."""

    def finish(self, outcome):
        self.last = copy.deepcopy(self.current)
        super().finish(outcome)


class ScriptedPlanner:
    """Planner.plan / Planner.generate stand-in (runs on the MLX worker)."""

    def __init__(self, turns=None, answer=None):
        self.turns = turns or [["done \"ok\""]]
        self.answer = answer
        self.plans: list[dict] = []
        self.generates: list[tuple[str, str]] = []

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             **kw):
        idx = min(len(self.plans), len(self.turns) - 1)
        self.plans.append({"goal": goal, "obs": observation})
        for line in self.turns[idx]:
            time.sleep(0.005)
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": self.turns[idx], "ttft_ms": 1.0, "tokens": 4,
                "plan_ms": 5.0, "decode_tok_s": 10.0}

    def generate(self, system, user, max_tokens=48, stop_at_newline=True):
        self.generates.append((system, user))
        return self.answer(system, user) if callable(self.answer) \
            else self.answer


class InlineWorker:
    """MLX worker stand-in: submit_async runs fn on a thread."""

    async def submit_async(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class SyncWorker:
    """MLX worker stand-in: submit_async calls fn inline."""

    async def submit_async(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


def engine_orch(tmp_path, server, routes=None, args=None, planner=None):
    """Orchestrator over `server` with a FakeEngine(routes, args)."""
    o = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"),
                     engine=FakeEngine(routes or {}, args or {}))
    o.planner = planner
    return o
