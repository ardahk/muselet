"""Rule-based end-state criterion for planner tasks (no model call)."""

from __future__ import annotations

import re

_PLAY = re.compile(
    r"\b(?:play|put on|listen(?:ing)? to|watch|stream)\b", re.IGNORECASE)
_CART = re.compile(
    r"\b(?:add|put)\b.+\b(?:cart|basket|bag)\b", re.IGNORECASE)
_SEARCH = re.compile(
    r"\b(?:search|look\s*up|find|show(?: me)?)\b", re.IGNORECASE)
_DIRECTIONS = re.compile(r"\bdirections?|route\b|navigate", re.IGNORECASE)
_OPEN = re.compile(
    r"^\s*(?:please\s+)?(?:open|launch|start|go to|switch to|show)\b",
    re.IGNORECASE)
_DET = re.compile(r"^(?:some|a|an|the|my|any)\s+", re.IGNORECASE)
_CUT = re.compile(r"\s+(?:on|in|from|for|with|to|into)\s+", re.IGNORECASE)


def _subject(goal: str, end: int) -> str:
    """The phrase after the verb: leading determiners stripped, cut at the
    first on/in/from/for/with. 'play some jazz on spotify' -> 'jazz'."""
    rest = goal[end:].strip()
    rest = re.sub(r"^\s*(?:about|for|to|up|on|into|my)\s+", "", rest,
                  flags=re.IGNORECASE)
    rest = _DET.sub("", rest)
    rest = _CUT.split(rest, maxsplit=1)[0].strip()
    return rest or goal.strip()


_TIMER = re.compile(r"\b(?:timer|countdown)\b", re.IGNORECASE)


def finish_when(goal: str) -> str | None:
    """The observable end state for a goal, or None for generic tasks."""
    g = goal.strip()
    if not g:
        return None
    if _TIMER.search(g):
        if re.search(r"\bpause\b", g, re.IGNORECASE):
            return "the Clock timer shows Resume (countdown stopped)"
        if re.search(r"\b(?:resume|unpause|continue)\b", g, re.IGNORECASE):
            return "the Clock timer shows Pause (counting down)"
        if re.search(r"\b(?:cancel|stop|kill|delete)\b", g, re.IGNORECASE):
            return "the timer is gone from Clock's Timers list"
    if _CART.search(g):
        m = re.search(r"\b(?:add|put)\b", g)
        x = _subject(g, m.end()) if m else g
        return (f"the page confirms {x} was added to the cart "
                "(e.g. 'Added to Cart' or the cart count went up)")
    if _DIRECTIONS.search(g):
        m = _DIRECTIONS.search(g)
        x = g[m.end():].strip() if m else g
        x = re.sub(r"^\s*(?:to|for)\s+", "", x, flags=re.IGNORECASE)
        return f"a route to {x} is showing"
    if _PLAY.search(g):
        m = _PLAY.search(g)
        x = _subject(g, m.end()) if m else g
        return (f"{x} is playing (a pause control is visible / "
                "player state is playing)")
    if _OPEN.search(g):
        x = g[_OPEN.search(g).end():].strip()
        x = re.sub(r"\s*(?:app|website|site|page)\s*[.!?]?\s*$", "",
                   x, flags=re.IGNORECASE)
        return f"{x or g} is frontmost"
    if _SEARCH.search(g):
        m = _SEARCH.search(g)
        x = _subject(g, m.end()) if m else g
        return f"a results page for {x} is showing"
    return None
