"""Messages RPC contract:
- `messages_people {query, limit:5}` ->
  `{people:[{name, handles:[{kind:"phone"|"email", value}], chat:true}], ms}`
- `contacts_search {query, limit:5, fuzzy?:bool}` ->
  `{matches:[{id, name, nickname?, handles:[{kind:"phone"|"email", value,
  label}], score?}], ms}`
  Errors: `contacts_denied` (no Contacts permission).
- `messages_compose {handle, body}` ->
  `{ok, frontmost, window_title, body_visible}`: opens Messages on that
  recipient's conversation with `body` in the compose field; never sends.
  Optional `name` is the resolved display name.
  Errors `not_frontmost`, `screen_locked`.
- `messages_send {}` -> `{ok, sent: bool}`: presses send in the window composed
  by the last `messages_compose`.
  Errors `not_frontmost`, `screen_locked`.

Errors may arrive either as a result with `ok:false, error:<kind>` or as
RuntimeError(<kind>) from `orch.server.rpc` (result-less error); treat both the
same (error string = res.get("error") or str(exc)).
"""

from __future__ import annotations

import difflib
import re
import time
import unicodedata

from . import slots
from .orchestrator import _excerpt

CONTACTS_TIMEOUT_S = 65
MESSAGES_TIMEOUT_S = 4

_EMAIL = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+"
                    r"(?:\.[A-Z0-9-]+)+$", re.IGNORECASE)
_PHONE = re.compile(r"^\+?[\d\s()./-]+$")
_APPLE_LABEL = re.compile(r"^_\$!<(.*?)>!\$_$")
_ANSWER_STOP = {"the", "one", "please", "i", "mean", "to", "that"}
_LABEL_WORDS = {"mobile", "home", "work", "iphone", "main", "email",
                "phone"}
_ORDINALS = {
    "first": 0, "1st": 0, "one": 0, "the first": 0, "the first one": 0,
    "second": 1, "2nd": 1, "two": 1, "the second": 1,
    "the second one": 1, "third": 2, "3rd": 2, "three": 2,
    "the third": 2, "the third one": 2, "last": -1, "the last": -1,
    "the last one": -1,
}

_EMAIL_WORD = re.compile(r"\b(?:e-?mails?|gmail|mail)\b", re.IGNORECASE)
_MESSAGING_WORD = re.compile(
    r"\b(?:text|texting|texts|texted|message|messages|imessage|sms)\b",
    re.IGNORECASE)
_FILLER_LEAD = re.compile(
    r"^(?:(?:hey\s+muselet|uh+|um+|er+|ah+|hey|okay|ok|so|please|and|"
    r"now|muselet)\b[,\.]?\s*)+", re.IGNORECASE)
_REQUEST_LEAD = re.compile(
    r"^(?:(?:can|could|would|will)\s+you|"
    r"i(?:\s+(?:want|need|would like)|(?:'d| 'd)\s+like)\s+"
    r"(?:you\s+)?to|"
    r"let's|go ahead and)\s+", re.IGNORECASE)
_NOUN = re.compile(
    r"(?:i\s+message|imessage|text|message|sms|note)"
    r"(?:\s+message)?", re.IGNORECASE)
_MESSAGE_NOUN = re.compile(
    r"(?:i\s+message|imessage|text|message|sms)(?:\s+message)?",
    re.IGNORECASE)
_VERB = r"(?:send|shoot|drop)"
_ART = r"(?:a|an|the)"
_QUICK = r"(?:quick|short|little|new|brief)"
_BODY_START = {
    "i", "i'm", "im", "i'll", "i've", "hi", "hello", "hey", "yes",
    "yeah", "no", "ok", "okay", "thanks", "thank", "lol", "sure",
    "running", "on", "call", "can", "are", "do", "did", "don't", "we",
    "we're", "you", "you're", "good", "happy", "see", "love", "miss",
    "sorry",
}
_BODYWORD_EXCLUDED = {
    "quick", "short", "little", "new", "brief", "voice", "audio", "group",
    "long", "private", "text", "message", "imessage", "sms", "note",
    "the", "a", "an",
}
_VAGUE_TO = {
    "her", "him", "them", "they", "she", "he", "someone", "somebody",
    "anyone", "anybody", "a friend", "my friend", "a contact",
}
_NAME_FILLERS = {"uh", "um", "er", "ah", "like"}
_REST_SEPARATOR = re.compile(
    r"\b(?:saying|that says|which says|that reads|to say|and say|that)\b"
    r"|:|\s-\s", re.IGNORECASE)
_REST_CORRECTION = re.compile(
    r"^(.+?)\s*,?\s*(?:i mean|sorry|no|or rather|actually|wait)\b,?\s+"
    r"(.+)$", re.IGNORECASE)
