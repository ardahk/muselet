"""Phase-one working memory and follow-up resolution."""

from __future__ import annotations

import re
import time
from typing import Callable

from .detect import detect, normalize_utterance
from .guard import allowed
from .policy import allowed_value
from .rewrite import llm_rewrite
from .rules import Resolution, apply
from .store import MemoryStore, TYPES
from .working import Turn, WorkingMemory


def resolve(text: str, wm: WorkingMemory, ctx: dict, now: float,
            catalog=None, llm=None,
            longterm: list[dict] | None = None) -> Resolution:
    source_text = text
    memory_text = apply_longterm(text, longterm) if longterm is not None \
        else text
    memory_changed = memory_text != source_text
    text = normalize_utterance(memory_text)
    reason = detect(text, wm, ctx, now, catalog)
    if reason is None:
        if memory_changed:
            return Resolution("memory", text, True, "memory")
        return Resolution("none", source_text, False, None)
    result = apply(text, reason, wm, ctx, now, catalog)
    if result is None and llm is not None:
        result = llm_rewrite(text, wm, ctx, now, llm,
                             memory=longterm)
    if result is None:
        if memory_changed:
            return Resolution("memory", text, True, "memory")
        return Resolution("none", source_text, False, reason)
    if result.reason == "guard":
        return Resolution("none", source_text, False, "guard")
    if result.changed and not allowed(source_text, result.text):
        return Resolution("none", source_text, False, "guard")
    result.reason = reason
    if memory_changed and not result.changed and result.path == "none":
        result.text = text
        result.changed = True
        result.path = "memory"
    if not result.changed and not memory_changed:
        result.text = source_text
    return result


def apply_longterm(text: str, rows: list[dict]) -> str:
    if not rows:
        return text
    from ..comms import is_messaging

    allow_person = is_messaging(text)
    file_command = re.search(
        r"\b(?:open|find|move|rename|trash|delete|save|export)\b",
        text, re.IGNORECASE)
    search_command = re.search(r"\b(?:search|look up|find)\b",
                               text, re.IGNORECASE)
    result = text
    eligible = []
    for row in rows:
        kind = row.get("type")
        if kind == "correction" or \
                kind in {"person", "contact"} and allow_person or \
                kind in {"file", "folder"} and file_command or \
                kind == "site" and search_command:
            eligible.append(row)
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
            additional = []
            for row in longterm:
                if isinstance(row, dict):
                    kind = row.get("type", "")
                    if kind in TYPES:
                        store.upsert(
                            kind, row.get("key", ""), row.get("value", ""),
                            now=row.get("created", 0))
                    else:
                        additional.append({**row, "created": 0})
            rows = store.list(limit=1000) + additional
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
