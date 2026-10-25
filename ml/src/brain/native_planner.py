"""Native tool-calling planner (experiment, `--planner-mode tools`).

The 35B plans with its own chat template + tool schema instead of our DSL: one tool call per turn (ReAct), free
bounded thinking, qwen sampler. Each call is mapped to ONE DSL line so `_planner_loop` executes it unchanged.
Qwen3.6's template emits `<tool_call><function=NAME><parameter=K>V</parameter></function></tool_call>`;
the hermes JSON form `<tool_call>{"name":...,"arguments":{...}}</tool_call>` is accepted too.
"""

import copy
import json
import re
import time
from collections import deque

import numpy as np

from . import dsl
from .planner import Planner, mx, sample_logits

HISTORY_TURNS = 8
THINK_BUDGET = 1024
RETRY_THINK = 256
CALL_MAX_TOKENS = 256
QWEN = {"temp": 0.6, "top_p": 0.95, "top_k": 20}
FALLBACK_LINE = 'ask "I couldn\'t decide the next step"'
CORRECTIVE = ("Your reply had no valid tool call ({err}). Reply with exactly one <tool_call> for one of the tools, "
              "based on the observation.")

RULES = """You are Muselet, an agent that operates the user's Mac through its accessibility tree.
Each turn you see the current observation: a header line, then one UI element per line as `#<ref> role "label"`.
Rules:
- Act on the current observation only; refs (#12) come from it and may change between turns.
- Call exactly one tool per turn. You will see its result and a fresh observation next turn.
- Prefer press/type on refs; use keys for shortcuts; use click(description) only when the target has no ref.
- Never send, post, buy, delete or do anything irreversible without calling confirm first.
- Call done only when the finish criterion is visible in the observation; summaries are at most 12 words.
- Call ask when you need information only the user has (or a login); call refuse for harmful requests.
- skill runs a built-in system skill (volume, wifi, files, ...); app work goes through the UI tools."""


def _fn(name, desc, props=None, required=()):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": list(required)}}}


_REF = {"type": "integer", "description": "element ref from the observation, e.g. 12 for #12"}


def build_tools(system_skills: dict | None = None) -> list[dict]:
    skills = system_skills or {}
    listing = "; ".join(f"{n}({', '.join(a['name'] for a in s.get('args') or ())})" for n, s in skills.items())
    return [
        _fn("press", "Press (click) the element with this ref.", {"ref": _REF}, ["ref"]),
        _fn("type", "Type text into the element with this ref (replaces its value); enter=true presses Return.",
            {"ref": _REF, "text": {"type": "string"},
             "enter": {"type": "boolean", "default": False}}, ["ref", "text"]),
        _fn("keys", "Press a key combo, e.g. cmd+l, cmd+shift+n, return, esc, tab, down.",
            {"combo": {"type": "string"}}, ["combo"]),
        _fn("scroll", "Scroll the element with this ref.",
            {"ref": _REF, "direction": {"type": "string", "enum": ["up", "down"]}}, ["ref", "direction"]),
        _fn("open_app", "Open (or switch to) an app by name.", {"name": {"type": "string"}}, ["name"]),
        _fn("open_url", "Open a URL in the browser.", {"url": {"type": "string"}}, ["url"]),
        _fn("click", "Click a visible target by description (grounded on a screenshot); only for targets "
            "without a ref.", {"description": {"type": "string"},
                               "double": {"type": "boolean", "default": False}}, ["description"]),
        _fn("wait", "Wait for the UI to update.", {"ms": {"type": "integer"}}, ["ms"]),
        _fn("ask", "Ask the user a short question and stop.", {"question": {"type": "string"}}, ["question"]),
        _fn("confirm", "Ask the user to confirm an irreversible step (send, buy, delete, post) before doing it.",
            {"summary": {"type": "string"}}, ["summary"]),
        _fn("done", "Finish: the goal is visibly complete.", {"summary": {"type": "string"}}, ["summary"]),
        _fn("refuse", "Refuse a harmful or impossible request.", {"reason": {"type": "string"}}, ["reason"]),
        _fn("skill", "Run a built-in system skill: " + (listing or "none"),
            {"name": {"type": "string", "enum": sorted(skills) or [""]},
             "args": {"type": "object"}}, ["name"]),
    ]


