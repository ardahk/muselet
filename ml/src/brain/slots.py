"""Missing required args: a per-skill fallback table (deterministic, safe
cases only) and slot-fill helpers (question per arg, answer cleaning and
type check). The orchestrator keeps the slot state."""

import re

SLOT_TTL_S = 60
CANCEL = re.compile(r"^(?:cancel|never ?mind|forget (?:it|about it)|stop|"
                    r"no(?:pe)?|nothing)[.!]?$", re.I)

_DATETIME_WORDS = (
    r"(?:(?:at|by|on|for|from|in|this|next|every|until|before|after)\s+)?"
    r"(?:today|tonight|tomorrow(?:\s+(?:morning|afternoon|evening|night))?|"
    r"noon|midnight|(?:this|tomorrow)\s+(?:morning|afternoon|evening)|"
    r"(?:next\s+)?(?:week|month|year|weekend)|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"(?:an?|\d+|one|two|three|four|five|ten|fifteen|twenty|thirty)\s+"
    r"(?:minutes?|hours?|days?|weeks?)|"
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|o'clock)?)")
_DT_PHRASE = re.compile(rf"(?:\s*\b{_DATETIME_WORDS}\b)+", re.I)
_LEAD = {
    "create_reminder": re.compile(
        r"^(?:please\s+)?(?:remind me(?:\s+to)?|(?:create|add|set|make)\s+"
        r"(?:a\s+|an\s+)?reminder(?:\s+(?:to|for|about|that))?|"
        r"don't let me forget(?:\s+to)?)(?:\s+|$)", re.I),
    "create_event": re.compile(
        r"^(?:please\s+)?(?:(?:create|add|schedule|make|put|set up|book)\s+"
        r"(?:an?\s+)?(?:new\s+)?(?:event|meeting|appointment|calendar event)?"
        r"(?:\s+(?:called|named|for|titled))?|schedule)\s+", re.I),
    "new_note": re.compile(
        r"^.*?\b(?:note|write down|jot down)\b(?:\s+(?:that\s+says|saying|"
        r"which\s+says|with|that|to|:))?\s+", re.I),
}
_NOTE_BODY = re.compile(
    r"\b(?:that says|saying|which says|with the text|with text|reading)\s+(.+)$",
    re.I)


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .,!?\"'")


def _title_from(skill: str, args: dict, utterance: str) -> str | None:
    """utterance minus the datetime phrase (and the command words)."""
    t = utterance
    for k in ("due", "start", "end"):
        v = args.get(k)
        if isinstance(v, str) and v and v.lower() in t.lower():
            i = t.lower().index(v.lower())
            t = t[:i] + " " + t[i + len(v):]
    t = _DT_PHRASE.sub(" ", t)
    t = _LEAD[skill].sub("", _strip(t))
    t = _strip(re.sub(r"^(?:to|about|that)\s+", "", _strip(t), flags=re.I))
    return t or None


def fill_defaults(skill: str, args: dict, utterance: str) -> dict:
    """Fill obviously-safe missing args from what we have (raw strings)."""
    args = dict(args)
    if skill == "new_note" and not args.get("body"):
        if args.get("title"):
            args["body"] = args["title"]
        else:
            m = _NOTE_BODY.search(utterance)
            if m and _strip(m.group(1)):
                args["body"] = _strip(m.group(1))
        if args.get("body"):
            args["title"] = " ".join(str(args["body"]).split()[:6])
    elif skill in ("create_reminder", "create_event") and not args.get("title"):
        title = _title_from(skill, args, utterance)
        if title:
            args["title"] = title
    return args


_QUESTIONS = {
    ("new_note", "body"): "What should the note say?",
    ("send_message", "body"): "What should the message say?",
    ("send_message", "to"): "Who should I text?",
    ("compose_email", "to"): "Who should I email?",
    ("compose_email", "body"): "What should the email say?",
    ("create_event", "title"): "What's the event called?",
    ("create_reminder", "title"): "What should I remind you about?",
    ("web_search", "query"): "What should I search for?",
    ("find_file", "query"): "Which file should I look for?",
    ("play_music", "query"): "What should I play?",
    ("new_folder", "name"): "What should I name the folder?",
    ("new_folder", "parent"): "Where should I put the folder?",
    ("type_text", "text"): "What should I type?",
    ("advisor_prep", "client"): "Which client?",
}
_BY_TYPE = {"datetime": "When?", "duration": "For how long?",
            "app": "Which app?", "url": "Which website?",
            "path": "Which file or folder?", "contact": "Who to?",
            "int": "What number?", "bool": "On or off?"}


def question(skill: str, arg: str, typ: str | None) -> str:
    q = _QUESTIONS.get((skill, arg)) or _BY_TYPE.get(typ or "")
    return q or f"What {arg.replace('_', ' ')} should I use?"


_FILLER = re.compile(r"^(?:(?:um+|uh+|so|okay|ok|well),?\s+)+", re.I)
_SAY_LEAD = re.compile(r"^(?:it should say|it says|that says|have it say|"
                       r"make it say|say|call it|name it)\s+", re.I)
_PREP_LEAD = re.compile(r"^(?:send it to|text|email|to|at|on|for|in|"
                        r"it's|it is)\s+", re.I)


def clean_answer(text: str, typ: str | None) -> str:
    """'it should say buy milk' -> 'buy milk'; 'to Mom' -> 'Mom'."""
    t = _FILLER.sub("", _strip(text))
    t = _SAY_LEAD.sub("", t) or t
    if typ in ("contact", "datetime", "duration", "app", "path", "int"):
        t = _PREP_LEAD.sub("", t) or t
    return _strip(t)


def valid(typ: str | None, value: str, a: dict) -> bool:
    """Would this answer coerce to the arg type?"""
    from . import decision as d
    if not value:
        return False
    if typ == "datetime":
        return d.parse_datetime(value) is not None
    if typ == "duration":
        return d.parse_duration(value) is not None
    if typ == "int":
        return d.normalize_level(value) is not None or \
            value.lstrip("+-").isdigit()
    if typ == "bool":
        return value.lower() in ("on", "off", "yes", "no", "true", "false")
    if typ == "enum" and a.get("values"):
        return value.lower() in {str(v).lower() for v in a["values"]}
    return True
