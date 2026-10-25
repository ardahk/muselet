"""Short progress phrases for the mascot bubble while the planner works
(`ui {mascot: "acting", bubble: <step>}` after each planner turn)."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from .sendgate import is_browser
from .sites import SITES

MAX_WORDS = 8
MAX_TEXT = 30          # never echo longer typed text (message bodies)

_SECRET_LABEL = re.compile(
    r"pass(?:word|code|phrase)?|\bpin\b|token|secret|api.?key|otp|"
    r"verification code|security code|cvv|cvc|card number|ssn", re.I)
_SECRET_TEXT = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])\S{12,}$")   # key-like blob
_PLAYBACK = re.compile(
    r"play(?:ing|back|er state)?\b|paused?\b|currentTime|duration|"
    r"\bvideo\b|\btrack\b|now playing", re.I)
_LABEL_CUT = re.compile(r"\s+[-|•·–—:]\s+|\s*\(|\.\.\.|…")
_HOST_NAMES = {
    "youtube.com": "YouTube", "youtu.be": "YouTube", "github.com": "GitHub",
    "linkedin.com": "LinkedIn", "mail.google.com": "Gmail",
    "docs.google.com": "Google Docs", "sheets.google.com": "Google Sheets",
    "slides.google.com": "Google Slides", "drive.google.com": "Google Drive",
    "maps.google.com": "Google Maps", "calendar.google.com": "Google Calendar",
    "x.com": "X", "chatgpt.com": "ChatGPT", "news.ycombinator.com": "Hacker News",
}
_KEY_NAMES = {"cmd": "⌘", "command": "⌘", "shift": "⇧", "alt": "⌥",
              "option": "⌥", "opt": "⌥", "ctrl": "⌃", "control": "⌃"}


def _opening_app(name: str | None) -> str:
    """'Opening Safari/Chrome/Zen' reads wrong — it's always the browser."""
    if name and is_browser(name):
        return "Opening browser"
    return f"Opening {_words(name or 'the app', 4)}"


def _words(s: str, n: int) -> str:
    return " ".join(str(s or "").split()[:n])


def _clip(phrase: str) -> str:
    return _words(phrase, MAX_WORDS)


def _element(elements, ref) -> dict:
    for e in elements or []:
        if e.get("ref") == ref:
            return e
    return {}


def _label(e: dict, n: int = 5) -> str:
    raw = str(e.get("label") or "").strip()
    raw = _LABEL_CUT.split(raw, 1)[0]
    return _words(raw, n).strip(" .,:;\"'")


def site_name(url: str) -> str:
    u = str(url or "")
    try:
        host = urlsplit(u if "://" in u else "https://" + u).hostname or ""
    except ValueError:
        host = ""
    host = host.casefold().removeprefix("www.")
    if not host:
        return ""
    if host in _HOST_NAMES:
        return _HOST_NAMES[host]
    for key, h in SITES.items():
        if h == host and key.isalpha():
            return key.capitalize()
    parts = host.split(".")
    base = parts[-2] if len(parts) >= 2 else parts[0]
    return base.capitalize()


def _keys(combo: str) -> str:
    parts = [p for p in str(combo or "").lower().split("+") if p]
    if parts == ["return"] or parts == ["enter"]:
        return "Pressing Return"
    if parts == ["esc"] or parts == ["escape"]:
        return "Pressing Escape"
    if parts == ["cmd", "l"]:
        return "Going to the address bar"
    if parts == ["cmd", "f"]:
        return "Searching the page"
    if parts == ["cmd", "t"]:
        return "Opening a new tab"
    pretty = "".join(_KEY_NAMES.get(p, p.upper() if len(p) == 1 else
                                    p.capitalize()) for p in parts)
    return f"Pressing {pretty}" if pretty else "Pressing keys"


def _typed(text: str, target: dict) -> str:
    text = " ".join(str(text or "").split())
    secret = (_SECRET_LABEL.search(str(target.get("label") or "")) or
              "secure" in str(target.get("role") or "").lower() or
              _SECRET_TEXT.match(text))
    if not text or secret or len(text) > MAX_TEXT:
        where = _label(target, 4)
        return f"Typing in {where}" if where and not secret else "Typing"
    return f"Typing {text}"


def _skill(name: str, args: dict) -> str:
    args = args or {}
    if name == "open_app" and (args.get("name") or args.get("app")):
        return _opening_app(args.get("name") or args.get("app"))
    if name == "open_url" and args.get("url"):
        site = site_name(str(args["url"]))
        return f"Opening {site}" if site else "Opening the page"
    if name == "web_search":
        q = str(args.get("query") or args.get("q") or "")
        return f"Searching {q}" if q and len(q) <= MAX_TEXT else "Searching the web"
    if name in ("type_text", "type"):
        return _typed(str(args.get("text") or ""), {})
    words = str(name or "").replace("_", " ").strip()
    return words.capitalize() if words else "Working on it"


def step_phrase(action: dict | None, elements=None) -> str | None:
    """Human phrase (<= 8 words) for a planner action; None for terminal
    ops (done/ask/confirm/refuse), which show their own bubble."""
    if not action:
        return None
    op = action.get("op")
    if op in ("done", "ask", "confirm", "refuse"):
        return None
    if op == "type":
        phrase = _typed(action.get("text", ""),
                        _element(elements, action.get("ref")))
    elif op == "press":
        label = _label(_element(elements, action.get("ref")))
        phrase = f"Clicking {label}" if label else "Clicking"
    elif op == "click":
        target = _words(action.get("target") or "", 5)
        phrase = f"Clicking {target}" if target else "Clicking"
    elif op == "url":
        site = site_name(str(action.get("url") or ""))
        phrase = f"Opening {site}" if site else "Opening the page"
    elif op == "open":
        phrase = _opening_app(action.get("name") or action.get("app"))
    elif op == "script":
        phrase = ("Checking playback" if _PLAYBACK.search(
            str(action.get("code") or "")) else "Running a quick script")
    elif op == "keys":
        phrase = _keys(action.get("combo", ""))
    elif op == "scroll":
        phrase = f"Scrolling {action.get('direction') or 'down'}"
    elif op == "wait":
        phrase = "Waiting for the page"
    elif op == "skill":
        phrase = _skill(str(action.get("name") or ""), action.get("args"))
    else:
        phrase = "Working on it"
    return _clip(phrase)