TOOLS = build_tools()
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
_TYPES = {t["function"]["name"]: {k: v.get("type") for k, v in t["function"]["parameters"]["properties"].items()}
          for t in TOOLS}


class ToolCallError(ValueError):
    pass


def _coerce(value, kind):
    if kind == "integer":
        if isinstance(value, bool):
            raise ToolCallError(f"expected integer, got {value!r}")
        if isinstance(value, (int, float)) and int(value) == value:
            return int(value)
        s = str(value).strip().lstrip("#")
        if not re.fullmatch(r"-?\d+", s):
            raise ToolCallError(f"expected integer, got {value!r}")
        return int(s)
    if kind == "boolean":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no", ""):
            return False
        raise ToolCallError(f"expected boolean, got {value!r}")
    if kind == "object":
        if isinstance(value, dict):
            return value
        s = str(value).strip()
        if not s:
            return {}
        try:
            out = json.loads(s)
        except json.JSONDecodeError:
            raise ToolCallError(f"expected JSON object, got {value!r}")
        if not isinstance(out, dict):
            raise ToolCallError(f"expected JSON object, got {value!r}")
        return out
    return value if isinstance(value, str) else json.dumps(value) if isinstance(value, (dict, list)) else str(value)


_XML_FN = re.compile(r"<function=([^>\s]+)>(.*?)(?:</function>|$)", re.S)
_XML_PARAM = re.compile(r"<parameter=([^>\s]+)>\n?(.*?)\n?</parameter>", re.S)


def answer_text(raw: str) -> str:
    """The part of a completion after the thinking block."""
    return raw.rsplit("</think>", 1)[-1].strip()


def parse_tool_call(raw: str) -> tuple[str, dict]:
    """First tool call in a completion as (name, typed args). Raises ToolCallError."""
    text = answer_text(raw)
    m = re.search(r"<tool_call>(.*?)(?:</tool_call>|$)", text, re.S)
    body = (m.group(1) if m else text).strip()
    if not m and "<function=" not in body and not body.startswith("{"):
        raise ToolCallError("no <tool_call> found")
    fm = _XML_FN.search(body)
    if fm:
        name = fm.group(1).strip()
        args = {k.strip(): v for k, v in _XML_PARAM.findall(fm.group(2))}
    else:
        try:
            obj, _ = json.JSONDecoder().raw_decode(body)
        except json.JSONDecodeError as e:
            raise ToolCallError(f"bad tool call JSON: {e.msg}")
        if not isinstance(obj, dict) or not isinstance(obj.get("name"), str):
            raise ToolCallError("tool call needs a name")
        name, args = obj["name"], obj.get("arguments", obj.get("parameters", {}))
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                raise ToolCallError("arguments are not a JSON object")
        if not isinstance(args, dict):
            raise ToolCallError("arguments are not an object")
    if name not in TOOL_NAMES:
        raise ToolCallError(f"unknown tool {name!r}")
    types = _TYPES[name]
    return name, {k: _coerce(v, types.get(k)) for k, v in args.items() if k in types}


_KEY_ALIASES = {"command": "cmd", "control": "ctrl", "option": "alt", "opt": "alt", "escape": "esc",
                "enter": "return", "⌘": "cmd"}


def _combo(s: str) -> str:
    parts = [p for p in re.split(r"\s*\+\s*|\s+", s.strip().lower()) if p]
    return "+".join(_KEY_ALIASES.get(p, p) for p in parts)


def _need(args, *keys):
    for k in keys:
        if k not in args or args[k] in (None, ""):
            raise ToolCallError(f"missing argument {k!r}")


