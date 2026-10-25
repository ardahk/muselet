"""Small, guarded LLM follow-up rewriter."""

from __future__ import annotations

import re

from .detect import _COMMAND_VERBS, _FILLER
from .guard import allowed
from .matching import distance_one
from .rules import Resolution


_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_FILLER_WORDS = set(re.findall(r"[a-z]+", _FILLER.pattern)) | {"okay"}
_STOPWORDS = _FILLER_WORDS | {
    "it", "that", "this", "him", "her", "them", "there", "one", "ones",
    "a", "an", "the", "no", "not", "actually", "instead", "also", "too",
    "again", "now", "just", "make", "other", "sorry", "i", "said", "meant",
    "wait", "please", "to", "and", "but", "so", "um", "uh",
}
_NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "half", "quarter",
}
_ALLOWED_WORDS = _STOPWORDS | _COMMAND_VERBS | {
    "open", "search", "play", "set", "remind", "add", "move", "send",
    "reply", "hide", "quit", "export", "using", "with", "for", "from",
    "about", "called", "named", "saying", "at", "on", "in", "minutes",
    "minute", "hours", "hour", "timer", "reminder", "note", "event",
    "message", "email", "tomorrow", "today", "tonight", "morning",
    "afternoon", "evening", "left", "right", "https", "http", "www", "com",
    "org",
}
_SHORT_COMMAND_TYPO = {
    word for word in _COMMAND_VERBS if len(word) >= 3
}


STATIC = """Rewrite the user's latest voice command into ONE self-contained command for a Mac assistant, using only the context lines. Merge new constraints into the previous request and keep every previous detail unless the user replaces it. Copy names, sites and values from the context; never add new actions. If the command is already self-contained or the context does not determine what it refers to, reply UNCHANGED. If you must know which one the user means, reply ASK: <short question>.

Focus: app=Zen site=wikipedia.org recent: search for history
Say: search for history
Output: open https://en.wikipedia.org/w/index.php?search=history

Focus: contact=Mom
Recent: send_message to=Mom ok
Say: send her a message saying hi
Output: send a message to Mom saying hi

Focus: file=report.pdf
Recent: open_file path=report.pdf ok
Say: move it to the trash
Output: move report.pdf to the trash

Focus: app=Finder
Say: open Safari
Output: UNCHANGED

Focus:
Say: open it
Output: ASK: What should I open?

Focus: app=Music
Recent: play song ok
Say: turn it up
Output: UNCHANGED

Focus: app=Music
Recent: play instrumental music for reading ok
Say: make it calmer
Output: play calmer instrumental music for reading

Recent: create_event title=Planning review start=Monday 10:00 ok
Say: move it to the afternoon
Output: move the Planning review to the afternoon

"""


def dynamic(text: str, wm, ctx: dict, now: float,
            memory: list[dict] | None = None) -> str:
    focus = wm.focus(now, ctx)
    fields = ("app", "site", "contact", "file", "query")
    focus_line = "Focus: " + " ".join(
        f"{key}={focus[key]}" for key in fields if focus.get(key))
    lines = [focus_line] if focus_line != "Focus: " else []
    recent_count = 3 if lines else 4
    detailed = getattr(wm, "recent_detail_lines", wm.recent_lines)
    lines.extend(f"Recent: {line}"
                 for line in detailed(recent_count, now=now))
    if memory:
        from .store import render
        lines.append("Memory:")
        lines.extend(render(memory[:3]))
    lines.extend((f"Say: {text}", "Output:"))
    return "\n".join(lines)


def _tokens(text: str) -> list[str]:
    return [match.group().casefold() for match in _TOKEN.finditer(text)]


def _context_tokens(context: str) -> set[str]:
    words = set()
    in_memory = False
    for line in context.splitlines():
        if line == "Memory:":
            in_memory = True
            continue
        if line.startswith(("Say:", "Output:")):
            in_memory = False
            continue
        if in_memory or line.startswith(("Focus:", "Recent:")):
            _, _, value = line.partition(":")
            words.update(_tokens(value))
    return words


def has_context(context: str) -> bool:
    return any(line.startswith(("Focus:", "Recent:"))
               for line in context.splitlines())


def _valid(text: str, new_text: str, context: str) -> bool:
    utterance = _tokens(text)
    output = _tokens(new_text)
    context_words = _context_tokens(context)
    utterance_words = set(utterance)
    output_words = set(output)

    for word in utterance:
        if len(word) < 3 or word in _STOPWORDS or word in _NUMBER_WORDS:
            continue
        if word in output_words:
            continue
        if len(word) >= 5 and any(
                distance_one(word, candidate) for candidate in output_words):
            continue
        if len(word) < 5 and any(
                candidate in _SHORT_COMMAND_TYPO and
                distance_one(word, candidate, min_length=1) and
                candidate in output_words for candidate in _SHORT_COMMAND_TYPO):
            continue
        return False

    for word in output:
        if len(word) < 3 or word.isdigit() or word in _ALLOWED_WORDS:
            continue
        if word in utterance_words or word in context_words:
            continue
        if any(distance_one(word, source, min_length=1)
               for source in utterance_words):
            continue
        return False
    return True


def llm_rewrite(text: str, wm, ctx: dict, now: float, llm,
                max_tokens: int = 40,
                memory: list[dict] | None = None) -> Resolution:
    context = dynamic(text, wm, ctx, now, memory)
    if not has_context(context):
        return Resolution("none", text, False, "llm-gated")
    prompt = STATIC + context
    output = str(llm(prompt, min(max_tokens, 40)) or "").strip()
    first = output.splitlines()[0].strip() if output else ""
    if first.casefold() == "unchanged":
        return Resolution("none", text, False, "llm")
    if first.casefold().startswith("ask:"):
        return Resolution("ask", text, False, "llm",
                          ask=first[4:].strip())
    new_text = first.strip(" \"'")
    if (not new_text or len(new_text) > 3 * len(text) + 60 or
            new_text.casefold() == text.casefold()):
        return Resolution("none", text, False, "llm")
    if not allowed(text, new_text):
        return Resolution("none", text, False, "guard")
    if not _valid(text, new_text, context):
        return Resolution("none", text, False, "llm-invalid")
    return Resolution("llm", new_text, True, "llm")
