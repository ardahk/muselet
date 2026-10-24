"""Phase-one working memory and follow-up resolution."""

from __future__ import annotations

import time
from typing import Callable

from .detect import detect, normalize_utterance
from .guard import allowed
from .rewrite import llm_rewrite
from .rules import Resolution, apply
from .working import Turn, WorkingMemory


def resolve(text: str, wm: WorkingMemory, ctx: dict, now: float,
            catalog=None, llm=None) -> Resolution:
    source_text = text
    text = normalize_utterance(text)
    reason = detect(text, wm, ctx, now, catalog)
    if reason is None:
        return Resolution("none", source_text, False, None)
    result = apply(text, reason, wm, ctx, now, catalog)
    if result is None and llm is not None:
        result = llm_rewrite(text, wm, ctx, now, llm)
    if result is None:
        return Resolution("none", source_text, False, reason)
    if result.reason == "guard":
        return Resolution("none", source_text, False, "guard")
    if result.changed and not allowed(source_text, result.text):
        return Resolution("none", source_text, False, "guard")
    result.reason = reason
    if not result.changed:
        result.text = source_text
    return result


def eval_adapter(utterance: str, ctx: dict, history: list[dict],
                 longterm: list[dict] | None = None,
                 llm: Callable[[str, int], str] | None = None) -> dict:
    started = time.perf_counter()
    now = float((ctx or {}).get("t", time.time()))
    wm = WorkingMemory.from_history(history, ctx or {})
    result = resolve(utterance, wm, ctx or {}, now, llm=llm)
    return {
        "text": result.text,
        "changed": result.changed,
        "path": result.path,
        "ask": result.ask,
        "ms": (time.perf_counter() - started) * 1000,
    }


__all__ = ["Resolution", "Turn", "WorkingMemory", "detect", "resolve",
           "eval_adapter"]