_COMMA_REST = re.compile(r"^(.+?),\s*(.+)$")
_BODY_LEAD = re.compile(r"^(?:uh+|um+)\b[\s,]*", re.IGNORECASE)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _strip_pair_quotes(text: str) -> str:
    value = str(text or "").strip()
    pairs = {'"': '"', "'": "'", "“": "”", "‘": "’"}
    if len(value) >= 2 and pairs.get(value[0]) == value[-1]:
        value = value[1:-1].strip()
    return value


def _body(text: str | None) -> str | None:
    value = _strip_pair_quotes(text or "")
    value = _BODY_LEAD.sub("", value)
    value = value.rstrip(" \t\r\n.,")
    return value or None


def _name_tokens(text: str) -> list[str]:
    return [token.strip(" \t\r\n.,!?;:\"'“”‘’") for token in text.split()
            if token.strip(" \t\r\n.,!?;:\"'“”‘’")]


def _correction(text: str) -> str:
    value = str(text or "").strip()
    while True:
        match = _REST_CORRECTION.match(value)
        if not match or len(_name_tokens(match.group(1))) > 2:
            return value
        value = match.group(2).strip()


def _cleanup_name(text: str, *, separator: bool = False) -> str:
    value = _correction(str(text or "").strip())
    comma = _COMMA_REST.match(value)
    if comma and (separator or len(_name_tokens(comma.group(1))) <= 2):
        value = comma.group(2)
    tokens = [token for token in _name_tokens(value)
              if token.casefold() not in _NAME_FILLERS]
    while tokens and tokens[-1].casefold() == "please":
        tokens.pop()
    return " ".join(tokens)


def _split_rest(text: str) -> tuple[str, str | None]:
    rest = re.sub(r"\s+", " ", str(text or "")).strip()
    separator = _REST_SEPARATOR.search(rest)
    if separator:
        name = _cleanup_name(rest[:separator.start()], separator=True)
        return name, _body(rest[separator.end():])

    rest = _correction(rest)
    comma = _COMMA_REST.match(rest)
    if comma and len(_name_tokens(comma.group(1))) <= 2:
        before, after = comma.groups()
        after_tokens = _name_tokens(after)
        if len(after_tokens) <= 2 and after_tokens and \
                after_tokens[0].casefold() not in _BODY_START:
            rest = after
        else:
            return _cleanup_name(before), _body(after)

    tokens = rest.split()
    cleaned = _name_tokens(rest)
    if len(cleaned) <= 2:
        if len(cleaned) == 2 and cleaned[1].casefold() in _BODY_START:
            return _cleanup_name(cleaned[0]), _body(cleaned[1])
        return _cleanup_name(rest), None

    name_tokens = [tokens[0]]
    second = _name_tokens(tokens[1])
    if second and tokens[1][:1].isupper() and \
            second[0].casefold() not in _BODY_START:
        name_tokens.append(tokens[1])
    body_start = len(name_tokens)
    return (_cleanup_name(" ".join(name_tokens)),
            _body(" ".join(tokens[body_start:])))


