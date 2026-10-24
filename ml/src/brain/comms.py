"""Messages RPC contract:
- `contacts_search {query, limit:5}` ->
  `{matches:[{id, name, nickname?, handles:[{kind:"phone"|"email", value,
  label}]}], ms}`
  Errors: `contacts_denied` (no Contacts permission).
- `messages_compose {handle, body}` ->
  `{ok, frontmost, window_title, body_visible}`: opens Messages on that
  recipient's conversation with `body` in the compose field; never sends.
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


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


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


async def _preview(orch, name: str, handle: dict, body: str) -> str:
    orch._comms = None
    orch._pending_task = None
    params = {"handle": handle["value"], "body": body}
    result, error = await _rpc(orch, "compose", "messages_compose", params, 10)
    _trace(orch, "compose", {"result": result if error is None else {
        "error": error}})
    if error:
        if error == "screen_locked":
            message = "Unlock your screen first"
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


async def send_message(orch, to, body, *, from_planner=False) -> str:
    handle = verbatim_handle(to) or spoken_email(to)
    if handle:
        query = clean_query(str(to))
        _trace(orch, "resolve", {
            "query": query, "n_matches": 0,
            "n_ranked": 0, "verbatim": True})
        return await _preview(orch, str(to), handle, str(body or ""))

    query = clean_query(str(to or ""))
    old = getattr(orch, "_comms", None)
    tries = old.get("tries", 0) if old and old.get("kind") == "handle" else 0
    result, error = await _rpc(
        orch, "resolve", "contacts_search", {"query": query, "limit": 5},
        CONTACTS_TIMEOUT_S)
    if error == "contacts_denied":
        _trace(orch, "resolve", {
            "query": query, "n_matches": 0,
            "n_ranked": 0, "verbatim": False})
        orch._comms = None
        return await _fail(
            orch, "Allow Contacts for Muselet in System Settings")
    if error:
        _trace(orch, "resolve", {
            "query": query, "n_matches": 0,
            "n_ranked": 0, "verbatim": False})
        orch._comms = None
        return await _fail(orch, "Couldn't search your contacts")
    matches = result.get("matches") or []
    ranked = rank(query, matches)
    opts = options(ranked)
    _trace(orch, "resolve", {
        "query": query, "n_matches": len(matches),
        "n_ranked": len(ranked), "verbatim": False})
    if not opts:
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
    return await _preview(orch, opt["name"], opt["handle"], str(body or ""))


async def answer(orch, text: str) -> str:
    pending = getattr(orch, "_comms", None)
    if not pending:
        return "failed"
    orch._pending_task = None
    if slots.CANCEL.fullmatch(str(text or "").strip()):
        orch._comms = None
        _trace(orch, "answer", {
            "text": text, "how": "cancel", "index": None})
        await orch.server.say("Okay, cancelled")
        await orch._end_ui("idle")
        return "cancelled"

    handle = verbatim_handle(text) or spoken_email(text)
    if pending["kind"] == "handle":
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

    index, how = (None, None) if handle else resolve_answer(
        text, pending["opts"])
    _trace(orch, "answer", {
        "text": text, "how": "handle" if handle else how,
        "index": index})
    if handle:
        return await _preview(orch, str(text), handle, pending["body"])
    if index is not None:
        opt = pending["opts"][index]
        return await _preview(orch, opt["name"], opt["handle"],
                              pending["body"])

    if orch.engine is not None:
        from .planner import worker
        routed = await worker().submit_async(
            orch.engine.route, text, dict(orch._ctx))
        spec = orch.catalog.get(routed.top)
        if routed.top != "send_message" and spec and routed.p_top >= 0.8:
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
