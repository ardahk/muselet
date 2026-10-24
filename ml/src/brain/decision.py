"""System-1 decision engine: ROUTE (single-token classification over the
skill catalog + 4 special options) and ARGS (short greedy extraction),
rendered byte-identically to the Tinker training side (training/SPEC.md 1.2).
"""

import copy
import re
import socket
import string
import time
from dataclasses import dataclass, field

import mlx.core as mx
import mlx_lm
import numpy as np
import dateparser as _dp
from tinker_cookbook import model_info, renderers, tokenizer_utils

from .vendor.tinker_decisions import (
    ChoiceRendering, Decision, DecisionRenderer, PrefixedChoiceRenderer,
)

SPECIAL = ["MULTI_STEP", "ASK", "REFUSE", "ANSWER"]

ROUTE_SYSTEM = (
    "You are the intent router of an on-device macOS voice assistant. "
    "Read the context and the user's spoken request, then pick exactly one "
    "choice. Reply with the id of your choice, written as `choice#?`, and "
    "nothing else.\n\nChoices:\n{choices}"
)
ROUTE_USER = (
    'Context: app={app} | focused={focused} | selection={sel} | '
    'online={online} | last_action={last}\nRequest: "{request}"'
)
ARGS_SYSTEM = (
    "You extract arguments for a macOS assistant skill from the user's "
    "spoken request. Reply with one line of key=value pairs using the skill's "
    "argument names. Quote values that contain spaces. Copy spoken dates, "
    "times and durations exactly as said; do not convert them. Convert spoken "
    "numbers to digits. If a required argument is missing, reply "
    "missing=<argument name>."
)
ARGS_USER = 'Skill: {name}({sig})\nContext: app={app} | last_action={last}\nRequest: "{request}"'

_WORD_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
             "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
             "forty": 40, "sixty": 60, "ninety": 90}
_UNITS = {"second": 1, "seconds": 1, "sec": 1, "secs": 1,
          "minute": 60, "minutes": 60, "min": 60, "mins": 60,
          "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600}
_WORD_SCALE = {"hundred": 100}


def parse_duration(text: str) -> int | None:
    """Spoken duration -> seconds. 'ten minutes', '90 seconds',
    '1 hour 30 minutes', 'an hour and a half'."""
    t = text.lower().strip()
    m = re.match(r"^an?\s+(hour|minute|second)s?\s+and a half$", t)
    if m:
        return int(1.5 * _UNITS[m.group(1)])
    m = re.search(r"half an? (hour|minute|second)s?", t)
    if m:
        return int(0.5 * _UNITS[m.group(1)])
    total = 0.0
    found = False
    for m in re.finditer(
            r"(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|fifteen|twenty|thirty|forty|sixty|ninety)\s*"
            r"(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", t):
        num = _WORD_NUM.get(m.group(1), None)
        if num is None:
            try:
                num = float(m.group(1))
            except ValueError:
                return None
        total += num * _UNITS[m.group(2)]
        found = True
    return int(total) if found else None


def parse_datetime(text: str) -> str | None:
    """Spoken date/time -> ISO-8601 local. Returns None if unparsable."""
    d = _dp.parse(text, languages=["en"],
                  settings={"PREFER_DATES_FROM": "future"})
    return d.isoformat(timespec="seconds") if d else None


def normalize_level(v, words: bool = False) -> int | None:
    """SPEC 1.4: max/full->100, half->50."""
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("max", "full", "maximum"): return 100
        if s == "half": return 50
        if s in _WORD_NUM: return _WORD_NUM[s]
        if s.isdigit(): return int(s)
        return None
    if isinstance(v, (int, float)): return int(v)
    return None


def normalize_delta(v, direction: str | None = None) -> int | None:
    """SPEC 1.4: 'a bit/little' = ±10, 'a lot' = ±25, louder/quieter ±10."""
    if isinstance(v, str):
        s = v.strip().lower()
        sign = -1 if direction == "down" or s.startswith("-") else 1
        s = s.lstrip("+-")
        if s in ("a bit", "a little", "bit", "little", "some"): return 10 * sign
        if s in ("a lot", "lot", "way"): return 25 * sign
        if s.isdigit(): return int(s) * sign
        if s in _WORD_NUM: return _WORD_NUM[s] * sign
        return None
    if isinstance(v, (int, float)): return int(v)
    return None


def _online_ok() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=0.5).close()
        return True
    except OSError:
        return False


