"""Deterministic follow-up rewrites."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlsplit

from .working import _COMMS, site_for_url


SEARCH_URLS: dict[str, str] = {
    "wikipedia.org": "https://en.wikipedia.org/w/index.php?search={q}",
    "youtube.com": "https://www.youtube.com/results?search_query={q}",
    "news.ycombinator.com": "https://hn.algolia.com/?q={q}",
    "docs.python.org": "https://docs.python.org/3/search.html?q={q}",
    "allrecipes.com": "https://www.allrecipes.com/search?q={q}",
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
_WEB_ENGINES = {"google.com", "bing.com", "duckduckgo.com"}
_PATH_SEARCH = {"maps.google.com", "spotify.com"}
_QUERY_KEYS = (
    "q", "query", "search", "search_query", "_nkw", "keywords", "term",
    "searchTerm", "find_desc", "st",
)
_QUERY_STOPWORDS = {
    "a", "an", "and", "at", "best", "for", "from", "good", "in", "long",
    "me", "my", "of", "on", "or", "the", "to", "top", "with",
}


def _query_from_url(url: str) -> str | None:
    try:
        parsed = urlsplit(str(url or ""))
        values = parse_qs(parsed.query)
    except ValueError:
        return None
    for key in _QUERY_KEYS:
        found = values.get(key)
        if found and found[0].strip():
            return found[0].strip()
    match = re.search(r"/(?:search|find)/([^/?#]+)", parsed.path,
                      re.IGNORECASE)
    return unquote(match.group(1)).replace("+", " ").strip() if match else None


def _search_details(turn) -> tuple[str, str | None, str] | None:
    if not turn or not turn.ok:
        return None
    args = turn.args or {}
    query = str(args.get("query") or "").strip()
    urls = [str(args.get("url") or ""), str(turn.url or "")]
    urls.extend(re.findall(r"https?://\S+", str(turn.resolved or "")))
    site = None
    for url in urls:
        if not url:
            continue
        parsed_query = _query_from_url(url)
        if parsed_query and not query:
            query = parsed_query
        if parsed_query and not site:
            site = site_for_url(url)
    mode = "play" if turn.skill == "play_music" else \
        ("site" if site else "search")
    if not query:
        match = re.search(
            r"\bsearch(?:\s+[\w.-]+)?\s+for\s+(.+)$",
            str(turn.resolved or ""), re.IGNORECASE)
        if match:
            query = match.group(1).strip()
        elif turn.skill == "play_music":
            match = re.search(r"\bplay(?:\s+some)?\s+(.+)$",
                              str(turn.resolved or ""), re.IGNORECASE)
            if match:
                query = match.group(1).strip()
    if not query or turn.skill not in {
            "web_search", "open_url", "play_music", "planner"}:
        return None
    return query, site, mode


def _search_url(site: str, query: str) -> str | None:
    template = SEARCH_URLS.get(site)
    if template is None:
        return None
    encoded = quote(query, safe="") if site in _PATH_SEARCH \
        else quote_plus(query)
    return template.format(q=encoded)


def _render_search(text: str, turn, query: str, reason: str,
                   site: str | None = None):
    details = _search_details(turn)
    if details is None:
        return None
    _, prior_site, mode = details
    site = site or prior_site
    if mode == "play":
        return _resolution(text, f"play {query}", reason)
    if site:
        url = _search_url(site, query)
        if url:
            return _resolution(
                text, f"open {url}", reason,
                direct={"skill": "open_url", "args": {"url": url}})
        return _resolution(text, f"search {site} for {query}", reason)
    return _resolution(text, f"search for {query}", reason)


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
    from .detect import SITE_SEARCH_RE, _ALIAS, _bare_search

    turn = wm.last(now)
    try_match = re.fullmatch(r"try\s+(.+?)[.!]?", text.strip(),
                             re.IGNORECASE)
    if try_match:
        name = try_match.group(1).casefold().strip()
        requested_site = _ALIAS.get(name, name if "." in name else None)
        details = _search_details(turn)
        if requested_site in SEARCH_URLS and details is not None and \
                details[1] != requested_site:
            return _render_search(
                text, turn, details[0], "site_search", requested_site)
        if not re.search(r"\binstead\b", name):
            return None
    match = SITE_SEARCH_RE.match(text.strip())
    if match:
        query = match.group(1).strip()
    elif turn and _bare_search(text.strip(), turn, ctx, now):
        query = text.strip()
    else:
        return None
    focus = wm.focus(now, ctx)
    site = focus.get("site") or site_for_url(focus.get("url"))
    current_url = str((ctx or {}).get("url") or focus.get("url") or "")
    if not site or "." not in site or not current_url:
        return None
    if site in _WEB_ENGINES:
        return None
    if site == "reddit.com":
        subreddit = re.search(
            r"/r/([^/]+)", current_url, re.IGNORECASE)
        if subreddit:
            url = ("https://www.reddit.com/r/" + subreddit.group(1) +
                   "/search/?q=" + quote_plus(query))
            return _resolution(
                text, f"open {url}", "site_search",
                direct={"skill": "open_url", "args": {"url": url}})
    template = SEARCH_URLS.get(site)
    if template is None:
        if not (turn and site_for_url(turn.url) == site):
            return None
        return _resolution(text, f"search {site} for {query}", "site_search")
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


def _number(value) -> str:
    try:
        number = float(value)
        return f"{number:g}"
    except (TypeError, ValueError):
        return str(value)


def _render_action(turn) -> str:
    skill, args = turn.skill, turn.args or {}
    if skill == "change_volume":
        delta = args.get("delta")
        try:
            amount = abs(float(delta))
            direction = "up" if float(delta) > 0 else "down"
            return f"turn the volume {direction} {_number(amount)}"
        except (TypeError, ValueError):
            return turn.resolved
    if skill in {"set_volume", "set_brightness"}:
        noun = "volume" if skill == "set_volume" else "brightness"
        value = args.get("level")
        return f"set the {noun} to {_number(value)}" if value is not None \
            else turn.resolved
    if skill == "take_screenshot":
        region = str(args.get("region") or "screen").casefold()
        region = region if region in {"window", "screen", "selection"} \
            else "screen"
        return f"take a screenshot of the {region}"
    if skill == "media_control":
        action = str(args.get("action") or "play").casefold()
        action = {"next": "skip to the next", "previous": "go to the previous",
                  "play_pause": "play or pause"}.get(action, action)
        return f"{action} the music"
    if skill == "dark_mode":
        return f"turn {'on' if args.get('on') else 'off'} dark mode"
    if skill == "mute":
        return "mute" if args.get("on") else "unmute"
    if skill == "open_url":
        return f"open {args.get('url')}" if args.get("url") else turn.resolved
    if skill == "open_app":
        return f"open {args.get('app')}" if args.get("app") else turn.resolved
    if skill == "web_search":
        return f"search for {args.get('query')}" if args.get("query") \
            else turn.resolved
    if skill == "window_layout":
        return f"snap the window {args.get('layout')}" \
            if args.get("layout") else turn.resolved
    if skill == "premiere_command":
        command = str(args.get("command") or "").replace("_", " ")
        preset = args.get("preset")
        return " ".join(part for part in ("premiere", command, str(preset or ""))
                        if part)
    return turn.resolved


def _undo_level(wm, turn, skill: str):
    level = None
    setting = "volume" if skill == "set_volume" else "brightness"
    setting_skills = ({"set_volume", "change_volume"} if setting == "volume"
                      else {"set_brightness"})
    for prior in wm.turns:
        if prior is turn:
            break
        if not prior.ok or prior.skill not in setting_skills:
            continue
        if prior.skill == skill:
            value = (prior.args or {}).get("level")
            if value is not None:
                level = value
        elif prior.skill == "change_volume":
            delta = (prior.args or {}).get("delta")
            reported = (prior.result or {}).get("level")
            if reported is not None:
                level = reported
            elif level is not None and delta is not None:
                try:
                    level = max(0, min(100, float(level) + float(delta)))
                except (TypeError, ValueError):
                    pass
            elif (prior.result or {}).get("level_before") is not None:
                before = prior.result["level_before"]
                try:
                    level = max(0, min(100, float(before) + float(delta)))
                except (TypeError, ValueError):
                    level = before
    return level


def _undo(text: str, turn, wm):
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
        value = _undo_level(wm, turn, skill)
        if value is None:
            value = turn.result.get("previous",
                                    turn.result.get("level_before"))
        if value is None:
            return None
        return (f"set the volume to {value}" if skill == "set_volume"
                else f"set brightness to {value}")
    if skill == "window_layout":
        return ""
    return None


_REPLAYABLE = {
    "change_volume", "set_volume", "set_brightness", "take_screenshot",
    "media_control", "dark_mode", "mute", "open_url", "open_app",
    "web_search", "window_layout", "premiere_command",
}


def _again(text: str, turn, catalog):
    same = re.fullmatch(
        r"same(?:\s+thing)?\s+but\s+(?:for|with)\s+([^\s.!?]+)[.!]?",
        text, re.IGNORECASE)
    if same:
        details = _search_details(turn)
        replacement = same.group(1)
        if details is None or len(replacement) < 4 or \
                not replacement.casefold().endswith("s"):
            return None
        words = re.findall(r"[^\W_]+", details[0], re.UNICODE)
        candidates = [
            word for word in words
            if len(word) >= 4 and word.casefold().endswith("s") and
            word.casefold() not in _QUERY_STOPWORDS
        ]
        if len(candidates) != 1:
            return None
        query = re.sub(
            rf"\b{re.escape(candidates[0])}\b", replacement, details[0],
            count=1, flags=re.IGNORECASE)
        return _render_search(text, turn, query, "again")
    if turn.skill in _COMMS or turn.skill == "type_text" or \
            "redacted" in turn.resolved.casefold():
        return Resolution(
            "ask", text, False, "again",
            ask="What should I send, and to whom?")
    if not turn.ok or not turn.skill or \
            str(turn.skill).casefold() in {"ask", "answer"}:
        return Resolution("ask", text, False, "again",
                          ask="What should I do again?")
    direct = None
    if turn.skill in _REPLAYABLE and catalog is not None and \
            catalog.risk(turn.skill) == "safe":
        spec = catalog.get(turn.skill) or {}
        required = [arg["name"] for arg in spec.get("args", [])
                    if arg.get("required")]
        if all(turn.args.get(key) not in (None, "") for key in required):
            direct = {"skill": turn.skill, "args": dict(turn.args)}
    return _resolution(text, _render_action(turn), "again", direct=direct)


_CAPITALIZED = re.compile(
    r"(?<![\w])([A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]*"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]*){0,2})")
_NOT_NAMES = {
    "a", "an", "and", "ask", "call", "calendar", "chrome", "close",
    "dinner", "documents", "doctor", "dr", "drive", "finder", "google",
    "i", "it", "mail", "make", "meeting", "message", "music", "notes",
    "open", "party", "physio", "remind", "reminder",
    "safari", "slack", "system", "text", "the", "this", "today", "tomorrow",
    "march", "october", "street", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
    "monday", "premiere", "premier", "spotify", "wikipedia", "youtube",
}


def _candidate_names(turn) -> list[str]:
    args = turn.args or {}
    found = []
    recipient = args.get("to")
    if turn.skill in _COMMS:
        if isinstance(recipient, str) and recipient.strip() and \
                recipient.casefold() not in _NOT_NAMES:
            return [recipient.strip()]
        return []
    if turn.skill in {"open_file", "open_folder", "find_file"}:
        return []
    explicit_re = re.compile(
        r"\b(?:with|to|call|ask|message|text|email|tell)\s+"
        r"(?:dr\.?\s+)?([A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]*"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]*){0,2})")
    for key in ("title", "body", "text"):
        value = args.get(key)
        if isinstance(value, str):
            if key != "title":
                value = re.sub(
                    r"\b(?:on|at|in)\s+[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)?",
                    " ", value)
            for match in explicit_re.finditer(value):
                name = match.group(1).strip(" .,'’")
                if name and name.split()[0].casefold() not in _NOT_NAMES:
                    found.append(name)
            if key != "title":
                for match in _CAPITALIZED.finditer(value):
                    name = match.group(1).strip(" .,'’")
                    if name.split()[0].casefold() not in _NOT_NAMES:
                        found.append(name)
    for value in (turn.utterance, turn.resolved):
        if not isinstance(value, str):
            continue
        value = re.split(r"\b(?:saying|that)\b", value, maxsplit=1,
                         flags=re.IGNORECASE)[0]
        for match in _CAPITALIZED.finditer(value):
            name = match.group(1).strip(" .,'’")
            if name.split()[0].casefold() not in _NOT_NAMES:
                found.append(name)
    unique = []
    seen = set()
    for name in found:
        folded = name.casefold()
        if folded not in seen:
            seen.add(folded)
            unique.append(name)
    return unique


def _person_candidate(text: str, wm, now: float):
    from .names import gender

    pronoun = re.search(r"\b(him|her|them)\b", text, re.IGNORECASE)
    if not pronoun:
        return None
    wanted = pronoun.group(1).casefold()
    for turn in reversed(wm.turns):
        if not 0 <= now - turn.t <= wm.ttl_s:
            continue
        candidates = _candidate_names(turn)
        if wanted == "them":
            matches = candidates
        else:
            gender_wanted = "male" if wanted == "him" else "female"
            matches = [name for name in candidates
                       if gender(name) in (None, gender_wanted)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def _person(text: str, wm, now: float):
    name = _person_candidate(text, wm, now)
    if not name:
        name = wm.focus(now, {}).get("contact")
    if not name:
        return Resolution("none", text, False, "person")
    rewritten, count = re.subn(
        r"\b(?:him|her|them)\b", name, text, count=1,
        flags=re.IGNORECASE)
    return _resolution(text, rewritten, "person") if count else None


def _file_referents(wm, now: float, folder_only: bool = False):
    results = []
    for turn in reversed(wm.turns):
        if not 0 <= now - turn.t <= wm.ttl_s or not turn.ok:
            continue
        args = turn.args or {}
        path = None
        is_folder = False
        if turn.skill == "open_folder":
            path, is_folder = args.get("path"), True
        elif turn.skill == "new_folder":
            parent, name = args.get("parent"), args.get("name")
            path = (f"{str(parent).rstrip('/')}/{name}"
                    if parent and name else name or parent)
            is_folder = True
        elif turn.skill == "open_file":
            path = args.get("path")
        elif turn.skill == "find_file":
            path = " ".join(str(args.get(key) or "")
                            for key in ("query", "kind")).strip()
            is_folder = str(args.get("kind") or "").casefold() == "folder"
        elif turn.skill == "take_screenshot":
            region = str(args.get("region") or "screen").casefold()
            path = f"{region} screenshot"
        if path and (not folder_only or is_folder):
            results.append(str(path))
    return results


def _item(text: str, wm, ctx: dict, now: float):
    focus = wm.focus(now, ctx)
    app_action = re.search(
        r"\b(?:quit|close|hide|minimize|maximize|snap)\b|"
        r"\b(?:make|put)\s+(?:it|that|this)\s+(?:full\s*screen|maximize)\b",
        text, re.IGNORECASE)
    if app_action:
        app = str((ctx or {}).get("app") or "")
        if not app or app.casefold() == "muselet":
            app = str(focus.get("app") or "")
        if not app or app.casefold() == "muselet":
            return None
        return _resolution(
            text, re.sub(r"\b(?:it|that|this)\b", app, text, count=1,
                         flags=re.IGNORECASE), "item")
    if re.search(r"\bthere\b", text, re.IGNORECASE):
        for turn in reversed(wm.turns):
            if not 0 <= now - turn.t <= wm.ttl_s or not turn.ok or \
                    turn.skill not in {"create_event", "create_reminder"}:
                continue
            args = turn.args or {}
            destination = str(args.get("location") or "").strip()
            if not destination:
                title = str(args.get("title") or "")
                destination = re.split(
                    r"\s+(?:with|at|on)\s+", title, maxsplit=1,
                    flags=re.IGNORECASE)[0].strip()
            if destination:
                rewritten = re.sub(r"\bthere\b", destination, text,
                                   count=1, flags=re.IGNORECASE)
                return _resolution(text, rewritten, "item")
    created = []
    for prior in reversed(wm.turns):
        if not 0 <= now - prior.t <= wm.ttl_s or not prior.ok or \
                prior.skill not in {"new_note", "create_reminder",
                                    "create_event"}:
            continue
        title = str((prior.args or {}).get("title") or "").strip()
        if title:
            created.append((prior.skill, title))
    if created:
        if re.search(r"\b(?:add|put|write|append)\b.+\bto\s+"
                     r"(?:it|that|this)\b", text, re.IGNORECASE):
            selected = next(
                (row for row in created if row[0] == "new_note"),
                created[0])
        else:
            selected = created[0]
        target = selected[1]
        if selected[0] == "new_note" and re.search(
                r"\bto\s+(?:it|that|this)\b", text, re.IGNORECASE):
            target = f"the {target} note"
        rewritten = re.sub(r"\b(?:it|that|this)\b", target, text, count=1,
                           flags=re.IGNORECASE)
        if rewritten != text:
            return _resolution(text, rewritten, "item")
    folder_only = bool(re.search(r"\bfolder\b", text, re.IGNORECASE))
    refs = _file_referents(wm, now, folder_only=folder_only)
    if not refs:
        refs = _file_referents(wm, now)
    if not refs:
        return None
    if folder_only and len(refs) > 1 and not re.search(
            r"\bin\s+there\b", text, re.IGNORECASE):
        names = [value.rstrip("/").split("/")[-1] for value in refs[:2]]
        return Resolution(
            "ask", text, False, "item",
            ask=f"Which folder should I use: {names[0]} or {names[1]}?")
    target = refs[0]
    if re.search(r"\bin\s+there\b", text, re.IGNORECASE):
        rewritten = re.sub(r"\bthere\b", target, text, count=1,
                           flags=re.IGNORECASE)
    else:
        rewritten = re.sub(r"\b(?:it|that|this)\b", target, text, count=1,
                           flags=re.IGNORECASE)
    return _resolution(text, rewritten, "item")


_DAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow"
_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def _words_number(value: str) -> int | None:
    value = value.casefold().strip()
    if value.isdigit():
        return int(value)
    words = re.findall(r"[a-z]+", value)
    if not words or any(word not in _ONES and word not in _TENS
                        for word in words):
        return None
    return sum(_ONES.get(word, _TENS.get(word, 0)) for word in words)


def _clock(value: str) -> tuple[str, str | None] | None:
    value = value.strip().casefold()
    period_match = re.search(r"\b([ap])\.?m\.?$", value)
    period = f"{period_match.group(1)}m" if period_match else None
    if period_match:
        value = value[:period_match.start()].strip()
    match = re.fullmatch(r"(\d{1,2})(?:[:.\s](\d{2}))?", value)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
    else:
        words = re.findall(r"[a-z]+", value)
        if not words:
            return None
        hour = _words_number(words[0])
        minute = _words_number(" ".join(words[1:])) if len(words) > 1 else 0
    if hour is None or minute is None or not 0 <= minute < 60:
        return None
    return (f"{hour}:{minute:02d}" if minute else str(hour), period)


def _change_value(text: str, turn):
    if not turn.ok:
        return None
    match = re.search(r"\bmake\s+it\s+(.+?)(?:\s+instead)?[.!]?$",
                      text, re.IGNORECASE)
    if not match:
        match = re.fullmatch(
            r"(?:and\s+)?(.+?)(?:\s+not\s+.+?)?(?:\s+instead)?[.!]?",
            text, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    prior = str(turn.resolved or "")
    day = re.fullmatch(_DAYS, value, re.IGNORECASE)
    if day:
        rewritten, count = re.subn(
            rf"\b(?:{_DAYS})\b", value, prior, count=1,
            flags=re.IGNORECASE)
        if not count:
            rewritten = f"{prior.rstrip()} on {value}"
        return _resolution(text, rewritten, "refinement")
    is_timer = turn.skill == "start_timer" or (
        turn.skill == "planner" and
        re.search(r"\btimer\b", prior, re.IGNORECASE))
    number = _words_number(value)
    if is_timer and number is not None:
        rewritten, count = re.subn(
            r"\b(?:\d+|(?:zero|one|two|three|four|five|six|seven|eight|nine|"
            r"ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
            r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
            r"eighty|ninety)(?:[-\s]+(?:one|two|three|four|five|six|seven|"
            r"eight|nine))?)\s+(?=(?:minute|hour|second)s?\b)",
            f"{number} ", prior, count=1, flags=re.IGNORECASE)
        return _resolution(text, rewritten, "refinement") if count else None
    clock = _clock(value)
    if clock:
        changed = False

        def replace_time(found):
            nonlocal changed
            if changed or _clock(" ".join(
                    part for part in (found.group(2), found.group(3))
                    if part)) is None:
                return found.group(0)
            old_period = found.group(3)
            period = clock[1] or old_period
            changed = True
            return found.group(1) + clock[0] + (
                f" {period}" if period else "")
        rewritten = re.sub(
            r"(\bat\s+)(\d{1,2}(?::\d{2})?|[a-z]+(?:\s+[a-z]+)?)"
            r"(?:\s+([ap]\.?m\.?))?", replace_time, prior,
            flags=re.IGNORECASE)
        return _resolution(text, rewritten, "refinement") if changed else None
    return None


def _folded_text(value: str) -> tuple[str, list[int]]:
    folded = []
    offsets = []
    for index, char in enumerate(value):
        for part in unicodedata.normalize(
                "NFKD", char.casefold()):
            if not unicodedata.combining(part):
                folded.append(part)
                offsets.append(index)
    return "".join(folded), offsets


def _replace_folded(text: str, old: str, new: str) -> str | None:
    needle, _ = _folded_text(old)
    haystack, offsets = _folded_text(text)
    if not needle:
        return None
    index = haystack.find(needle)
    while index >= 0:
        end = index + len(needle)
        start_char, end_char = offsets[index], offsets[end - 1] + 1
        if (start_char == 0 or not text[start_char - 1].isalnum()) and \
                (end_char == len(text) or not text[end_char].isalnum()):
            return text[:start_char] + new + text[end_char:]
        index = haystack.find(needle, index + 1)
    return None


def _distance_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 5 or abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    row = list(range(len(left) + 1))
    for index, char in enumerate(right, 1):
        next_row = [index]
        for offset, other in enumerate(left, 1):
            next_row.append(min(
                next_row[-1] + 1, row[offset] + 1,
                row[offset - 1] + (char != other)))
        row = next_row
    return row[-1] <= 1


def _refinement(text: str, turn):
    skill = turn.skill
    if not turn.ok:
        return None
    details = _search_details(turn)
    search = re.fullmatch(
        r"(?:just|only)(?:\s+(?:for|from|the|in|on))*\s+(.+)|"
        r"something\s+(?:more\s+|less\s+)?(.+)",
        text, re.IGNORECASE)
    if search and details:
        constraint = next(group for group in search.groups() if group)
        query = (f"{constraint} {details[0]}" if search.group(2)
                 else f"{details[0]} {constraint}")
        return _render_search(text, turn, query, "refinement")
    changed = _change_value(text, turn)
    if changed:
        return changed
    if skill == "window_layout":
        direction = re.search(
            r"\b(left|right|top|bottom|full\s*screen)\b", text,
            re.IGNORECASE)
        if direction:
            prior = str(turn.resolved or _render_action(turn))
            rewritten, count = re.subn(
                r"\b(?:left|right|top|bottom|full\s*screen|full)\b",
                direction.group(1), prior, count=1, flags=re.IGNORECASE)
            return _resolution(
                text, rewritten if count else
                f"{prior.rstrip()} {direction.group(1)}", "refinement")
    normalized = text.casefold()
    maximum = bool(re.search(r"\bcrank\s+it\s+(?:all\s+the\s+way\s+)?up\b",
                             normalized))
    too = re.search(r"\btoo\s+(dim|dark|bright|loud|quiet)\b", normalized)
    if maximum:
        if skill in {"change_volume", "set_volume"}:
            return _resolution(
                text, "set the volume to 100", "refinement",
                direct={"skill": "set_volume", "args": {"level": 100}})
        if skill == "set_brightness":
            return _resolution(
                text, "set the brightness to 100", "refinement",
                direct={"skill": "set_brightness", "args": {"level": 100}})
    up = bool(re.search(r"\b(?:louder|brighter|higher|more|up)\b",
                        normalized))
    down = bool(re.search(r"\b(?:quieter|softer|dimmer|darker|lower|less|"
                          r"down)\b", normalized))
    if too:
        direction = {
            "dim": "up", "dark": "up", "bright": "down",
            "loud": "down", "quiet": "up",
        }[too.group(1)]
        up, down = direction == "up", direction == "down"
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


def _other_option(turn, wm, now):
    old = str((turn.args or {}).get("to") or "")
    if old:
        for prior in reversed(wm.turns):
            if prior is turn or not 0 <= now - prior.t <= wm.ttl_s:
                continue
            candidates = _candidate_names(prior)
            if len(candidates) == 2 and any(
                    value.casefold() == old.casefold()
                    for value in candidates):
                return next(value for value in candidates
                            if value.casefold() != old.casefold()), old
    selected = " ".join(str(v) for v in (turn.args or {}).values()
                        if isinstance(v, str))
    selected += " " + str(turn.resolved or "")
    for prior in reversed(wm.turns):
        if prior is turn or not 0 <= now - prior.t <= wm.ttl_s:
            continue
        for source in ((prior.args or {}).get("body"),
                       (prior.args or {}).get("title"),
                       prior.utterance):
            if not isinstance(source, str) or not re.search(
                    r"\s+(?:and|or)\s+", source, re.IGNORECASE):
                continue
            left, right = re.split(r"\s+(?:and|or)\s+", source, maxsplit=1,
                                   flags=re.IGNORECASE)
            left = re.sub(r"^(?:the|a|an)\s+", "", left.strip(),
                          flags=re.IGNORECASE)
            right = re.sub(r"^(?:the|a|an)\s+", "", right.strip(),
                           flags=re.IGNORECASE)
            selected_words = set(re.findall(r"[^\W_]+", selected.casefold()))
            left_words = [word for word in re.findall(
                r"[^\W_]+", left.casefold()) if word not in _QUERY_STOPWORDS]
            right_words = [word for word in re.findall(
                r"[^\W_]+", right.casefold()) if word not in _QUERY_STOPWORDS]
            left_matches = [word for word in left_words
                            if word in selected_words and
                            re.search(rf"\b{re.escape(word)}\b",
                                      turn.resolved, re.IGNORECASE)]
            right_matches = [word for word in right_words
                             if word in selected_words and
                             re.search(rf"\b{re.escape(word)}\b",
                                       turn.resolved, re.IGNORECASE)]
            if left_matches and not right_matches:
                return right, max(left_matches, key=len)
            if right_matches and not left_matches:
                return left, max(right_matches, key=len)
    return None


def _correction(text: str, turn, wm, now):
    if not turn.ok:
        return None
    if re.search(r"\bthe other one\b", text, re.IGNORECASE):
        option = _other_option(turn, wm, now)
        if not option:
            return None
        replacement, old = option
        if turn.skill in _COMMS:
            body = (turn.args or {}).get("body") or ""
            return _resolution(
                text, f"text {replacement} saying {body}".strip(),
                "correction")
        if old:
            resolved = re.sub(re.escape(str(old)), replacement,
                              turn.resolved, count=1, flags=re.IGNORECASE)
            return _resolution(text, resolved, "correction")
        return None

    replacement = old_override = None
    match = re.match(
        r"^(?:(?:no,?\s+)?actually,?\s+)?(?:sorry,?\s+)?"
        r"(?:no,?\s+)?i\s+(?:said|meant)\s+"
        r"(.+?)\s*[.!?]*$",
        text, re.IGNORECASE)
    if match:
        replacement = match.group(1).strip()
    if replacement is None:
        match = re.match(
            r"^(?:no,?\s+)?(.+?)\s*,?\s*not\s+(.+?)[.!?]*$",
            text, re.IGNORECASE)
        if match:
            replacement, old_override = match.group(1), match.group(2)
            replacement = re.sub(r"^not\s+", "", replacement,
                                 flags=re.IGNORECASE).strip()
    if replacement is None:
        match = re.match(r"^(?:no,?\s+)?the\s+(.+?)\s+one[.!?]*$",
                         text, re.IGNORECASE)
        if match:
            replacement = match.group(1).strip()
    if replacement is None:
        wrong = re.match(
            r"^wrong\s+folder,?\s+put\s+it\s+in\s+(.+?)\s*[.!?]*$",
            text, re.IGNORECASE)
        if wrong and turn.skill == "new_folder":
            args = turn.args or {}
            name = args.get("name") or "the folder"
            parent = str(args.get("parent") or "").rstrip("/").split("/")[-1]
            return _resolution(
                text, f"move the {name} folder from {parent} to "
                      f"{wrong.group(1).strip()}", "correction")
    if not replacement:
        return None
    key = {
        "open_app": "app", "quit_app": "app", "hide_app": "app",
        "open_url": "url", "web_search": "query",
        "open_file": "path", "open_folder": "path", "find_file": "path",
        "send_message": "to", "compose_email": "to", "draft_email": "to",
        "premiere_command": "preset",
    }.get(turn.skill)
    args = turn.args or {}
    old = old_override or (args.get(key) if key else None)
    if turn.skill in _COMMS and key == "to":
        body = args.get("body") or ""
        return _resolution(
            text, f"text {replacement} saying {body}".strip(), "correction")
    if old:
        if key == "preset":
            old_head = str(old).split()[0]
            new_head = re.sub(r"^(?:the|that)\s+|\s+(?:one|preset)$", "",
                              str(replacement).strip(), flags=re.IGNORECASE)
            resolved = _replace_folded(turn.resolved, old_head, new_head)
            count = resolved is not None
        else:
            resolved = _replace_folded(turn.resolved, str(old), replacement)
            count = resolved is not None
            if not count:
                old_word = re.findall(r"[^\W_]+", str(old), re.UNICODE)
                if old_word:
                    target, _ = _folded_text(old_word[0])
                    for word in re.finditer(r"[^\W_]+", turn.resolved,
                                            re.UNICODE):
                        candidate, _ = _folded_text(word.group())
                        if candidate == target or (
                                min(len(candidate), len(target)) >= 4 and
                                (candidate.startswith(target) or
                                 target.startswith(candidate))) or \
                                _distance_one(candidate, target):
                            resolved = (
                                turn.resolved[:word.start()] + replacement +
                                turn.resolved[word.end():])
                            count = 1
                            break
        if count:
            return _resolution(text, resolved, "correction")
    if turn.skill == "open_app":
        return _resolution(text, f"open {replacement}", "correction")
    return None


def apply(text: str, reason: str, wm, ctx: dict, now: float,
          catalog=None) -> Resolution | None:
    turn = wm.last(now)
    focus = wm.focus(now, ctx)
    if reason == "site_search":
        return _site_search(text, wm, ctx, now)
    if turn is None:
        return None
    if reason == "again":
        return _again(text, turn, catalog)
    if reason == "undo":
        rewritten = _undo(text, turn, wm)
        if rewritten in {None, ""}:
            previous = next((
                prior for prior in reversed(wm.turns)
                if prior is not turn and prior.ok and
                prior.skill == turn.skill and
                0 <= now - prior.t <= wm.ttl_s and prior.resolved
            ), None)
            if previous is not None:
                return _resolution(text, previous.resolved, "undo")
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
        return _person(text, wm, now)
    if reason == "pronoun":
        if re.search(r"\b(?:him|her|them)\b", text, re.IGNORECASE):
            return _person(text, wm, now)
        return _item(text, wm, ctx, now)
    if reason == "item":
        return _item(text, wm, ctx, now)
    if reason == "refinement":
        return _refinement(text, turn)
    if reason == "correction":
        return _correction(text, turn, wm, now)
    return None
