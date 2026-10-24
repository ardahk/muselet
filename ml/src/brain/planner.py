"""System-2 planner: streams DSL action batches from a 4B-class model on ONE
dedicated MLX worker thread shared by every model call (route, args, plan).

Rendering: same qwen3_5 tinker-cookbook renderer + empty think block; the
static catalog system prompt is prefix-cached once and deep-copied per call.
"""

import asyncio
import copy
import queue as _queue
import re
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import mlx.core as mx
import mlx_lm
import numpy as np
from tinker_cookbook.renderers import Message

from .decision import DecisionEngine, _OnlineProbe, split_model  # noqa: F401
from .dsl import action_line

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "planner_system.md"
TERMINAL_OPS = {"ask", "confirm", "done", "refuse"}
MAX_TOKENS = 320   # room for multi-line script blocks
SENTINEL = "SENTINELMARKER9Z"

# ---------- shared MLX worker (single thread, FIFO) ----------

_WORKER = None
_WORKER_LOCK = threading.Lock()


OP_STRS = ["skill ", "press #", "type #", "keys ", "scroll #", "click ", 'open "', 'url "', "script ", "wait ",
           'ask "', 'confirm "', "done", 'refuse "', "expect ", "# "]
ACTION_OPS = [o for o in OP_STRS if o not in ("done", "expect ", "# ")]
HISTORY_FORMATS = ("marked", "dsl", "repr")
PLANNER_CONSTRAIN_DEFAULT = True   # line-start op constraint; the lead sets the final default
ROOT = Path(__file__).resolve().parents[3]
FEWSHOT_PATH = "prompts/planner_fewshot.md"


def _compatible(x: str, ops) -> bool:
    return any(o.startswith(x) or x.startswith(o) for o in ops)


class OpConstraint:
    """Line-start grammar: the first characters of every line must spell a DSL op keyword. Allowed token ids are
    precomputed per partial-line prefix, so decoding pays a dict lookup. `done_alone`: once the batch has an
    action line, `done` can't start a line (it must be alone in its batch, prompt rule 13)."""

    def __init__(self, tok, done_alone: bool):
        import bisect
        by_str: dict[str, list[int]] = {}
        for i in range(len(tok.get_vocab())):
            s = tok.decode([i])
            if s and "\n" not in s and "\ufffd" not in s:
                by_str.setdefault(s, []).append(i)
        keys = sorted(by_str)

        def starting_with(rem: str) -> list[int]:     # tokens whose text starts with rem
            out, j = [], bisect.bisect_left(keys, rem)
            while j < len(keys) and keys[j].startswith(rem):
                out.extend(by_str[keys[j]])
                j += 1
            return out

        self.done_alone = done_alone
        self.table = {}
        for ops_key, ops in (("all", OP_STRS), ("no_done", [o for o in OP_STRS if o != "done"])):
            prefixes = {""} | {o[:k] for o in ops for k in range(1, len(o))}
            for b in prefixes:
                ids: set[int] = set()
                for o in ops:
                    if not o.startswith(b):
                        continue
                    rem = o[len(b):]
                    for k in range(1, len(rem) + 1):        # token is a prefix of the remainder
                        ids.update(by_str.get(rem[:k], ()))
                    ids.update(starting_with(rem))          # token completes the keyword and goes on
                self.table[(ops_key, b)] = sorted(ids)

    def allowed(self, line_buf: str, has_action: bool):
        """Token ids allowed next, or None once the op keyword is complete (free decoding)."""
        ops_key = "no_done" if self.done_alone and has_action else "all"
        ops = OP_STRS if ops_key == "all" else [o for o in OP_STRS if o != "done"]
        if any(line_buf.startswith(o) for o in ops):
            return None
        return self.table.get((ops_key, line_buf))


def history(lines, fmt: str):
    """Last-batch lines in a given presentation. Scenarios store 'action -> result'."""
    if not lines or fmt == "dsl":
        return lines
    if fmt == "repr":
        return [runtime_repr(x) for x in lines]
    out = []                                   # "marked": result first, so a line can't be copied as an action
    for x in lines:
        act, res = x.rsplit(" -> ", 1) if " -> " in x else (x, "ok")
        out.append(f"[{res}] {act}")
    return out