def _parse_message_text(text: str) -> dict | None:
    original = re.sub(r"\s+", " ", str(text or "")).strip()
    if not original or _EMAIL_WORD.search(original):
        return None
    value = _FILLER_LEAD.sub("", original).strip()
    value = _REQUEST_LEAD.sub("", value, count=1).strip()
    value = re.sub(r"^please\b[,\.]?\s*", "", value,
                   flags=re.IGNORECASE).strip()
    if not value:
        return None

    noun = _NOUN.pattern
    verb = rf"{_VERB}\s+"
    article = rf"(?:{_ART}\s+)?"
    saying_first = re.match(
        rf"^{verb}(?:me\s+)?{article}(?:{_QUICK}\s+)?(?:{noun})\s+"
        rf"(?:saying|that says|which says|to say)\s+(.+)\s+to\s+"
        rf"([^\s,]+(?:\s+[^\s,]+){{0,2}})$", value, re.IGNORECASE)
    if saying_first:
        return _message_parts(saying_first.group(2),
                              _body(saying_first.group(1)))
    prefix = re.match(
        rf"^{verb}(?:me\s+)?{article}(?:(?!a\b|i\b)[a-z]\s+)?"
        rf"(?:{_QUICK}\s+)?", value, re.IGNORECASE)
    if prefix:
        tail = value[prefix.end():]
        noun_match = _NOUN.match(tail)
        if noun_match:
            rest_match = re.match(r"\s+to\s+(.+)$",
                                  tail[noun_match.end():], re.IGNORECASE)
            if rest_match:
                to, body = _split_rest(rest_match.group(1))
                return _message_parts(to, body)

    match = re.match(
        rf"^{_VERB}\s+(?:{_ART}\s+)?(.+?)\s+({noun})\s+to\s+(.+)$",
        value, re.IGNORECASE)
    if match:
        body_words = _name_tokens(match.group(1))
        if 1 <= len(body_words) <= 3 and all(
                token.casefold() not in _BODYWORD_EXCLUDED and
                not (len(token) == 1 and token.casefold() not in ("a", "i"))
                for token in body_words):
            to, _ = _split_rest(match.group(3))
            return _message_parts(to, " ".join(body_words))

    match = re.match(rf"^({_MESSAGE_NOUN.pattern})\s+(?:to\s+)?(.+)$", value,
                     re.IGNORECASE)
    if match:
        to, body = _split_rest(match.group(2))
        return _message_parts(to, body)

    match = re.match(
        rf"^{_VERB}\s+(.+?)\s+{article}(?:{_QUICK}\s+)?({_NOUN.pattern})"
        rf"(?:\s+(?:saying|that says|which says|that reads|to say|and say|"
        rf"that|:)\s*(.+))?$", value, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if 1 <= len(_name_tokens(name)) <= 3 and \
                _norm(name) not in {"a", "an", "the"}:
            return _message_parts(name, _body(match.group(3)))

    match = re.match(r"^tell\s+(.+)$", value, re.IGNORECASE)
    if match:
        rest = match.group(1).strip()
        if not _norm(rest).startswith("the "):
            explicit = re.match(r"^(.+?)\s+(?:that|to)\s+(.+)$", rest,
                                re.IGNORECASE)
            if explicit:
                name, body_text = explicit.groups()
            else:
                tokens = rest.split()
                body_at = next((i for i in range(1, min(4, len(tokens)))
                                if _name_tokens(tokens[i]) and
                                _name_tokens(tokens[i])[0].casefold()
                                in _BODY_START), None)
                if body_at is None and len(tokens) > 1:
                    body_at = 1
                if body_at is not None:
                    name = " ".join(tokens[:body_at])
                    body_text = " ".join(tokens[body_at:])
                else:
                    name = body_text = ""
            if re.match(r"^(?:a|my)\s+friend\b", rest, re.IGNORECASE):
                name = " ".join(rest.split()[:2])
                body_text = " ".join(rest.split()[2:])
            if 1 <= len(_name_tokens(name)) <= 3 and body_text and \
                    (_norm(name).split() or [""])[0] not in {
                        "", "me", "us", "it", "this", "that", "siri", "alexa",
                        "google", "muselet", "devin", "chatgpt", "claude",
                        "computer"} and \
                    not _norm(name).startswith(("the ", "my mac", "my computer")):
                return _message_parts(name, _body(body_text))
    return None


def _message_parts(to: str, body: str | None) -> dict:
    cleaned = _cleanup_name(to)
    return {
        "to": None if _norm(cleaned) in _VAGUE_TO else cleaned or None,
        "body": body,
    }


def parse_message(text: str) -> dict | None:
    """Parse a clear message request without relying on the decision model."""
    return _parse_message_text(text)


def is_messaging(text: str) -> bool:
    """Whether the utterance names a message channel rather than email."""
    return bool(_MESSAGING_WORD.search(str(text or ""))) and \
        not _EMAIL_WORD.search(str(text or ""))


def verbatim_handle(text: str) -> dict | None:
    """Parse a literal phone number or email address, never a raw name."""
    value = str(text or "").strip().strip(".,!?;:")
    if _EMAIL.fullmatch(value):
        return {"kind": "email", "value": value.casefold(), "label": ""}
    if _PHONE.fullmatch(value):
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) >= 7:
            return {"kind": "phone",
                    "value": ("+" if value.lstrip().startswith("+") else "")
                    + digits, "label": ""}
    return None


def spoken_email(text: str) -> dict | None:
    """Convert a spoken email address such as 'arda at gmail dot com'."""
    value = str(text or "").strip().casefold()
    value = re.sub(r"\s+at\s+", "@", value)
    value = re.sub(r"\s+dot\s+", ".", value)
    parsed = verbatim_handle(value)
    return parsed if parsed and parsed["kind"] == "email" else None


def clean_query(to: str) -> str:
    value = str(to or "").strip()
    value = re.sub(r"^(?:(?:to\s+)?my\s+|to\s+)", "", value,
                   flags=re.IGNORECASE)
    value = re.sub(r"'s(?=[\s.,!?;:]|$)", "", value,
                   flags=re.IGNORECASE)
    return value.strip(" \t\r\n.,!?;:")


