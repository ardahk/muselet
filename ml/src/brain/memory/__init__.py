"""Phase-one working memory and follow-up resolution."""

from __future__ import annotations

import re
import time
from typing import Callable

from .detect import detect
from .guard import allowed
from .policy import allowed_value
from .rewrite import llm_rewrite
from .rules import Resolution, apply
from .store import MemoryStore
from .working import Turn, WorkingMemory


def resolve(text: str, wm: WorkingMemory, ctx: dict, now: float,
            catalog=None, llm=None,
            longterm: list[dict] | None = None) -> Resolution:
    source_text = text
    if longterm is not None:
        text = apply_longterm(text, longterm)
    reason = detect(text, wm, ctx, now)
    if reason is None:
        if text != source_text:
            return Resolution("memory", text, True, "memory")
        return Resolution("none", source_text, False, None)
    result = apply(text, reason, wm, ctx, now, catalog)
    if result is None and llm is not None:
        result = llm_rewrite(text, wm, ctx, now, llm,
                             memory=longterm)
    if result is None:
        if text != source_text:
            return Resolution("memory", text, True, "memory")
        return Resolution("none", text, False, reason)
    if result.reason == "guard":
        return Resolution("none", text, False, "guard")
    if result.changed and not allowed(text, result.text):
        return Resolution("none", text, False, "guard")
    result.reason = reason
    if text != source_text and not result.changed:
        result.text = text
        result.changed = True
        result.path = "memory"
    return result


def apply_longterm(text: str, rows: list[dict]) -> str:
    if not rows:
        return text
    from ..comms import is_messaging

    allow_person = is_messaging(text)
    result = text
    eligible = [row for row in rows if row.get("type") == "correction" or
                row.get("type") == "person" and allow_person]
    eligible.sort(key=lambda row: len(str(row.get("key") or "")),
                  reverse=True)
    for row in eligible:
        key, value = str(row.get("key") or ""), str(row.get("value") or "")
        if not key or not value:
            continue
        result = re.sub(
            rf"(?<!\w){re.escape(key)}(?!\w)",
            lambda _match: value, result, flags=re.IGNORECASE)
    return result


def eval_adapter(utterance: str, ctx: dict, history: list[dict],
                 longterm: list[dict] | None = None,
                 llm: Callable[[str, int], str] | None = None) -> dict:
    started = time.perf_counter()
    now = float((ctx or {}).get("t", time.time()))
    wm = WorkingMemory.from_history(history, ctx or {})
    if longterm is None:
        result = resolve(utterance, wm, ctx or {}, now, llm=llm)
    else:
        store = MemoryStore(":memory:")
        try:
            for row in longterm:
                if isinstance(row, dict):
                    store.upsert(
                        row.get("type", ""), row.get("key", ""),
                        row.get("value", ""),
                        now=row.get("created", now))
            rows = store.list(limit=1000)
            result = resolve(utterance, wm, ctx or {}, now, llm=llm,
                             longterm=rows)
        finally:
            store.close()
    return {
        "text": result.text,
        "changed": result.changed,
        "path": result.path,
        "ask": result.ask,
        "ms": (time.perf_counter() - started) * 1000,
    }


__all__ = ["Resolution", "Turn", "WorkingMemory", "detect", "resolve",
           "eval_adapter", "apply_longterm", "MemoryStore", "allowed_value"]
