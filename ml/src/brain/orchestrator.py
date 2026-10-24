"""v0 stub router + batch executor.

Utterance -> regex rule -> skill call or DSL batch -> hands executes.
Everything is traced and the app gets ui/say messages.
"""

import asyncio
import logging
import os
import re
import threading
import time

from . import calc, dsl, obsdiff, replies, slots
from .catalog import Catalog, CatalogError
from .traces import Tracer

log = logging.getLogger("brain.orchestrator")

_WORD_NUM = {"zero": 0, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20,
             "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
             "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
             "hundred": 100, "max": 100, "full": 100, "half": 50}

# script-lang batches that must be confirmed before running
_DANGEROUS_SCRIPT = re.compile(
    r"\b(delete|remove|rm\s|empty trash|send|quit|shut ?down|restart|"
    r"log ?out|do shell script|erase|format)\b", re.IGNORECASE)


def _num(tok: str) -> int | None:
    tok = tok.strip().lower()
    if tok.isdigit():
        return int(tok)
    return _WORD_NUM.get(tok)


def _norm(text: str) -> str:
    # case/punctuation-insensitive: Parakeet finals add both
    return " ".join(re.sub(r"[^\w\s']", " ", text.lower()).split())


def _repr_line(a: dict) -> str:
    """legacy Last-batch action text: `{op} k=v ...` from the parsed dict"""
    return f"{a['op']} " + " ".join(
        f"{k}={v}" for k, v in a.items() if k != "op")


def _log_act(a: dict) -> str:
    """the action as one DSL line for Last batch (expect dropped; a long
    script body is cut to 200 chars)"""
    a = {k: v for k, v in a.items() if k != "expect"}
    if a.get("op") == "script" and len(a.get("code", "")) > 200:
        a["code"] = a["code"][:200] + "…"
    try:
        return dsl.serialize([a])
    except (dsl.DSLError, KeyError):
        return _repr_line(a)


def _script_failure(error: str, res: dict | None) -> tuple[str, str]:
    """(bubble, planner reason) for a failed script act: HandsKit sends
    timed_out / exit_code / stderr and `script_failed: exit N: <stderr>`."""
    res = res or {}
    err = " ".join(str(res.get("stderr") or "").split())[:200]
    if res.get("timed_out") or re.search(r"timed? ?out", error or ""):
        return "That script timed out", "timed out" + (f"; stderr: {err}" if err else "")
    code = res.get("exit_code")
    if code is None and (m := re.search(r"exit (-?\d+)", error or "")):
        code = int(m.group(1))
    if code is None:
        return "Script failed", error or "?"
    if not err:
        err = re.sub(r"^script_failed: exit -?\d+:? ?", "", error or "")[:200]
    return "Script failed", f"exit {code}" + (f"; stderr: {err}" if err else "")


_ABS_SKILL = {"change_volume": "set_volume", "change_brightness": "set_brightness"}
_ABS_WORDS = {"max": 100, "maximum": 100, "full": 100, "half": 50,
              "min": 0, "minimum": 0}


_ABS_ANYWHERE = {"max", "maximum", "full", "half"}
_REL_UNITS = {"notch": 10, "notches": 10, "step": 10, "steps": 10,
              "click": 10, "clicks": 10, "tick": 10, "ticks": 10,
              "bar": 10, "bars": 10, "level": 10, "levels": 10,
              "point": 1, "points": 1, "percent": 1}
_UP = {"up", "louder", "raise", "increase", "higher", "brighter", "boost"}
_DOWN = {"down", "quieter", "lower", "decrease", "softer", "dimmer",
         "reduce", "dim"}
_BIT = re.compile(r"\b(a (little )?bit|a little|a touch|a tad|slightly)\b")


