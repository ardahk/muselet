"""v0 stub router + batch executor.

Utterance -> regex rule -> skill call or DSL batch -> hands executes.
Everything is traced and the app gets ui/say messages.
"""

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


def _num(tok: str) -> int | None:
    tok = tok.strip().lower()
    if tok.isdigit():
        return int(tok)
    return _WORD_NUM.get(tok)


class Orchestrator:
    def __init__(self, server, catalog: Catalog | None = None,
                 tracer: Tracer | None = None):
        self.server = server
        self.catalog = catalog or Catalog.load()
        self.tracer = tracer or Tracer()
        self._last_epoch = None

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
            plan = self.route(text)
            trace["decisions"].append({"router": plan})
            if plan["kind"] == "skill":
                ok = await self.execute_actions(
                    [{"op": "skill", "name": plan["name"],
                      "args": plan["args"]}])
                outcome = "ok" if ok else "failed"
            elif plan["kind"] == "batch":
                ok = await self.execute_actions(plan["actions"])
                outcome = "ok" if ok else "failed"
            else:
                await self._observe()
                await self.server.say("I can't do that yet")
                await self.server.ui("confused")
                outcome = "fallback"
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            return {"outcome": outcome}
        finally:
            self.tracer.finish(outcome)

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
        kv = " ".join(f"{k}={v}" for k, v in args.items())
        return f"{desc}" + (f" ({kv})" if kv else "")

    async def execute_actions(self, actions: list[dict]) -> bool:
        """Run a batch; stop at the first failed action or failed expect."""
        if len(actions) > dsl.MAX_BATCH:
            actions = actions[: dsl.MAX_BATCH]
        for a in actions:
            op = a["op"]
            if op == "skill":
                ok = await self._skill(a)
                if not ok:
                    return False
                continue
            if op in ("ask",):
                await self.server.say(a["question"])
                await self.server.ui("listening")
                continue
            if op == "confirm":
                yes = await self.server.ask_confirm(a["summary"])
                if not yes:
                    await self.server.say("Cancelled")
                    return False
                continue
            if op == "done":
                await self.server.say(a["summary"])
                await self.server.ui("success")
                return True
            if op == "refuse":
                await self.server.say(f"I can't do that: {a['reason']}")
                await self.server.ui("confused")
                return False
            if op == "wait":
                import asyncio
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
                await self.server.say(f"Action failed: {e}")
                await self.server.ui("confused")
                return False
            self.tracer.rpc("act", params, res,
                            (time.perf_counter() - t) * 1000)
            if res.get("epoch"):
                self._last_epoch = res["epoch"]
            if not res.get("ok", True):
                await self.server.say(
                    f"Action failed: {res.get('error', '?')}")
                await self.server.ui("confused")
                return False
        return True

    async def _skill(self, a: dict) -> bool:
        name, args = a["name"], a.get("args", {})
        try:
            args = self.catalog.validate_args(name, args)
        except CatalogError as e:
            await self.server.say(str(e))
            return False
        spec = self.catalog.get(name) or {}
        if spec.get("risk") == "confirm" and not args.get("confirmed"):
            await self.server.ui("thinking", self._summary(name, args))
            try:
                yes = await self.server.ask_confirm(self._summary(name, args))
            except RuntimeError:
                yes = False
            if not yes:
                await self.server.say("Cancelled")
                return False
            args["confirmed"] = True
        await self.server.ui("acting")
        t = time.perf_counter()
        try:
            res = await self.server.rpc(
                "skill", {"name": name, "args": args}, timeout=30)
        except RuntimeError as e:
            self.tracer.rpc("skill", {"name": name, "args": args},
                            {"error": str(e)}, (time.perf_counter() - t) * 1000)
            await self.server.say(f"{name} failed: {e}")
            await self.server.ui("confused")
            return False
        self.tracer.rpc("skill", {"name": name, "args": args}, res,
                        (time.perf_counter() - t) * 1000)
        if not res.get("ok", True):
            err = res.get("error", "?")
            await self.server.say(f"{name} failed: {err}")
            await self.server.ui("confused")
            return False
        await self.server.ui("success")
        return True