def _name_score(query: str, name: str, nickname: str | None) -> int:
    q = _norm(query)
    q_tokens = q.split()
    if not q_tokens:
        return 0
    names = [_norm(name), _norm(nickname or "")]
    name_tokens = [n.split() for n in names if n]
    if any(q == n for n in names if n):
        return 3
    tokens = name_tokens[0] if name_tokens else []
    if q in (tokens[:1] + tokens[-1:]) or any(
            set(q_tokens) <= set(toks) for toks in name_tokens):
        return 2
    for qt in q_tokens:
        if not any(
                qt == token or token.startswith(qt) or
                difflib.SequenceMatcher(None, qt, token).ratio() >= 0.8
                for toks in name_tokens for token in toks):
            return 0
    return 1


def rank(query: str, matches: list[dict]) -> list[dict]:
    """Keep the highest-ranked Contacts tier in Swift's returned order."""
    scored = []
    for contact in matches or []:
        handles = contact.get("handles") or []
        if not any(isinstance(h, dict) and h.get("kind") in ("phone", "email")
                   and h.get("value") for h in handles):
            continue
        score = _name_score(query, str(contact.get("name") or ""),
                            contact.get("nickname"))
        scored.append((score, contact))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    if best == 0:
        return [contact for _, contact in scored]
    return [contact for score, contact in scored if score == best]


def _label(handle: dict) -> str:
    value = str(handle.get("label") or "")
    match = _APPLE_LABEL.fullmatch(value)
    value = match.group(1) if match else value
    return value.strip().casefold() or str(handle.get("kind") or "").casefold()


def options(contacts: list[dict]) -> list[dict]:
    """Flatten Contacts into at most three options in Contacts order."""
    out = []
    for contact in contacts or []:
        handles = [
            h for h in contact.get("handles") or []
            if isinstance(h, dict) and h.get("kind") in ("phone", "email")
            and h.get("value")]
        handles.sort(key=lambda h: (
            0 if h.get("kind") == "phone" and
            _label(h) in ("mobile", "iphone") else
            1 if h.get("kind") == "phone" else 2))
        for handle in handles:
            out.append({
                "id": contact.get("id"),
                "name": str(contact.get("name") or ""),
                "handle": {
                    "kind": handle["kind"],
                    "value": str(handle["value"]),
                    "label": _label(handle),
                },
            })
            if len(out) == 3:
                return out
    return out


def display(opt: dict, opts: list[dict]) -> str:
    name = str(opt.get("name") or "")
    repeated = sum(o.get("id") == opt.get("id") for o in opts) > 1
    same_name = sum(o.get("name") == name for o in opts) > 1
    label = str((opt.get("handle") or {}).get("label") or "")
    shown = f"{name} ({label})" if (repeated or same_name) and label else name
    if sum(display_name == shown for display_name in
           [_base_display(o, opts) for o in opts]) > 1:
        handle = opt.get("handle") or {}
        value = str(handle.get("value") or "")
        suffix = "".join(c for c in value if c.isdigit())[-4:]
        disambiguator = suffix if handle.get("kind") == "phone" else value
        shown = f"{shown} {disambiguator}" if disambiguator else shown
    return shown


def _base_display(opt: dict, opts: list[dict]) -> str:
    name = str(opt.get("name") or "")
    repeated = sum(o.get("id") == opt.get("id") for o in opts) > 1
    same_name = sum(o.get("name") == name for o in opts) > 1
    label = str((opt.get("handle") or {}).get("label") or "")
    return f"{name} ({label})" if (repeated or same_name) and label else name


def question(opts: list[dict]) -> str:
    names = [display(opt, opts) for opt in opts]
    if len(names) == 2:
        return f"{names[0]} or {names[1]}?"
    if len(names) >= 3:
        return f"{', '.join(names[:-1])}, or {names[-1]}?"
    return f"{names[0]}?" if names else ""


