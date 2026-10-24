"""Message helpers for the app <-> brain WebSocket protocol (AGENTS.md).

One JSON object per frame; `t` = message type.
"""

import json

# App -> brain: hello, utterance, cancel, rpc_result, confirm_reply
# Brain -> app: rpc, ui, say, confirm


def encode(msg: dict) -> str:
    return json.dumps(msg)


def parse(raw) -> dict:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def hello(screens: list) -> dict:
    return {"t": "hello", "screens": screens}


def utterance(uid: str, text: str, final: bool = True,
              ctx: dict | None = None) -> dict:
    m = {"t": "utterance", "id": uid, "text": text, "final": final}
    if ctx is not None:
        m["ctx"] = ctx
    return m


def rpc(rid: str, method: str, params: dict) -> dict:
    return {"t": "rpc", "id": rid, "method": method, "params": params}


def rpc_result(rid: str, ok: bool, result=None, error=None) -> dict:
    m = {"t": "rpc_result", "id": rid, "ok": ok}
    if ok and result is not None:
        m["result"] = result
    if not ok:
        m["error"] = error or "error"
    return m


def ui(mascot: str, bubble: str | None = None) -> dict:
    m = {"t": "ui", "mascot": mascot}
    if bubble is not None:
        m["bubble"] = bubble
    return m


def say(text: str) -> dict:
    return {"t": "say", "text": text}


def confirm(cid: str, summary: str) -> dict:
    return {"t": "confirm", "id": cid, "summary": summary}


def confirm_reply(cid: str, yes: bool) -> dict:
    return {"t": "confirm_reply", "id": cid, "yes": yes}
