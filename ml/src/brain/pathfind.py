"""Bounded, local path lookup for names spoken without an absolute path."""

import difflib
import os
import re
import time
from pathlib import Path


_ALIASES = {
    "download": "~/Downloads",
    "downloads": "~/Downloads",
    "document": "~/Documents",
    "documents": "~/Documents",
    "desktop": "~/Desktop",
    "home": "~",
    "applications": "/Applications",
    "application": "/Applications",
    "apps": "/Applications",
    "pictures": "~/Pictures",
    "picture": "~/Pictures",
    "music": "~/Music",
    "movies": "~/Movies",
    "movie": "~/Movies",
    "trash": "~/.Trash",
    "photos": "~/Pictures",
    "videos": "~/Movies",
    "video": "~/Movies",
    "icloud": "~/Library/Mobile Documents/com~apple~CloudDocs",
    "icloud drive": "~/Library/Mobile Documents/com~apple~CloudDocs",
}

_LEAD = re.compile(r"^(?:(?:my|the|on|in|to|into)\s+)+", re.IGNORECASE)
_TRAIL = re.compile(r"\s+folder$", re.IGNORECASE)
PATH_ARGS = {"new_folder": ("parent",), "open_folder": ("path",),
             "open_file": ("path",), "move_to_trash": ("path",),
             "find_file": ("scope",)}


def _spoken(value: str) -> str:
    text = " ".join(str(value).strip().strip("\"'").split()).rstrip(" ,.!?")
    text = _LEAD.sub("", text)
    return _TRAIL.sub("", text)


def alias(value: str, home: str | None = None) -> str:
    name = _spoken(value).lower()
    result = _ALIASES.get(name)
    if result is None:
        return str(value)
    if home:
        result = result.replace("~", str(home), 1)
    return result


def is_alias(value: str) -> bool:
    return _spoken(value).lower() in _ALIASES


def absolute(value, home: str | None = None) -> tuple[str | None, str]:
    """Spoken folder name -> absolute path by code (brain-8).

    Returns (path, how): how is ``absolute`` / ``tilde`` (passed through),
    ``alias`` (well-known name, optionally plus a rest), ``home`` (relative
    path that exists under the home dir), or ``unresolved`` (path None)."""
    raw = str(value or "").strip()
    if not raw:
        return None, "unresolved"
    if raw.startswith("/"):
        return raw, "absolute"
    if raw.startswith("~"):
        return raw, "tilde"
    home = str(home or os.path.expanduser("~"))
    text = _spoken(raw)
    head, sep, rest = text.partition("/")
    mapped = _ALIASES.get(_TRAIL.sub("", head.strip()).lower())
    if mapped is not None:
        base = mapped.replace("~", home, 1) if mapped.startswith("~") \
            else mapped
        rest = rest.strip().strip("/")
        return (os.path.join(base, rest) if sep and rest else base), "alias"
    if text and not text.startswith(("/", "~")):
        candidate = os.path.join(home, text)
        if os.path.exists(candidate):
            return candidate, "home"
    return None, "unresolved"


def object_phrase(skill: str, text: str) -> str | None:
    t = " ".join(str(text or "").strip().split())
    patterns = {
        "move_to_trash": (
            r"^(?:move|put|throw|drag|send)\s+(.+?)\s+"
            r"(?:to|in|into)\s+(?:the\s+)?(?:trash|bin)\b",
            r"^(?:trash|delete|remove)\s+(.+)$",
        ),
        "open_file": (
            r"^open(?:\s+up)?\s+(?:(?:the|my)\s+)?"
            r"(?:(?:file|document)\s+)?(.+)$",
        ),
        "open_folder": (
            r"^(?:open|show)\s+(?:(?:my|the)\s+)?"
            r"(.+?)(?:\s+folder)?(?:\s+in\s+finder)?$",
        ),
    }
    for pattern in patterns.get(skill, ()):
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            phrase = match.group(1).strip(" ,.!?\"'")
            phrase = re.sub(r"\s+(?:in|on|to)\s+finder$", "",
                            phrase, flags=re.IGNORECASE)
            phrase = re.sub(
                r"\s+(?:as\s+a\s+list|list\s+view|as\s+icons?|"
                r"icon\s+view|column\s+view|columns?|gallery)$", "",
                phrase, flags=re.IGNORECASE)
            phrase = re.sub(r"^(?:a|an|the|my)\s+", "", phrase,
                            flags=re.IGNORECASE)
            phrase = re.sub(r"^(?:called|named)\s+", "", phrase,
                            flags=re.IGNORECASE)
            phrase = re.sub(
                r"^(?:file|folder)\s+(?:called|named)\s+", "",
                phrase, flags=re.IGNORECASE)
            phrase = re.sub(r"^(?:file|folder|document)\s+", "", phrase,
                            flags=re.IGNORECASE)
            phrase = re.sub(
                r"\s+(?:file|folder)\s+(?:called|named)\s+(.+)$",
                r" \1", phrase, flags=re.IGNORECASE)
            return phrase or None
    return None


def _normalize(name: str, is_file: bool) -> str:
    if is_file:
        name = os.path.splitext(name)[0]
    return re.sub(r"[\s\-_.]+", " ", name.lower()).strip()


def is_exact_match(phrase: str, path: str) -> bool:
    return _normalize(phrase, is_file=True) == _normalize(
        os.path.basename(path), is_file=not os.path.isdir(path))


def resolve(phrase: str, home: str | None = None,
            roots: tuple[str, ...] = ("Desktop", "Documents", "Downloads"),
            max_depth: int = 2, max_entries: int = 2000,
            budget_ms: int = 150) -> list[str]:
    home_path = Path(home or os.path.expanduser("~"))
    target = _normalize(str(phrase), is_file=True)
    if not target:
        return []
    started = time.perf_counter()
    count = 0
    candidates: list[tuple[float, str]] = []
    stack = [(home_path / root, 1) for root in roots]
    while stack and count < max_entries:
        if (time.perf_counter() - started) * 1000 >= budget_ms:
            break
        directory, depth = stack.pop()
        if directory.is_symlink():
            continue
        try:
            entries = os.scandir(directory)
        except OSError:
            continue
        with entries:
            iterator = iter(entries)
            while count < max_entries:
                if (time.perf_counter() - started) * 1000 >= budget_ms:
                    stack.clear()
                    break
                try:
                    entry = next(iterator)
                except StopIteration:
                    break
                count += 1
                if entry.name.startswith(".") or entry.is_symlink():
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if is_dir and depth < max_depth:
                    stack.append((Path(entry.path), depth + 1))
                normalized = _normalize(entry.name, is_file=not is_dir)
                if normalized == target:
                    candidates.append((1.0, entry.path))
                elif normalized and re.findall(r"\d+", target) == re.findall(
                        r"\d+", normalized):
                    score = difflib.SequenceMatcher(
                        None, target, normalized).ratio()
                    if score >= 0.88:
                        candidates.append((score, entry.path))
    exact = [(score, path) for score, path in candidates if score == 1.0]
    matches = exact or candidates
    return [path for _, path in sorted(matches, key=lambda item: (-item[0],
                                                                  item[1]))]