def resolve_answer(
        text: str, opts: list[dict]) -> tuple[int | None, str | None]:
    answer = " ".join(str(text or "").casefold().split())
    if answer in _ORDINALS:
        index = _ORDINALS[answer]
        if index == -1:
            index = len(opts) - 1
        return (index, "ordinal") if 0 <= index < len(opts) else (None, None)

    answer_handle = verbatim_handle(answer) or spoken_email(answer)
    if answer_handle:
        matches = [i for i, opt in enumerate(opts)
                   if (opt.get("handle") or {}).get("kind") ==
                   answer_handle["kind"] and
                   (opt.get("handle") or {}).get("value", "").casefold() ==
                   answer_handle["value"].casefold()]
        if len(matches) == 1:
            return matches[0], "handle"

    all_words = [word for word in _norm(answer).split()
                 if word not in _ANSWER_STOP]
    label_words = set(all_words) & _LABEL_WORDS
    words = [word for word in all_words if word not in _LABEL_WORDS]
    if words:
        matches = []
        for i, opt in enumerate(opts):
            name_tokens = _norm(opt.get("name") or "").split()
            if all(any(word == token or
                       difflib.SequenceMatcher(None, word, token).ratio()
                       >= 0.85 for token in name_tokens)
                   for word in words):
                matches.append(i)
        if len(matches) > 1:
            if label_words:
                filtered = [i for i in matches if label_words &
                            set(_norm((opts[i].get("handle") or {}).get(
                                "label") or "").split())]
                if filtered:
                    matches = filtered
        if len(matches) == 1:
            return matches[0], "name"
        if matches and label_words:
            filtered = [i for i in matches if label_words &
                        set(_norm((opts[i].get("handle") or {}).get(
                            "label") or "").split())]
            if len(filtered) == 1:
                return filtered[0], "label"

    if label_words:
        label_matches = [
            i for i, opt in enumerate(opts)
            if label_words & set(_norm((opt.get("handle") or {}).get(
                "label") or "").split())
        ]
        if len(label_matches) == 1:
            return label_matches[0], "label"

    digits = "".join(c for c in answer if c.isdigit())
    if len(digits) >= 2:
        matches = [i for i, opt in enumerate(opts)
                   if (opt.get("handle") or {}).get("kind") == "phone"
                   and "".join(c for c in str((opt.get("handle") or {}).get(
                       "value") or "") if c.isdigit()).endswith(digits)]
        if len(matches) == 1:
            return matches[0], "digits"

    compact = _norm(answer).replace(" ", "")
    if compact:
        by_name: dict[str, tuple[str, list[int], float]] = {}
        for i, opt in enumerate(opts):
            name = str(opt.get("name") or "")
            key = _norm(name)
            tokens = key.split()
            candidates = [key]
            if len(tokens) >= 2:
                candidates.append(f"{tokens[0]}{tokens[-1]}")
            score = max(
                difflib.SequenceMatcher(
                    None, compact, candidate.replace(" ", "")).ratio()
                for candidate in candidates if candidate)
            old = by_name.get(key)
            if old:
                by_name[key] = (name, old[1] + [i], max(old[2], score))
            else:
                by_name[key] = (name, [i], score)
        ranked_names = sorted(by_name.items(), key=lambda item: -item[1][2])
        best_key, (_, best_indices, best_score) = ranked_names[0]
        second_score = ranked_names[1][1][2] if len(ranked_names) > 1 else 0
        if best_score >= 0.75 and best_score - second_score >= 0.10 and \
                len(best_indices) == 1:
            return best_indices[0], "fuzzy_name"
    return None, None


def _trace(orch, key: str, value: dict) -> None:
    trace = getattr(getattr(orch, "tracer", None), "current", None)
    if trace is not None:
        trace.setdefault("comms", []).append({key: value})


async def _rpc(orch, stage: str, method: str, params: dict,
               timeout: float) -> tuple[dict | None, str | None]:
    started = time.perf_counter()
    try:
        result = await orch.server.rpc(method, params, timeout=timeout)
        error = (str(result.get("error") or "rpc failed")
                 if isinstance(result, dict) and result.get("ok") is False
                 else None)
        traced = result
    except RuntimeError as exc:
        error = str(exc)
        result = None
        traced = {"error": error}
    elapsed = (time.perf_counter() - started) * 1000
    orch.tracer.rpc(method, params, traced, elapsed)
    orch.tracer.stage(f"comms_{stage}", elapsed)
    if isinstance(result, dict) and isinstance(result.get("result"), dict):
        result = {**result, **result["result"]}
    return result, error


def _say_name(to: str) -> str:
    value = str(to or "").strip()
    return value[:1].upper() + value[1:]


async def _fail(orch, message: str) -> str:
    await orch.server.say(message)
    await orch._end_ui("confused")
    return "failed"


async def _preview(orch, name: str, handle: dict, body: str,
                   contact_name: str | None = None) -> str:
    orch._comms = None
    orch._pending_task = None
    params = {"handle": handle["value"], "body": body}
    if contact_name is not None:
        params["name"] = contact_name
    result, error = await _rpc(orch, "compose", "messages_compose", params, 10)
    _trace(orch, "compose", {"result": result if error is None else {
        "error": error}})
    if error:
        if error == "screen_locked":
            message = "Unlock your screen first"
        elif error == "recipient_unverified":
            message = "Couldn't confirm that conversation, so I stopped"
        elif error == "no_text_target":
            message = "Couldn't find the Messages text box"
        elif error == "bad_handle":
            message = "That number or email doesn't look right"
        else:
            message = "Messages didn't come to the front"
        return await _fail(orch, message)
    if result.get("frontmost") is False:
        return await _fail(orch, "Messages didn't come to the front")
    if result.get("body_visible") is False:
        return await _fail(orch, "Couldn't put the text in Messages")

    label = str(handle.get("label") or "")
    excerpt = _excerpt(body, 8)
    summary = f"Send '{excerpt}' to {name}"
    if label:
        summary += f" ({label})"
    summary += "?"
    await orch.server.ui("thinking", summary)
    started = time.perf_counter()
    try:
        yes = await orch.server.ask_confirm(summary)
    except RuntimeError:
        yes = False
        timed_out = True
    else:
        timed_out = False
    elapsed = (time.perf_counter() - started) * 1000
    orch.tracer.stage("comms_confirm", elapsed)
    _trace(orch, "confirm", {"timeout": True} if timed_out else {"yes": yes})
    if not yes:
        await orch.server.say("Left it as a draft")
        await orch._end_ui("idle")
        return "cancelled"

    result, error = await _rpc(orch, "send", "messages_send", {}, 15)
    _trace(orch, "send", {"result": result if error is None else {
        "error": error}})
    if error:
        if error == "not_frontmost":
            message = "Messages isn't in front, so I didn't send"
        elif error == "screen_locked":
            message = "Unlock your screen first"
        else:
            message = "Message didn't send"
        return await _fail(orch, message)
    if not result.get("sent"):
        return await _fail(orch, "Message didn't send")
    await orch.server.say(f"Sent to {name}")
    await orch._end_ui("success")
    return "ok"


