"""Rule-based end-state criterion for planner tasks (no model call)."""

from __future__ import annotations

import re
from datetime import datetime

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


def finish_when(goal: str) -> str | None:
    """The observable end state for a goal, or None for generic tasks."""
    g = goal.strip()
    if not g:
        return None
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


def app_finish(skill: str, args: dict) -> str | None:
    """Observable end state for an app skill."""
    args = {
        key: value for key, value in args.items()
        if key not in {"ms", "_raw", "missing", "confirmed"}
        and value not in (None, "")
    }
    if skill == "start_timer":
        duration = args.get("duration")
        if duration is None:
            return "Clock shows a running countdown"
        if isinstance(duration, str) and duration.strip().isdigit():
            duration = int(duration.strip())
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            seconds = int(duration)
            if seconds >= 60 and seconds % 60 == 0:
                duration = f"{seconds // 60} minutes"
            else:
                duration = f"{seconds} seconds"
        return f"Clock shows a running countdown of about {duration}"
    if skill == "create_event":
        title = args.get("title", "")
        start = args.get("start")
        if start:
            try:
                value = str(start)
                date = datetime.fromisoformat(value.replace("Z", "+00:00"))
                rendered = f"{date.strftime('%A %b')} {date.day}"
                if "T" in value or " " in value:
                    rendered += " at " + date.strftime("%I:%M %p").lstrip("0")
            except (TypeError, ValueError):
                rendered = str(start)
            return f"the event {title} appears in Calendar on {rendered}"
        return f"the event {title} appears in Calendar"
    if skill == "create_reminder":
        return f"the reminder {args.get('title', '')} appears in Reminders"
    if skill in ("new_note", "compose_text"):
        topic = args.get("topic") or args.get("title") or args.get("body", "")
        excerpt = " ".join(str(topic).split()[:8])
        return f"a new note containing {excerpt} is open"
    if skill == "send_message":
        return (f"the message to {args.get('to', '')} is typed in Messages "
                "and you have asked to confirm sending")
    if skill in ("compose_email", "draft_email"):
        return "a draft reply with the text is visible in the reply box (not sent)"
    if skill == "play_music":
        return finish_when(f"play {args.get('query', '')}")
    if skill == "todays_agenda":
        return "today's events are read back from Calendar"
    return None
