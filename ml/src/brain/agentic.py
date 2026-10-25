"""Planner hints for app-level skills."""

from __future__ import annotations


_INTERNAL = {"ms", "_raw", "missing", "confirmed"}


def _clean(args: dict) -> dict:
    return {
        key: value for key, value in args.items()
        if key not in _INTERNAL and value not in (None, "")
    }


def hint(skill: str, args: dict) -> str:
    args = _clean(args)
    if skill == "start_timer":
        result = f"use the Clock app's Timers tab; duration {args.get('duration', '')}".rstrip()
        if args.get("label"):
            result += f"; label {args['label']}"
        return result
    if skill == "create_event":
        result = f"use the Calendar app; new event titled {args.get('title', '')}; starts {args.get('start', '')}".rstrip()
        for key in ("end", "location"):
            if args.get(key):
                result += f"; {key} {args[key]}"
        return result
    if skill == "create_reminder":
        result = f"use the Reminders app; reminder {args.get('title', '')}".rstrip()
        if args.get("due"):
            result += f"; due {args['due']}"
        return result
    if skill == "new_note":
        result = "use the Notes app; new note"
        if args.get("title"):
            result += f" titled {args['title']}"
        return f"{result}; text: {args.get('body', '')}".rstrip()
    if skill == "compose_text":
        target = f" (or {args['target']})" if args.get("target") else ""
        return f"use the Notes app{target}; write a new note about {args.get('topic', '')}".rstrip()
    if skill == "play_music":
        return f"use the Music app; play {args.get('query', '')}".rstrip()
    if skill == "todays_agenda":
        return "use the Calendar app; read today's events back to the user"
    if skill == "send_message":
        return (f"use the Messages app; recipient {args.get('to', '')}; "
                f"message: {args.get('body', '')}; ask to confirm before sending").rstrip()
    if skill == "compose_email":
        result = f"use the Mail app; to {args.get('to', '')}"
        if args.get("subject"):
            result += f"; subject {args['subject']}"
        return f"{result}; body: {args.get('body', '')}; leave it as a draft, don't send".rstrip()
    if skill == "draft_email":
        result = "the email is open in the browser/Mail; write a draft reply"
        if args.get("to"):
            result += f" to {args['to']}"
        if args.get("about"):
            result += f" about {args['about']}"
        return f"{result} in the reply box; don't send"
    if skill in ("premiere_command", "premiere_edit"):
        facts = "; ".join(f"{key} {value}" for key, value in args.items())
        return "use Adobe Premiere Pro; " + facts
    return ""