def runtime_repr(line: str) -> str:
    """'press #4 -> ok' as the runtime currently logs it: '{op} k=v ...-> ok' from the parsed dict."""
    from . import dsl
    if " -> " not in line:
        return line
    act, res = line.rsplit(" -> ", 1)
    try:
        a = dsl.parse(act)[0]
    except Exception:
        return line
    return f"{a['op']} " + " ".join(f"{k}={v}" for k, v in a.items() if k != "op") + f"-> {res}"


def has_action(lines) -> bool:
    return any(not re.match(r"^(#|expect\b|done\b)", ln) for ln in lines)


def few_shot_text(path: str | None) -> str | None:
    """Few-shot examples file (repo-relative or absolute); None/'none' = off."""
    if not path or str(path).lower() == "none":
        return None
    f = Path(path)
    return (f if f.is_absolute() else ROOT / f).read_text()


class BatchCutter:
    """Streaming batch limits: <= 5 actions (a script block is one action),
    the 5th action's `expect` is kept (brain-11), a terminal op ends it."""

    def __init__(self, max_actions: int = 5):
        self.max, self.n, self.full, self.done = max_actions, 0, False, False

    def push(self, line: str) -> str | None:
        """The line to emit, or None. Sets .done when the batch is over."""
        if self.full:
            if line.startswith("#"):
                return None
            self.done = True
            return line if line.startswith("expect") else None
        if not re.match(r"^(expect|#)", line) and action_line(line):
            self.n += 1
            self.done = line.split()[0] in TERMINAL_OPS
            self.full = self.n >= self.max
        return line


class MLXWorker:
    """All MLX model calls run on this one thread — never concurrently."""

    def __init__(self):
        self._q: _queue.Queue = _queue.Queue()
        self._t = threading.Thread(target=self._run, daemon=True,
                                   name="mlx-worker")
        self._t.start()

    def _run(self):
        while True:
            item = self._q.get()
            if item is None:
                return
            fn, args, kwargs, fut = item
            try:
                fut.set_result(fn(*args, **kwargs))
            except BaseException as e:      # noqa: BLE001
                fut.set_exception(e)

    def submit(self, fn, *args, **kwargs) -> Future:
        fut = Future()
        self._q.put((fn, args, kwargs, fut))
        return fut

    def submit_async(self, fn, *args, **kwargs):
        """asyncio-friendly wrapper."""
        return asyncio.wrap_future(self.submit(fn, *args, **kwargs))


def worker() -> MLXWorker:
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is None:
            _WORKER = MLXWorker()
        return _WORKER


# ---------- shared model cache (weights loaded once per path) ----------

_MODELS: dict = {}
_MODELS_LOCK = threading.Lock()


def load_model(path: str):
    """Memoized mlx_lm.load — Planner and DecisionEngine share weights."""
    with _MODELS_LOCK:
        if path not in _MODELS:
            _MODELS[path] = mlx_lm.load(path)
        return _MODELS[path]


def planner_prompt(catalog_desc: str) -> str:
    text = Path(PROMPT_PATH).read_text()
    return text.replace("{catalog}", catalog_desc)


def catalog_desc(catalog, arg_signature) -> str:
    """one line per skill: name(arg_signature): description"""
    lines = []
    for name, spec in catalog.skills.items():
        sig = arg_signature(name)
        lines.append(f"{name}({sig}): {spec.get('description', name)}")
    return "\n".join(lines)


