"""Small, guarded LLM follow-up rewriter."""

from __future__ import annotations

from .guard import allowed
from .rules import Resolution


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


def llm_rewrite(text: str, wm, ctx: dict, now: float, llm,
                max_tokens: int = 40,
                memory: list[dict] | None = None) -> Resolution:
    prompt = STATIC + dynamic(text, wm, ctx, now, memory)
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
    return Resolution("llm", new_text, True, "llm")
