"""Rule-based end-state criterion for planner tasks (no model call)."""

from __future__ import annotations

import re
from urllib.parse import unquote_plus

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


def criterion(goal: str) -> tuple[str, str, str] | None:
    """(kind, subject, text) for a goal's observable end state, or None.
    kind is cart | directions | play | open | search."""
    g = goal.strip()
    if not g:
        return None
    if _TIMER.search(g):
        if re.search(r"\bpause\b", g, re.IGNORECASE):
            return ("timer", "", "the Clock timer shows Resume (countdown stopped)")
        if re.search(r"\b(?:resume|unpause|continue)\b", g, re.IGNORECASE):
            return ("timer", "", "the Clock timer shows Pause (counting down)")
        if re.search(r"\b(?:cancel|stop|kill|delete)\b", g, re.IGNORECASE):
            return ("timer", "", "the timer is gone from Clock's Timers list")
    if _CART.search(g):
        m = re.search(r"\b(?:add|put)\b", g)
        x = _subject(g, m.end()) if m else g
        return ("cart", x, f"the page confirms {x} was added to the cart "
                "(e.g. 'Added to Cart' or the cart count went up)")
    if _DIRECTIONS.search(g):
        m = _DIRECTIONS.search(g)
        x = g[m.end():].strip() if m else g
        x = re.sub(r"^\s*(?:to|for)\s+", "", x, flags=re.IGNORECASE)
        return ("directions", x, f"a route to {x} is showing")
    if _PLAY.search(g):
        m = _PLAY.search(g)
        x = _subject(g, m.end()) if m else g
        return ("play", x, f"{x} is playing (a pause control is visible / "
                "player state is playing)")
    if _OPEN.search(g):
        x = g[_OPEN.search(g).end():].strip()
        x = re.sub(r"\s*(?:app|website|site|page)\s*[.!?]?\s*$", "",
                   x, flags=re.IGNORECASE)
        return ("open", x or g, f"{x or g} is frontmost")
    if _SEARCH.search(g):
        m = _SEARCH.search(g)
        x = _subject(g, m.end()) if m else g
        return ("search", x, f"a results page for {x} is showing")
    return None


def finish_when(goal: str) -> str | None:
    """The observable end state for a goal, or None for generic tasks."""
    c = criterion(goal)
    return c[2] if c else None


EVIDENCE_KINDS = ("play", "cart", "search", "directions")
_PAUSE = re.compile(r"(?i)^pause\b")
_BUTTON = re.compile(r'^\s*#\d+\s+button\s+"([^"]*)"', re.MULTILINE)
_CART_DONE = re.compile(r"(?i)added to (?:your )?cart|cart subtotal|\b1 item")
_ROUTE = re.compile(r"(?i)\b(?:directions|route)\b")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unquote_plus(str(text or "")).lower())


def evidence(kind: str, subject: str, obs: dict | None = None,
             script_stdout: str = "", ocr: str = "", url: str = "") -> bool:
    """Is the end state of `kind` visible? play: a Pause button in the AX
    tree or a script reported "playing"; search: the window title or URL
    contains the subject; cart: a cart confirmation in AX/OCR text;
    directions: "Directions"/"Route" in the title or observation."""
    obs = obs or {}
    text = str(obs.get("text") or "")
    title = str(obs.get("window") or "")
    if kind == "play":
        labels = [str(e.get("label") or "") for e in obs.get("elements") or []
                  if str(e.get("role") or "").lower() == "button"]
        labels += _BUTTON.findall(text)
        return any(_PAUSE.match(label.strip()) for label in labels) or \
            "playing" in str(script_stdout or "").lower()
    if kind == "search":
        want = [w for w in _words(subject) if w not in ("some", "a", "the")]
        if not want:
            return False
        page_url = str(obs.get("url") or url or "")
        return any(all(w in _words(hay) for w in want)
                   for hay in (title, page_url) if hay)
    if kind == "cart":
        return bool(_CART_DONE.search(text) or _CART_DONE.search(ocr or ""))
    if kind == "directions":
        return bool(_ROUTE.search(title) or _ROUTE.search(text))
    return True
