"""Planner hints for app-level skills."""

from __future__ import annotations


_INTERNAL = {"ms", "_raw", "missing", "confirmed"}


def _clean(args: dict) -> dict:
    return {
        key: value for key, value in args.items()
        if key not in _INTERNAL and value not in (None, "")
    }


def content(args: dict) -> str | None:
    args = _clean(args)
    for key in ("body", "text", "message", "about", "title"):
        value = args.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _with_content(skill: str, args: dict, result: str) -> str:
    value = content(args)
    if skill != "compose_text" and result and value:
        return f'{result}; type exactly: "{value}"'
    return result


def hint(skill: str, args: dict) -> str:
    args = _clean(args)
    if skill == "start_timer":
        result = f"use the Clock app's Timers tab; duration {args.get('duration', '')}".rstrip()
        if args.get("label"):
            result += f"; label {args['label']}"
        return _with_content(skill, args, result)
    if skill == "create_event":
        result = f"use the Calendar app; new event titled {args.get('title', '')}; starts {args.get('start', '')}".rstrip()
        for key in ("end", "location"):
            if args.get(key):
                result += f"; {key} {args[key]}"
        return _with_content(skill, args, result)
    if skill == "create_reminder":
        result = f"use the Reminders app; reminder {args.get('title', '')}".rstrip()
        if args.get("due"):
            result += f"; due {args['due']}"
        return _with_content(skill, args, result)
    if skill == "new_note":
        result = "use the Notes app; new note"
        if args.get("title"):
            result += f" titled {args['title']}"
        return _with_content(
            skill, args, f"{result}; text: {args.get('body', '')}".rstrip())
    if skill == "compose_text":
        target = f" (or {args['target']})" if args.get("target") else ""
        return _with_content(
            skill, args,
            f"use the Notes app{target}; write a new note about "
            f"{args.get('topic', '')}".rstrip())
    if skill == "play_music":
        return _with_content(
            skill, args, f"use the Music app; play {args.get('query', '')}".rstrip())
    if skill == "todays_agenda":
        return _with_content(
            skill, args, "use the Calendar app; read today's events back to the user")
    if skill == "send_message":
        return _with_content(
            skill, args, (f"use the Messages app; recipient {args.get('to', '')}; "
                          f"message: {args.get('body', '')}; ask to confirm "
                          "before sending").rstrip())
    if skill == "compose_email":
        result = f"use the Mail app; to {args.get('to', '')}"
        if args.get("subject"):
            result += f"; subject {args['subject']}"
        return _with_content(
            skill, args,
            f"{result}; body: {args.get('body', '')}; leave it as a draft, "
            "don't send".rstrip())
    if skill == "draft_email":
        result = "the email is open in the browser/Mail; write a draft reply"
        if args.get("to"):
            result += f" to {args['to']}"
        if args.get("about"):
            result += f" about {args['about']}"
        return _with_content(skill, args, f"{result} in the reply box; don't send")
    if skill in ("premiere_command", "premiere_edit"):
        facts = "; ".join(f"{key} {value}" for key, value in args.items())
        return _with_content(skill, args, "use Adobe Premiere Pro; " + facts)
    return ""