def _is_vague_to(to: str | None) -> bool:
    return _norm(str(to or "")) in _VAGUE_TO or \
        _norm(clean_query(str(to or ""))) in _VAGUE_TO


def _pending(orch, kind: str, to: str | None, body: str | None,
             from_planner: bool = False, **extra) -> None:
    orch._comms = {
        "kind": kind, "to": to, "body": body, "opts": [],
        "t": time.time(), "tries": 0, "from_planner": from_planner,
        **extra,
    }


async def start(orch, parsed: dict, text: str, *,
                from_planner: bool = False) -> str:
    to = parsed.get("to")
    body = _body(parsed.get("body"))
    if _is_vague_to(to):
        to = None
    if to is None:
        _pending(orch, "to", None, body, from_planner)
        _trace(orch, "ask", {"kind": "to"})
        await orch.server.say("Who should I text?")
        await orch.server.ui("listening")
        return "awaiting_user"
    if body is None:
        _pending(orch, "body", str(to), None, from_planner)
        spoken = _say_name(clean_query(str(to)))
        _trace(orch, "ask", {"kind": "body"})
        await orch.server.say(f"What should the message to {spoken} say?")
        await orch.server.ui("listening")
        return "awaiting_user"
    return await send_message(
        orch, to, body, from_planner=from_planner)


def _overlaps(left: dict, right: dict) -> bool:
    for first in left.get("handles") or []:
        for second in right.get("handles") or []:
            if first.get("kind") != second.get("kind"):
                continue
            if first.get("kind") == "phone":
                a = "".join(c for c in str(first.get("value") or "")
                            if c.isdigit())
                b = "".join(c for c in str(second.get("value") or "")
                            if c.isdigit())
                if a and b and a[-10:] == b[-10:]:
                    return True
            elif first.get("kind") == "email" and \
                    str(first.get("value") or "").casefold() == \
                    str(second.get("value") or "").casefold():
                return True
    return False


def _messages_contacts(people: list[dict]) -> list[dict]:
    out = []
    for person in people or []:
        handles = [dict(handle, label="") for handle in
                   person.get("handles") or []]
        out.append({
            "id": f'msg:{person.get("name") or ""}',
            "name": str(person.get("name") or ""),
            "handles": handles,
            "source": "messages",
        })
    return out