def to_dsl(name: str, args: dict, system_skills=None) -> str:
    """One tool call as one DSL line `dsl.parse` accepts. Raises ToolCallError."""
    q = dsl._q
    if name in ("press", "type", "scroll"):
        _need(args, "ref")
    if name == "press":
        line = f"press #{args['ref']}"
    elif name == "type":
        if not isinstance(args.get("text"), str):
            raise ToolCallError("missing argument 'text'")
        line = f"type #{args['ref']} {q(args['text'])}" + (" enter" if args.get("enter") else "")
    elif name == "keys":
        _need(args, "combo")
        line = f"keys {_combo(args['combo'])}"
    elif name == "scroll":
        direction = str(args.get("direction", "down")).strip().lower()
        if direction not in ("up", "down", "left", "right"):
            raise ToolCallError(f"bad scroll direction {direction!r}")
        line = f"scroll #{args['ref']} {direction}"
    elif name == "open_app":
        _need(args, "name")
        line = f"open {q(args['name'].strip())}"
    elif name == "open_url":
        _need(args, "url")
        line = f"url {q(args['url'].strip())}"
    elif name == "click":
        _need(args, "description")
        line = f"click {q(args['description'].strip())}" + (" double" if args.get("double") else "")
    elif name == "wait":
        _need(args, "ms")
        line = f"wait {min(max(int(args['ms']), 0), 10000)}"
    elif name in ("ask", "confirm", "done", "refuse"):
        key = {"ask": "question", "confirm": "summary", "done": "summary", "refuse": "reason"}[name]
        _need(args, key)
        line = f"{name} {q(args[key].strip())}"
    elif name == "skill":
        _need(args, "name")
        skill = str(args["name"]).strip()
        if system_skills is not None and skill not in system_skills:
            raise ToolCallError(f"{skill!r} is not a system skill")
        sargs = args.get("args") or {}
        if any(not isinstance(v, (str, int, float, bool)) for v in sargs.values()):
            raise ToolCallError("skill args must be strings, numbers or booleans")
        line = dsl.serialize([{"op": "skill", "name": skill, "args": sargs}])
    else:
        raise ToolCallError(f"unknown tool {name!r}")
    try:
        dsl.parse(line)
    except dsl.DSLError as e:
        raise ToolCallError(f"not executable: {e.msg}")
    return line