def _level_toks(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+", text.lower().replace("%", " percent "))


def _num_runs(toks: list[str]) -> list[tuple[int, int, float]]:
    """(start, end, value) of every spoken/digit number run"""
    runs, i = [], 0
    while i < len(toks):
        v, j = calc._parse_run(toks, i)
        if v is None or j <= i:
            i += 1
            continue
        runs.append((i, j, v))
        i = j
    return runs


def abs_level(text: str) -> int | None:
    """Absolute 0-100 target, only after an absolute marker: 'to N', 'at N',
    'N percent' / 'N%', 'half', 'max', 'full'. Relative phrasing ('up two to
    three notches', 'by 20', 'a bit') -> None (brain-16)."""
    toks = _level_toks(text)
    n = len(toks)
    for i, w in enumerate(toks):
        prev, nxt = toks[i - 1] if i else "", toks[i + 1: i + 3]
        if w in _ABS_WORDS and prev != "by" and \
                not any(t in _REL_UNITS for t in nxt) and \
                (w in _ABS_ANYWHERE or prev in ("to", "at", "the")):
            return _ABS_WORDS[w]
    runs = _num_runs(toks)
    ends = {e for _, e, _ in runs}
    for i, j, v in runs:
        nxt = toks[j] if j < n else ""
        if nxt in _REL_UNITS and nxt != "percent":
            continue                          # 'three notches'
        k = i - 1 - (i >= 2 and toks[i - 1] == "the")
        marker = toks[k] if k >= 0 else ""
        if marker in ("to", "at"):
            if marker == "to" and k in ends:  # 'two to three': a range
                continue
            if (nxt == "percent" or nxt not in _REL_UNITS) and \
                    0 <= v <= 100 and v == int(v):
                return int(v)
            continue
        prev = toks[i - 1] if i else ""
        if nxt == "percent" and prev not in ("by",) and prev not in _UP \
                and prev not in _DOWN and 0 <= v <= 100 and v == int(v):
            return int(v)
    return None


def rel_delta(text: str) -> int | None:
    """Signed relative step by code (notch/step = 10): 'up two to three
    notches' -> 25, 'down by 20' -> -20, 'a bit quieter' -> -10; None when
    the direction or the amount isn't stated."""
    toks = _level_toks(text)
    sign = next((1 if t in _UP else -1 for t in toks
                 if t in _UP or t in _DOWN), None)
    if sign is None:
        return None
    runs, n, amt = _num_runs(toks), len(toks), None
    for x, (i, j, v) in enumerate(runs):
        nxt = toks[j] if j < n else ""
        lo = v
        if x and runs[x - 1][1] == i - 1 and toks[i - 1] == "to":
            lo = runs[x - 1][2]               # 'two to three'
        unit = _REL_UNITS.get(nxt)
        if unit is None and lo != v:
            unit = 10 if v <= 10 else 1       # bare small range = notches
        if unit is None and i and toks[i - 1] == "by":
            unit = 1
        if unit is not None:
            amt = (lo + v) / 2 * unit
    if amt is None and _BIT.search(" ".join(toks)):
        amt = 10
    if amt is None:
        return None
    return sign * round(min(amt, 100))


_JOIN = re.compile(r",?\s+(and\s+then|then|and)\s+", re.IGNORECASE)
MAX_CLAUSES = 4


def split_clauses(text: str) -> tuple[list[str], list[str]]:
    """'a and then b' -> (['a', 'b'], ['and then']); never splits inside
    "quoted text". One clause -> ([text], [])."""
    parts, joins, start = [], [], 0
    for m in _JOIN.finditer(text):
        if text[:m.start()].count('"') % 2:
            continue
        parts.append(text[start:m.start()])
        joins.append(" ".join(m.group(1).lower().split()))
        start = m.end()
    parts.append(text[start:])
    parts = [p.strip(" ,.") for p in parts]
    if len(parts) < 2 or not all(parts):
        return [text], []
    return parts, joins


# common spoken names -> app (the `apps` RPC list wins when it matches)
_APP_ALIASES = {"finder": "Finder", "chrome": "Google Chrome",
                "google chrome": "Google Chrome", "safari": "Safari",
                "notes": "Notes", "numbers": "Numbers",
                "premiere": "Adobe Premiere Pro",
                "premiere pro": "Adobe Premiere Pro"}
APPS_TTL_S = 60


def app_in(text: str, names: list[str]) -> str | None:
    """Longest installed/running app name (or alias) in the utterance."""
    u = f" {_norm(text)} "
    hits = [n for n in names if _norm(n) and f" {_norm(n)} " in u]
    if hits:
        return max(hits, key=lambda n: len(_norm(n)))
    for alias in sorted(_APP_ALIASES, key=len, reverse=True):
        if f" {alias} " in u:
            full = _APP_ALIASES[alias]
            return next((n for n in names if _norm(full) in _norm(n)), full)
    return None


def _action_key(a: dict) -> str:
    """normalized DSL line of an action (loop-guard identity)."""
    try:
        line = dsl.serialize([dict(a, expect=None)])
    except Exception:       # noqa: BLE001
        line = str(a)
    return " ".join(line.lower().split())


def _headtail(s: str, n: int = 1500) -> str:
    """Script output for the planner: head + tail when longer than n."""
    if len(s) <= n:
        return s
    h = n * 2 // 3
    return s[:h] + "\n...\n" + s[-(n - h - 5):]


def _excerpt(text, n: int) -> str:
    """first n words of text (ellipsis when cut)."""
    w = str(text or "").split()
    return " ".join(w[:max(1, n)]) + ("…" if len(w) > max(1, n) else "")


def _cap12(s: str) -> str:
    w = s.split()
    if len(w) <= 12:
        return s
    return " ".join(w[:12]).rstrip(",.:;?\"") + "?"


def script_needs_confirm(lang: str, code: str) -> bool:
    """Brain-side script policy: shell always confirms; applescript/jxa
    confirm when the code matches a destructive pattern."""
    if lang == "shell":
        return True
    if lang in ("applescript", "jxa"):
        return bool(_DANGEROUS_SCRIPT.search(code))
    return True


class Orchestrator:
    WEB_AX_WINDOW_S = 2.2     # Chrome's web AX tree lands ~2 s after a switch
    COMPOUND_P = 0.75         # every clause must route this confidently

    def __init__(self, server, catalog: Catalog | None = None,
                 tracer: Tracer | None = None, engine=None, tau: float = 0.55):
        self.server = server
        self.catalog = catalog or Catalog.load()
        self.tracer = tracer or Tracer()
        self.engine = engine
        self.tau = tau
        self.planner = None
        self.planner_escalate = None    # opt-in bigger planner (loop guard)
        self._active_planner = None
        self._ms_kind = None
        self._last_epoch = None
        self._last_obs = None
        self._ctx = {"app": "none", "focused": "none", "selection": False,
                     "last_action": "none"}
        self._t_final = 0.0
        self._web_ax_t0 = None      # first web_ax_pending observe arrival
        self._first_action_ms: float | None = None
        self._batch_confirmed = False
        self._pending_task: dict | None = None
        self._script_output: str | None = None
        self._spec_norm = ""
        self._spec_fut = None
        self._spec_gen = 0
        self._current_goal = ""
        self._done_summary = None
        self._slot: dict | None = None     # {skill, args, missing, t, ...}
        self._utterance = ""
        self._diff_chain: list[str] | None = None
        self._apps: tuple[float, list[str]] | None = None   # (t, names)
        self._collect: list[str] | None = None   # compound: replies to join

    # ---------- v0 router ----------

    def route(self, text: str) -> dict:
        """Return a plan: {"kind": "skill"|"batch"|"fallback", ...}."""
        t = text.strip().lower()

        if "volume" in t:
            rest = t[t.index("volume") + len("volume"):]
            for tok in re.split(r"[\s,.]+", rest):
                n = _num(tok) if tok else None
                if n is not None:
                    return {"kind": "skill", "name": "set_volume",
                            "args": {"level": n}}

        if re.search(r"\bunmute\b|\bunmute the", t):
            return {"kind": "skill", "name": "mute", "args": {"on": False}}
        if re.search(r"\bmute\b|\bsilence\b", t):
            return {"kind": "skill", "name": "mute", "args": {"on": True}}

        if re.search(r"dark\s*mode|go dark", t):
            return {"kind": "skill", "name": "dark_mode", "args": {"on": True}}
        if re.search(r"light\s*mode|go light", t):
            return {"kind": "skill", "name": "dark_mode", "args": {"on": False}}

        m = re.search(r"(?:search|google|look up|lookup)(?:\s+for)?\s+(.+)", t)
        if m:
            return {"kind": "skill", "name": "web_search",
                    "args": {"query": m.group(1).strip()}}

        if re.search(r"open (?:my )?(downloads|documents|desktop)\b", t):
            folder = re.search(r"open (?:my )?(downloads|documents|desktop)\b",
                               t).group(1)
            return {"kind": "skill", "name": "open_folder",
                    "args": {"path": folder}}

        m = re.search(r"^(?:open|launch|start)\s+(.+?)\s*$", t)
        if m:
            return {"kind": "skill", "name": "open_app",
                    "args": {"app": m.group(1)}}

        if re.search(r"(take |make |grab )?a? ?screenshot", t):
            return {"kind": "skill", "name": "take_screenshot", "args": {}}

        return {"kind": "fallback"}

    # ---------- utterance ----------

    async def handle_utterance(self, text: str, ctx: dict | None = None) -> dict:
        t0 = time.perf_counter()
        self._t_final = t0
        self._first_action_ms = None
        self._web_ax_t0 = None
        self._ms_kind = None
        trace = self.tracer.begin(text)
        # utterance-frame ctx wins (app/focused/selection/online)
        if ctx:
            for k in ("app", "focused", "selection", "online"):
                if k in ctx:
                    self._ctx[k] = ctx[k]
        outcome = "ok"
        try:
            await self.server.ui("thinking")
            self._utterance = text
            if self._slot and \
                    time.time() - self._slot["t"] >= slots.SLOT_TTL_S:
                self._slot = None
            if self._slot:
                outcome = await self._slot_answer(text, trace)
            # a pending ask keeps task state for 90 s: next utterance answers it
            elif self._pending_task and \
                    time.time() - self._pending_task["t"] < 90:
                goal = self._pending_task["goal"]
                self._pending_task = None
                outcome = await self._planner_loop(
                    goal, trace, answer=text)
            elif self.engine is not None:
                outcome = await self._engine_route(text, trace)
            else:
                plan = self.route(text)
                trace["decisions"].append({"router": plan})
                if plan["kind"] == "skill":
                    outcome = await self.execute_actions(
                        [{"op": "skill", "name": plan["name"],
                          "args": plan["args"]}])
                elif plan["kind"] == "batch":
                    outcome = await self.execute_actions(plan["actions"])
                elif (ans := calc.answer(text)) is not None:
                    trace["decisions"].append({"calc": ans})
                    await self.server.say(ans)
                    await self._end_ui("success")
                else:
                    await self._observe()
                    await self.server.say("I can't do that yet")
                    await self._end_ui("confused")
                    outcome = "fallback"
            trace["release_to_first_action_ms"] = self._first_action_ms
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            return {"outcome": outcome}
        except asyncio.CancelledError:
            outcome = "cancelled"
            trace["release_to_first_action_ms"] = self._first_action_ms
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            raise
        except Exception as e:      # never leave the mascot thinking (ux-11)
            log.exception("utterance failed")
            outcome = "error"
            trace["error"] = f"{type(e).__name__}: {e}"
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            try:
                await self.server.say("Something went wrong. Try again?")
                await self._end_ui("confused")
            except Exception:
                pass
            return {"outcome": outcome}
        finally:
            self.tracer.finish(outcome)

    # ---------- engine path ----------

    async def _brain_tool(self, label: str, args: dict, text: str) -> str:
        """executor:brain skills — local tools, never sent to HandsKit."""
        from . import tools
        self._ms_kind = "total"
        out = await tools.run(self, label, args, text)
        if out == "fallback":
            await self.server.say("That workflow is almost ready")
            await self._end_ui("confused")
        elif out == "ok":
            self._ctx["last_action"] = label
        return out

    async def _engine_route(self, text: str, trace: dict, pre=None) -> str:
        from .planner import worker
        # reuse a speculative route (+ARGS) when the final text matches the
        # last partial (architect-5a)
        if pre is None and self._collect is None:
            out = await self._compound(text, trace)
            if out is not None:
                return out
        norm = _norm(text)
        spec_hit = False
        spec_ext = None
        if pre is not None:
            res = pre
        elif self._spec_fut is not None and norm == self._spec_norm:
            got = await asyncio.wrap_future(self._spec_fut)
            if got is not None:
                res, spec_ext = got
                spec_hit = True
            else:
                res = await worker().submit_async(
                    self.engine.route, text, dict(self._ctx))
        else:
            self._spec_gen += 1          # queued stale partials skip (brain-13)
            res = await worker().submit_async(
                self.engine.route, text, dict(self._ctx))
        self._spec_fut = None
        self._spec_norm = ""
        self._spec_gen += 1
        top5 = sorted(res.probs.items(), key=lambda kv: -kv[1])[:5]
        trace["decisions"].append({"route_probs": top5, "p_top": res.p_top,
                                   "route_ms": res.ms.get("route_ms"),
                                   "spec_hit": spec_hit})
        label = res.top
        if res.p_top < self.tau:
            # unsure -> System 2 with a hint (AGENTS.md contract)
            hint = f"{top5[0][0]} or {top5[1][0]}"
            return await self._planner_loop(text, trace, hint=hint)
        if label == "MULTI_STEP":
            return await self._planner_loop(text, trace)
        if label == "REFUSE":
            await self.server.say("Sorry, I can't do that")
            await self._end_ui("confused")
            return "failed"
        if label == "ANSWER":
            return await self._answer(text, trace)
        if label == "ASK":
            return await self._engine_ask(text, trace, top5)
        # a skill: extract args then execute (skip ARGS for arg-less skills)
        spec = self.catalog.get(label) or {}
        if not spec.get("args"):
            if spec.get("executor") == "brain":
                return await self._brain_tool(label, {}, text)
            return await self.execute_actions(
                [{"op": "skill", "name": label, "args": {}}])
        if spec_ext is not None:
            ext = spec_ext
        else:
            ext = await worker().submit_async(
                self.engine.args, label, text, dict(self._ctx))
        trace["decisions"].append({"args_ms": ext.get("ms", {}).get("args_ms"),
                                   "raw": ext.get("_raw"),
                                   "spec_args": spec_ext is not None})
        raw_args = {k: v for k, v in ext.items()
                    if k not in ("ms", "_raw", "missing")}
        return await self._run_skill(label, raw_args, text, trace)

    def _missing(self, name: str, args: dict) -> list[str]:
        return [a["name"] for a in (self.catalog.get(name) or {}).get("args", [])
                if a.get("required") and args.get(a["name"]) in (None, "")]

    async def _run_skill(self, label: str, raw_args: dict, text: str,
                         trace: dict) -> str:
        """fallback table -> slot fill for still-missing args -> execute."""
        to = _ABS_SKILL.get(label)
        if to and self.catalog.get(to) and (lvl := abs_level(text)) is not None:
            trace["decisions"].append({"abs_switch": [label, to, lvl]})
            label, raw_args = to, {"level": lvl}
        elif label in _ABS_SKILL and (d := rel_delta(text)) is not None:
            trace["decisions"].append({"rel_delta": d})
            raw_args = dict(raw_args, delta=d)
        spec = self.catalog.get(label) or {}
        raw_args = slots.fill_defaults(label, raw_args, text)
        for a in spec.get("args", []):
            if a.get("type") == "app" and a.get("required") and \
                    raw_args.get(a["name"]) in (None, ""):
                app = app_in(text, await self._app_names())
                if app:
                    raw_args[a["name"]] = app
                    trace["decisions"].append({"app_fill": app})
        missing = self._missing(label, raw_args)
        if missing:
            return await self._start_slot(label, raw_args, missing, text,
                                          trace)
        # last_action in the training format, from raw ARGS strings
        # (e.g. 'open_app app=Safari', 'start_timer duration="10 minutes"')
        parts = " ".join(
            f'{k}="{v}"' if isinstance(v, str) and " " in v else f"{k}={v}"
            for k, v in raw_args.items())
        args = self._coerce_args(label, raw_args, utterance=text)
        if spec.get("executor") == "brain":
            out = await self._brain_tool(label, args, text)
        else:
            out = await self.execute_actions(
                [{"op": "skill", "name": label, "args": args}])
        if out == "ok":
            self._ctx["last_action"] = f"{label} {parts}".strip()
            if self.engine is not None:
                self.engine.last_action = self._ctx["last_action"]
        return out

    async def _app_names(self) -> list[str]:
        """running + installed app names from the `apps` RPC, cached 60 s
        (a failed RPC is cached too: aliases still work)."""
        now = time.time()
        if self._apps and now - self._apps[0] < APPS_TTL_S:
            return self._apps[1]
        names = []
        try:
            res = await self.server.rpc("apps", {}, timeout=3)
            names = [a.get("name") if isinstance(a, dict) else a
                     for a in res.get("running") or []] + \
                list(res.get("installed") or [])
        except RuntimeError:
            pass
        names = [n for n in dict.fromkeys(names) if isinstance(n, str) and n]
        self._apps = (now, names)
        return names

    async def _compound(self, text: str, trace: dict) -> str | None:
        """'X and then Y': route each clause on the worker; when every clause
        is a confident native skill, run them in order (ARGS per clause) with
        one combined reply. None -> route the whole utterance instead."""
        parts, joins = split_clauses(text)
        if len(parts) < 2 or len(parts) > MAX_CLAUSES:
            return None
        from .planner import worker
        routed = []
        for c in parts:
            r = await worker().submit_async(self.engine.route, c,
                                            dict(self._ctx))
            spec = self.catalog.get(r.top)
            routed.append([c, r.top, round(r.p_top, 3)])
            if not spec or spec.get("executor") == "brain" or \
                    r.p_top < self.COMPOUND_P:
                trace["decisions"].append({"compound_reject": routed})
                return None
        # a plain 'and' between two same-skill clauses is one phrase
        # ("search for salt and pepper"); 'then' always sequences
        if any(j == "and" and routed[i][1] == routed[i + 1][1]
               for i, j in enumerate(joins)):
            trace["decisions"].append({"compound_reject": routed})
            return None
        trace["compound"] = len(parts)
        trace["decisions"].append({"compound_routes": routed})
        self._spec_fut, self._spec_norm = None, ""
        self._spec_gen += 1
        self._collect = []
        try:
            for c, label, _ in routed:
                if (self.catalog.get(label) or {}).get("args"):
                    ext = await worker().submit_async(
                        self.engine.args, label, c, dict(self._ctx))
                    trace["decisions"].append(
                        {"args_ms": ext.get("ms", {}).get("args_ms"),
                         "raw": ext.get("_raw")})
                    out = await self._run_skill(label, {
                        k: v for k, v in ext.items()
                        if k not in ("ms", "_raw", "missing")}, c, trace)
                else:
                    out = await self.execute_actions(
                        [{"op": "skill", "name": label, "args": {}}])
                if out != "ok":
                    return out
            said = self._collect
        finally:
            self._collect = None
        reply = ", ".join(s if i == 0 else s[:1].lower() + s[1:]
                          for i, s in enumerate(said))
        await self.server.say(_cap12(reply or "Done"))
        await self._end_ui("success")
        return "ok"

    def _arg_spec(self, skill: str, arg: str) -> dict:
        return next((a for a in (self.catalog.get(skill) or {}).get("args", [])
                     if a.get("name") == arg), {})

    async def _start_slot(self, skill: str, args: dict, missing: list[str],
                          text: str, trace: dict) -> str:
        """ask for the first missing arg; the next final utterance fills it."""
        self._slot = {"skill": skill, "args": dict(args),
                      "missing": list(missing), "t": time.time(),
                      "utterance": text, "tries": 0}
        trace["slot_fill"] = True
        trace["decisions"].append({"slot_fill": {"skill": skill,
                                                 "missing": list(missing)}})
        a = self._arg_spec(skill, missing[0])
        await self.server.say(slots.question(skill, missing[0], a.get("type")))
        await self.server.ui("listening")
        return "awaiting_user"

    async def _slot_answer(self, text: str, trace: dict) -> str:
        slot = self._slot
        trace["slot_fill"] = True
        self._spec_fut, self._spec_norm = None, ""
        if slots.CANCEL.match(text.strip()):
            self._slot = None
            trace["decisions"].append({"slot_fill": "cancelled"})
            await self.server.say("Okay, cancelled")
            await self.server.ui("idle")
            return "cancelled"
        # a different-looking command cancels the slot and runs normally
        if self.engine is not None:
            from .planner import worker
            pre = await worker().submit_async(
                self.engine.route, text, dict(self._ctx))
            if pre.top != slot["skill"] and self.catalog.get(pre.top) \
                    and pre.p_top >= 0.8:
                self._slot = None
                trace["decisions"].append({"slot_fill": "superseded",
                                           "by": pre.top})
                return await self._engine_route(text, trace, pre=pre)
        else:
            plan = self.route(text)
            if plan["kind"] == "skill" and plan["name"] != slot["skill"]:
                self._slot = None
                trace["decisions"].append({"router": plan,
                                           "slot_fill": "superseded"})
                return await self.execute_actions(
                    [{"op": "skill", "name": plan["name"],
                      "args": plan["args"]}])
        arg = slot["missing"][0]
        a = self._arg_spec(slot["skill"], arg)
        val = slots.clean_answer(text, a.get("type"))
        trace["decisions"].append({"slot_fill": {
            "skill": slot["skill"], "arg": arg, "value": val}})
        if not slots.valid(a.get("type"), val, a):
            slot["tries"] += 1
            if slot["tries"] >= 2:
                self._slot = None
                await self.server.say("Sorry, I didn't catch that")
                await self._end_ui("confused")
                return "failed"
            slot["t"] = time.time()
            await self.server.say(slots.question(slot["skill"], arg,
                                                 a.get("type")))
            await self.server.ui("listening")
            return "awaiting_user"
        self._slot = None
        args = dict(slot["args"], **{arg: val})
        return await self._run_skill(slot["skill"], args, slot["utterance"],
                                     trace)

    @staticmethod
    def _human(name: str) -> str:
        """'change_volume' -> 'change volume'; specials -> plain words."""
        return {"MULTI_STEP": "a multi-step task", "ASK": "a clarifying question",
                "REFUSE": "a refusal", "ANSWER": "a spoken answer"}.get(
                    name, name.replace("_", " "))

    # ---------- System-2 planner ----------

    _DANGEROUS_LABEL = re.compile(
        r"send|delete|remove|buy|purchase|pay|place order|post|publish|"
        r"erase|empty trash|replace|submit order", re.IGNORECASE)
    _DANGEROUS_COMBOS = {"cmd+delete", "cmd+opt+delete", "cmd+shift+d"}

    def _speculative_route(self, text: str, ctx: dict | None = None):
        """Called for partial utterances — routes (and, for a confident
        skill, extracts ARGS) ahead on the MLX worker, keyed by normalized
        text. A newer partial supersedes: the stale job skips its ARGS."""
        if self.engine is None:
            return
        norm = _norm(text)
        if norm and norm != self._spec_norm:
            self._spec_norm = norm
            self._spec_gen += 1
            c = dict(self._ctx)
            for k in ("app", "focused", "selection", "online"):
                if ctx and k in ctx:
                    c[k] = ctx[k]
            from .planner import worker
            self._spec_fut = worker().submit(
                self._spec_job, text, c, self._spec_gen)

    def _spec_job(self, text: str, ctx: dict, gen: int):
        """worker thread: (route, args|None); None when superseded before it
        ran, so at most one speculative job is ever ahead of the final."""
        if gen != self._spec_gen:
            return None
        res = self.engine.route(text, ctx)
        if res.p_top < self.tau or gen != self._spec_gen or \
                not (self.catalog.get(res.top) or {}).get("args"):
            return res, None
        ext = self.engine.args(res.top, text, ctx)
        return res, (ext if gen == self._spec_gen else None)

    async def _answer(self, text: str, trace: dict) -> str:
        ans = calc.answer(text)      # exact by code: never ask the model
        if ans is not None:
            trace["decisions"].append({"calc": ans})
            await self.server.say(ans)
            await self._end_ui("success")
            return "ok"
        if self.planner is not None:
            from .planner import worker
            ans = await worker().submit_async(
                self.planner.generate,
                "Answer in at most 12 words.",
                f'Question: "{text}"', 48)
            await self.server.say(ans or "I don't know")
        else:
            await self.server.say("I'll answer that soon")
        await self._end_ui("success")
        return "ok"

    def _label_of(self, ref: int | None) -> str:
        if ref is None or not self._last_obs:
            return ""
        for e in self._last_obs.get("elements", []):
            if e.get("ref") == ref:
                return e.get("label", "")
        return ""

    def _app_name(self) -> str:
        return (self._last_obs or {}).get("app") or self._ctx.get("app") \
            or "this app"

    async def _confirm_summary(self, a: dict) -> str:
        """<=12-word summary that names the object (recipient + first body
        words, file name, app)."""
        op = a["op"]
        if op == "confirm":
            return _cap12(str(a.get("summary") or "Continue?").strip('"'))
        if op == "skill":
            n, ar = a["name"], a.get("args", {})
            if n in ("send_message", "compose_email"):
                to = str(ar.get("to") or "them")
                verb = "Text" if n == "send_message" else "Email"
                body = ar.get("body") or ar.get("subject") or ""
                left = 12 - 1 - len(to.split())
                if not body or left < 1:
                    return _cap12(f"{verb} {to}?")
                return f'{verb} {to}: "{_excerpt(body, left)}"?'
            if n == "move_to_trash":
                p = str(ar.get("path") or "this file").rstrip("/")
                return _cap12(f"Move {os.path.basename(p) or p} to Trash?")
            if n == "empty_trash":
                return "Empty the Trash permanently?"
            if n == "quit_app":
                return _cap12(f"Quit {ar.get('app') or self._app_name()}?")
            human = self._human(n).capitalize()
            obj = " ".join(str(v) for k, v in ar.items() if k != "confirmed")
            return _cap12(f"{human} {_excerpt(obj, 6)}?" if obj else
                          f"{human} in {self._app_name()}?")
        app = self._app_name()
        if op == "press":
            label = self._label_of(a.get("ref")) or f"#{a.get('ref')}"
            return _cap12(f'Press "{_excerpt(label, 5)}" in {app}?')
        if op == "keys":
            return _cap12(f"Press {a.get('combo')} in {app}?")
        if op == "type":
            send = " and send" if a.get("enter") else ""
            return _cap12(f'Type "{_excerpt(a.get("text"), 5)}"{send} in {app}?')
        if op == "script":
            code = str(a.get("code") or "")
            m = re.search(r'(?:tell\s+application\s+(?:id\s+)?"|'
                          r'Application\(\s*[\'"])([^"\']+)', code, re.IGNORECASE)
            lang = {"applescript": "AppleScript", "jxa": "JXA"}.get(
                a.get("lang"), a.get("lang") or "a")
            if m:
                return _cap12(f"Run {lang} on {m.group(1)}?")
            first = code.strip().split("\n")[0]
            return _cap12(f'Run {lang} command "{_excerpt(first, 6)}"?')
        return _cap12(f"Continue in {app}?")

    def _batch_line(self, act: str, res: str, legacy: str) -> str:
        """One Last-batch line in the planner's history format: marked
        `[ok] <dsl>`, dsl `<dsl> -> ok`, repr = the legacy dict-repr line."""
        fmt = getattr(self._active_planner or self.planner, "history", "dsl")
        if fmt == "repr":
            return legacy
        if fmt == "dsl":
            return f"{act} -> {res}"
        return f"[{res}] {act}"

    async def _exec_one(self, a: dict) -> dict:
        """Execute one DSL action; `_log` is its Last-batch line."""
        legacy = "script -> " if a["op"] == "script" else _repr_line(a) + "-> "
        act = _log_act(a)
        r = await self._exec_action(a)
        log = r.get("_log") or legacy + str(r.get("status", "?"))
        res = log[len(legacy):] if log.startswith(legacy) \
            else str(r.get("status", "?"))
        r["_log"] = self._batch_line(act, res, log)
        return r

    async def _exec_action(self, a: dict) -> dict:
        """Execute one DSL action. Returns
        {status: ok|failed|awaiting_user|cancelled|done, ...details}."""
        op = a["op"]
        dsl_line = _repr_line(a)
        if op == "ask":
            await self.server.say(a["question"])
            await self.server.ui("listening")
            return {"status": "awaiting_user", "_log": f"{dsl_line}-> ask"}
        if op == "confirm":
            yes = await self.server.ask_confirm(await self._confirm_summary(a))
            if not yes:
                await self.server.say("Okay, cancelled")
                return {"status": "cancelled",
                        "_log": f"{dsl_line}-> cancelled"}
            # one confirm unlocks only the next dangerous action (brain-14)
            self._batch_confirmed = True
            return {"status": "ok", "confirmed": True,
                    "_log": f"{dsl_line}-> confirmed"}
        if op == "done":
            self._done_summary = a["summary"].strip('"')
            return {"status": "done", "summary": a["summary"],
                    "_log": f"{dsl_line}-> done"}
        if op == "refuse":
            await self.server.say("Sorry, I can't do that")
            await self._end_ui("confused")
            return {"status": "failed", "_log": f"{dsl_line}-> refused"}
        if op == "wait":
            self._diff_chain = None
            await asyncio.sleep(a["ms"] / 1000)
            return {"status": "ok", "_log": f"{dsl_line}-> ok"}
        if op == "skill":
            self._diff_chain = None
            a = dict(a)
            a.get("args", {}).pop("confirmed", None)   # model can't self-confirm
            spec = self.catalog.get(a["name"]) or {}
            if spec.get("executor") == "brain":
                # brain-executor skills never reach HandsKit
                st = await self._brain_tool(
                    a["name"], a.get("args", {}), self._current_goal or "")
                st_label = st if st != "ok" else "ok"
                return {"status": st,
                        "_log": f"{dsl_line}-> {st_label}"}
            risk = spec.get("risk")
            if risk in ("confirm", "confirm_if_unsaved"):
                # if we can't tell the unsaved state, confirm (spec rule)
                if not self._take_confirm():
                    yes = await self.server.ask_confirm(
                        await self._confirm_summary(a))
                    if not yes:
                        return {"status": "cancelled"}
                a.setdefault("args", {})["confirmed"] = True
            r = await self._rpc_action("skill",
                                       {"name": a["name"],
                                        "args": a.get("args", {})}, a)
            r["_log"] = f"{dsl_line}-> {'ok' if r['status']=='ok' else 'failed: ' + r.get('error','?')}"
            return r
        if op == "script":
            lang, code = a["lang"], a["code"]
            if self.script_needs_confirm(lang, code) and \
                    not self._take_confirm():
                yes = await self.server.ask_confirm(
                    await self._confirm_summary(a))
                if not yes:
                    return {"status": "cancelled"}
            r = await self._rpc_action(
                "act", {"op": "script", "lang": lang, "code": code}, a)
            if r.get("status") == "failed":
                bubble, why = _script_failure(r.get("error", "?"),
                                              r.get("res"))
                r["_log"] = f"script -> failed: {why}"
                await self.server.say(bubble)
            else:
                r["_log"] = f"script -> {r['status']}"
            if r.get("status") == "ok":
                out = r.get("res", {})
                text_out = out.get("output") or out.get("stdout") or ""
                if text_out:
                    self._script_output = _headtail(str(text_out))
            return r
        if op == "click":
            return {"status": "failed", "error": "no screenshot attached",
                    "_log": f"{dsl_line}-> failed: no screenshot attached"}
        if op in ("press", "type", "keys"):
            # injection + danger guard: destructive labels need a confirm
            needs = False
            if op == "press":
                needs = bool(self._DANGEROUS_LABEL.search(
                    self._label_of(a.get("ref"))))
            elif op == "keys":
                combo = str(a.get("combo", "")).lower()
                needs = combo in self._DANGEROUS_COMBOS or (
                    combo == "cmd+return"
                    and (self._ctx.get("app") or "") in ("Mail", "Messages"))
            elif op == "type" and a.get("enter"):
                needs = bool(self._DANGEROUS_LABEL.search(
                    self._label_of(a.get("ref"))))
                if not needs:
                    app = ((self._last_obs or {}).get("app")
                           or self._ctx.get("app") or "")
                    needs = app in ("Messages", "Mail", "Slack")
            if needs and not self._take_confirm():
                yes = await self.server.ask_confirm(
                    await self._confirm_summary(a))
                if not yes:
                    return {"status": "cancelled"}
            params = {k: v for k, v in a.items() if k != "op"}
            params["op"] = op
            r = await self._rpc_action("act", params, a)
            r["_log"] = f"{dsl_line}-> {'ok' if r['status']=='ok' else 'failed: ' + r.get('error','?')}"
            return r
        # everything else: open, url, scroll -> act
        params = {k: v for k, v in a.items() if k != "op"}
        params["op"] = op
        r = await self._rpc_action("act", params, a)
        r["_log"] = f"{dsl_line}-> {'ok' if r['status']=='ok' else 'failed: ' + r.get('error','?')}"
        return r

    def _take_confirm(self) -> bool:
        """Consume a pending model `confirm`: it covers one dangerous action."""
        ok, self._batch_confirmed = self._batch_confirmed, False
        return ok

    async def _rpc_action(self, method: str, params: dict,
                          action: dict) -> dict:
        """send act/skill rpc; verify expect afterwards."""
        if self._first_action_ms is None:
            self._first_action_ms = (time.perf_counter() - self._t_final) * 1000
        t = time.perf_counter()
        try:
            res = await self.server.rpc(method, params, timeout=45)
        except RuntimeError as e:
            self.tracer.rpc(method, params, {"error": str(e)},
                            (time.perf_counter() - t) * 1000)
            self._diff_chain = None
            return {"status": "failed", "error": str(e)}
        self.tracer.rpc(method, params, self._trace_res(res),
                        (time.perf_counter() - t) * 1000)
        if res.get("epoch"):
            self._last_epoch = res["epoch"]
        # act diffs chain into the next planner observation (skills and
        # full/truncated re-observations break the chain -> fresh observe)
        if self._diff_chain is not None:
            if method == "act" and isinstance(res.get("diff_text"), str) \
                    and not res.get("full") and not res.get("truncated"):
                self._diff_chain.append(res["diff_text"])
            else:
                self._diff_chain = None
        if not res.get("ok", False):
            return {"status": "failed",
                    "error": res.get("error", "?"), "res": res}
        # expect passthrough for every action type (incl. skill/script)
        exp = action.get("expect")
        if exp:
            t2 = time.perf_counter()
            try:
                vres = await self.server.rpc("verify", {"expect": exp},
                                             timeout=15)
            except RuntimeError as e:
                vres = {"ok": False, "observed": str(e)}
            self.tracer.rpc("verify", {"expect": exp}, vres,
                            (time.perf_counter() - t2) * 1000)
            if not vres.get("ok", False):
                return {"status": "failed",
                        "error": f"expect failed: {vres.get('observed', '?')}",
                        "res": res}
        return {"status": "ok", "res": res, "expect_ok": bool(exp)}

    # script confirmation policy (evals-safety-2)
    _SCRIPT_BLOCK = re.compile(
        r"do shell script|doShellScript|do script|run script|keystroke|"
        r"key code|ObjC|\$\.|NSFileManager|trash|delete|remove|saving no|"
        r"send|erase|format|quit|close|move|duplicate|make new|"
        r"set .* to .*|click|perform action|AXPress|do JavaScript|"
        r"open location|«event|\braw\b|open\s+(?:POSIX\s+)?file|"
        r"\.command\b|\.sh\b|removeItem|\brm\s", re.IGNORECASE)
    _SCRIPT_APPS_READ = {
        "com.apple.numbers", "numbers", "music", "calendar", "system events"}
    _SCRIPT_APPS_LIMITED = {"finder", "safari"}
    _READ_VERBS = re.compile(
        r"\b(get|count|exists|reveal|open)\b", re.IGNORECASE)
    _NUMBERS_OK = re.compile(
        r"set value|set background color|sort|make new table", re.IGNORECASE)

    def script_needs_confirm(self, lang: str, code: str) -> bool:
        """confirm unless the script targets only allow-listed apps with
        read-only verbs and contains no blocked pattern. Numbers gets a
        wider exception (set value / background color / sort / make new
        table need no confirm). shell always confirms."""
        if lang == "shell":
            return True
        targets = {t.lower() for t in re.findall(
            r'tell\s+application\s+(?:id\s+)?"([^"]+)"', code, re.IGNORECASE)}
        if lang == "jxa" and not targets:
            targets = {t.lower() for t in re.findall(
                r'Application\(\s*[\'"]([^\'"]+)', code)}
        allowed = self._SCRIPT_APPS_READ | self._SCRIPT_APPS_LIMITED
        if not targets or not targets <= allowed:
            return True
        numbers_only = targets <= {"com.apple.numbers", "numbers"}
        if numbers_only:
            # allowed mutations exempted; any other blocked pattern confirms
            stripped = self._NUMBERS_OK.sub("", code)
            return bool(self._SCRIPT_BLOCK.search(stripped))
        # non-Numbers: blocked pattern -> confirm
        if self._SCRIPT_BLOCK.search(code):
            return True
        # and a read verb must appear (Finder reveal/open, Safari get URL...)
        return not self._READ_VERBS.search(code)

    async def _planner_loop(self, text: str, trace: dict,
                            hint: str | None = None,
                            answer: str | None = None) -> str:
        """System 2: observe -> plan(stream) -> execute -> replan.
        12 turns / 60 s. Returns final outcome."""
        if self.planner is None:
            await self.server.say("Planning isn't ready yet")
            await self._end_ui("confused")
            return "fallback"
        from . import dsl
        from .planner import worker
        goal = text
        if answer:
            goal += f'\nUser answer: "{answer}"'
        self._ms_kind = "total"
        t_start = time.perf_counter()
        self._script_output = None
        last_batch: list[str] | None = None
        prev_had_failure = False
        done_rejected = False
        prev_expect_ok = False
        obs_text = ""
        diffs: list[str] | None = None
        fail_streak, prev_fail_key = 0, None
        planner, escalated = self.planner, False
        self._active_planner = planner
        for turn in range(12):
            if time.perf_counter() - t_start > 60:
                break
            if diffs is not None and self._last_obs:
                # last batch's act diffs describe the UI: skip the observe RPC
                for d in diffs:
                    obs_text = obsdiff.apply_diff(obs_text, d)
                self._last_obs = dict(
                    self._last_obs, text=obs_text, diff_text="\n".join(diffs),
                    elements=obsdiff.elements(
                        obs_text, self._last_obs.get("elements")))
                trace["decisions"].append({"obs_from_diff": turn,
                                           "n_diffs": len(diffs)})
                obs_fresh = False
            else:
                obs = await self._observe()
                obs_fresh = bool(obs)
                if obs:
                    obs_text = obs["text"]
                    self._last_obs = obs
                elif not obs_text:
                    obs_text = "(no observation available)"
            self._diff_chain = []
            q: asyncio.Queue = asyncio.Queue()
            cancel = threading.Event()
            loop = asyncio.get_running_loop()
            fut = worker().submit(
                planner.plan, goal, obs_text, last_batch, q, loop,
                cancel, hint, self._script_output)
            self._script_output = None   # consumed by this turn
            self._current_goal = goal
            # stream-consume lines; execute each action once complete
            lines: list[str] = []
            pending: list[dict] = []       # parsed, not yet flushed
            batch_log: list[str] = []
            harness_reject = False
            failed = False
            self._batch_confirmed = False
            res_status = "ok"
            done_seen = False
            n_executed = 0
            last_exp_ok = False
            skipped: list[str] = []      # prose / tags / fences, not actions
            n_actions = 0
            fail_key = None              # normalized action line that failed
            script_buf: list[str] | None = None   # multi-line """ block
            try:
                while True:
                    line = await q.get()
                    if line is None:
                        break
                    lines.append(line)
                    # accumulate triple-quoted script blocks until they close
                    if script_buf is not None:
                        script_buf.append(line)
                        if '"""' in line:
                            line = "\n".join(script_buf)
                            script_buf = None
                        else:
                            continue
                    elif line.startswith("script") and line.count('"""') % 2:
                        script_buf = [line]
                        continue
                    if re.match(r"^(expect|#)", line):
                        if pending and line.startswith("expect"):
                            pending[-1]["expect"] = line[7:].strip()
                        continue
                    dl = dsl.action_line(line, self.catalog.skills)
                    if dl is None:
                        skipped.append(line)
                        continue
                    line = dl
                    n_actions += 1
                    # a new action line: flush the previous pending action
                    if pending and not failed and not done_seen:
                        a = pending.pop(0)
                        r = await self._exec_one(a)
                        batch_log.append(r["_log"])
                        if r["status"] == "done":
                            done_seen = True
                            cancel.set()      # done ends the batch's execution
                        else:
                            n_executed += 1
                            last_exp_ok = bool(r.get("expect_ok"))
                            if r["status"] != "ok":
                                failed = True
                                cancel.set()
                                res_status = r["status"]
                                fail_key = _action_key(a)
                    try:
                        acts = dsl.parse(line)
                        pending.extend(acts)
                    except Exception as e:
                        failed = True
                        res_status = "failed"
                        fail_key = " ".join(line.lower().split())
                        batch_log.append(self._batch_line(
                            line, f"failed: {e}", f"{line} -> failed: {e}"))
                        cancel.set()
            except asyncio.CancelledError:
                cancel.set()   # stop the decode
                raise
            # flush tail action(s)
            while pending and not failed and not done_seen:
                a = pending.pop(0)
                r = await self._exec_one(a)
                batch_log.append(r["_log"])
                if r["status"] == "done":
                    done_seen = True
                else:
                    n_executed += 1
                    last_exp_ok = bool(r.get("expect_ok"))
                    if r["status"] != "ok":
                        failed = True
                        res_status = r["status"]
                        fail_key = _action_key(a)
                        cancel.set()
            info = await asyncio.wrap_future(fut)
            trace["decisions"].append({
                "planner_turn": turn, "lines": lines,
                "ttft_ms": round(info["ttft_ms"], 1),
                "decode_tok_s": round(info["decode_tok_s"], 1),
                "tokens": info["tokens"]})
            if skipped:
                trace["decisions"].append({"skipped_lines": skipped})
                batch_log.append(f"ignored {len(skipped)} non-action lines")
            last_batch = batch_log or None
            lo = self._last_obs or {}
            # capped/truncated observations can't be rebuilt from diffs: an
            # element pushed past max_nodes shows up as `- #ref` (hands-13)
            diffs = self._diff_chain if n_executed and not lo.get("truncated") \
                and len(lo.get("elements") or []) < 150 else None
            self._diff_chain = None
            if res_status == "awaiting_user":
                self._pending_task = {"goal": text, "t": time.time()}
                return "awaiting_user"
            if res_status == "cancelled":
                return "cancelled"
            if res_status == "fallback":
                return "fallback"     # brain tool not ready: one bubble (planner-18)
            # done is verified, never trusted (planner-13): alone in its batch
            # and either the previous batch's last expect passed, or the
            # planner saw a fresh observe (not a diff rebuild); after a
            # failure, done is rejected once
            if done_seen and not failed:
                if n_executed == 0 and (prev_expect_ok or obs_fresh and (
                        not prev_had_failure or done_rejected)):
                    summary = self._done_summary or "Done"
                    await self.server.say(summary[:60])
                    await self._end_ui("success")
                    return "ok"
                done_rejected = True
                harness_reject = True
                why = "failed: not verified; check the fresh observation"
                batch_log.append(self._batch_line("done", why,
                                                  f"done -> {why}"))
                failed = True
                diffs = None          # force a fresh observe next turn
            prev_expect_ok = n_executed > 0 and not failed and last_exp_ok
            if harness_reject and res_status != "failed":
                # the harness's own done rejection isn't a planner failure
                # for the loop guard (planner-20)
                prev_had_failure = True
                continue
            if res_status == "failed" or failed or not n_actions:
                # loop guard: same action failing twice in a row, or three
                # failed turns -> ask the user instead of burning turns
                fail_streak += 1
                same = fail_key is not None and fail_key == prev_fail_key
                if self.planner_escalate is not None and fail_streak >= 2:
                    if not escalated:
                        # opt-in: the escalation planner takes the remaining
                        # turns instead of stopping
                        planner, escalated = self.planner_escalate, True
                        self._active_planner = planner
                        trace["planner_escalated"] = True
                        trace["decisions"].append({"planner_escalated": turn})
                        fail_streak, prev_fail_key = 0, None
                        prev_had_failure = True
                        continue
                    same = True         # escalation failed twice: stop
                if same or fail_streak >= 3:
                    trace["decisions"].append({"loop_guard": "same_action"
                                               if same else "3_failed_turns",
                                               "line": fail_key})
                    self._pending_task = {"goal": text, "t": time.time()}
                    await self.server.say("I'm stuck on that, can you help?")
                    await self._end_ui("confused")
                    return "awaiting_user"
                prev_fail_key = fail_key
                prev_had_failure = True
                continue          # replan with fresh observation
            fail_streak, prev_fail_key = 0, None
            # batch fully executed without a terminal op -> keep going
            prev_had_failure = False
        await self.server.say("That didn't work")
        await self._end_ui("confused")
        return "failed"

    async def _engine_ask(self, text: str, trace: dict, top5) -> str:
        # nearest skill below the special options
        skill = next((n for n, _ in top5 if self.catalog.get(n)), None)
        if skill:
            from .planner import worker
            ext = await worker().submit_async(
                self.engine.args, skill, text, dict(self._ctx))
            if "missing" in ext:
                await self.server.say(f"What {ext['missing']} should I use?")
                await self._end_ui("confused")
                return "awaiting_user"
        await self.server.say("What did you mean?")
        await self._end_ui("confused")
        return "awaiting_user"

    @staticmethod
    def _coerce_typed(typ: str, v, a: dict):
        """Coerce an extracted arg to its catalog type. None = uncoercible."""
        from . import decision as _d
        if typ == "datetime" and isinstance(v, str):
            return _d.parse_datetime(v) or v
        if typ == "duration" and isinstance(v, str):
            sec = _d.parse_duration(v)
            return sec if sec is not None else v
        if typ == "int":
            n = _d.normalize_level(v)
            return n if n is not None else (int(v) if str(v).lstrip("+-").isdigit() else None)
        if typ == "float":
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        if typ == "bool":
            if isinstance(v, bool):
                return v
            s = str(v).strip().lower()
            if s in ("true", "yes", "on", "1"):
                return True
            if s in ("false", "no", "off", "0"):
                return False
            return None
        if typ == "enum" and a.get("values"):
            s = str(v).strip().lower()
            for opt in a["values"]:
                if str(opt).lower() == s:
                    return opt
            return str(v)   # leave; catalog.validate_args catches bad enum
        return v

    _BOOL_OFF = re.compile(
        r"\b(off|disable|deactivate|stop|kill|shut\s*off|turn off)\b", re.IGNORECASE)
    _BOOL_ON = re.compile(
        r"\b(on|enable|activate|start|turn on|back on)\b", re.IGNORECASE)

    def _bool_on(self, name: str, utterance: str) -> bool | None:
        """`on` from the utterance, or None (keep the model's value). For mute,
        on/off words describe the sound: 'sound off' = mute on."""
        u = utterance.lower()
        snd = r"\b(sound|audio|volume|speakers?)\b"
        if name == "mute":
            if re.search(r"\bunmute\b|" + snd + r"[^,.;]*\bon\b|"
                         r"\bturn (the )?(sound|audio) (back )?on\b", u):
                return False
            if re.search(r"\bmute\b|\bsilence\b|" + snd + r"[^,.;]*\boff\b|"
                         r"\b(kill|cut|shut off|turn off)\b[^,.;]*" + snd, u):
                return True
            return None
        if name not in ("wifi", "bluetooth", "dark_mode"):
            return None
        if name == "dark_mode" and re.search(r"\blight mode\b", u):
            return False
        if re.search(r"\bback on\b|\boff and (then )?on\b", u):
            return True
        m = re.search(r"\b(?:turn|switch|put|set)\b[^,.;]*?\b(on|off)\b", u)
        if m:
            return m.group(1) == "on"
        off, on = self._BOOL_OFF.search(u), self._BOOL_ON.search(u)
        return bool(on) if bool(off) != bool(on) else None

    def _coerce_args(self, name: str, args: dict,
                     utterance: str | None = None) -> dict:
        """datetime/duration by code; catalog-typed coercion (SPEC 1.4).
        For bool args named `on`, the utterance decides by regex and
        overrides the model output when it matches."""
        from . import decision as _d
        spec = self.catalog.get(name) or {}
        out = {}
        for a in spec.get("args", []):
            key, typ = a.get("name"), a.get("type")
            if key == "on" and typ == "bool" and utterance:
                b = self._bool_on(name, utterance)
                if b is not None:
                    out[key] = b
                    continue
            if key not in args:
                continue
            v = args[key]
            if key == "level":
                n = _d.normalize_level(v)
                out[key] = n if n is not None else v
            elif key == "delta":
                n = _d.normalize_delta(v)
                out[key] = n if n is not None else v
            else:
                c = self._coerce_typed(typ, v, a)
                out[key] = c if c is not None else v
        # zero-shot fallback: model echoed e.g. 'set_volume=30' — if no known
        # arg was emitted and the skill has exactly one required arg, use it.
        if not out and args:
            req = [a for a in spec.get("args", []) if a.get("required")]
            if len(req) == 1:
                v = next(iter(args.values()))
                typ = req[0].get("type")
                from . import decision as _d
                if typ == "datetime":
                    out[req[0]["name"]] = _d.parse_datetime(str(v)) or v
                elif typ == "duration":
                    out[req[0]["name"]] = _d.parse_duration(str(v)) or v
                else:
                    out[req[0]["name"]] = v
        return out

    # ---------- execution ----------

    async def _observe(self):
        """observe; while Chrome fills its web AX tree (`web_ax_pending`,
        ~2 s after the switch) wait out the window once and re-observe;
        never a screenshot because of it."""
        res = await self._observe_once()
        if not res or not res.get("web_ax_pending"):
            if res:
                self._web_ax_t0 = None
            return res
        now = time.perf_counter()
        if self._web_ax_t0 is None:
            self._web_ax_t0 = now
        await asyncio.sleep(max(0.0, self.WEB_AX_WINDOW_S
                                - (now - self._web_ax_t0)))
        res = await self._observe_once() or res
        if self.tracer.current is not None:
            tr = self.tracer.current
            tr["web_ax_wait_ms"] = round(tr.get("web_ax_wait_ms", 0) + (
                time.perf_counter() - now) * 1000, 1)
        return res

    async def _observe_once(self):
        t = time.perf_counter()
        try:
            res = await self.server.rpc(
                "observe", {"scope": "focused_window", "max_nodes": 150,
                            "diff": True}, timeout=10)
            self._last_epoch = res.get("epoch")
            self.tracer.rpc("observe", {}, res,
                            (time.perf_counter() - t) * 1000)
            return res
        except RuntimeError as e:
            self.tracer.rpc("observe", {}, {"error": str(e)},
                            (time.perf_counter() - t) * 1000)
            return None

    def _summary(self, name: str, args: dict) -> str:
        desc = (self.catalog.get(name) or {}).get("description", name)
        return desc

    async def _end_ui(self, mascot: str, bubble: str | None = None):
        """Final ui of a request carries `ms` (AGENTS.md): release-to-first-
        action for native skills, total for planner/brain-tool/answer."""
        ms = None
        if getattr(self, "_t_final", None) is not None:
            ms = (time.perf_counter() - self._t_final) * 1000
            if self._ms_kind == "skill" and self._first_action_ms is not None:
                ms = self._first_action_ms
        await self.server.ui(mascot, bubble, ms=ms)

    async def _fail(self, raw_error: str, friendly: str = "That didn't work"):
        if self.tracer.current is not None:
            self.tracer.current.setdefault("decisions", []).append(
                {"error": raw_error})
        await self.server.say(friendly)
        await self._end_ui("confused")
        return "failed"

    async def execute_actions(self, actions: list[dict]) -> str:
        """Run a batch; stop at the first failed action or failed expect.
        Returns an outcome: ok | failed | awaiting_user | cancelled."""
        if len(actions) > dsl.MAX_BATCH:
            actions = actions[: dsl.MAX_BATCH]
        unverified = False        # an act ran without a passing expect
        for a in actions:
            op = a["op"]
            if op == "skill":
                r = await self._skill(a)
                if r != "ok":
                    return r
                unverified = False    # HandsKit skills verify their own result
                continue
            if op == "ask":
                await self.server.say(a["question"])
                await self.server.ui("listening")
                return "awaiting_user"
            if op == "confirm":
                yes = await self.server.ask_confirm(
                    await self._confirm_summary(a))
                if not yes:
                    await self.server.say("Okay, cancelled")
                    return "cancelled"
                continue
            if op == "done":
                await self.server.say(a["summary"])
                if unverified:     # DONE is verified, never trusted (es-11)
                    await self._end_ui("idle")
                    return "unverified"
                await self._end_ui("success")
                return "ok"
            if op == "refuse":
                await self.server.say("Sorry, I can't do that")
                await self._end_ui("confused")
                return "failed"
            if op == "script":
                return await self._script(a)
            if op == "wait":
                await asyncio.sleep(a["ms"] / 1000)
                continue
            # everything else goes to hands via act
            params = {k: v for k, v in a.items() if k != "op"}
            params["op"] = op
            if self._last_epoch is not None:
                params["epoch"] = self._last_epoch
            t = time.perf_counter()
            try:
                res = await self.server.rpc("act", params, timeout=15)
            except RuntimeError as e:
                self.tracer.rpc("act", params, {"error": str(e)},
                                (time.perf_counter() - t) * 1000)
                return await self._fail(str(e))
            self.tracer.rpc("act", params, self._trace_res(res),
                            (time.perf_counter() - t) * 1000)
            if res.get("epoch"):
                self._last_epoch = res["epoch"]
            if not res.get("ok", False):
                return await self._fail(res.get("error", "act failed"))
            unverified = True
            if a.get("expect"):
                vres = await self.server.rpc("verify", {"expect": a["expect"]},
                                             timeout=15)
                if not vres.get("ok", False):
                    return await self._fail(
                        f"expect failed: {vres.get('observed', '?')}")
                unverified = False
        return "ok"

    @staticmethod
    def _trace_res(res) -> dict:
        if not isinstance(res, dict):
            return res
        keep = {k: res[k] for k in
                ("ok", "error", "observed", "diff_text", "expect_ok",
                 "act_ms", "settle_ms", "epoch")
                if k in res}
        return keep

    async def _script(self, a: dict) -> str:
        lang, code = a["lang"], a["code"]
        if self.script_needs_confirm(lang, code):
            yes = await self.server.ask_confirm(
                await self._confirm_summary(a))
            if not yes:
                await self.server.say("Okay, cancelled")
                return "cancelled"
        params = {"op": "script", "lang": lang, "code": code}
        t = time.perf_counter()
        try:
            res = await self.server.rpc("act", params, timeout=30)
        except RuntimeError as e:
            self.tracer.rpc("act", params, {"error": str(e)},
                            (time.perf_counter() - t) * 1000)
            return await self._fail(str(e), "Script failed")
        self.tracer.rpc("act", params, self._trace_res(res),
                        (time.perf_counter() - t) * 1000)
        if not res.get("ok", False):
            err = res.get("error", "script failed")
            return await self._fail(err, _script_failure(err, res)[0])
        return "ok"

    async def _skill(self, a: dict) -> str:
        name, args = a["name"], a.get("args", {})
        args = slots.fill_defaults(name, args, self._utterance)
        missing = self._missing(name, args)
        if missing and self.catalog.get(name):
            trace = self.tracer.current or {"decisions": []}
            return await self._start_slot(name, args, missing,
                                          self._utterance, trace)
        try:
            args = self.catalog.validate_args(name, args)
        except CatalogError as e:
            return await self._fail(
                str(e), f"I didn't catch the details to {replies.human(name)}.")
        spec = self.catalog.get(name) or {}
        if spec.get("risk") == "confirm" and not args.get("confirmed"):
            summary = await self._confirm_summary(
                {"op": "skill", "name": name, "args": args})
            await self.server.ui("thinking", summary)
            try:
                yes = await self.server.ask_confirm(summary)
            except RuntimeError:
                yes = False
            if not yes:
                await self.server.say("Okay, cancelled")
                return "cancelled"
            args["confirmed"] = True
        await self.server.ui("acting")
        if self._ms_kind is None:
            self._ms_kind = "skill"
        if self._first_action_ms is None:
            self._first_action_ms = \
                (time.perf_counter() - self._t_final) * 1000
        t = time.perf_counter()
        try:
            res = await self.server.rpc(
                "skill", {"name": name, "args": args}, timeout=45)
        except RuntimeError as e:
            self.tracer.rpc("skill", {"name": name, "args": args},
                            {"error": str(e)}, (time.perf_counter() - t) * 1000)
            return await self._fail(str(e), replies.fail_text(name, args, str(e)))
        self.tracer.rpc("skill", {"name": name, "args": args},
                        self._trace_res(res), (time.perf_counter() - t) * 1000)
        if not res.get("ok", False):
            return await self._fail(res.get("error", "?"), replies.fail_text(
                name, args, str(res.get("error", ""))))
        reply = replies.success_text(name, args, res.get("result"))
        if self._collect is not None:
            self._collect.append(reply)
            return "ok"
        await self.server.say(reply)
        await self._end_ui("success")
        return "ok"
