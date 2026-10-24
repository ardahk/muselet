"""v0 stub router + batch executor.

Utterance -> regex rule -> skill call or DSL batch -> hands executes.
Everything is traced and the app gets ui/say messages.
"""

import asyncio
import logging
import re
import threading
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
        self.planner = None
        self._last_epoch = None
        self._last_obs = None
        self._ctx = {"app": "none", "focused": "none", "selection": False,
                     "last_action": "none"}
        self._t_final = 0.0
        self._first_action_ms: float | None = None
        self._batch_confirmed = False
        self._pending_task: dict | None = None
        self._script_output: str | None = None
        self._spec_norm = ""
        self._spec_fut = None
        self._current_goal = ""
        self._done_summary = None

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
        trace = self.tracer.begin(text)
        # utterance-frame ctx wins (app/focused/selection/online)
        if ctx:
            for k in ("app", "focused", "selection", "online"):
                if k in ctx:
                    self._ctx[k] = ctx[k]
        outcome = "ok"
        try:
            await self.server.ui("thinking")
            # a pending ask keeps task state for 90 s: next utterance answers it
            if self._pending_task and \
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
                else:
                    await self._observe()
                    await self.server.say("I can't do that yet")
                    await self.server.ui("confused")
                    outcome = "fallback"
            trace["release_to_first_action_ms"] = self._first_action_ms
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            return {"outcome": outcome}
        except asyncio.CancelledError:
            outcome = "cancelled"
            trace["release_to_first_action_ms"] = self._first_action_ms
            self.tracer.stage("total", (time.perf_counter() - t0) * 1000)
            raise
        finally:
            self.tracer.finish(outcome)

    # ---------- engine path ----------

    async def _brain_tool(self, label: str, args: dict, text: str) -> str:
        """executor:brain skills — local tools, never sent to HandsKit."""
        from . import tools
        out = await tools.run(self, label, args, text)
        if out == "fallback":
            await self.server.say("That workflow is almost ready")
            await self.server.ui("confused")
        elif out == "ok":
            self._ctx["last_action"] = label
        return out

    async def _engine_route(self, text: str, trace: dict) -> str:
        from .planner import worker
        # reuse a speculative route when the final text matches the last
        # partial (architect-5a)
        norm = re.sub(r"\s+", " ", text.strip().lower())
        spec_hit = False
        if self._spec_fut is not None and norm == self._spec_norm:
            res = await asyncio.wrap_future(self._spec_fut)
            spec_hit = True
        else:
            res = await worker().submit_async(
                self.engine.route, text, dict(self._ctx))
        self._spec_fut = None
        self._spec_norm = ""
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
            await self.server.ui("confused")
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
        t_args = time.perf_counter()
        ext = self.engine.args(label, text, self._ctx)
        trace["decisions"].append({"args_ms": ext["ms"].get("args_ms"),
                                   "raw": ext.get("_raw")})
        if "missing" in ext:
            await self.server.say(f"What {ext['missing']} should I use?")
            await self.server.ui("confused")
            return "awaiting_user"
        raw_args = {k: v for k, v in ext.items()
                    if k not in ("ms", "_raw", "missing")}
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
            self.engine.last_action = self._ctx["last_action"]
        return out

    @staticmethod
    def _human(name: str) -> str:
        """'change_volume' -> 'change volume'; specials -> plain words."""
        return {"MULTI_STEP": "a multi-step task", "ASK": "a clarifying question",
                "REFUSE": "a refusal", "ANSWER": "a spoken answer"}.get(
                    name, name.replace("_", " "))

    # ---------- System-2 planner ----------

    _DANGEROUS_LABEL = re.compile(
        r"send|delete|remove|buy|purchase|pay|place order|post|publish|"
        r"erase|empty trash|replace|submit order", re.I)
    _DANGEROUS_COMBOS = {"cmd+delete", "cmd+opt+delete", "cmd+shift+d"}

    def _speculative_route(self, text: str):
        """Called for partial utterances — routes ahead on the MLX worker,
        keyed by normalized text."""
        if self.engine is None:
            return
        norm = re.sub(r"\s+", " ", text.strip().lower())
        if norm and norm != getattr(self, "_spec_norm", None):
            self._spec_norm = norm
            from .planner import worker
            self._spec_fut = worker().submit(
                self.engine.route, text, dict(self._ctx))

    async def _answer(self, text: str, trace: dict) -> str:
        if self.planner is not None:
            from .planner import worker
            ans = await worker().submit_async(
                self.planner.generate,
                "Answer in at most 12 words.",
                f'Question: "{text}"', 48)
            await self.server.say(ans or "I don't know")
        else:
            await self.server.say("I'll answer that soon")
        await self.server.ui("success")
        return "ok"

    def _label_of(self, ref: int | None) -> str:
        if ref is None or not self._last_obs:
            return ""
        for e in self._last_obs.get("elements", []):
            if e.get("ref") == ref:
                return e.get("label", "")
        return ""

    async def _confirm_summary(self, a: dict) -> str:
        """<=12-word summary built from resolved args."""
        if a["op"] == "confirm":
            return a.get("summary", "Continue?")[:80]
        if a["op"] == "skill":
            n, ar = a["name"], a.get("args", {})
            if n == "send_message":
                return f"Text {ar.get('to')}: \"{str(ar.get('message'))[:30]}\"?"
            if n == "move_to_trash":
                return f"Move {ar.get('path')} to Trash?"
            if n == "quit_app":
                return f"Quit {ar.get('app')}?"
            return (self.catalog.get(n) or {}).get("description", n)[:60] + "?"
        if a["op"] == "press":
            return f"Press \"{self._label_of(a.get('ref'))}\"?"
        if a["op"] == "script":
            return f"Run a {a.get('lang')} script?"
        return "Continue?"

    async def _exec_one(self, a: dict) -> dict:
        """Execute one DSL action. Returns
        {status: ok|failed|awaiting_user|cancelled|done, ...details}."""
        op = a["op"]
        dsl_line = f"{op} " + " ".join(
            f"{k}={v}" for k, v in a.items() if k != "op")
        if op == "ask":
            await self.server.say(a["question"])
            await self.server.ui("listening")
            return {"status": "awaiting_user", "_log": f"{dsl_line}-> ask"}
        if op == "confirm":
            yes = await self.server.ask_confirm(a["summary"])
            if not yes:
                await self.server.say("Okay, cancelled")
                return {"status": "cancelled",
                        "_log": f"{dsl_line}-> cancelled"}
            self._batch_confirmed = True      # no double confirm this batch
            return {"status": "ok", "confirmed": True,
                    "_log": f"{dsl_line}-> confirmed"}
        if op == "done":
            self._done_summary = a["summary"].strip('"')
            return {"status": "done", "summary": a["summary"],
                    "_log": f"{dsl_line}-> done"}
        if op == "refuse":
            await self.server.say("Sorry, I can't do that")
            await self.server.ui("confused")
            return {"status": "failed", "_log": f"{dsl_line}-> refused"}
        if op == "wait":
            await asyncio.sleep(a["ms"] / 1000)
            return {"status": "ok", "_log": f"{dsl_line}-> ok"}
        if op == "skill":
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
                yes = await self.server.ask_confirm(
                    await self._confirm_summary(a))
                if not yes:
                    return {"status": "cancelled"}
                a["args"]["confirmed"] = True
            r = await self._rpc_action("skill",
                                       {"name": a["name"],
                                        "args": a.get("args", {})}, a)
            r["_log"] = f"{dsl_line}-> {'ok' if r['status']=='ok' else 'failed: ' + r.get('error','?')}"
            return r
        if op == "script":
            lang, code = a["lang"], a["code"]
            if self.script_needs_confirm(lang, code):
                yes = await self.server.ask_confirm(
                    await self._confirm_summary(a))
                if not yes:
                    return {"status": "cancelled"}
            r = await self._rpc_action(
                "act", {"op": "script", "lang": lang, "code": code}, a)
            r["_log"] = f"script -> {'ok' if r['status']=='ok' else 'failed: ' + r.get('error','?')}"
            if r.get("status") == "ok":
                out = r.get("res", {})
                text_out = out.get("output") or out.get("stdout") or ""
                if text_out:
                    self._script_output = str(text_out)[:300]
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
            if needs and not self._batch_confirmed:
                yes = await self.server.ask_confirm(
                    await self._confirm_summary(a))
                if not yes:
                    return {"status": "cancelled"}
                self._batch_confirmed = True
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
            return {"status": "failed", "error": str(e)}
        self.tracer.rpc(method, params, self._trace_res(res),
                        (time.perf_counter() - t) * 1000)
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
        return {"status": "ok", "res": res}

    # script confirmation policy (evals-safety-2)
    _SCRIPT_BLOCK = re.compile(
        r"do shell script|doShellScript|do script|run script|keystroke|"
        r"key code|ObjC|\$\.|NSFileManager|trash|delete|remove|saving no|"
        r"send|erase|format|quit|close|move|duplicate|make new|"
        r"set .* to .*", re.I)
    _SCRIPT_APPS_READ = {
        "com.apple.numbers", "numbers", "music", "calendar", "system events"}
    _SCRIPT_APPS_LIMITED = {"finder", "safari"}
    _READ_VERBS = re.compile(
        r"\b(get|count|exists|reveal|open)\b", re.I)
    _NUMBERS_OK = re.compile(
        r"set value|set background color|sort|make new table", re.I)

    def script_needs_confirm(self, lang: str, code: str) -> bool:
        """confirm unless the script targets only allow-listed apps with
        read-only verbs and contains no blocked pattern. Numbers gets a
        wider exception (set value / background color / sort / make new
        table need no confirm). shell always confirms."""
        if lang == "shell":
            return True
        targets = {t.lower() for t in re.findall(
            r'tell\s+application\s+(?:id\s+)?"([^"]+)"', code, re.I)}
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
            await self.server.ui("confused")
            return "fallback"
        from . import dsl
        from .planner import worker
        goal = text
        if answer:
            goal += f'\nUser answer: "{answer}"'
        t_start = time.perf_counter()
        self._script_output = None
        last_batch: list[str] | None = None
        prev_had_failure = False
        done_rejected = False
        obs_text = ""
        for turn in range(12):
            if time.perf_counter() - t_start > 60:
                break
            obs = await self._observe()
            if obs:
                obs_text = obs["text"]
                self._last_obs = obs
            elif not obs_text:
                obs_text = "(no observation available)"
            q: asyncio.Queue = asyncio.Queue()
            cancel = threading.Event()
            loop = asyncio.get_running_loop()
            fut = worker().submit(
                self.planner.plan, goal, obs_text, last_batch, q, loop,
                cancel, hint, self._script_output)
            self._script_output = None   # consumed by this turn
            self._current_goal = goal
            # stream-consume lines; execute each action once complete
            lines: list[str] = []
            pending: list[dict] = []       # parsed, not yet flushed
            batch_log: list[str] = []
            failed = False
            self._batch_confirmed = False
            res_status = "ok"
            done_seen = False
            n_executed = 0
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
                    # a new action line: flush the previous pending action
                    if pending and not failed and not done_seen:
                        r = await self._exec_one(pending.pop(0))
                        batch_log.append(r["_log"])
                        if r["status"] == "done":
                            done_seen = True
                            cancel.set()      # done ends the batch's execution
                        else:
                            n_executed += 1
                            if r["status"] != "ok":
                                failed = True
                                cancel.set()
                                res_status = r["status"]
                    try:
                        acts = dsl.parse(line)
                        pending.extend(acts)
                    except Exception as e:
                        failed = True
                        res_status = "failed"
                        batch_log.append(f"{line} -> failed: {e}")
                        cancel.set()
            except asyncio.CancelledError:
                cancel.set()   # stop the decode
                raise
            # flush tail action(s)
            while pending and not failed and not done_seen:
                r = await self._exec_one(pending.pop(0))
                batch_log.append(r["_log"])
                if r["status"] == "done":
                    done_seen = True
                else:
                    n_executed += 1
                    if r["status"] != "ok":
                        failed = True
                        res_status = r["status"]
                        cancel.set()
            info = await asyncio.wrap_future(fut)
            trace["decisions"].append({
                "planner_turn": turn, "lines": lines,
                "ttft_ms": round(info["ttft_ms"], 1),
                "decode_tok_s": round(info["decode_tok_s"], 1),
                "tokens": info["tokens"]})
            last_batch = batch_log or None
            if res_status == "awaiting_user":
                self._pending_task = {"goal": text, "t": time.time()}
                return "awaiting_user"
            if res_status == "cancelled":
                return "cancelled"
            # done validation: alone in batch + no prior failure
            if done_seen and not failed:
                if n_executed == 0 and (not prev_had_failure or done_rejected):
                    summary = self._done_summary or "Done"
                    await self.server.say(summary[:60])
                    await self.server.ui("success")
                    return "ok"
                # reject once, then let a subsequent alone-done succeed
                # ("re-plan once" — a strict prev-batch check would reject
                # done forever after any failure)
                done_rejected = True
                batch_log.append("done -> failed: done without evidence")
                failed = True
            if res_status == "failed" or failed:
                prev_had_failure = True
                continue          # replan with fresh observation
            if not lines:
                prev_had_failure = True
                continue
            # batch fully executed without a terminal op -> keep going
            prev_had_failure = False
        await self.server.say("That didn't work")
        await self.server.ui("confused")
        return "failed"

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
        r"\b(off|disable|deactivate|stop|kill|shut\s*off|turn off)\b", re.I)
    _BOOL_ON = re.compile(
        r"\b(on|enable|activate|start|turn on|back on)\b", re.I)

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
                if self._BOOL_OFF.search(utterance):
                    out[key] = False
                    continue
                if self._BOOL_ON.search(utterance):
                    out[key] = True
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
