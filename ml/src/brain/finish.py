"""Rule-based end-state criterion for planner tasks (no model call)."""

from __future__ import annotations

import re
from datetime import datetime
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

_LIVE_ROW = re.compile(r'button "(?:Resume|Pause)"', re.IGNORECASE)
_CART_COUNT = re.compile(r"(\d+)\s+items?\s+in\s+cart", re.IGNORECASE)


def _timer_evidence(goal: str, obs_text: str) -> bool:
    """Clock Timers tab state proves the pause/resume/cancel happened."""
    has_resume = bool(re.search(r'button "Resume"', obs_text))
    has_pause = bool(re.search(r'button "Pause"', obs_text))
    if re.search(r"\bpause\b", goal, re.IGNORECASE):
        return has_resume
    if re.search(r"\b(?:resume|unpause|continue)\b", goal, re.IGNORECASE):
        return has_pause
    if re.search(r"\b(?:cancel|stop|kill|delete)\b", goal, re.IGNORECASE):
        return not (has_resume or has_pause)
    return False


def cart_count(obs_text: str) -> int | None:
    m = _CART_COUNT.search(obs_text)
    return int(m.group(1)) if m else None


def progress_evidence(goal: str, obs_text: str, baseline: int | None = None) -> bool:
    """Programmatic done-check: goal reached per the post-action obs text."""
    g = goal.lower()
    if "timer" in g:
        return _timer_evidence(goal, obs_text)
    if "cart" in g or "basket" in g:
        cur = cart_count(obs_text)
        if cur is None:
            return False
        return cur > baseline if baseline is not None else cur >= 1
    return False


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