async def send_message(orch, to, body, *, from_planner=False) -> str:
    if _is_vague_to(to):
        return await start(orch, {"to": None, "body": body}, "",
                           from_planner=from_planner)
    if body is None or not str(body).strip():
        return await start(orch, {"to": to, "body": None}, "",
                           from_planner=from_planner)
    handle = verbatim_handle(to) or spoken_email(to)
    if handle:
        query = clean_query(str(to))
        _trace(orch, "resolve", {
            "query": query, "n_matches": 0,
            "n_ranked": 0, "verbatim": True, "source": "contacts",
            "n_people": 0})
        return await _preview(orch, str(to), handle, str(body or ""))

    query = clean_query(str(to or ""))
    old = getattr(orch, "_comms", None)
    tries = old.get("tries", 0) if old and old.get("kind") == "handle" else 0
    people_result, people_error = await _rpc(
        orch, "resolve", "messages_people", {"query": query, "limit": 5},
        MESSAGES_TIMEOUT_S)
    people = [] if people_error else people_result.get("people") or []
    message_contacts = _messages_contacts(people)
    mranked = rank(query, message_contacts)
    if len(mranked) == 1 and \
            _name_score(query, mranked[0]["name"], None) >= 2:
        ranked = mranked
        opts = options(ranked)[:1]
        matches = message_contacts
        source = "messages"
    else:
        result, error = await _rpc(
            orch, "resolve", "contacts_search",
            {"query": query, "limit": 5}, CONTACTS_TIMEOUT_S)
        if error and not message_contacts:
            _trace(orch, "resolve", {
                "query": query, "n_matches": 0, "n_ranked": 0,
                "verbatim": False, "source": "contacts",
                "n_people": len(people)})
            orch._comms = None
            if error == "contacts_denied":
                return await _fail(
                    orch, "Allow Contacts for Muselet in System Settings")
            return await _fail(orch, "Couldn't search your contacts")
        contacts = [] if error else result.get("matches") or []
        contact_matches = []
        for contact in contacts:
            if any(_overlaps(person, contact)
                   for person in message_contacts):
                continue
            contact_matches.append({**contact, "source": "contacts"})
        matches = message_contacts + contact_matches
        ranked = rank(query, matches)
        opts = options(ranked)
        sources = {item.get("source") for item in ranked}
        source = "both" if sources == {"messages", "contacts"} else \
            "messages" if "messages" in sources else "contacts"

    _trace(orch, "resolve", {
        "query": query, "n_matches": len(matches),
        "n_ranked": len(ranked), "verbatim": False,
        "source": source, "n_people": len(people)})
    if not opts:
        fuzzy_result, fuzzy_error = await _rpc(
            orch, "fuzzy_resolve", "contacts_search",
            {"query": query, "limit": 5, "fuzzy": True},
            CONTACTS_TIMEOUT_S)
        fuzzy_matches = [] if fuzzy_error else \
            fuzzy_result.get("matches") or []
        fuzzy_matches = sorted(
            fuzzy_matches,
            key=lambda item: float(item.get("score") or 0),
            reverse=True)
        fuzzy_matches = [
            {**contact, "source": "contacts"}
            for contact in fuzzy_matches
            if any(isinstance(handle, dict) and
                   handle.get("kind") in ("phone", "email") and
                   handle.get("value")
                   for handle in contact.get("handles") or [])
        ]
        opts = options(fuzzy_matches)
        if opts:
            orch._comms = {
                "kind": "choose", "to": str(to), "body": str(body),
                "opts": opts, "t": time.time(), "tries": 0,
                "from_planner": from_planner, "fuzzy": True,
            }
            prompt = f"Did you mean {display(opts[0], opts)}?" \
                if len(opts) == 1 else question(opts)
            _trace(orch, "ask", {
                "kind": "choose", "fuzzy": True,
                "options": [display(opt, opts) for opt in opts]})
            await orch.server.say(prompt)
            await orch.server.ui("listening")
            return "awaiting_user"
        spoken = _say_name(str(to))
        orch._comms = {
            "kind": "handle", "to": str(to), "body": str(body or ""),
            "opts": [], "t": time.time(), "tries": tries,
            "from_planner": from_planner,
        }
        _trace(orch, "ask", {"kind": "handle", "options": []})
        await orch.server.say(
            f"I couldn't find {spoken} in your contacts. "
            "What's their number or email?")
        await orch.server.ui("listening")
        return "awaiting_user"
    if len(opts) > 1:
        orch._comms = {
            "kind": "choose", "to": str(to), "body": str(body or ""),
            "opts": opts, "t": time.time(), "tries": 0,
            "from_planner": from_planner,
        }
        prompt = question(opts)
        _trace(orch, "ask", {
            "kind": "choose",
            "options": [display(o, opts) for o in opts]})
        await orch.server.say(prompt)
        await orch.server.ui("listening")
        return "awaiting_user"
    opt = opts[0]
    return await _preview(orch, opt["name"], opt["handle"], str(body or ""),
                          contact_name=opt["name"])