class _OnlineProbe:
    """Background reachability check: refreshes every 10 s, never blocks."""

    def __init__(self):
        self.value = True
        import threading
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while True:
            self.value = _online_ok()
            time.sleep(10)


def split_model(model):
    """(transformer body taking token ids, lm_head) — same trick as
    bench/speed_lab.py. Inner model embeds + runs layers, returns hidden."""
    inner = getattr(model, "model", model)
    lm_head = getattr(inner, "lm_head", None) or getattr(model, "lm_head", None)
    if lm_head is None:
        lm_head = inner.embed_tokens.as_linear   # tied weights
    return inner, lm_head


class AlphaChoiceRenderer(PrefixedChoiceRenderer):
    """choice#<ID> where ID alphabet is A..Z, 0..9, a..z — filtered to ids
    that tokenize as exactly one token after the prefix (SPEC 1.2)."""
    IDS = list(string.ascii_uppercase + string.digits + string.ascii_lowercase)

    def __init__(self, renderer):
        # PrefixedChoiceRenderer.__init__ validates '?' is one token after prefix.
        super().__init__(renderer, prefix="choice#", placeholder="?")
        n = len(self.prefix_tokens)
        keep = []
        for c in self.IDS:
            toks = self.tokenizer.encode(self.prefix + c, add_special_tokens=False)
            if toks[:n] == self.prefix_tokens and len(toks) == n + 1:
                keep.append(c)
        if len(keep) < 40:
            raise RuntimeError(f"only {len(keep)} usable choice ids, need >= 40")
        self.usable_ids = keep


class RouteDecisionRenderer(DecisionRenderer):
    """SPEC 1.2 / training/src/muselet_train/route_render.py: option list in
    the SYSTEM message (static prefix), request in the USER message,
    `choice#?` prefill."""

    def _build_messages(self, decision, choice_rendering):
        from tinker_cookbook.renderers import Message
        lines = []
        for label, description in decision.choices:
            reply = str(self.tokenizer.decode(
                choice_rendering.answer_tokens_for(label)))
            choice_id = str(self.tokenizer.decode(
                [choice_rendering.label_tokens[label]]))
            line = reply if choice_id == label else f'{reply} = "{label}"'
            lines.append(f"{line}: {description}" if description else line)
        return [
            Message(role="system",
                    content=ROUTE_SYSTEM.format(choices="\n".join(lines))),
            Message(role="user", content=decision.text),
        ]


@dataclass
class RouteResult:
    probs: dict = field(default_factory=dict)   # label -> prob
    top: str = ""
    p_top: float = 0.0
    ms: dict = field(default_factory=dict)


def catalog_options(catalog) -> list[tuple[str, str]]:
    """(name, description) — skills in file order, then special_options in
    file order (matches training muselet_train.catalog.options)."""
    opts = [(s["name"], s["description"]) for s in catalog.skills.values()]
    for s in catalog.special_options:
        opts.append((s["name"], s["description"]))
    return opts


