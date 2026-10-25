"""Phase-one working memory and follow-up resolution."""

from __future__ import annotations

import re
import time
from typing import Callable

from .detect import detect, normalize_utterance
from .guard import IRREVERSIBLE, allowed
from .matching import distance_one
from .policy import allowed_value
from .rewrite import llm_rewrite
from .rules import Resolution, apply
from .store import MemoryStore, TYPES
from .working import Turn, WorkingMemory

_MEMORY_TOKEN = re.compile(r"[^\W_]+(?:['’]s)?", re.UNICODE)
_MEMORY_PREFIXES = {"my", "the", "our"}
_MEMORY_SUFFIXES = {
    "folder", "playlist", "music", "preset", "project", "dashboard",
}
_PERSON_TYPES = {"person", "contact"}
_PATH_TYPES = {"file", "folder", "site"}
_FILE_ACTION = re.compile(
    r"\b(?:open|find|move|rename|trash|delete|save|export)\b",
    re.IGNORECASE)
_SITE_ACTION = re.compile(
    r"\b(?:open|visit|go to|look up|search|navigate to|pull up|browse)\b",
    re.IGNORECASE)


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
            return Resolution("rule", text, True, "longterm")
        return Resolution("none", source_text, False, None)
    result = apply(text, reason, wm, ctx, now, catalog)
    if result is None or (result.path == "none" and not result.changed):
        if reason == "site_search" or IRREVERSIBLE.search(text):
            if memory_changed:
                return Resolution("rule", text, True, "longterm")
            return Resolution("none", source_text, False, "llm-gated")
        if result is None and llm is not None:
            result = llm_rewrite(text, wm, ctx, now, llm,
                                 memory=longterm)
    if result is None:
        if memory_changed:
            return Resolution("rule", text, True, "longterm")
        return Resolution("none", source_text, False, reason)
    if result.reason == "guard":
        return Resolution("none", source_text, False, "guard")
    if result.changed and not allowed(text, result.text):
        if reason not in {"again", "correction"}:
            return Resolution("none", source_text, False, "guard")
        prior = wm.last(now)
        prior_text = (f"{str(prior.skill or '').replace('_', ' ')} "
                      f"{prior.resolved} "
                      f"{normalize_utterance(prior.utterance)}"
                      if prior is not None else "")
        if prior is None or not allowed(prior_text, result.text):
            return Resolution("none", source_text, False, "guard")
    result.reason = reason
    if memory_changed and not result.changed and result.path == "none":
        return Resolution("rule", text, True, "longterm")
    if result.reason not in {"llm-invalid", "llm-gated"}:
        result.reason = reason
    if not result.changed and not memory_changed:
        result.text = source_text
    return result