class NativeToolPlanner(Planner):
    """Same `plan()` contract as Planner (puts DSL lines on the queue, returns the info dict).
    `decode_fn(prompt_text, think_budget, cancel) -> (completion, stats)` replaces MLX decoding (tests)."""

    mode = "tools"

    def __init__(self, model_path: str, catalog, engine=None, app_hints: bool = False, hidden_skills=(),
                 think_budget: int = THINK_BUDGET, think_seed: int = 0, tokenizer=None, decode_fn=None, **_ignored):
        if decode_fn is None:
            super().__init__(model_path, catalog, engine=engine, constrain=False, few_shot=None, history="dsl",
                             think_budget=think_budget, think_on="all", think_sampler="qwen",
                             think_seed=think_seed, app_hints=app_hints, hidden_skills=hidden_skills)
        else:
            self.model_path, self.catalog, self.engine = model_path, catalog, None
            self.tokenizer, self.app_hints = tokenizer, app_hints
            self.think_budget, self.think_seed, self.think_sampler = think_budget, think_seed, "qwen"
            self.hidden_skills, self.plan_bank, self._decider = (
                frozenset(set(hidden_skills) | set(catalog.app_skills())),
                None, None)
            self.history, self.retrieval_k, self.last_retrieval = "dsl", 0, {"ids": [], "ms": 0.0}
        self.decode_fn = decode_fn
        self.system_skills = {n: s for n, s in catalog.skills.items()
                              if s.get("kind") == "system" and n not in self.hidden_skills}
        self.tools = build_tools(self.system_skills)
        self.last_hint_ids: list[str] = []
        self._prefix = None            # (prefix token ids, prompt cache)
        self._goal = None
        self._turns: deque = deque(maxlen=HISTORY_TURNS)

    def settings(self) -> str:
        return (f"mode=tools think={self.think_budget} sampler=qwen history={HISTORY_TURNS} "
                f"app_hints={self.app_hints} system_skills={len(self.system_skills)}")

    def begin_task(self, keep: bool = False):
        if not keep:
            self._goal = None
            self._turns.clear()

    # ---------- prompt ----------

    def system_prompt(self, goal: str, finish: list[str], hint: str | None, app: str) -> str:
        parts = [RULES, "", f'Goal: "{goal}"']
        if hint:
            parts.append(f"Hint: likely {hint}")
        if finish:
            parts.extend(finish)
        if self.app_hints:
            from .app_hints import match_hints, render_hints
            matched = match_hints(goal, app, route_hint=hint or "")
            self.last_hint_ids = [h.id for h in matched]
            if (tips := render_hints(matched)):
                parts.append(tips)
        return "\n".join(parts)

    def user_prompt(self, observation: str, last_batch, script_output=None, login_page=False,
                    recent=None, memory=None, context=None, earlier=()) -> str:
        parts = []
        if recent:
            parts += ["Recent:", *recent]
        if memory:
            parts += list(memory[:3])
        if context:
            parts.append(context)
        if login_page:
            parts.append("Login page: ask the user to sign in")
        if earlier:
            parts += ["Earlier steps (oldest first):", *[f"- {x}" for turn in earlier for x in turn]]
        if last_batch:
            parts += ["Last result:", *[f"- {x}" for x in last_batch]]
        if script_output:
            parts.append(f"Script result: {script_output[:1600]}")
        parts += ["Observation:", observation, "Call one tool."]
        return "\n".join(parts)

    def messages(self, goal, observation, last_batch, hint=None, script_output=None, login_page=False,
                 recent=None, memory=None, context=None, earlier=()) -> list[dict]:
        keep, finish = [], []
        for line in observation.splitlines():
            (finish if line.startswith("Finish when:") else keep).append(line)
        header = next((x for x in keep if x.strip().startswith("app:")), "")
        app = m.group(1) if (m := re.search(r"\bapp:\s*(.*?)\s*(?:\||$)", header)) else ""
        return [{"role": "system", "content": self.system_prompt(goal, finish, hint, app)},
                {"role": "user", "content": self.user_prompt(
                    "\n".join(keep), last_batch, script_output, login_page, recent, memory, context, earlier)}]

    def render(self, messages) -> str:
        return self.tokenizer.apply_chat_template(messages, tools=self.tools, add_generation_prompt=True,
                                                  enable_thinking=True, tokenize=False)

    def _prefix_text(self) -> str:
        """Rendered text shared by every prompt (tool block + rules), ending right before `Goal:`."""
        text = self.render([{"role": "system", "content": RULES + "\n\nGoal: \"x\""},
                            {"role": "user", "content": "x"}])
        return text[:text.index("Goal: ")]

    # ---------- decoding (MLX worker thread) ----------

    def _ensure_prefix(self):
        if self._prefix is None:
            ids = self.tokenizer.encode(self._prefix_text(), add_special_tokens=False)
            self._prefix = (ids, self._prefill(mx.array([ids])))
        return self._prefix

    def _mlx_decode(self, prompt: str, think_budget: int, cancel) -> tuple[str, dict]:
        t0 = time.perf_counter()
        toks = self.tokenizer.encode(prompt, add_special_tokens=False)
        pids, pcache = self._ensure_prefix()
        if toks[:len(pids)] == pids:
            cache, dyn = copy.deepcopy(pcache), toks[len(pids):]
        else:
            from mlx_lm.models.cache import make_prompt_cache
            cache, dyn = make_prompt_cache(self.model), toks
        saved, self.think_budget = self.think_budget, think_budget
        try:
            feed, think = self.think(cache, dyn, cancel)   # dyn ends with the template's "<think>\n"
        finally:
            self.think_budget = saved
        ttft = (time.perf_counter() - t0) * 1000
        stop_ids = {self.tokenizer.eos_token_id}
        end = self.tokenizer.encode("<" + "|im_end|>", add_special_tokens=False)
        if len(end) == 1:
            stop_ids.add(end[0])
        rng = np.random.default_rng(self.think_seed + 1)
        out, cur, text = [], feed, ""
        t1 = time.perf_counter()
        for _ in range(CALL_MAX_TOKENS):
            if cancel is not None and cancel.is_set():
                break
            logits = np.array(self.lm_head(self.body(mx.array([cur]), cache=cache)[:, -1:, :])
                              .astype(mx.float32)[0, 0])
            nxt = sample_logits(logits, QWEN["temp"], QWEN["top_p"], QWEN["top_k"], rng)
            if nxt in stop_ids:
                break
            out.append(nxt)
            cur = [nxt]
            text = self.tokenizer.decode(out)
            if "</tool_call>" in text:
                break
        dt = (time.perf_counter() - t1) * 1000
        return (f"{think['text']}\n</think>\n\n{text}",
                {"ttft_ms": ttft, "tokens": len(out) + think["tokens"], "call_tokens": len(out),
                 "decode_tok_s": len(out) / max(dt, 1) * 1000, "prompt_tokens": len(toks),
                 "dynamic_tokens": len(dyn), "think": think})

    def _decode(self, prompt: str, think_budget: int, cancel):
        if self.decode_fn is not None:
            return self.decode_fn(prompt, think_budget, cancel)
        return self._mlx_decode(prompt, think_budget, cancel)

    def warm(self) -> dict:
        t = time.perf_counter()
        if self.decode_fn is None:
            self._ensure_prefix()
        return {"warm_ms": round((time.perf_counter() - t) * 1000, 2)}

    # ---------- plan ----------

    def decide_line(self, msgs, cancel) -> tuple[str, dict]:
        """One DSL line for this turn (with one corrective retry) + stats."""
        stats = {"tokens": 0, "retries": 0, "errors": [], "ttft_ms": None, "decode_tok_s": 0.0,
                 "prompt_tokens": 0, "dynamic_tokens": 0, "think": None, "text": ""}
        for attempt in range(2):
            raw, st = self._decode(self.render(msgs), THINK_BUDGET if attempt == 0 else RETRY_THINK, cancel)
            stats["tokens"] += st.get("tokens", 0)
            if stats["ttft_ms"] is None:
                stats["ttft_ms"] = st.get("ttft_ms")
            for k in ("decode_tok_s", "prompt_tokens", "dynamic_tokens"):
                stats[k] = st.get(k, stats[k])
            stats["think"] = st.get("think") or stats["think"]
            stats["text"] = answer_text(raw)[:400]
            if cancel is not None and cancel.is_set():
                break
            try:
                name, args = parse_tool_call(raw)
                stats["tool"] = name
                return to_dsl(name, args, self.system_skills), stats
            except (ToolCallError, ValueError, TypeError) as e:
                stats["errors"].append(str(e))
                if attempt == 0:
                    stats["retries"] = 1
                    msgs = msgs + [{"role": "assistant", "content": answer_text(raw)},
                                   {"role": "user", "content": CORRECTIVE.format(err=e)}]
        return FALLBACK_LINE, stats

    def plan(self, goal: str, observation: str, last_batch, lines_out, loop, cancel=None, hint=None,
             script_output=None, login_page=False, recent=None, memory=None, context=None, **_kw) -> dict:
        t0 = time.perf_counter()
        base_goal = goal.split('\nUser answer: "', 1)[0]
        if base_goal != self._goal:
            self._goal = base_goal
            self._turns.clear()
        earlier = list(self._turns)
        if last_batch:
            self._turns.append(list(last_batch))
        msgs = self.messages(goal, observation, last_batch, hint, script_output, login_page, recent, memory,
                             context, earlier)
        line, st = self.decide_line(msgs, cancel)
        lines = [] if cancel is not None and cancel.is_set() and line == FALLBACK_LINE else [line]
        for x in lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, x)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        dt = (time.perf_counter() - t0) * 1000
        think = st["think"]
        return {"lines": lines, "ttft_ms": st["ttft_ms"] or dt, "decode_tok_s": st["decode_tok_s"],
                "tokens": st["tokens"], "plan_ms": dt, "retrieved": [], "prompt_tokens": st["prompt_tokens"],
                "dynamic_tokens": st["dynamic_tokens"], "think": think,
                "think_tokens": think["tokens"] if think else 0, "text": st["text"], "mode": "tools",
                "native": {"tool": st.get("tool"), "retries": st["retries"], "errors": st["errors"]}}
