"""System-2 planner: streams DSL action batches from a 4B-class model on ONE
dedicated MLX worker thread shared by every model call (route, args, plan).

Rendering: same qwen3_5 tinker-cookbook renderer; optional bounded thinking
fills the empty think block. The static catalog prefix is cached once.
"""

import asyncio
import copy
import queue as _queue
import re
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import numpy as np
from tinker_cookbook.renderers import Message

from .catalog import Catalog
from .decision import DecisionEngine, _OnlineProbe, split_model  # noqa: F401
from .dsl import action_line

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "planner_system.md"
TERMINAL_OPS = {"ask", "confirm", "done", "refuse"}
MAX_TOKENS = 320   # room for multi-line script blocks
SENTINEL = "SENTINELMARKER9Z"
THINK_ON = ("all", "retry")
THINK_SAMPLERS = {"greedy": None, "qwen": {"temp": 0.6, "top_p": 0.95, "top_k": 20}}
THINK_NGRAM = 12
THINK_REPEATS = 3
THINK_TRACE_CHARS = 400
RETRY_RE = re.compile(r"(?:->\s*|^\[)(?:failed|confirmed|cancelled|yes|no)\b")

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


def _mlx_core():
    import mlx.core as mx

    return mx


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


def is_retry(goal: str, last_batch) -> bool:
    return '\nUser answer: "' in goal or any(
        RETRY_RE.search(line) for line in (last_batch or ()))


