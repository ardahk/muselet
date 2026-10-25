"""Load and select concise app-specific planner tips."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "prompts" / "app_hints.jsonl"
_BARE_OPEN = re.compile(
    r"^\s*(please\s+)?(open|launch|start|go to|show)\s+(up\s+)?"
    r"(the\s+)?[\w .'-]{1,40}?(\s+(app|website|site|page))?\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_TASK_VERBS = (
    "play", "add", "search", "find", "rename", "set", "change",
    "directions", "create", "make", "listen", "watch", "look up", "put",
)


@dataclass(frozen=True)
class AppHint:
    id: str
    match: tuple[str, ...]
    skills: frozenset[str]
    tips: tuple[str, ...]
    generic: bool = False


def _read_hints(path: Path) -> tuple[AppHint, ...]:
    return tuple(
        AppHint(
            id=row["id"],
            match=tuple(row["match"]),
            skills=frozenset(row["skills"]),
            tips=tuple(row["tips"]),
            generic=bool(row.get("generic", False)),
        )
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in (json.loads(line),)
    )


@lru_cache(maxsize=1)
def _default_hints() -> tuple[AppHint, ...]:
    return _read_hints(DEFAULT_PATH)


def load_hints(path: Path | None = None) -> list[AppHint]:
    return list(_default_hints() if path is None else _read_hints(Path(path)))


def _phrase_matches(phrase: str, text: str) -> bool:
    return bool(re.search(rf"\b{re.escape(phrase.lower())}\b", text))


def match_hints(
    goal: str,
    app: str = "",
    hints: list[AppHint] | None = None,
    k: int = 2,
) -> list[AppHint]:
    goal, app = goal.lower(), app.lower()
    rows = load_hints() if hints is None else hints
    matched: list[AppHint] = []
    app_only: list[AppHint] = []
    for hint in rows:
        if hint.generic:
            continue
        goal_match = any(_phrase_matches(phrase, goal) for phrase in hint.match)
        app_match = any(phrase.lower() in app for phrase in hint.match)
        if goal_match:
            matched.append(hint)
        elif app_match:
            app_only.append(hint)
    selected = (matched + app_only)[:max(0, k)]
    if not selected:
        return selected

    generic = next((hint for hint in rows
                    if hint.id == "search_then_act" and hint.generic), None)
    if generic and any(_phrase_matches(phrase, goal)
                       for phrase in generic.match):
        selected.append(generic)
    return selected


def render_hints(hints: list[AppHint]) -> str:
    if not hints:
        return ""
    rendered = "App tips (known facts about these apps; prefer them over guessing):"
    for tip in (tip for hint in hints for tip in hint.tips):
        line = "- " + tip
        if len(rendered) + 1 + len(line) > 1200:
            break
        rendered += "\n" + line
    return rendered


def open_ended_redirect(
    label: str,
    text: str,
    catalog_risk: str | None,
) -> AppHint | None:
    if label in {"MULTI_STEP", "ASK", "REFUSE"}:
        return None
    if catalog_risk not in (None, "safe"):
        return None
    if _BARE_OPEN.fullmatch(text) and not any(
        re.search(rf"\b{re.escape(verb)}\b", text, re.IGNORECASE)
        for verb in _TASK_VERBS
    ):
        return None
    return next(
        (hint for hint in match_hints(text)
         if not hint.generic and label not in hint.skills),
        None,
    )
