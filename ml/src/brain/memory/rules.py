"""Deterministic follow-up rewrites."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote, quote_plus

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
    from .detect import SITE_SEARCH_RE, _bare_search

    match = SITE_SEARCH_RE.match(text.strip())
    turn = wm.last(now)
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


def _refinement(text: str, turn):
    skill = turn.skill
    if not turn.ok:
        return None
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
    big = bool(re.search(r"\b(?:way|a\s+lot|lots|much|tons?)\b", normalized))
    step, amount = (30, "a lot") if big else (10, "a bit")
    if skill in {"change_volume", "set_volume"}:
        last_delta = turn.args.get("delta")
        sign = -1 if down else 1
        if not up and not down and last_delta is not None:
            try:
                sign = 1 if float(last_delta) >= 0 else -1
            except (TypeError, ValueError):
                pass
        direction = "down" if sign < 0 else "up"
        direct = {"skill": "change_volume", "args": {"delta": step * sign}}
        return _resolution(text, f"turn the volume {direction} {amount}",
                           "refinement", direct=direct)
    if skill == "set_brightness":
        sign = -1 if down else 1
        direction = "down" if sign < 0 else "up"
        return _resolution(
            text, f"turn brightness {direction} {amount}", "refinement",
            direct={"skill": "set_brightness", "args": {"delta": step * sign}})
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
                            if value.casefold() != old.casefold())
    selected = " ".join(str(v) for v in (turn.args or {}).values()
                        if isinstance(v, str))
    selected += " " + str(turn.resolved or "")
    for prior in reversed(wm.turns):
        if prior is turn or not 0 <= now - prior.t <= wm.ttl_s:
            continue
        for source in ((prior.args or {}).get("body"),
                       (prior.args or {}).get("title"),
                       prior.utterance):
            if not isinstance(source, str) or not re.search(r"\s+or\s+", source,
                                                             re.IGNORECASE):
                continue
            left, right = re.split(r"\s+or\s+", source, maxsplit=1,
                                   flags=re.IGNORECASE)
            left = re.sub(r"^(?:the|a|an)\s+", "", left.strip(),
                          flags=re.IGNORECASE)
            right = re.sub(r"^(?:the|a|an)\s+", "", right.strip(),
                           flags=re.IGNORECASE)
            if left and right and left.casefold() in selected.casefold():
                return right
            if left and right and right.casefold() in selected.casefold():
                return left
    return None


def _correction(text: str, turn, wm, now):
    if not turn.ok:
        return None
    if re.search(r"\bthe other one\b", text, re.IGNORECASE):
        replacement = _other_option(turn, wm, now)
        if not replacement:
            return None
        if turn.skill in _COMMS:
            body = (turn.args or {}).get("body") or ""
            return _resolution(
                text, f"text {replacement} saying {body}".strip(),
                "correction")
        old = (turn.args or {}).get("to")
        if old:
            resolved = re.sub(re.escape(str(old)), replacement,
                              turn.resolved, count=1, flags=re.IGNORECASE)
            return _resolution(text, resolved, "correction")
        return None

    replacement = old_override = None
    match = re.match(
        r"^(?:(?:no,?\s+)?actually,?\s+)?(?:no,?\s+)?i meant\s+"
        r"(.+?)\s*[.!?]*$",
        text, re.IGNORECASE)
    if match:
        replacement = match.group(1).strip()
    if replacement is None:
        match = re.match(
            r"^(?:no,?\s+)?(.+?)\s*,\s*not\s+(.+?)[.!?]*$",
            text, re.IGNORECASE)
        if match:
            replacement, old_override = match.group(1), match.group(2)
            replacement = re.sub(r"^not\s+", "", replacement,
                                 flags=re.IGNORECASE).strip()
    if replacement is None:
        match = re.match(r"^sorry,?\s+i said\s+(.+?)[.!?]*$",
                         text, re.IGNORECASE)
        if match:
            replacement = match.group(1).strip()
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
            resolved, count = re.subn(
                re.escape(old_head), new_head, turn.resolved, count=1,
                flags=re.IGNORECASE)
        else:
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
    focus = wm.focus(now, ctx)
    if reason == "site_search":
        return _site_search(text, wm, ctx, now)
    if turn is None:
        return None
    if reason == "again":
        return _again(text, turn, catalog)
    if reason == "undo":
        rewritten = _undo(text, turn, wm)
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
