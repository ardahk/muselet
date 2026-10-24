"""Cheap follow-up detection. Regexes are compiled once at import."""

from __future__ import annotations

import re

from .rules import SEARCH_URLS
from .working import BROWSERS


SITE_SEARCH_RE = re.compile(
    r"^(?:(?:now|ok(?:ay)?|and)\s+)?"
    r"(?:search(?:\s+for)?|look\s+up|look\s+for|find)\s+(.+)$",
    re.IGNORECASE)
_AGAIN = re.compile(
    r"^(?:again|do that again|repeat that|one more time|same thing again)[.!]?$",
    re.IGNORECASE)
_UNDO = re.compile(
    r"^(?:undo(?: that)?|revert that|put it back|change it back)[.!]?$",
    re.IGNORECASE)
_PERSON = re.compile(
    r"\b(?:him|her|them)\b.*\b(?:text|message|email|mail|call|send|tell|remind)\b|"
    r"\b(?:text|message|email|mail|call|send|tell|remind)\b.*\b(?:him|her|them)\b",
    re.IGNORECASE)
_ITEM = re.compile(
    r"\b(?:open|close|show|move|rename|delete|trash|find)\b.*"
    r"\b(?:it|that|this|there)\b|\bopen that folder\b",
    re.IGNORECASE)
_CORRECTION = re.compile(
    r"\b(?:no,?\s+(?:i meant\b|the other one\b)|not that one\b)",
    re.IGNORECASE)
_ORDINAL = re.compile(
    r"\b(?:the\s+)?(?:first|second|third|fourth|last)\s+one\b",
    re.IGNORECASE)
_PRONOUN = re.compile(
    r"\b(?:it|that|this|there|the same|one|him|her|them)\b",
    re.IGNORECASE)
_REFINEMENT = re.compile(
    r"\b(?:louder|quieter|brighter|dimmer|a bit more|more|less|too|"
    r"make it louder|make it quieter|make it brighter|make it dimmer)\b",
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
_SITE_NAME = r"(?:google\s+maps|stack\s+overflow|best\s+buy|[a-z0-9.-]+)"
_SITE_NAMES = re.compile(
    rf"\b(?:on|from|using)\s+({_SITE_NAME})|"
    rf"\bsearch(?:\s+for)?\s+({_SITE_NAME})\s+for\b",
    re.IGNORECASE)
_REFINEMENT_SKILLS = {
    "change_volume", "set_volume", "set_brightness", "window_layout",
}


def _names_other_site(text: str, site: str | None) -> bool:
    expected = site or ""
    for match in _SITE_NAMES.finditer(text):
        name = (match.group(1) or match.group(2) or "").casefold().strip()
        host = _ALIAS.get(name, name)
        if host and host not in {expected, expected.removeprefix("www.")}:
            return True
    return False


def detect(text: str, wm, ctx: dict | None, now: float) -> str | None:
    turn = wm.last(now)
    if turn is None:
        return None
    text = text.strip()
    if not text:
        return None
    focus = wm.focus(now, ctx or {})
    if SITE_SEARCH_RE.match(text):
        site = focus.get("site")
        if site in SEARCH_URLS and not _names_other_site(text, site):
            return "site_search"
    if _AGAIN.fullmatch(text):
        return "again"
    if _UNDO.fullmatch(text):
        return "undo"
    if _PERSON.search(text):
        return "person"
    if _REFINEMENT.search(text):
        if turn.skill in _REFINEMENT_SKILLS:
            return "refinement"
        if _NATIVE_IDIOM.search(text):
            return None
    if _CORRECTION.search(text):
        return "correction"
    if _ORDINAL.search(text):
        return "ordinal"
    if _ITEM.search(text):
        return "item"
    if _PRONOUN.search(text):
        return "pronoun"
    if _NATIVE_IDIOM.search(text):
        return None
    return None
