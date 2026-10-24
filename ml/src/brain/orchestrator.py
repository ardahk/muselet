"""v0 stub router + batch executor.

Utterance -> regex rule -> skill call or DSL batch -> hands executes.
Everything is traced and the app gets ui/say messages.
"""

import asyncio
import logging
import re
import time

from . import dsl
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
    r"log ?out|do shell script|erase|format)\b", re.I)


def _num(tok: str) -> int | None:
    tok = tok.strip().lower()
    if tok.isdigit():
        return int(tok)
    return _WORD_NUM.get(tok)


def script_needs_confirm(lang: str, code: str) -> bool:
    """Brain-side script policy: shell always confirms; applescript/jxa
    confirm when the code matches a destructive pattern."""
    if lang == "shell":
        return True
    if lang in ("applescript", "jxa"):
        return bool(_DANGEROUS_SCRIPT.search(code))
    return True


class Orchestrator:
    def __init__(self, server, catalog: Catalog | None = None,
                 tracer: Tracer | None = None, engine=None, tau: float = 0.55):
        self.server = server
        self.catalog = catalog or Catalog.load()
        self.tracer = tracer or Tracer()
        self.engine = engine
        self.tau = tau
        self._last_epoch = None
        self._ctx = {"app": "none", "focused": "none", "selection": False,
                     "last_action": "none"}

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

    async def handle_utterance(self, text: str) -> dict:
        t0 = time.perf_counter()
        trace = self.tracer.begin(text)
        outcome = "ok"
        try:
            await self.server.ui("thinking")
            if self.engine is not None:
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
                else:
                    await self._observe()
                    await self.server.say("I can't do that yet")
                    await self.server.ui("confused")
                    outcome = "fallback"
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            return {"outcome": outcome}
        except asyncio.CancelledError:
            outcome = "cancelled"
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            raise
        finally:
            self.tracer.finish(outcome)

    # ---------- engine path ----------

    async def _engine_route(self, text: str, trace: dict) -> str:
        res = self.engine.route(text, self._ctx)
        top5 = sorted(res.probs.items(), key=lambda kv: -kv[1])[:5]
        trace["decisions"].append({"route_probs": top5, "p_top": res.p_top,
                                   "route_ms": res.ms.get("route_ms")})
        label = res.top
        if res.p_top < self.tau:
            a, b = top5[0][0], top5[1][0]
            await self.server.say(f"Did you mean {a} or {b}?")
            await self.server.ui("confused")
            return "awaiting_user"
        if label == "MULTI_STEP":
            await self.server.say("Multi-step tasks are coming soon")
            await self.server.ui("confused")
            return "fallback"
        if label == "REFUSE":
            await self.server.say("Sorry, I can't do that")
            await self.server.ui("confused")
            return "failed"
        if label == "ANSWER":
            await self.server.say("I'll answer that soon")
            await self.server.ui("confused")
            return "fallback"
        if label == "ASK":
            return await self._engine_ask(text, trace, top5)
        # a skill: extract args then execute
        t_args = time.perf_counter()
        ext = self.engine.args(label, text, self._ctx)
        trace["decisions"].append({"args_ms": ext["ms"].get("args_ms"),
                                   "raw": ext.get("_raw")})
        if "missing" in ext:
            await self.server.say(f"What {ext['missing']} should I use?")
            await self.server.ui("confused")
            return "awaiting_user"
        args = {k: v for k, v in ext.items()
                if k not in ("ms", "_raw", "missing")}
        args = self._coerce_args(label, args)
        return await self.execute_actions(
            [{"op": "skill", "name": label, "args": args}])

    async def _engine_ask(self, text: str, trace: dict, top5) -> str:
        # nearest skill below the special options
        skill = next((n for n, _ in top5 if self.catalog.get(n)), None)
        if skill:
            ext = self.engine.args(skill, text, self._ctx)
            if "missing" in ext:
                await self.server.say(f"What {ext['missing']} should I use?")
                await self.server.ui("confused")
                return "awaiting_user"
        await self.server.say("What did you mean?")
        await self.server.ui("confused")
        return "awaiting_user"

    def _coerce_args(self, name: str, args: dict) -> dict:
        """datetime/duration by code; level/delta normalizations (SPEC 1.4)."""
        from . import decision as _d
        spec = self.catalog.get(name) or {}
        out = {}
        for a in spec.get("args", []):
            key, typ = a.get("name"), a.get("type")
            if key not in args:
                continue
            v = args[key]
            if typ == "datetime" and isinstance(v, str):
                out[key] = _d.parse_datetime(v) or v
            elif typ == "duration" and isinstance(v, str):
                sec = _d.parse_duration(v)
                out[key] = sec if sec is not None else v
            elif key == "level":
                n = _d.normalize_level(v)
                out[key] = n if n is not None else v
            elif key == "delta":
                n = _d.normalize_delta(v)
                out[key] = n if n is not None else v
            else:
                out[key] = v
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

    async def _fail(self, raw_error: str, friendly: str = "That didn't work"):
        await self.server.say(friendly)
        await self.server.ui("confused")
        return "failed"

    async def execute_actions(self, actions: list[dict]) -> str:
        """Run a batch; stop at the first failed action or failed expect.
        Returns an outcome: ok | failed | awaiting_user | cancelled."""
        if len(actions) > dsl.MAX_BATCH:
            actions = actions[: dsl.MAX_BATCH]
        for a in actions:
            op = a["op"]
            if op == "skill":
                r = await self._skill(a)
                if r != "ok":
                    return r
                continue
            if op == "ask":
                await self.server.say(a["question"])
                await self.server.ui("listening")
                return "awaiting_user"
            if op == "confirm":
                yes = await self.server.ask_confirm(a["summary"])
                if not yes:
                    await self.server.say("Okay, cancelled")
                    return "cancelled"
                continue
            if op == "done":
                await self.server.say(a["summary"])
                await self.server.ui("success")
                return "ok"
            if op == "refuse":
                await self.server.say("Sorry, I can't do that")
                await self.server.ui("confused")
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
        if script_needs_confirm(lang, code):
            yes = await self.server.ask_confirm(f"Run a {lang} script?")
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
            return await self._fail(res.get("error", "script failed"),
                                  "Script failed")
        return "ok"

    async def _skill(self, a: dict) -> str:
        name, args = a["name"], a.get("args", {})
        try:
            args = self.catalog.validate_args(name, args)
        except CatalogError as e:
            await self.server.say("I'm missing some details")
            return "failed"
        spec = self.catalog.get(name) or {}
        if spec.get("risk") == "confirm" and not args.get("confirmed"):
            await self.server.ui("thinking", self._summary(name, args))
            try:
                yes = await self.server.ask_confirm(self._summary(name, args))
            except RuntimeError:
                yes = False
            if not yes:
                await self.server.say("Okay, cancelled")
                return "cancelled"
            args["confirmed"] = True
        await self.server.ui("acting")
        t = time.perf_counter()
        try:
            res = await self.server.rpc(
                "skill", {"name": name, "args": args}, timeout=45)
        except RuntimeError as e:
            self.tracer.rpc("skill", {"name": name, "args": args},
                            {"error": str(e)}, (time.perf_counter() - t) * 1000)
            return await self._fail(str(e), f"{name} didn't work")
        self.tracer.rpc("skill", {"name": name, "args": args},
                        self._trace_res(res), (time.perf_counter() - t) * 1000)
        if not res.get("ok", False):
            return await self._fail(res.get("error", "?"),
                                    f"{name} didn't work")
        await self.server.ui("success")
        return "ok"
