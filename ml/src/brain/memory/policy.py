"""Deterministic, privacy-aware long-term memory write policy."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .store import _tokens

_SECRET = re.compile(
    r"\b(?:password|passcode|pin|ssn|verification|code\s+(?:is|:|=))\b|"
    r"\d{6,}|(?:\d[\s-]?){13,19}",
    re.IGNORECASE)
_BODY = re.compile(
    r"\b(?:message|email|typed?|writing|write|body|content)\b",
    re.IGNORECASE)
_REMEMBER = re.compile(
    r"^(?:remember(?:\s+that)?|note\s+that)\s+(.+?)\s*[.!]?$",
    re.IGNORECASE)
_FAVORITE = re.compile(
    r"^(?:remember\s+)?my\s+favorite\s+(.+?)\s+is\s+(.+?)\s*[.!]?$",
    re.IGNORECASE)
_PREFER = re.compile(
    r"^(?:remember\s+)?i\s+prefer\s+(.+?)\s+for\s+(.+?)\s*[.!]?$",
    re.IGNORECASE)
_PERSON_IS = re.compile(
    r"^(?:remember\s+)?(?:my\s+)?(?P<key>[A-Za-z][\w'-]*"
    r"(?:\s+[A-Za-z][\w'-]*)?)\s+is\s+"
    r"(?P<value>[A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*){0,2})[.!]?$",
    re.IGNORECASE)
_CALL_PERSON = re.compile(
    r"^call\s+(?:my\s+)?(?P<key>[A-Za-z][\w'-]*)\s+"
    r"(?P<value>[A-Za-z][\w'-]+(?:\s+[A-Za-z][\w'-]+){1,2})[.!]?$",
    re.IGNORECASE)
_CORRECTION = re.compile(
    r"^(?:no,?\s+)?i\s+meant\s+(.+?)\s*[.!?]?$", re.IGNORECASE)


@dataclass(frozen=True)
class MemoryCommand:
    kind: str
    reply: str
    write: dict | None = None


def allowed_value(text: str) -> bool:
    value = str(text or "")
    return bool(value.strip()) and not _SECRET.search(value) and \
        not _BODY.search(value)


def _normalized(text: str) -> str:
    return " ".join(_tokens(text))


def _write(type: str, key: str, value: str) -> dict | None:
    key, value = _normalized(key), " ".join(str(value).split()).strip(" .")
    if not key or not value or not allowed_value(key) or \
            not allowed_value(value):
        return None
    return {"type": type, "key": key, "value": value}


def memory_command(text: str) -> MemoryCommand | None:
    value = str(text or "").strip()
    match = _FAVORITE.fullmatch(value)
    if match:
        write = _write("preference", *match.groups())
    else:
        match = _PREFER.fullmatch(value)
        if match:
            preferred, category = match.groups()
            write = _write("preference", category, preferred)
        else:
            match = _REMEMBER.fullmatch(value)
            if match:
                fact = match.group(1).strip()
                key = " ".join(_normalized(fact).split()[:6])
                write = _write("fact", key, fact)
            else:
                match = _PERSON_IS.fullmatch(value)
                if match:
                    key = re.sub(r"^my\s+", "", match.group("key"),
                                 flags=re.IGNORECASE)
                    write = _write("person", key, match.group("value"))
                else:
                    match = _CALL_PERSON.fullmatch(value)
                    if not match:
                        return None
                    write = _write("person", match.group("key"),
                                   match.group("value"))
    if write is None:
        return None
    return MemoryCommand("remember", "Got it, I'll remember that.", write)


def forget_command(text: str) -> tuple[str, str | None] | None:
    value = " ".join(str(text or "").casefold().split()).strip(" .!?")
    if value == "forget everything":
        return "clear", None
    if value == "forget that":
        return "that", None
    if value.startswith("forget what i told you about "):
        query = value[len("forget what i told you about "):].strip()
        return ("query", query) if query else None
    if value.startswith("forget about "):
        query = value[len("forget about "):].strip()
        return ("query", query) if query else None
    match = re.fullmatch(r"what do you remember(?: about (.+))?", value)
    if match:
        return "remember", match.group(1)
    return None


def extract_writes(text: str, *, skill: str | None = None,
                   args: dict | None = None, outcome: str = "ok",
                   previous_turn=None, app: str | None = None) -> list[dict]:
    if outcome != "ok":
        return []
    command = memory_command(text)
    if command and command.write:
        return [command.write]
    match = _CORRECTION.fullmatch(str(text or "").strip())
    if not match or previous_turn is None:
        return []
    replacement = match.group(1).strip()
    if not allowed_value(replacement):
        return []
    old_args = getattr(previous_turn, "args", {}) or {}
    for name in ("to", "app", "query", "path", "url"):
        old = old_args.get(name)
        if not isinstance(old, str) or not old.strip():
            continue
        if len(_normalized(old).split()) <= 3 and \
                _normalized(old) != _normalized(replacement):
            write = _write("correction", old, replacement)
            return [write] if write else []
    return []


def planner_writes(goal: str, app: str, steps: int) -> list[dict]:
    normalized = _normalized(goal)
    if not normalized or not allowed_value(goal):
        return []
    episode = _write(
        "episode", normalized, f"{goal.strip()} → ok ({int(steps)} steps, "
        f"{str(app or 'unknown')})")
    workflow = _write(
        "workflow", normalized, f"{int(steps)} steps in {str(app or 'unknown')}")
    return [row for row in (episode, workflow) if row]
