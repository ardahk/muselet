"""In-process fakes (no WebSocket): a server that records say/ui/confirm/rpc
and a scripted System-1 engine with the DecisionEngine route/args API."""

import threading

from brain.decision import RouteResult


class FakeServer:
    def __init__(self, act=None, observe=None):
        self.said: list[str] = []
        self.uis: list[str] = []
        self.ui_ms: list = []
        self.confirms: list[str] = []
        self.rpcs: list[tuple[str, dict]] = []
        self.confirm_yes = True
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
        return self.confirm_yes

    async def rpc(self, method, params, timeout=30):
        self.rpcs.append((method, params))
        if method == "observe":
            return self.observe()
        if method == "act":
            return self.act(params)
        if method == "verify":
            return {"ok": True, "observed": "x"}
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
