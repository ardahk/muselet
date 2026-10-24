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

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "planner_system.md"
TERMINAL_OPS = {"ask", "confirm", "done", "refuse"}
MAX_TOKENS = 320   # room for multi-line script blocks
SENTINEL = "SENTINELMARKER9Z"

# ---------- shared MLX worker (single thread, FIFO) ----------

_WORKER = None
_WORKER_LOCK = threading.Lock()


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
        if not re.match(r"^(expect|#)", line):
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

    def __init__(self, model_path: str, catalog, engine: DecisionEngine | None = None):
        self.model_path = model_path
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
            logits = self.lm_head(out[:, -1:, :]).astype(mx.float32)
            nxt = int(np.argmax(np.array(logits[0, 0])))
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

    def generate(self, system: str, user: str, max_tokens: int = 48) -> str:
        """One short greedy generation on the worker (ANSWER path)."""
        msgs = [Message(role="system", content=system),
                Message(role="user", content=user),
                Message(role="assistant", content=SENTINEL)]
        toks = self._render_msgs(msgs)
        acut = self._content_cut(toks, SENTINEL)
        from mlx_lm.models.cache import make_prompt_cache
        cache = make_prompt_cache(self.model)
        stop_ids = {self.tokenizer.eos_token_id}
        for s in ("<" + "|im_end|>", chr(10)):
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
