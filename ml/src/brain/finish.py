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
_TIMER_PAUSE = re.compile(r"\bpause\b", re.IGNORECASE)
_TIMER_RESUME = re.compile(r"\b(?:resume|unpause|continue)\b", re.IGNORECASE)
_TIMER_CANCEL = re.compile(
    r"\b(?:cancel|stop|kill|delete)\b", re.IGNORECASE)
_DURATION = re.compile(
    r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)",
    re.IGNORECASE)


def norm_words(text: str) -> str:
    """Accent/case-insensitive word text: NFKD, strip combining marks,
    Turkish dotless i handled, casefold."""
    import unicodedata
    t = unicodedata.normalize("NFKD", text.replace("I", "i").replace(
        "\u0130", "i"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.casefold().split())


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
APP_KINDS = {
    "start_timer": "timer_start", "create_reminder": "reminder",
    "new_note": "note", "compose_text": "note", "create_event": "event",
    "send_message": "message", "compose_email": "email",
    "draft_email": "email", "play_music": "play",
}
_PAUSE = re.compile(r"(?i)^pause\b")
_BUTTON = re.compile(
    r'^\s*[+~]?\s*#\d+\s+button\s+"([^"]*)"', re.MULTILINE)
_CART_DONE = re.compile(r"(?i)added to (?:your )?cart|cart subtotal|\b1 item")
_ROUTE = re.compile(r"(?i)\b(?:directions|route)\b")
_COUNTDOWN = re.compile(r'(?:(\d{1,2}):)?(\d{1,2}):(\d{2})')
_COUNTDOWN_EDITABLE = re.compile(
    r"^\s*[+~]?\s*#\d+\s+"
    r"(?:textfield|textarea|textview|combobox|searchfield|spinbutton|"
    r"incrementor)\b", re.IGNORECASE)
_COUNTDOWN_ELEMENT = re.compile(r"^\s*[+~]?\s*#\d+\s+\S+", re.IGNORECASE)
_KEYWORD_STOP = {
    "the", "and", "for", "with", "about", "note", "new", "write",
    "that", "this",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unquote_plus(str(text or "")).lower())


def _key_words(text: str) -> list[str]:
    return [word for word in _words(text)
            if len(word) >= 3 and word not in _KEYWORD_STOP][:6]


def _contains_words(text: str, words: list[str]) -> bool:
    return bool(words) and all(word in _words(text) for word in words)


def _app_headers(text: str) -> list[str]:
    return re.findall(r"(?m)^\s*app:\s*([^|]+)", text)


def _quoted_values(text: str) -> list[str]:
    values = []
    for line in text.splitlines():
        if re.match(r"^\s*[+~]?\s*#\d+\b", line):
            values.extend(re.findall(r'"([^"]*)"', line))
    return values


def _focused_ref(obs: dict, text: str) -> str | None:
    ref = obs.get("focused_ref")
    if ref is not None:
        return str(ref)
    matches = re.findall(r"(?m)^\s*app:.*?\bfocused:\s*#(\d+)", text)
    return matches[-1] if matches else None


def _latest_value(text: str, ref: str) -> str | None:
    matches = re.findall(
        rf'(?m)^[+~]?\s*#{re.escape(ref)}\b.*?\bvalue="([^"]*)"', text)
    return matches[-1] if matches else None


def _composer_value(obs: dict, text: str) -> str:
    ref = _focused_ref(obs, text)
    if ref is not None:
        value = _latest_value(text, ref)
        if value is not None:
            return value
    matches = re.findall(
        r'(?m)^[+~]?\s*#\d+\s+(?:textarea|textview|textfield)\b'
        r'.*?\bvalue="([^"]*)"', text, re.IGNORECASE)
    return matches[-1] if matches else ""


def _seconds(duration) -> float | None:
    if isinstance(duration, bool) or duration is None:
        return None
    if isinstance(duration, (int, float)):
        return float(duration)
    value = str(duration).strip().lower()
    if value.isdigit():
        return float(value)
    matches = list(_DURATION.finditer(value))
    if not matches or re.sub(_DURATION, "", value).strip(" ,and") != "":
        return None
    seconds = 0.0
    for match in matches:
        amount = float(match.group(1))
        unit = match.group(2)
        if unit.startswith(("hour", "hr")):
            seconds += amount * 3600
        elif unit.startswith(("minute", "min")):
            seconds += amount * 60
        else:
            seconds += amount
    return seconds


def progress_kind(
        goal: str, agentic: dict | None = None) -> tuple[str, str, dict] | None:
    """Return the observable progress criterion for a goal or app skill."""
    clean_goal = str(goal or "").split("\nUser answer:")[0]
    agentic = agentic or {}
    skill = agentic.get("skill")
    args = dict(agentic.get("args") or {})
    if skill in APP_KINDS:
        kind = APP_KINDS[skill]
        if kind in ("reminder", "event"):
            subject = str(args.get("title") or "")
        elif kind == "note":
            subject = str(args.get("topic") or args.get("title") or
                          args.get("body") or "")
        elif kind == "message":
            subject = str(args.get("body") or "")
        elif kind == "email":
            subject = str(args.get("body") or args.get("about") or "")
        elif kind == "play":
            subject = str(args.get("query") or "")
        else:
            subject = ""
        return kind, subject, args
    if "timer" in clean_goal.lower():
        if (_TIMER_PAUSE.search(clean_goal) or
                _TIMER_RESUME.search(clean_goal) or
                _TIMER_CANCEL.search(clean_goal)):
            return "timer", "", {}
        durations = [match.group(0)
                     for match in _DURATION.finditer(clean_goal)]
        args = {"duration": " ".join(durations)} if durations else {}
        return "timer_start", "", args
    if "cart" in clean_goal.lower() or "basket" in clean_goal.lower():
        return "cart", "", {}
    crit = criterion(clean_goal)
    if crit and crit[0] == "play":
        return "play", crit[1], {}
    match = _DIRECTIONS.search(clean_goal)
    if match:
        criterion_value = criterion(clean_goal)
        return "directions", criterion_value[1] if criterion_value else "", {}
    return None


def evidence(kind: str, subject: str = "", obs: dict | str | None = None,
             script_stdout: str = "", ocr: str = "", url: str = "", *,
             goal: str = "", args: dict | None = None,
             baseline: int | None = None, confirmed: bool = False,
             progress: bool = False) -> bool:
    """Is the end state of `kind` visible? play: a Pause button in the AX
    tree or a script reported "playing"; search: the window title or URL
    contains the subject; cart: a cart confirmation in AX/OCR text;
    directions: "Directions"/"Route" in the title or observation."""
    if isinstance(obs, str):
        obs = {"text": obs}
    obs = obs or {}
    text = str(obs.get("text") or "")
    title = str(obs.get("window") or "")
    args = args or {}
    if kind == "play":
        labels = [str(e.get("label") or "") for e in obs.get("elements") or []
                  if str(e.get("role") or "").lower() == "button"]
        labels += _BUTTON.findall(text)
        # a bare "Pause" label on the wrong page (a Google results embed)
        # is not proof the named media is playing
        if "youtube" in goal.lower():
            where = norm_words(str(obs.get("window") or "") + " " +
                               str(obs.get("url") or ""))
            if "youtube" not in where:
                return False
        if "spotify" in goal.lower():
            st = norm_words(str(script_stdout or ""))
            return "playing" in st and (not subject or
                                        norm_words(subject) in st)
        page_url = str(obs.get("url") or url or "")
        watch_url = bool(re.search(
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=",
            page_url, re.IGNORECASE))
        if not title:
            match = re.search(r'\bwindow:\s*"([^"]*)"', text)
            title = match.group(1) if match else ""
        title = re.sub(
            r"\s+-\s+(?:Google Chrome|Chrome|Safari|Firefox|"
            r"Microsoft Edge|Edge|Brave|Arc|Zen|Opera)\s*$",
            "", title.strip(), flags=re.IGNORECASE)
        normalized_title = " ".join(title.casefold().split())
        search_title = normalized_title == " ".join(
            f"{subject} - YouTube".casefold().split()) or (
                normalized_title.endswith(" - youtube") and not watch_url)
        return any(_PAUSE.match(label.strip()) for label in labels) or \
            "playing" in str(script_stdout or "").lower() or \
            watch_url and not search_title
    if kind == "timer":
        return _timer_evidence(goal, text)
    if kind == "timer_start":
        if not re.search(
                r'(?im)^\s*[+~]?\s*#\d+\s+button\s+"Pause"', text):
            return False
        countdowns = []
        for line in text.splitlines():
            if (not _COUNTDOWN_ELEMENT.match(line) or
                    _COUNTDOWN_EDITABLE.match(line)):
                continue
            for value in _quoted_values(line):
                for match in _COUNTDOWN.finditer(value):
                    hours, minutes, seconds = match.groups()
                    total = (int(hours or 0) * 3600 +
                             int(minutes) * 60 + int(seconds))
                    countdowns.append(total)
        if not countdowns:
            return False
        requested = _seconds(args.get("duration"))
        if requested is None:
            return True
        tolerance = max(requested * 0.1, 2)
        return any(abs(value - requested) <= tolerance
                   for value in countdowns)
    if kind == "reminder":
        headers = _app_headers(text)
        if headers and headers[-1].strip().casefold() != "reminders":
            return False
        wanted = _words(subject)
        if not wanted:
            return False
        for line in text.splitlines():
            if re.match(r'^\s*[+~]?\s*#\d+\s+(?:row|checkbox|cell)\b',
                        line, re.IGNORECASE):
                if any(_contains_words(value, wanted)
                       for value in _quoted_values(line)):
                    return True
        return False
    if kind == "event":
        headers = _app_headers(text)
        if headers and headers[-1].strip().casefold() != "calendar":
            return False
        wanted = _words(subject)
        return any(_contains_words(value, wanted)
                   for value in _quoted_values(text))
    if kind == "note":
        wanted = _key_words(subject)
        if not wanted:
            return False
        value = _composer_value(obs, text)
        return _contains_words(value, wanted)
    if kind == "message":
        if not confirmed:
            return False
        value = _composer_value(obs, text)
        return _contains_words(value, _key_words(subject))
    if kind == "email":
        value = _composer_value(obs, text)
        wanted = _key_words(subject)
        return bool(value.strip()) if not wanted else _contains_words(
            value, wanted)
    if kind == "cart" and progress:
        current = cart_count(text)
        if current is None:
            return False
        return current > baseline if baseline is not None else current >= 1
    if kind == "directions" and progress:
        return bool((_ROUTE.search(title) or _ROUTE.search(text)) and
                    re.search(r"\b\d+\s*min\b", text, re.IGNORECASE))
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
    return not progress

_LIVE_ROW = re.compile(r'button "(?:Resume|Pause)"', re.IGNORECASE)
_CART_COUNT = re.compile(r"(\d+)\s+items?\s+in\s+cart", re.IGNORECASE)


def _timer_evidence(goal: str, obs_text: str) -> bool:
    """Clock Timers tab state proves the pause/resume/cancel happened."""
    has_resume = bool(re.search(r'button "Resume"', obs_text))
    has_pause = bool(re.search(r'button "Pause"', obs_text))
    if _TIMER_PAUSE.search(goal):
        return has_resume
    if _TIMER_RESUME.search(goal):
        return has_pause
    if _TIMER_CANCEL.search(goal):
        return not (has_resume or has_pause)
    return False


def cart_count(obs_text: str) -> int | None:
    matches = _CART_COUNT.findall(obs_text)
    return int(matches[-1]) if matches else None


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
