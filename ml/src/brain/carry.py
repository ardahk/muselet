"""Cross-app "carry" tasks: read something on one screen, use it in another
app ("look up X and text it to Caleb", "summarize this article into a new
note"). Rule-based (no model call); the planner does the work as one task."""

from __future__ import annotations

import re

_LOOKUP = (r"(?:look\s*up|lookup|find|get|check|search\s+for|search|google|"
           r"see|what'?s)")
_OBJ = (r"(?:it|that|this|them|those|the\s+(?:[\w-]+\s+){0,2}?"
        r"(?:result|results|answer|address|forecast|temperature|weather|link|"
        r"name|number|price|details|info|location|place|time|hours))")
_RELAY = re.compile(
    rf"^\s*(?:please\s+|can you\s+|could you\s+)?(?P<lookup>{_LOOKUP}\b.+?)"
    rf",?\s+(?:and\s+(?:then\s+)?|then\s+)"
    rf"(?:text|message|imessage|send)\s+(?P<obj>{_OBJ})\s+to\s+"
    r"(?P<to>[A-Za-z][\w'.-]*(?:\s+[A-Z][\w'.-]*)?)\s*[.!?]?\s*$",
    re.IGNORECASE)
_SUMMARY = re.compile(
    r"^\s*(?:please\s+|can you\s+|could you\s+)?"
    r"(?:summari[sz]e|sum\s+up|write\s+(?:a\s+|up\s+a\s+)?summary\s+of|"
    r"make\s+(?:a\s+)?summary\s+of)\s+(?:this|the|that|my)\s+"
    r"(?P<source>article|page|web\s*page|post|story|blog\s+post|site|email)\s+"
    r"(?:in|into|to|as|on)\s+(?:a\s+)?(?:new\s+)?note\b"
    r"(?:\s+in\s+notes)?\s*[.!?]?\s*$",
    re.IGNORECASE)
NOTE_MAX, NOTES_KEPT = 300, 4


def parse(text: str) -> dict | None:
    """{"kind": "relay", "lookup", "obj", "to"} | {"kind": "summary_note",
    "source"} | None."""
    value = " ".join(str(text or "").split())
    if (m := _RELAY.match(value)):
        obj = re.sub(r"^the\s+", "", m["obj"], flags=re.IGNORECASE)
        return {"kind": "relay", "lookup": m["lookup"].strip(" ,"),
                "obj": obj.lower(), "to": m["to"]}
    if (m := _SUMMARY.match(value)):
        return {"kind": "summary_note", "source": m["source"].lower()}
    return None


def hint(task: dict) -> str:
    """Route hint. Avoids the word 'n-o-t-e' for relays so app-hint matching
    picks the lookup app + Messages, not Notes."""
    if task["kind"] == "relay":
        what = "the value" if task["obj"] in ("it", "that", "this", "them",
                                              "those") else task["obj"]
        return (f"two apps, one task: first {task['lookup']} and read "
                f"{what} on screen; save it as a scratch line; then use the "
                f"Messages app; new message to {task['to']}; type a short "
                f"text with {what}; confirm before sending; never send")
    return (f"read the open {task['source']} (observation / on-screen text); "
            "save a 2-4 sentence summary in your own words as a scratch line; "
            "then use the Notes app; cmd+n; type a title line, return, then "
            "the summary")


def finish(task: dict) -> str:
    if task["kind"] == "relay":
        what = "looked-up value" if task["obj"] in (
            "it", "that", "this", "them", "those") else f"looked-up {task['obj']}"
        return (f"a Messages draft to {task['to']} contains the {what} and "
                "you have asked to confirm sending (not sent)")
    return (f"a new note in Notes contains a short summary of the "
            f"{task['source']}")


def add_note(notes: list[str], text: str) -> str:
    value = " ".join(str(text or "").split())[:NOTE_MAX]
    if value and value not in notes:
        notes.append(value)
        del notes[:-NOTES_KEPT]
    return value


_GENERIC = {"sunny", "today", "weather", "tokyo", "address", "with", "from",
            "your", "that", "this", "here", "there", "caleb", "message"}


def carries(value: str, notes: list[str]) -> bool:
    """Does the draft carry something from the notes? Numbers count first
    (temperatures, street numbers); else a distinctive word."""
    v = str(value or "").lower()
    if not v.strip():
        return False
    if not notes:
        return len(v.split()) >= 2
    text = " ".join(notes).lower()
    numbers = set(re.findall(r"\d+(?:[.,:]\d+)*", text))
    if numbers:
        return bool(numbers & set(re.findall(r"\d+(?:[.,:]\d+)*", v)))
    words = {w for w in re.findall(r"[a-z]{4,}", text)} - _GENERIC
    return bool(words & set(re.findall(r"[a-z]{4,}", v)))