def apply_longterm(text: str, rows: list[dict]) -> str:
    if not rows:
        return text

    def tokens(value: str) -> list[tuple[str, int, int]]:
        found = []
        normalized = value
        for dash in ("-", "‐", "–", "—"):
            normalized = normalized.replace(dash, " ")
        for match in _MEMORY_TOKEN.finditer(normalized):
            token = match.group().casefold()
            if token.endswith(("'s", "’s")):
                token = token[:-2]
            start, end = match.span()
            if token == "up" and found and found[-1][0] == "warm":
                previous, start, _ = found.pop()
                found.append(("warmup", start, end))
            else:
                found.append((token, start, end))
        return found

    def matches(key: list[str], phrase: list[str]) -> bool:
        if key and phrase and key[-1] == phrase[-1] and \
                key[-1] in _MEMORY_SUFFIXES:
            key, phrase = key[:-1], phrase[:-1]
        return len(key) == len(phrase) and all(
            distance_one(left, right) for left, right in zip(key, phrase))

    utterance_tokens = tokens(text)
    if not utterance_tokens:
        return text
    candidates = []
    for row in rows:
        key = str(row.get("key") or "")
        value = str(row.get("value") or "").strip()
        if not key or not value:
            continue
        key_tokens = [token for token, _, _ in tokens(key)]
        while key_tokens and key_tokens[0] in _MEMORY_PREFIXES:
            key_tokens.pop(0)
        if not key_tokens:
            continue
        kind = str(row.get("type") or "").casefold()
        if kind in {"file", "folder"} and not _FILE_ACTION.search(text):
            continue
        if kind == "site" and not _SITE_ACTION.search(text):
            continue
        for start in range(len(utterance_tokens)):
            prefix = utterance_tokens[start - 1][0] if start > 0 else ""
            prefixed = prefix in _MEMORY_PREFIXES
            span_start = start - 1 if prefixed else start
            for end in range(start + 1,
                             min(len(utterance_tokens),
                                 start + len(key_tokens)) + 1):
                phrase = [token for token, _, _ in
                          utterance_tokens[start:end]]
                if len(key_tokens) == 1:
                    command_before = bool(re.search(
                        r"\b(?:text|tex|send|message|email|mail|call|tell)\b"
                        r"[^.!?]{0,24}$",
                        text[:utterance_tokens[span_start][1]],
                        re.IGNORECASE))
                    if not prefixed and not (
                            kind in _PERSON_TYPES and command_before):
                        continue
                    if prefixed and prefix not in {"my", "the"}:
                        continue
                    if len(key_tokens[0]) < 4 and not (
                            kind in _PERSON_TYPES and command_before):
                        continue
                if matches(key_tokens, phrase):
                    candidates.append({
                        "start": utterance_tokens[span_start][1],
                        "end": utterance_tokens[end - 1][2],
                        "key_length": len(key),
                        "key": key,
                        "value": value,
                        "type": kind,
                    })
                    break
    candidates.sort(key=lambda item: (
        -item["key_length"], item["start"], item["end"]))
    selected = []
    for candidate in candidates:
        if any(candidate["start"] < row["end"] and
               row["start"] < candidate["end"] for row in selected):
            continue
        selected.append(candidate)
        if len(selected) == 2:
            break
    if not selected:
        return text
    if any(row["type"] in _PATH_TYPES for row in selected):
        path_row = next(row for row in selected if row["type"] in _PATH_TYPES)
        value = path_row["value"]
        if path_row["type"] == "site" and not re.match(
                r"^https?://", value, re.IGNORECASE):
            value = f"https://{value.lstrip('/')}"
        if path_row["type"] in _PERSON_TYPES:
            value = re.sub(r"\s*(?:\([^)]*@[^)]*\)|<[^>]*@[^>]*>)\s*$",
                           "", value).strip()
        return f"open {value}"
    result = text
    for row in sorted(selected, key=lambda item: item["start"], reverse=True):
        value = row["value"]
        if row["type"] in _PERSON_TYPES:
            value = re.sub(r"\s*(?:\([^)]*@[^)]*\)|<[^>]*@[^>]*>)\s*$",
                           "", value).strip()
        elif row["type"] == "preference" and \
                tokens(str(row.get("key") or ""))[-1:]:
            if tokens(str(row.get("key") or ""))[-1][0] == "timer":
                value = f"a {value} timer"
        result = result[:row["start"]] + value + result[row["end"]:]
    return result


def eval_adapter(utterance: str, ctx: dict, history: list[dict],
                 longterm: list[dict] | None = None,
                 llm: Callable[[str, int], str] | None = None) -> dict:
    started = time.perf_counter()
    now = float((ctx or {}).get("t", time.time()))
    wm = WorkingMemory()
    for item in history:
        history_ctx = dict(item.get("ctx") or {})
        history_text = str(item.get("utterance") or "")
        history_now = float(history_ctx.get("t", 0.0))
        history_result = resolve(
            history_text, wm, history_ctx, history_now)
        outcome = item.get("outcome") or {}
        wm.record(
            history_text, history_result.text, outcome.get("skill"),
            outcome.get("args", {}), bool(outcome.get("ok")), history_ctx,
            said=outcome.get("said"), t=history_now,
            result=outcome.get("result"))
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