class RouteRenderer:
    """Tokenizer-only route rendering — no model weights needed (parity
    tests, eval pre-checks)."""

    def __init__(self, tokenizer_path: str, catalog):
        rname = model_info.get_recommended_renderer_name("Qwen/Qwen3.5-4B")
        self.renderer = renderers.get_renderer(
            rname, tokenizer_utils.get_tokenizer(tokenizer_path))
        self.tokenizer = self.renderer.tokenizer
        self.choice_renderer = AlphaChoiceRenderer(self.renderer)
        self.route_renderer = RouteDecisionRenderer(
            self.renderer, choice_renderer=self.choice_renderer)
        self._options = catalog_options(catalog)

    @property
    def options(self) -> list[tuple[str, str]]:
        return self._options

    @property
    def id_alphabet(self) -> list[str]:
        return self.choice_renderer.usable_ids

    def decision(self, utterance: str, ctx: dict) -> Decision:
        text = ROUTE_USER.format(
            app=ctx.get("app") or "none",
            focused=ctx.get("focused") or "none",
            sel="yes" if ctx.get("selection") else "no",
            online="yes" if ctx.get("online", True) else "no",
            last=ctx.get("last_action") or "none",
            request=utterance)
        return Decision(text=text, choices=self._options)

    def render(self, utterance: str, ctx: dict):
        return self.route_renderer.render(self.decision(utterance, ctx))


