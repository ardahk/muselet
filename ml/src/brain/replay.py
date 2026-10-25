"""Offline trace replay: real user sessions through the real Orchestrator.

A replay case is one JSON object (JSONL, one session per line):

  {"id": "...", "source": "trace|reconstructed", "failure": "...",
   "apps": {"running": [...], "installed": [...]},
   "longterm": [{"type": "person", "key": "caleb", "value": "..."}],
   "turns": [{
     "utterance": "...", "ctx": {...},           # or "memory": {"op": "clear"} (Settings frame)
     "route": {"<clause text>": {"LABEL": p}},   # recorded router probabilities per routed text
     "args": {"<skill>": {"key": "raw value"}},  # recorded ARGS extraction
     "planner": [["line", ...], ...],            # recorded planner batches, in order
     "generate": ["..."],                        # recorded planner.generate outputs
     "confirm": [true],                          # user's confirm replies, in order
     "rpc": [{"method": "observe", "result": {...}},
             {"method": "skill", "match": {"name": "open_app"}, "result": {...}}],
     "expect": [<check>, ...], "precondition": false}]}

Hands is recorded, not permissive: an RPC is answered only by a recorded entry
whose `match` is a subset of the params (method, then skill `name` / `args`,
act `op` ...). Entries are consumed in order; `observe`/`apps`/`timers` keep
returning the latest recorded value. Anything unrecorded is a *divergence*:
the brain gets RuntimeError("replay_unrecorded") and the turn
fails unless it sets `"allow_divergence": true`.

Checks grade what the brain *did* (RPCs, confirms, pending state, memory),
never what it *said* it did; `said_none` only forbids false claims.

CLI: uv run --project ml python -m brain.replay evals/replay/user_2026-10-24.jsonl
     uv run --project ml python -m brain.replay --from-trace runs/traces/X.jsonl > case.json
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

from .catalog import Catalog
from .decision import RouteResult
from .memory.store import MemoryStore
from .memory.working import WorkingMemory
from .orchestrator import Orchestrator
from .traces import Tracer

STICKY = {"observe", "apps", "timers", "timer_backend", "verify", "screenshot",
          "ocr"}


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def _subset(want, have) -> bool:
    if isinstance(want, dict):
        return isinstance(have, dict) and all(
            k in have and _subset(v, have[k]) for k, v in want.items())
    if isinstance(want, str) and isinstance(have, str):
        return _norm(want) == _norm(have)
    return want == have


class RecordedHands:
    """The app side of the WebSocket, answered from a recording."""

    def __init__(self, apps=None):
        self.apps = apps or {"running": [], "installed": []}
        self.turn: dict = {}
        self.queue: list[dict] = []
        self.sticky: dict[str, dict] = {}
        self.confirm_replies: list[bool] = []
        self.log: list[dict] = []          # every frame the brain sent
        self.divergences: list[str] = []

    def start_turn(self, turn: dict):
        self.turn = turn
        self.queue = [copy.deepcopy(r) for r in turn.get("rpc", [])]
        self.confirm_replies = list(turn.get("confirm", []))
        self.log = []
        self.divergences = []

    def _match(self, method: str, params: dict):
        for i, rec in enumerate(self.queue):
            if rec.get("method") == method and \
                    _subset(rec.get("match", {}), params):
                if not (method in STICKY and not rec.get("once")):
                    return self.queue.pop(i)
                self.sticky[method] = self.queue.pop(i)
                return self.sticky[method]
        return self.sticky.get(method)

    async def rpc(self, method: str, params: dict, timeout: float = 30):
        """Same contract as BrainServer.rpc: the result payload (`ok` filled
        in), or RuntimeError for a result-less error."""
        self.log.append({"t": "rpc", "method": method, "params": params})
        if method == "apps" and method not in self.sticky and \
                not any(r.get("method") == "apps" for r in self.queue):
            return dict(copy.deepcopy(self.apps), ok=True)
        rec = self._match(method, params)
        if rec is None:
            self.divergences.append(f"{method} {json.dumps(params)[:160]}")
            raise RuntimeError("replay_unrecorded")
        if rec.get("raise"):
            raise RuntimeError(rec["raise"])
        res = copy.deepcopy(rec.get("result"))
        ok = rec.get("ok", not (isinstance(res, dict) and res.get("ok") is False))
        if res is None:
            if ok:
                return {"ok": True}
            raise RuntimeError(rec.get("error") or "rpc failed")
        if isinstance(res, dict):
            res.setdefault("ok", ok)
            if not ok:
                res.setdefault("error", rec.get("error") or "failed")
        return res

    async def say(self, text: str):
        self.log.append({"t": "say", "text": text})

    async def ui(self, mascot: str, bubble=None, ms=None):
        self.log.append({"t": "ui", "mascot": mascot, "bubble": bubble})

    async def ask_confirm(self, summary: str, timeout: float = 120) -> bool:
        self.log.append({"t": "confirm", "summary": summary})
        if not self.confirm_replies:
            self.divergences.append(f"confirm {summary[:120]!r}")
            return False
        return bool(self.confirm_replies.pop(0))

    async def send(self, msg: dict):
        self.log.append(dict(msg))


class RecordedEngine:
    """System 1 router + ARGS answered from the recording."""

    def __init__(self, hands: RecordedHands):
        self.hands = hands
        self.last_action = None
        self.calls: list[tuple[str, str]] = []

    def route(self, text, ctx):
        self.calls.append(("route", text))
        routes = {_norm(k): v for k, v in self.hands.turn.get("route", {}).items()}
        probs = routes.get(_norm(text))
        if probs is None:
            self.hands.divergences.append(f"route {text!r}")
            probs = {"ASK": 1.0}
        top = max(probs, key=probs.get)
        return RouteResult(probs=dict(probs), top=top, p_top=probs[top],
                           ms={"route_ms": 0.0})

    def args(self, skill, text, ctx):
        self.calls.append(("args", skill))
        rec = self.hands.turn.get("args", {}).get(skill)
        if rec is None:
            self.hands.divergences.append(f"args {skill} {text!r}")
            rec = {}
        raw = " ".join(f'{k}="{v}"' for k, v in rec.items())   # as in traces
        return dict(rec, ms={"args_ms": 0.0}, _raw=raw)


class RecordedPlanner:
    """System 2 planner: streams recorded batches; records every call."""

    history = "dsl"

    def __init__(self, hands: RecordedHands):
        self.hands = hands
        self.calls: list[dict] = []
        self.plan_bank = None

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             **kw):
        self.calls.append({"goal": goal, "observation": observation})
        batches = self.hands.turn.setdefault("_batches",
                                             list(self.hands.turn.get("planner", [])))
        if batches:
            lines = list(batches.pop(0))
        else:
            self.hands.divergences.append(f"planner {goal[:80]!r}")
            lines = ['refuse "replay: no recorded planner batch"']
        for line in lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 0.0, "decode_tok_s": 0.0,
                "tokens": 0, "plan_ms": 0.0, "retrieved": [], "think": None,
                "think_tokens": 0}

    def generate(self, system, user, max_tokens=256, **kw):
        self.calls.append({"generate": user})
        outs = self.hands.turn.setdefault("_gen", list(self.hands.turn.get("generate", [])))
        if outs:
            return outs.pop(0)
        self.hands.divergences.append("generate")
        return ""

    complete = generate


def _said(log):
    return [m["text"] for m in log if m.get("t") == "say"]


def _rpcs(log):
    return [m for m in log if m.get("t") == "rpc"]


def _rpc_hit(m: dict, want: dict) -> bool:
    want = dict(want)
    method = want.pop("method", None)
    if method and m["method"] != method:
        return False
    return _subset(want, m["params"])


def check(c: dict, ctx: dict) -> tuple[bool, str]:
    """One expectation against what the brain did this turn."""
    log, orch = ctx["log"], ctx["orch"]
    k, v = next(iter(c.items()))
    if k == "rpc":                   # subset match on {method, **params}
        hits = [m for m in _rpcs(log) if _rpc_hit(m, v)]
        return bool(hits), f"no rpc matching {v}; sent {[(m['method'], m['params']) for m in _rpcs(log)]}"
    if k == "no_rpc":
        hits = [m for m in _rpcs(log) if _rpc_hit(m, v)]
        return not hits, f"forbidden rpc sent: {hits[:2]}"
    if k == "rpc_text":              # some rpc param text matches regex
        blob = [json.dumps(m["params"]) for m in _rpcs(log)]
        return any(re.search(v, b) for b in blob), f"no rpc params match {v!r}"
    if k == "confirm":
        got = [m["summary"] for m in log if m.get("t") == "confirm"]
        return any(re.search(v, s) for s in got), f"confirms {got}"
    if k == "no_confirm":
        got = [m["summary"] for m in log if m.get("t") == "confirm"]
        return not any(re.search(v, s) for s in got), f"confirms {got}"
    if k == "said_none":             # forbid a claim (never grade a pass on it)
        got = _said(log)
        return not any(re.search(v, s) for s in got), f"said {got}"
    if k == "outcome":
        return ctx["outcome"] in (v if isinstance(v, list) else [v]), \
            f"outcome {ctx['outcome']!r}"
    if k == "outcome_not":
        return ctx["outcome"] not in (v if isinstance(v, list) else [v]), \
            f"outcome {ctx['outcome']!r}"
    if k == "pending":               # bool: a task/slot/comms/draft is still open
        open_ = any(getattr(orch, a, None) for a in
                    ("_pending_task", "_slot", "_comms", "_draft"))
        return open_ == bool(v), f"pending={open_}"
    if k == "planner_calls":         # max planner calls this turn
        n = len([p for p in ctx["planner"] if "goal" in p])
        return n <= v, f"planner called {n}x: {[p['goal'][:60] for p in ctx['planner']]}"
    if k == "planner_goal_none":     # no planner goal matching regex
        got = [p["goal"] for p in ctx["planner"] if "goal" in p]
        return not any(re.search(v, g) for g in got), f"planner goals {got}"
    if k == "memory_items":          # Settings list after the turn
        n = len(orch.memory_request({"op": "list"})["items"])
        return n == v, f"memory list has {n} items"
    if k == "working_turns":
        n = len(orch.memory.turns)
        return n == v, f"working memory has {n} turns"
    if k == "workflows":             # learned workflow rows on disk
        p = Path(ctx["tmp"]) / "workflows.jsonl"
        n = len([l for l in p.read_text().splitlines() if l.strip()]) \
            if p.exists() else 0
        return n == v, f"{n} learned workflows on disk"
    if k == "any":                   # at least one sub-check passes
        res = [check(sub, ctx) for sub in v]
        return any(ok for ok, _ in res), "; ".join(w for _, w in res)
    if k == "no_divergence":
        return not ctx["divergences"], f"unrecorded: {ctx['divergences']}"
    raise ValueError(f"unknown check {k!r}")


async def replay_case(case: dict, tmp: str | Path) -> dict:
    """Run one case; returns {id, passed, turns:[{passed, failures, ...}]}."""
    import os
    tmp = Path(tmp)
    os.environ["MUSELET_MEMORY_DB"] = str(tmp / "memory.sqlite")
    hands = RecordedHands(case.get("apps"))
    engine = RecordedEngine(hands)
    orch = Orchestrator(hands, Catalog.load(), Tracer(tmp / "traces"),
                        engine=engine, tau=case.get("tau", 0.50),
                        longterm_store=MemoryStore(tmp / "memory.sqlite"))
    orch.memory = WorkingMemory(path=tmp / "working.json")
    orch.memory_llm = False
    orch.planner = planner = RecordedPlanner(hands)
    for row in case.get("longterm", []):
        orch.longterm.upsert(row["type"], row["key"], row["value"])
    for row in case.get("workflows", []):
        with open(tmp / "workflows.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
    out = {"id": case["id"], "turns": [], "passed": True}
    for i, turn in enumerate(case["turns"]):
        hands.start_turn(turn)
        n_plan = len(planner.calls)
        if "memory" in turn:          # a Settings frame, not an utterance
            hands.log.append({"t": "memory",
                              **orch.memory_request(turn["memory"])})
            outcome = "ok"
        else:
            res = await asyncio.wait_for(
                orch.handle_utterance(turn["utterance"], turn.get("ctx")),
                turn.get("timeout_s", 60))
            outcome = (res or {}).get("outcome")
        ctx = {"log": hands.log, "orch": orch, "outcome": outcome, "tmp": tmp,
               "planner": planner.calls[n_plan:],
               "divergences": list(hands.divergences)}
        checks = list(turn.get("expect", []))
        if not turn.get("allow_divergence"):
            checks.append({"no_divergence": True})
        fails = []
        for c in checks:
            ok, why = check(c, ctx)
            if not ok:
                fails.append(f"{json.dumps(c)}: {why}")
        t = {"turn": i, "utterance": turn.get("utterance") or turn.get("memory"),
             "outcome": outcome, "said": _said(hands.log),
             "sent": [[m["method"], m["params"]] for m in _rpcs(hands.log)],
             "failures": fails, "precondition": bool(turn.get("precondition"))}
        out["turns"].append(t)
        if fails:
            out["passed"] = False
            if turn.get("precondition"):
                out["skipped"] = f"turn {i} precondition: {fails[0]}"
            break
    return out


def run_case(case: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(replay_case(case, tmp))


def load(path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines()
            if l.strip() and not l.lstrip().startswith("//")]


def from_trace(rows: list[dict]) -> dict:
    """Draft a replay case from real trace rows (runs/traces/*.jsonl).
    The router/args/planner decisions and every RPC result are copied; the
    author adds `expect` checks and, for old traces without `ctx`, the ctx."""
    turns = []
    for row in rows:
        route, args, planner = {}, {}, []
        for d in row.get("decisions", []):
            if "route_probs" in d:      # [[label, p], ...] top5
                route[d.get("text") or row.get("utterance", "")] = dict(
                    d["route_probs"])
            if "raw" in d and "args_ms" in d:
                from .decision import DecisionEngine
                skill = d.get("skill") or (max(route[list(route)[-1]].items(),
                                                key=lambda kv: kv[1])[0]
                                            if route else "?")
                args[skill] = DecisionEngine._parse_args_line(d["raw"] or "")
            if "planner_turn" in d:
                planner.append(d.get("lines") or [])
        rpc = [{"method": r.get("method"),
                **({"match": {k: r["params"][k] for k in ("name", "op")
                              if k in (r.get("params") or {})}}
                   if r.get("method") in ("skill", "act") else {}),
                "result": r.get("result")}
               for r in row.get("rpc", [])]
        turns.append({"utterance": row.get("utterance", ""),
                      "ctx": row.get("ctx", {}), "route": route, "args": args,
                      "planner": planner, "rpc": rpc, "expect": []})
    return {"id": "trace-" + str(int(time.time())), "source": "trace",
            "turns": turns}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m brain.replay")
    ap.add_argument("cases", nargs="?")
    ap.add_argument("--only")
    ap.add_argument("--from-trace", help="trace JSONL -> draft case on stdout")
    ap.add_argument("--ts", nargs="*", help="with --from-trace: only these ts")
    a = ap.parse_args(argv)
    if a.from_trace:
        rows = load(a.from_trace)
        if a.ts:
            rows = [r for r in rows if str(r.get("ts")) in a.ts]
        print(json.dumps(from_trace(rows)))
        return 0
    fails = 0
    for case in load(a.cases):
        if a.only and a.only not in case["id"]:
            continue
        r = run_case(case)
        state = "SKIP" if r.get("skipped") else "PASS" if r["passed"] else "FAIL"
        fails += state == "FAIL"
        print(f"{state} {r['id']}")
        for t in r["turns"]:
            for f in t["failures"]:
                print(f"   turn {t['turn']} {t['utterance']!r}: {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
