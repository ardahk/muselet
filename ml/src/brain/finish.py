"""Rule-based end-state criterion for planner tasks (no model call)."""

from __future__ import annotations

import re

_PLAY = re.compile(
    r"\b(?:play|put on|listen(?:ing)? to|watch|stream)\b", re.IGNORECASE)
_CART = re.compile(
    r"\b(?:add|put)\b.+\b(?:cart|basket|bag)\b", re.IGNORECASE)
_SEARCH = re.compile(
    r"\b(?:search|look\s*up|find|show(?: me)?)\b", re.IGNORECASE)
_DIRECTIONS = re.compile(
    r"\b(?:directions?|route|navigate|directions? to)\b", re.IGNORECASE)
_OPEN = re.compile(
    r"^\s*(?:please\s+)?(?:open|launch|start|go to|switch to|show)\b",
    re.IGNORECASE)
_TARGET = re.compile(
    r"\b(?:on|in|to|from|for|of|the|a|an|some|with)\b", re.IGNORECASE)


def _subject(goal: str, verb_re: re.Pattern[str]) -> str:
    """The phrase after the verb: 'play some jazz on spotify' -> 'jazz'."""
    m = verb_re.search(goal)
    rest = goal[m.end():].strip() if m else goal.strip()
    rest = re.sub(r"^[\w'-]+\s+(?=(?:some|a|an|the|my)\b)", "", rest,
                  flags=re.IGNORECASE)
    rest = _TARGET.split(rest, maxsplit=1)[0].strip()
    return rest or goal.strip()


def finish_when(goal: str) -> str | None:
    """The observable end state for a goal, or None for generic tasks."""
    g = goal.strip()
    if not g:
        return None
    if _CART.search(g):
        x = _subject(g, _CART)
        return (f"the page confirms {x} was added to the cart "
                "(e.g. 'Added to Cart' or the cart count went up)")
    if _DIRECTIONS.search(g):
        x = _subject(g, _DIRECTIONS)
        return f"a route to {x} is showing"
    if _PLAY.search(g):
        x = _subject(g, _PLAY)
        return (f"{x} is playing (a pause control is visible / "
                "player state is playing)")
    if _OPEN.search(g):
        x = g[_OPEN.search(g).end():].strip()  # type: ignore[union-attr]
        x = re.sub(r"\s*(?:app|website|site|page)\s*[.!?]?\s*$", "",
                   x, flags=re.IGNORECASE)
        return f"{x or g} is frontmost"
    if _SEARCH.search(g):
        x = _subject(g, _SEARCH)
        return f"a results page for {x} is showing"
    return None