class DecisionEngine:
    def __init__(self, model_path: str, catalog=None):
        self.model_path = model_path
        self.model, self.tokenizer = mlx_lm.load(model_path)
        self.body, self.lm_head = split_model(self.model)
        self.rr = RouteRenderer(model_path, catalog)
        self.choice_renderer = self.rr.choice_renderer
        self.route_renderer = self.rr.route_renderer
        self.catalog = catalog
        self.last_action = "none"
        self._probe = _OnlineProbe()
        self._route_prefix_tokens: list[int] | None = None
        self._route_cache = None          # static system+user-header prefix
        self._args_cache = None
        parse_datetime("now")             # warm dateparser's english locale

    # ---------- catalog ----------

    def options(self) -> list[tuple[str, str]]:
        return self.rr.options

    def online(self) -> bool:
        return self._probe.value

    # ---------- route ----------

    def _route_decision(self, utterance: str, ctx: dict) -> Decision:
        # ctx-supplied online wins (app/eval); engine probe is the fallback
        ctx = dict(ctx)
        if "online" not in ctx:
            ctx["online"] = self.online()
        ctx.setdefault("last_action", self.last_action)
        return self.rr.decision(utterance, ctx)

    def _content_cut(self, rendered_tokens, sentinel: str) -> int:
        sent = self.tokenizer.encode(sentinel, add_special_tokens=False)
        n = len(sent)
        for i in range(len(rendered_tokens) - n + 1):
            if rendered_tokens[i:i + n] == sent:
                return i
        raise RuntimeError("sentinel not found in rendered tokens")

    def _build_route_cache(self):
        """Cache = model state after prefilling every token before the user
        content (system message + user header). A sentinel user message marks
        the split point."""
        sentinel = "SENTINELMARKER9Z"
        probe = Decision(text=sentinel, choices=self.options())
        toks = self.route_renderer.render(probe).tokens
        cut = self._content_cut(toks, sentinel)
        self._route_prefix_tokens = toks[:cut]
        self._route_prefix_cut = cut
        self._route_cache = self._prefill(mx.array([toks[:cut]]))

    def _build_args_cache(self):
        """Same trick for the ARGS system message: static prefix ends where
        the user content starts."""
        from tinker_cookbook.renderers import Message
        sentinel = "SENTINELMARKER9Z"
        msgs = [Message(role="system", content=ARGS_SYSTEM),
                Message(role="user", content=sentinel),
                Message(role="assistant", content=sentinel)]
        toks = self._render_msgs(msgs)
        ucut = self._content_cut(toks, sentinel)
        acut = self._content_cut(toks[ucut + 1:], sentinel) + ucut + 1
        self._args_prompt_end = acut          # prompt tokens end here
        self._args_prefix_tokens = toks[:ucut]
        self._args_cut = ucut
        self._args_cache = self._prefill(mx.array([toks[:ucut]]))

    def _render_msgs(self, msgs):
        mi, _ = self.route_renderer.renderer.build_supervised_example(msgs)
        return mi.to_ints()

    def _prefill(self, tokens):
        from mlx_lm.models.cache import make_prompt_cache
        cache = make_prompt_cache(self.model)
        self.body(tokens, cache=cache)
        return cache

    def _logits_last(self, cache, tokens):
        """Prefill `tokens` (ids) into cache; lm_head on the last position."""
        out = self.body(tokens, cache=cache)
        logits = self.lm_head(out[:, -1:, :]).astype(mx.float32)
        return logits[0, 0]

    def route(self, utterance: str, ctx: dict) -> RouteResult:
        t0 = time.perf_counter()
        if self._route_cache is None:
            self._build_route_cache()
        rendering = self.route_renderer.render(self._route_decision(utterance, ctx))
        toks = rendering.tokens
        cut = self._route_prefix_cut
        assert toks[:cut] == self._route_prefix_tokens, \
            "route render diverged from cached prefix"
        cache = copy.deepcopy(self._route_cache)
        # Feed tokens up to (not including) the placeholder; logits of the last
        # fed position score the answer token at choice_pos.
        logits = self._logits_last(cache, mx.array([toks[cut:rendering.choice_pos]]))
        labels = rendering.labels
        lp = np.array(logits[[rendering.label_tokens[l] for l in labels]])
        lp = lp - lp.max()
        p = np.exp(lp); p = p / p.sum()
        probs = dict(zip(labels, p.tolist()))
        top = max(probs, key=probs.get)
        return RouteResult(probs=probs, top=top, p_top=probs[top],
                           ms={"route_ms": round((time.perf_counter() - t0) * 1000, 2)})

    # ---------- args ----------

    def arg_signature(self, name: str) -> str:
        # exact match to training muselet_train.catalog.arg_signature:
        # "level:int 0-100 required, kind:enum any|pdf optional"
        spec = (self.catalog.get(name) or {}) if self.catalog else {}
        parts = []
        for a in spec.get("args", []):
            sig = f"{a['name']}:{a['type']}"
            if "min" in a or "max" in a:
                sig += f" {a.get('min', '')}-{a.get('max', '')}"
            if a.get("values"):
                sig += " " + "|".join(a["values"])
            sig += " required" if a.get("required") else " optional"
            parts.append(sig)
        return ", ".join(parts)

    def args(self, skill: str, utterance: str, ctx: dict) -> dict:
        """Extract skill args; returns dict (may contain 'missing')."""
        t0 = time.perf_counter()
        if self._args_cache is None:
            self._build_args_cache()
        user = ARGS_USER.format(name=skill, sig=self.arg_signature(skill),
                                app=ctx.get("app", "none"),
                                last=ctx.get("last_action", self.last_action),
                                request=utterance)
        from tinker_cookbook.renderers import Message
        sentinel = "SENTINELMARKER9Z"
        msgs = [Message(role="system", content=ARGS_SYSTEM),
                Message(role="user", content=user),
                Message(role="assistant", content=sentinel)]
        toks = self._render_msgs(msgs)
        acut = self._content_cut(toks, sentinel)   # prompt ends at sentinel
        assert toks[:self._args_cut] == self._args_prefix_tokens, \
            "args render diverged from cached prefix"
        cache = copy.deepcopy(self._args_cache)
        stop_ids = {self.tokenizer.eos_token_id}
        for _s in ("
        parsed["ms"] = {"args_ms": round((time.perf_counter() - t0) * 1000, 2)}
        parsed["_raw"] = text
        return parsed

    @staticmethod
    def _parse_args_line(text: str) -> dict:
        """key=value pairs, quoted values allowed; missing=<arg> special."""
        out = {}
        first = text.splitlines()[0] if text.strip() else ""
        for m in re.finditer(r'(\w+)=(?:"((?:[^"\\]|\\.)*)"|(\S+))', first):
            k = m.group(1)
            v = m.group(2) if m.group(2) is not None else m.group(3)
            v = v.replace('\\"', '"').replace("\\\\", "\\")
            if k == "missing":
                out["missing"] = v
            else:
                out[k] = v
        return out