class Planner:
    """Streams DSL batches. plan() runs ON the MLX worker thread."""

    def __init__(self, model_path: str, catalog, engine: DecisionEngine | None = None,
                 constrain: bool = PLANNER_CONSTRAIN_DEFAULT, done_alone: bool = True,
                 few_shot: str | None = FEWSHOT_PATH, history: str = "dsl"):
        if history not in HISTORY_FORMATS:
            raise ValueError(f"history must be one of {HISTORY_FORMATS}")
        self.model_path = model_path
        self.constrain, self.done_alone = constrain, done_alone
        self.few_shot, self.history = few_shot, history
        self._constraint = None
        if engine is not None and engine.model_path == model_path:
            self.model, self.tokenizer = engine.model, engine.tokenizer
            self.body, self.lm_head = engine.body, engine.lm_head
            self.rr = engine.rr
            self.engine = engine
        else:
            self.model, self.tokenizer = load_model(model_path)
            self.body, self.lm_head = split_model(self.model)
            from .decision import RouteRenderer
            self.rr = RouteRenderer(model_path, catalog)
            self.engine = None
        self.catalog = catalog
        self._prefix_tokens = None
        self._cut = None
        self._cache = None
        self.system = planner_prompt(
            catalog_desc(catalog, self._arg_sig_for))
        if (fs := few_shot_text(few_shot)):
            self.system += "\n\n" + fs      # part of the cached prefix

    def _op_constraint(self):
        """Line-start op constraint, built once per Planner (vocab scan)."""
        if self.constrain and self._constraint is None:
            self._constraint = OpConstraint(self.tokenizer, done_alone=self.done_alone)
        return self._constraint if self.constrain else None

    def settings(self) -> str:
        return (f"constrain={self.constrain} done_alone={self.done_alone} "
                f"few_shot={self.few_shot or 'none'} history={self.history}")

    def _arg_sig_for(self, name):
        eng = self.engine or DecisionEngine.__new__(DecisionEngine)
        eng.catalog = self.catalog
        return DecisionEngine.arg_signature(eng, name)

    # ---------- rendering ----------

    def _render_msgs(self, msgs):
        mi, _ = self.rr.renderer.build_supervised_example(msgs)
        return mi.to_ints()

    def _content_cut(self, toks, sentinel: str) -> int:
        sent = self.tokenizer.encode(sentinel, add_special_tokens=False)
        n = len(sent)
        for i in range(len(toks) - n + 1):
            if toks[i:i + n] == sent:
                return i
        raise RuntimeError("sentinel not found in rendered tokens")

    def _prefill(self, tokens):
        from mlx_lm.models.cache import make_prompt_cache
        cache = make_prompt_cache(self.model)
        self.body(tokens, cache=cache)
        return cache

    def _build_cache(self):
        msgs = [Message(role="system", content=self.system),
                Message(role="user", content=SENTINEL)]
        toks = self._render_msgs(msgs)
        cut = self._content_cut(toks, SENTINEL)
        self._prefix_tokens = toks[:cut]
        self._cut = cut
        self._cache = self._prefill(mx.array([toks[:cut]]))

    def user_message(self, goal: str, observation: str,
                     last_batch: list[str] | None,
                     hint: str | None = None,
                     script_output: str | None = None) -> str:
        parts = [f'Goal: "{goal}"']
        if hint:
            parts.append(f"Hint: likely {hint}")
        parts.append(observation)
        if script_output:
            parts.append(f"Script result: {script_output[:1600]}")
        if last_batch:
            parts.append("Last batch:")
            parts.extend(last_batch)
        return "\n".join(parts)

    # ---------- streaming decode (runs on the MLX worker thread) ----------

    def plan(self, goal: str, observation: str, last_batch,
             lines_out: asyncio.Queue, loop, cancel: threading.Event,
             hint: str | None = None,
             script_output: str | None = None) -> list[str]:
        """Blocking — submit via worker(). Streams each finished line to
        `lines_out` (call_soon_threadsafe), then a None sentinel. Returns the
        full line list."""
        t0 = time.perf_counter()
        if self._cache is None:
            self._build_cache()
        msgs = [Message(role="system", content=self.system),
                Message(role="user", content=self.user_message(
                    goal, observation, last_batch, hint, script_output)),
                Message(role="assistant", content=SENTINEL)]
        toks = self._render_msgs(msgs)
        acut = self._content_cut(toks, SENTINEL)     # prompt ends here
        cache = copy.deepcopy(self._cache)
        stop_ids = {self.tokenizer.eos_token_id}
        for s in ("<" + "|im_end|>",):
            t_ = self.tokenizer.encode(s, add_special_tokens=False)
            if len(t_) == 1:
                stop_ids.add(t_[0])
        constraint = self._op_constraint()
        cur = mx.array([toks[self._cut:acut]])
        buf = ""
        lines: list[str] = []
        cutter = BatchCutter()
        ttft = None
        n_decoded = 0
        in_script = False      # inside a `script ... """` block
        script_lines: list[str] = []
        for _ in range(MAX_TOKENS):
            if cancel.is_set():
                break
            out = self.body(cur, cache=cache)
            logits = np.array(self.lm_head(out[:, -1:, :]).astype(mx.float32)[0, 0])
            if constraint is not None and not in_script:
                allow = constraint.allowed(buf.lstrip(" "), has_action(lines))
                if allow is not None:
                    if lines and buf == "":
                        allow = allow + sorted(stop_ids)
                    mask = np.full_like(logits, -np.inf)
                    mask[allow] = 0
                    logits = logits + mask
            nxt = int(np.argmax(logits))
            if ttft is None:
                ttft = (time.perf_counter() - t0) * 1000
            if nxt in stop_ids:
                break
            n_decoded += 1
            buf += self.tokenizer.decode([nxt])
            cur = mx.array([[nxt]])
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if in_script:
                    # inside """...""" — emit the whole block as one action
                    script_lines.append(line)
                    if '"""' not in line:
                        continue
                    in_script = False
                    line = "\n".join(script_lines).strip()
                    script_lines = []
                else:
                    line = line.strip()
                    if not line:
                        continue
                    if re.match(r"^script\b", line) and line.count('"""') % 2:
                        in_script = True     # opening line of a script block
                        script_lines = [line]
                        continue
                out = cutter.push(line)
                if out is not None:
                    lines.append(out)
                    loop.call_soon_threadsafe(lines_out.put_nowait, out)
                if cutter.done:
                    break
            if cutter.done or cancel.is_set():
                break
        if in_script and script_lines:
            tail_block = "\n".join(script_lines + [buf]).strip()
            lines.append(tail_block)
            loop.call_soon_threadsafe(lines_out.put_nowait, tail_block)
            buf = ""
        tail = buf.strip()
        if tail and not cutter.done and (out := cutter.push(tail)):
            lines.append(out)
            loop.call_soon_threadsafe(lines_out.put_nowait, out)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        dt = (time.perf_counter() - t0) * 1000
        return {"lines": lines, "ttft_ms": ttft or dt,
                "decode_tok_s": n_decoded / max(dt - (ttft or 0), 1) * 1000,
                "tokens": n_decoded, "plan_ms": dt}

    def generate(self, system: str, user: str, max_tokens: int = 48,
                 stop_at_newline: bool = True) -> str:
        """One short greedy generation on the worker (ANSWER path)."""
        msgs = [Message(role="system", content=system),
                Message(role="user", content=user),
                Message(role="assistant", content=SENTINEL)]
        toks = self._render_msgs(msgs)
        acut = self._content_cut(toks, SENTINEL)
        from mlx_lm.models.cache import make_prompt_cache
        cache = make_prompt_cache(self.model)
        stop_ids = {self.tokenizer.eos_token_id}
        for s in (("<" + "|im_end|>", chr(10)) if stop_at_newline
                  else ("<" + "|im_end|>",)):
            t_ = self.tokenizer.encode(s, add_special_tokens=False)
            if len(t_) == 1:
                stop_ids.add(t_[0])
        out_tokens = []
        cur = mx.array([toks[:acut]])   # whole prompt in one shot
        for _ in range(max_tokens):
            out = self.body(cur, cache=cache)
            logits = self.lm_head(out[:, -1:, :]).astype(mx.float32)
            nxt = int(np.argmax(np.array(logits[0, 0])))
            if nxt in stop_ids:
                break
            out_tokens.append(nxt)
            cur = mx.array([[nxt]])
        return self.tokenizer.decode(out_tokens).strip()