async def answer(orch, text: str) -> str:
    pending = getattr(orch, "_comms", None)
    if not pending:
        return "failed"
    orch._pending_task = None
    if slots.CANCEL.fullmatch(str(text or "").strip()):
        if pending["kind"] == "choose" and pending.get("fuzzy") and \
                _norm(text) in {"no", "nope"}:
            pending.update(kind="handle", opts=[], tries=0)
            _trace(orch, "ask", {"kind": "handle", "options": []})
            await orch.server.say("What's their number or email?")
            await orch.server.ui("listening")
            return "awaiting_user"
        orch._comms = None
        _trace(orch, "answer", {
            "text": text, "how": "cancel", "index": None})
        await orch.server.say("Okay, cancelled")
        await orch._end_ui("idle")
        return "cancelled"

    if pending["kind"] in {"handle", "choose", "body", "to"}:
        parsed = parse_message(text)
        if parsed is not None:
            orch._comms = None
            _trace(orch, "answer", {"text": text, "how": "restart",
                                    "index": None})
            return await start(orch, parsed, text)

    handle = verbatim_handle(text) or spoken_email(text)
    if pending["kind"] == "handle":
        if not handle and orch.engine is not None:
            from .planner import worker
            routed = await worker().submit_async(
                orch.engine.route, text, dict(orch._ctx))
            spec = orch.catalog.get(routed.top)
            if routed.top == "send_message" and routed.p_top >= 0.8:
                orch._comms = None
                return await orch._engine_route(
                    text, orch.tracer.current, pre=routed)
            if spec and routed.p_top >= 0.8:
                orch._comms = None
                return await orch._engine_route(
                    text, orch.tracer.current, pre=routed)
        _trace(orch, "answer", {
            "text": text, "how": "handle" if handle else "name",
            "index": None})
        if handle:
            return await _preview(orch, str(text), handle, pending["body"])
        if pending["tries"] >= 1:
            orch._comms = None
            return await _fail(orch, "Sorry, I didn't catch that")
        pending["tries"] += 1
        return await send_message(orch, text, pending["body"],
                                  from_planner=pending.get("from_planner",
                                                           False))

    if pending["kind"] == "body":
        if orch.engine is not None:
            from .planner import worker
            routed = await worker().submit_async(
                orch.engine.route, text, dict(orch._ctx))
            spec = orch.catalog.get(routed.top)
            say_lead = re.match(
                r"^(?:say|it should say|tell (?:him|her|them)|that)\b",
                text.strip(), re.IGNORECASE)
            if routed.top not in {
                    "send_message", "type_text", "compose_email",
                    "draft_email", "new_note"} and spec and \
                    routed.p_top >= 0.8 and not say_lead:
                orch._comms = None
                return await orch._engine_route(
                    text, orch.tracer.current, pre=routed)
        body = slots.clean_answer(text, "string")
        body = _body(body)
        if body is None:
            pending["tries"] += 1
            if pending["tries"] >= 2:
                orch._comms = None
                return await _fail(orch, "Sorry, I didn't catch that")
            pending["t"] = time.time()
            await orch.server.say(
                f"What should the message to "
                f"{_say_name(clean_query(pending['to']))} say?")
            await orch.server.ui("listening")
            return "awaiting_user"
        _trace(orch, "answer", {"text": text, "how": "body",
                                "index": None})
        return await send_message(
            orch, pending["to"], body,
            from_planner=pending.get("from_planner", False))

    if pending["kind"] == "to":
        if handle:
            name = str(text)
        else:
            name = slots.clean_answer(text, "contact")
        if _is_vague_to(name):
            pending["tries"] += 1
            if pending["tries"] >= 2:
                orch._comms = None
                return await _fail(orch, "Sorry, I didn't catch that")
            pending["t"] = time.time()
            await orch.server.say("Who should I text?")
            await orch.server.ui("listening")
            return "awaiting_user"
        _trace(orch, "answer", {
            "text": text, "how": "handle" if handle else "name",
            "index": None})
        if pending.get("body") is None:
            return await start(
                orch, {"to": name, "body": None}, text,
                from_planner=pending.get("from_planner", False))
        return await send_message(
            orch, name, pending["body"],
            from_planner=pending.get("from_planner", False))

    index, how = (None, None) if handle else resolve_answer(
        text, pending["opts"])
    if index is None and pending["kind"] == "choose" and \
            pending.get("fuzzy") and len(pending["opts"]) == 1 and \
            _norm(text) in {
                "yes", "yeah", "yep", "yes please", "sure", "correct",
                "that's right", "right",
            }:
        index, how = 0, "yes"
    _trace(orch, "answer", {
        "text": text, "how": "handle" if handle else how,
        "index": index})
    if handle:
        return await _preview(orch, str(text), handle, pending["body"])
    if index is not None:
        opt = pending["opts"][index]
        return await _preview(orch, opt["name"], opt["handle"],
                              pending["body"], contact_name=opt["name"])

    if orch.engine is not None:
        from .planner import worker
        routed = await worker().submit_async(
            orch.engine.route, text, dict(orch._ctx))
        spec = orch.catalog.get(routed.top)
        if routed.top == "send_message" and routed.p_top >= 0.8:
            orch._comms = None
            return await orch._engine_route(text, orch.tracer.current,
                                            pre=routed)
        if spec and routed.p_top >= 0.8:
            orch._comms = None
            return await orch._engine_route(text, orch.tracer.current,
                                            pre=routed)
    pending["tries"] += 1
    if pending["tries"] >= 2:
        orch._comms = None
        return await _fail(orch, "Sorry, I didn't catch that")
    _trace(orch, "ask", {
        "kind": "choose",
        "options": [display(o, pending["opts"])
                    for o in pending["opts"]]})
    await orch.server.say(question(pending["opts"]))
    await orch.server.ui("listening")
    return "awaiting_user"
