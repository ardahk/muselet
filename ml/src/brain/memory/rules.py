"""Deterministic follow-up rewrites."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote, quote_plus

from .working import _COMMS, site_for_url


SEARCH_URLS: dict[str, str] = {
    "wikipedia.org": "https://en.wikipedia.org/w/index.php?search={q}",
    "youtube.com": "https://www.youtube.com/results?search_query={q}",
    "amazon.com": "https://www.amazon.com/s?k={q}",
    "github.com": "https://github.com/search?q={q}",
    "reddit.com": "https://www.reddit.com/search/?q={q}",
    "maps.google.com": "https://www.google.com/maps/search/{q}",
    "google.com": "https://www.google.com/search?q={q}",
    "ebay.com": "https://www.ebay.com/sch/i.html?_nkw={q}",
    "etsy.com": "https://www.etsy.com/search?q={q}",
    "imdb.com": "https://www.imdb.com/find/?q={q}",
    "stackoverflow.com": "https://stackoverflow.com/search?q={q}",
    "x.com": "https://x.com/search?q={q}",
    "spotify.com": "https://open.spotify.com/search/{q}",
    "netflix.com": "https://www.netflix.com/search?q={q}",
    "linkedin.com": "https://www.linkedin.com/search/results/all/?keywords={q}",
    "yelp.com": "https://www.yelp.com/search?find_desc={q}",
    "duckduckgo.com": "https://duckduckgo.com/?q={q}",
    "bing.com": "https://www.bing.com/search?q={q}",
    "pypi.org": "https://pypi.org/search/?q={q}",
    "npmjs.com": "https://www.npmjs.com/search?q={q}",
    "walmart.com": "https://www.walmart.com/search?q={q}",
    "target.com": "https://www.target.com/s?searchTerm={q}",
    "bestbuy.com": "https://www.bestbuy.com/site/searchpage.jsp?st={q}",
    "goodreads.com": "https://www.goodreads.com/search?q={q}",
    "developer.mozilla.org": "https://developer.mozilla.org/en-US/search?q={q}",
    "twitch.tv": "https://www.twitch.tv/search?term={q}",
    "quizlet.com": "https://quizlet.com/search?query={q}",
}
_PATH_SEARCH = {"maps.google.com", "spotify.com"}


@dataclass
class Resolution:
    path: str
    text: str
    changed: bool
    reason: str | None
    ask: str | None = None
    direct: dict | None = None


def _resolution(text, new_text, reason, direct=None):
    changed = new_text.casefold() != text.casefold()
    return Resolution("rule", new_text, changed, reason, direct=direct)


def _site_search(text: str, wm, ctx: dict, now: float):
    from .detect import SITE_SEARCH_RE

    match = SITE_SEARCH_RE.match(text.strip())
    if not match:
        return None
    focus = wm.focus(now, ctx)
    site = focus.get("site") or site_for_url(focus.get("url"))
    template = SEARCH_URLS.get(site)
    if not template:
        return None
    query = match.group(1).strip()
    encoded = quote(query, safe="") if site in _PATH_SEARCH else quote_plus(query)
    url = template.format(q=encoded)
    return _resolution(
        text, f"open {url}", "site_search",
        direct={"skill": "open_url", "args": {"url": url}})


def _toggle_text(skill: str, args: dict) -> str | None:
    key = "on"
    if skill in {"dark_mode", "mute", "wifi", "bluetooth"} and key in args:
        noun = {"dark_mode": "dark mode", "mute": "mute",
                "wifi": "Wi-Fi", "bluetooth": "Bluetooth"}[skill]
        if skill == "mute":
            return "mute" if not bool(args[key]) else "unmute"
        verb = "turn on" if not bool(args[key]) else "turn off"
        return f"{verb} {noun}"
    return None


def _undo(text: str, turn):
    skill, args = turn.skill, turn.args
    if not turn.ok:
        return None
    if skill in {"dark_mode", "mute", "wifi", "bluetooth"}:
        return _toggle_text(skill, args)
    if skill == "change_volume":
        delta = args.get("delta")
        try:
            return f"turn the volume {'down' if float(delta) > 0 else 'up'} by {abs(float(delta)):g}"
        except (TypeError, ValueError):
            return None
    if skill in {"set_volume", "set_brightness"}:
        value = turn.result.get("previous", turn.result.get("level_before"))
        if value is None:
            return None
        return (f"set the volume to {value}" if skill == "set_volume"
                else f"set brightness to {value}")
    if skill == "window_layout":
        return ""
    return None


def _again(text: str, turn, catalog):
    if not turn.ok:
        return None
    if turn.skill in _COMMS or "redacted" in turn.resolved.casefold():
        return Resolution(
            "ask", text, False, "again",
            ask="What should I send, and to whom?")
    if not turn.resolved:
        return None
    direct = None
    if turn.skill == "planner":
        pass
    elif turn.skill and catalog is not None and catalog.risk(turn.skill) == "safe":
        spec = catalog.get(turn.skill) or {}
        required = [arg["name"] for arg in spec.get("args", [])
                    if arg.get("required")]
        if all(turn.args.get(key) not in (None, "") for key in required):
            direct = {"skill": turn.skill, "args": dict(turn.args)}
    return _resolution(text, turn.resolved, "again", direct=direct)


def _person(text: str, focus: dict):
    contact = focus.get("contact")
    if not contact:
        return None
    pattern = re.compile(
        r"\b(?:him|her|them)\b", re.IGNORECASE)
    rewritten, count = pattern.subn(str(contact), text, count=1)
    return _resolution(text, rewritten, "person") if count else None


def _item(text: str, focus: dict):
    item = focus.get("file") or focus.get("app")
    if not item:
        return None
    pattern = re.compile(
        r"\b(?:it|that|this|there)\b", re.IGNORECASE)
    rewritten, count = pattern.subn(str(item), text, count=1)
    return _resolution(text, rewritten, "item") if count else None


def _refinement(text: str, turn):
    skill = turn.skill
    if not turn.ok:
        return None
    normalized = text.casefold()
    up = bool(re.search(r"\b(?:louder|brighter|higher|more|up)\b",
                        normalized))
    down = bool(re.search(r"\b(?:quieter|softer|dimmer|darker|lower|less|"
                          r"down)\b", normalized))
    if skill in {"change_volume", "set_volume"}:
        last_delta = turn.args.get("delta")
        sign = -1 if down else 1
        if not up and not down and last_delta is not None:
            try:
                sign = 1 if float(last_delta) >= 0 else -1
            except (TypeError, ValueError):
                pass
        direction = "down" if sign < 0 else "up"
        direct = {"skill": "change_volume", "args": {"delta": 10 * sign}}
        return _resolution(text, f"turn the volume {direction} a bit",
                           "refinement", direct=direct)
    if skill == "set_brightness":
        sign = -1 if down else 1
        direction = "down" if sign < 0 else "up"
        return _resolution(
            text, f"turn brightness {direction} a bit", "refinement",
            direct={"skill": "set_brightness", "args": {"delta": 10 * sign}})
    return None


def _correction(text: str, turn):
    match = re.search(
        r"^(?:(?:actually,?\s+)?i meant|no,?\s+i meant)\s+"
        r"(.+?)\s*[.!?]*$",
        text, re.IGNORECASE)
    if not match:
        return None
    replacement = match.group(1).strip()
    if not replacement:
        return None
    key = {
        "open_app": "app", "quit_app": "app", "hide_app": "app",
        "open_url": "url", "web_search": "query",
        "open_file": "path", "open_folder": "path", "find_file": "path",
        "send_message": "to", "compose_email": "to", "draft_email": "to",
    }.get(turn.skill)
    old = turn.args.get(key) if key else None
    if old:
        resolved, count = re.subn(re.escape(str(old)), replacement,
                                  turn.resolved, count=1,
                                  flags=re.IGNORECASE)
        if count:
            return _resolution(text, resolved, "correction")
    if turn.skill == "open_app":
        return _resolution(text, f"open {replacement}", "correction")
    return None


def apply(text: str, reason: str, wm, ctx: dict, now: float,
          catalog=None) -> Resolution | None:
    turn = wm.last(now)
    if turn is None:
        return None
    focus = wm.focus(now, ctx)
    if reason == "site_search":
        return _site_search(text, wm, ctx, now)
    if reason == "again":
        return _again(text, turn, catalog)
    if reason == "undo":
        rewritten = _undo(text, turn)
        if rewritten == "":
            return Resolution("ask", text, False, "undo",
                              ask="I can't undo that. What should I do?")
        if rewritten is None:
            question = ("What level should I go back to?"
                        if turn.skill in {"set_volume", "set_brightness"}
                        else "I can't undo that. What should I do?")
            return Resolution("ask", text, False, "undo", ask=question)
        return _resolution(text, rewritten, "undo")
    if reason == "person":
        return _person(text, focus)
    if reason == "item":
        return _item(text, focus)
    if reason == "refinement":
        return _refinement(text, turn)
    if reason == "correction":
        return _correction(text, turn)
    return None
