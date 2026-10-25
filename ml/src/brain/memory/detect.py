"""Cheap follow-up detection. Regexes are compiled once at import."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .rules import SEARCH_URLS
from .working import BROWSERS, site_for_url


_FILLER = re.compile(
    r"^(?:(?:uh|um|hmm|ok(?:ay)?|so|oh|and|now|nah|eh|ugh|cool|well|"
    r"actually|wait|hey|never\s+mind)\b[,]?\s*)+",
    re.IGNORECASE)


def normalize_utterance(text: str) -> str:
    value = str(text or "").strip()
    previous = None
    while value and value != previous:
        previous = value
        value = _FILLER.sub("", value, count=1).lstrip(" ,")
    for wrong, right in (("serch", "search"), ("surch", "search"),
                         ("tex", "text"), ("agin", "again"),
                         ("agen", "again"), ("dew", "do")):
        value = re.sub(rf"\b{wrong}\b", right, value,
                       flags=re.IGNORECASE)
    value = re.sub(r"\bclothes(?=\s+(?:it|that|this)\b)", "close",
                   value, flags=re.IGNORECASE)
    return value


SITE_SEARCH_RE = re.compile(
    r"^(?:search(?:\s+for)?|look\s+(?:up|for)|"
    r"find(?:\s+me)?(?:\s+the\s+one\s+about)?|try)\s+"
    r"(.+?)(?:\s+instead)?[.!]?$",
    re.IGNORECASE)
_AGAIN = re.compile(
    r"^(?:again|do\s+(?:it|that)\s+again|one\s+more\s+time|"
    r"once\s+more|repeat(?:\s+that)?|same\s+again)[.!]?$",
    re.IGNORECASE)
_UNDO = re.compile(
    r"\b(?:undo(?:\s+that)?|put\s+it\s+back(?:\s+how\s+it\s+was)?|"
    r"go\s+back(?:\s+to\s+how\s+it\s+was)?|change\s+it\s+back|"
    r"revert(?:\s+that)?|back\s+to\s+how\s+it\s+was)\b",
    re.IGNORECASE)
_PERSON = re.compile(
    r"\b(?:him|her|them)\b",
    re.IGNORECASE)
_ITEM = re.compile(
    r"\b(?:quit|close|hide|minimize|maximize|snap)\b.*"
    r"\b(?:it|that|this)\b|"
    r"\b(?:make|put)\s+(?:it|that|this)\s+(?:full\s*screen|maximize)\b|"
    r"\b(?:open|show|move|rename|trash|delete|duplicate|share)\b.*"
    r"\b(?:it|that)\b|"
    r"\bin\s+there\b|\b(?:open|show|move|rename|trash|delete)\b.*"
    r"\bthere\b|\bopen\s+that\s+folder\b",
    re.IGNORECASE)
_CORRECTION = re.compile(
    r"^(?:actually,?\s+)?i meant\s+.+$|"
    r"^(?:no,?\s+)?[^,!.?]+\s*,?\s+not\s+[^,!.?]+[.!?]*$|"
    r"^(?:sorry,?\s+i said|wrong\s+\w+,\s+put\s+it\s+in)\b.*$|"
    r"\bno,?\s+(?:i meant\b|the other one\b)|\bnot that one\b|"
    r"\bthe other one\b",
    re.IGNORECASE)
_ORDINAL = re.compile(
    r"\b(?:the\s+)?(?:first|second|third|fourth|last)\s+one\b",
    re.IGNORECASE)
_PRONOUN = re.compile(
    r"\b(?:it|that|this|there|the same|him|her|them)\b",
    re.IGNORECASE)
_REFINEMENT = re.compile(
    r"^(?:bump\s+it\s+(?:up|down)|a\s+little\s+(?:more|less)|"
    r"too\s+(?:dim|dark|bright|loud|quiet)(?:\s+bump\s+it\s+up)?|"
    r"crank\s+it\s+(?:all\s+the\s+way\s+)?up|"
    r"(?:(?:and|now|ok(?:ay)?)\s+)?"
    r"(?:(?:make\s+it|turn\s+it|go|a\s+(?:little\s+|tiny\s+)?bit|"
    r"slightly|even|much|way|a\s+lot)\s+)*"
    r"(?:louder|quieter|softer|brighter|dimmer|darker|higher|lower|more|"
    r"less|up|down)(?:\s+(?:a\s+(?:little\s+|tiny\s+)?bit|a\s+lot|please|still|"
    r"again|more|less))*)[.!]?$",
    re.IGNORECASE)
_NONPRONOUN_THIS = re.compile(
    r"\bthis\s+(?:week|weekend|morning|afternoon|evening|month|year|time)\b",
    re.IGNORECASE)
_THAT_CONJUNCTION = re.compile(
    r"\b(?:remind\s+me|say|saying|tell\b(?:\s+\w+){0,5})\s+"
    r"(?P<that>that)\b",
    re.IGNORECASE)
_NATIVE_IDIOM = re.compile(
    r"\bturn it (?:up|down)\b|\bwhat time is it\b|"
    r"\bis it\b.+\?|\bweather\b|"
    r"\bit['’]s\b.+|"
    r"\b(?:make it )?(?:louder|quieter|brighter|dimmer)\b",
    re.IGNORECASE)
_ALIAS = {
    "google": "google.com", "youtube": "youtube.com",
    "wikipedia": "wikipedia.org", "amazon": "amazon.com",
    "hacker news": "news.ycombinator.com",
    "github": "github.com", "reddit": "reddit.com",
    "maps": "maps.google.com", "google maps": "maps.google.com",
    "ebay": "ebay.com", "etsy": "etsy.com", "imdb": "imdb.com",
    "stackoverflow": "stackoverflow.com",
    "stack overflow": "stackoverflow.com", "x": "x.com",
    "twitter": "x.com", "spotify": "spotify.com", "netflix": "netflix.com",
    "linkedin": "linkedin.com", "yelp": "yelp.com",
    "duckduckgo": "duckduckgo.com", "bing": "bing.com",
    "pypi": "pypi.org", "npm": "npmjs.com", "npmjs": "npmjs.com",
    "walmart": "walmart.com", "target": "target.com",
    "bestbuy": "bestbuy.com", "best buy": "bestbuy.com",
    "goodreads": "goodreads.com", "mdn": "developer.mozilla.org",
    "twitch": "twitch.tv", "quizlet": "quizlet.com",
}
_SITE_NAME = r"(?:google\s+maps|stack\s+overflow|hacker\s+news|best\s+buy|[a-z0-9.-]+)"
_SITE_NAMES = re.compile(
    rf"\b(?:on|from|using)\s+({_SITE_NAME})|"
    rf"\bsearch(?:\s+for)?\s+({_SITE_NAME})\s+for\b|"
    rf"\btry\s+({_SITE_NAME})\b",
    re.IGNORECASE)
_WEB_SEARCH = re.compile(
    r"\bsearch(?:\s+for)?\s+(?:the\s+)?(?:web|internet)\s+for\b",
    re.IGNORECASE)
_SELF_CONTAINED_RELATIVE = re.compile(
    r"\b(?:louder|quieter|softer|brighter|dimmer|darker|volume|brightness)\b",
    re.IGNORECASE)
_EXPLICIT_TARGET = re.compile(
    r"\b(?:in|on|with|using|via|from)\s+(?:the\s+)?(?:safari|(?:google\s+)?chrome|"
    r"zen|firefox|arc|edge|brave|opera|browser|google|youtube|bing|"
    r"duckduckgo|a\s+new\s+tab|new\s+tab)\b|"
    r"\b[a-z0-9-]+\.(?:com|org|net|io|dev|edu|gov|co|tv|ai|app|me|uk)\b",
    re.IGNORECASE)
_QUESTION = re.compile(
    r"^(?:(?:search(?:\s+for)?|look\s+(?:up|for)|find(?:\s+out)?|try|"
    r"tell\s+me|check)\s+)?(?:when|what|who|whom|whose|where|why|how|which|"
    r"is|are|was|were|does|do|did|can|could|should|will|would)\b",
    re.IGNORECASE)
_REFINEMENT_SKILLS = {
    "change_volume", "set_volume", "set_brightness", "window_layout",
}
_COMMAND_VERBS = {
    "add", "call", "change", "check", "close", "copy", "create", "cut",
    "delete", "draft", "duplicate", "email", "find", "hide", "launch",
    "lock", "make", "maximize", "minimize", "move", "mute", "note", "open",
    "paste", "play", "quit", "remind", "rename", "resize", "schedule",
    "search", "send", "set", "share", "show", "sleep", "snap", "start",
    "text", "trash", "turn", "type", "write",
}


def _names_other_site(text: str, site: str | None) -> bool:
    expected = site or ""
    for match in _SITE_NAMES.finditer(text):
        name = next((value for value in match.groups() if value), "")
        name = name.casefold().strip()
        host = _ALIAS.get(name, name if "." in name else None)
        if host and host not in {expected, expected.removeprefix("www.")}:
            return True
    return False


def _verbs(catalog=None) -> set[str]:
    verbs = set(_COMMAND_VERBS)
    for spec in getattr(catalog, "skills", {}).values():
        name = str(spec.get("name") or "")
        if name:
            verbs.add(name.split("_", 1)[0].casefold())
        for example in spec.get("examples", []):
            words = str(example).casefold().split()
            if words:
                verbs.add(words[0])
    return verbs


def _is_search_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
    except ValueError:
        return False
    return (any(key.casefold() in {
        "q", "search", "search_query", "_nkw", "keywords", "term",
    } for key in query) or
        re.search(r"/(?:search|find)(?:/|$)", parsed.path,
                  re.IGNORECASE) is not None)


def _bare_search(text: str, turn, ctx: dict, now: float,
                 catalog=None) -> bool:
    words = re.findall(r"[\w'-]+", text, re.UNICODE)
    if not words or len(words) > 5 or \
            any(word.casefold() in _verbs(catalog) for word in words):
        return False
    current_url = str((ctx or {}).get("url") or "")
    current_site = site_for_url(current_url)
    previous_url = str((turn.args or {}).get("url") or turn.url or "")
    previous_site = site_for_url(previous_url)
    return bool(
        turn.skill == "open_url" and current_site and
        current_site == previous_site and _is_search_url(previous_url) and
        0 <= now - turn.t <= 600)


def _has_pronoun(text: str) -> bool:
    cleaned = _NONPRONOUN_THIS.sub(" ", text)
    cleaned = _THAT_CONJUNCTION.sub(
        lambda match: match.group(0)[:match.start("that") - match.start()],
        cleaned)
    return _PRONOUN.search(cleaned) is not None


def detect(text: str, wm, ctx: dict | None, now: float,
           catalog=None) -> str | None:
    text = normalize_utterance(text)
    if not text:
        return None
    turn = wm.last(now)
    focus = wm.focus(now, ctx or {})
    search_match = SITE_SEARCH_RE.fullmatch(text)
    if search_match and re.match(
            r"^find\s+(?:the\s+)?(?:pdf|file|document|folder|picture|image)\b",
            text, re.IGNORECASE):
        search_match = None
    if search_match or (turn and _bare_search(text, turn, ctx or {}, now)):
        site = focus.get("site") or site_for_url(
            str((ctx or {}).get("url") or ""))
        if not _WEB_SEARCH.search(text) and \
                not _EXPLICIT_TARGET.search(text) and \
                not _QUESTION.search(text) and \
                not _names_other_site(text, site):
            return "site_search"
    if turn is None:
        return None
    if _AGAIN.fullmatch(text):
        return "again"
    if _UNDO.search(text):
        return "undo"
    if _PERSON.search(text):
        return "person"
    if _REFINEMENT.fullmatch(text) or re.search(
            r"\bcrank\s+it\s+(?:all\s+the\s+way\s+)?up\b", text,
            re.IGNORECASE):
        if turn.skill in _REFINEMENT_SKILLS and \
                not _SELF_CONTAINED_RELATIVE.search(text):
            return "refinement"
        if _NATIVE_IDIOM.search(text):
            return None
    if _NATIVE_IDIOM.search(text):
        return None
    if _CORRECTION.search(text):
        return "correction"
    if _ORDINAL.search(text):
        return "ordinal"
    if _ITEM.search(text):
        return "item"
    if _has_pronoun(text):
        return "pronoun"
    return None