def sample_logits(logits, temp: float, top_p: float, top_k: int, rng) -> int:
    if temp <= 0:
        return int(np.argmax(logits))
    z = logits / temp
    if top_k > 0:
        kth = np.partition(z, -top_k)[-top_k]
        z = np.where(z < kth, -np.inf, z)
    z = z - np.max(z)
    pr = np.exp(z)
    pr /= pr.sum()
    if top_p < 1:
        idx = np.argsort(-pr)
        c = np.cumsum(pr[idx])
        keep = idx[:int(np.searchsorted(c, top_p)) + 1]
        q = np.zeros_like(pr)
        q[keep] = pr[keep]
        pr = q / q.sum()
    return int(rng.choice(len(pr), p=pr))


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

    def __init__(self, max_actions: int = 5, skills=None):
        self.max, self.n, self.full, self.done = max_actions, 0, False, False
        self.skills = Catalog.load().skills if skills is None else skills

    def push(self, line: str) -> str | None:
        """The line to emit, or None. Sets .done when the batch is over."""
        if self.full:
            if line.startswith("#"):
                return None
            self.done = True
            return line if line.startswith("expect") else None
        action = action_line(line, self.skills) or action_line(line)
        if not re.match(r"^(expect|#)", line) and action:
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
    import mlx_lm

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
                 few_shot: str | None = FEWSHOT_PATH, history: str = "dsl",
                 retrieval_k: int = 0, retrieval_bank: str = "v2-tune",
                 think_budget: int = 0, think_on: str = "all",
                 think_sampler: str = "greedy", think_seed: int = 0):
        if history not in HISTORY_FORMATS:
            raise ValueError(f"history must be one of {HISTORY_FORMATS}")
        if retrieval_k not in (0, 1, 2):
            raise ValueError("retrieval_k must be 0, 1, or 2")
        if think_budget < 0:
            raise ValueError("think_budget must be non-negative")
        if think_on not in THINK_ON:
            raise ValueError(f"think_on must be one of {THINK_ON}")
        if think_sampler not in THINK_SAMPLERS:
            raise ValueError(f"think_sampler must be one of {tuple(THINK_SAMPLERS)}")
        self.model_path = model_path
        self.constrain, self.done_alone = constrain, done_alone
        self.few_shot, self.history = few_shot, history
        self.retrieval_k, self.retrieval_bank = retrieval_k, retrieval_bank
        self.think_budget, self.think_on = think_budget, think_on
        self.think_sampler, self.think_seed = think_sampler, think_seed
        self.plan_bank = None
        if retrieval_k > 0:
            from .plan_bank import PlanBank, load_bank
            self.plan_bank = PlanBank(load_bank(retrieval_bank))
        self.last_retrieval = {"ids": [], "ms": 0.0}
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
        result = (f"constrain={self.constrain} done_alone={self.done_alone} "
                  f"few_shot={self.few_shot or 'none'} history={self.history} "
                  f"retrieval_k={self.retrieval_k}")
        if self.retrieval_k > 0:
            result += f" retrieval_bank={self.retrieval_bank}"
        if self.think_budget > 0:
            result += (f" think={self.think_budget} think_on={self.think_on} "
                       f"think_sampler={self.think_sampler}")
        return result

    def wants_think(self, goal: str, last_batch) -> bool:
        return self.think_budget > 0 and (
            self.think_on == "all" or is_retry(goal, last_batch))

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
        mx = _mlx_core()
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
                     script_output: str | None = None,
                     login_page: bool = False) -> str:
        parts = [f'Goal: "{goal}"']
        if hint:
            parts.append(f"Hint: likely {hint}")
        if login_page:
            parts.append("Login page: ask the user to sign in")
        parts.append(observation)
        if script_output:
            parts.append(f"Script result: {script_output[:1600]}")
        if last_batch:
            parts.append("Last batch:")
            parts.extend(last_batch)
        return "\n".join(parts)

    def retrieval_block(self, goal: str, observation: str) -> str:
        from .plan_bank import render_block

        started = time.perf_counter()
        demos = self.plan_bank.retrieve(goal, observation, self.retrieval_k) if self.plan_bank else []
        ids = [demo.id or demo.goal for demo in demos]
        block = render_block(demos)
        self.last_retrieval = {"ids": ids, "ms": (time.perf_counter() - started) * 1000}
        return block

    def user_content(self, goal: str, observation: str,
                     last_batch: list[str] | None,
                     hint: str | None = None,
                     script_output: str | None = None,
                     login_page: bool = False) -> str:
        return self.retrieval_block(goal, observation) + self.user_message(
            goal, observation, last_batch, hint, script_output, login_page)

    def prompt_tokens(self, goal: str, observation: str, last_batch,
                      hint: str | None = None,
                      script_output: str | None = None,
                      login_page: bool = False) -> list[int]:
        """Full prompt plan() decodes from (system + user + assistant header with the empty think block)."""
        msgs = [Message(role="system", content=self.system),
                Message(role="user", content=self.user_content(
                    goal, observation, last_batch, hint, script_output,
                    login_page)),
                Message(role="assistant", content=SENTINEL)]
        toks = self._render_msgs(msgs)
        return toks[:self._content_cut(toks, SENTINEL)]

    # ---------- streaming decode (runs on the MLX worker thread) ----------

    def think(self, cache, dyn: list[int], cancel=None) -> tuple[list[int], dict]:
        started = time.perf_counter()
        open_tokens = self.tokenizer.encode("<think>", add_special_tokens=False)
        close_tokens = self.tokenizer.encode("</think>", add_special_tokens=False)
        if len(open_tokens) != 1 or len(close_tokens) != 1:
            raise RuntimeError("think markers must each encode to one token")
        open_id, close_id = open_tokens[0], close_tokens[0]
        idx = next((i for i in range(len(dyn) - 1, -1, -1)
                    if dyn[i] == open_id), None)
        if idx is None:
            raise RuntimeError("think start token not found")
        nl = self.tokenizer.encode("\n", add_special_tokens=False)
        after = self.tokenizer.encode("\n\n", add_special_tokens=False)
        stop_ids = {self.tokenizer.eos_token_id}
        end_tokens = self.tokenizer.encode("<" + "|im_end|>", add_special_tokens=False)
        if len(end_tokens) == 1:
            stop_ids.add(end_tokens[0])
        rng = np.random.default_rng(self.think_seed)
        sampler = THINK_SAMPLERS[self.think_sampler]
        cur = dyn[:idx + 1] + nl
        thought = []
        repeats = {}
        feed = None
        closed = None

        def close_tail():
            text = self.tokenizer.decode(thought)
            return ([] if text.endswith("\n") else nl) + [close_id] + after

        while len(thought) < self.think_budget:
            out = self.body(mx.array([cur]), cache=cache)
            logits = np.array(self.lm_head(out[:, -1:, :]).astype(mx.float32)[0, 0])
            nxt = int(np.argmax(logits)) if sampler is None else sample_logits(
                logits, sampler["temp"], sampler["top_p"], sampler["top_k"], rng)
            if nxt == close_id:
                closed, feed = "model", [close_id] + after
                break
            if nxt in stop_ids:
                closed, feed = "eos", close_tail()
                break
            thought.append(nxt)
            cur = [nxt]
            if len(thought) >= THINK_NGRAM:
                ngram = tuple(thought[-THINK_NGRAM:])
                repeats[ngram] = repeats.get(ngram, 0) + 1
                if repeats[ngram] >= THINK_REPEATS:
                    closed, feed = "loop", [nxt] + close_tail()
                    break
            if cancel is not None and cancel.is_set():
                closed, feed = "cancel", [nxt] + close_tail()
                break
            if len(thought) >= self.think_budget:
                closed, feed = "budget", [nxt] + close_tail()
                break
        text = self.tokenizer.decode(thought)
        return feed, {"tokens": len(thought),
                      "ms": round((time.perf_counter() - started) * 1000, 1),
                      "text": text[:THINK_TRACE_CHARS], "closed": closed}

    def plan(self, goal: str, observation: str, last_batch,
             lines_out: asyncio.Queue, loop, cancel: threading.Event,
             hint: str | None = None,
             script_output: str | None = None,
             login_page: bool = False) -> list[str]:
        """Blocking — submit via worker(). Streams each finished line to
        `lines_out` (call_soon_threadsafe), then a None sentinel. Returns the
        full line list."""
        t0 = time.perf_counter()
        mx = _mlx_core()
        if self._cache is None:
            self._build_cache()
        toks = self.prompt_tokens(goal, observation, last_batch, hint, script_output, login_page)
        acut = len(toks)     # prompt ends here
        cache = copy.deepcopy(self._cache)
        stop_ids = {self.tokenizer.eos_token_id}
        for s in ("<" + "|im_end|>",):
            t_ = self.tokenizer.encode(s, add_special_tokens=False)
            if len(t_) == 1:
                stop_ids.add(t_[0])
        constraint = self._op_constraint()
        dyn = toks[self._cut:acut]
        think = None
        if self.wants_think(goal, last_batch):
            dyn, think = self.think(cache, dyn, cancel)
        cur = mx.array([dyn])
        buf = ""
        lines: list[str] = []
        cutter = BatchCutter(skills=self.catalog.skills)
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
                "tokens": n_decoded, "plan_ms": dt,
                "retrieved": self.last_retrieval["ids"], "prompt_tokens": acut,
                "dynamic_tokens": acut - self._cut, "think": think,
                "think_tokens": think["tokens"] if think else 0}

    def generate(self, system: str, user: str, max_tokens: int = 48,
                 stop_at_newline: bool = True) -> str:
        """One short greedy generation on the worker (ANSWER path)."""
        mx = _mlx_core()
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
