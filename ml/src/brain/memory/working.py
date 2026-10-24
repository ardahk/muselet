"""Small, privacy-conscious working memory for recent turns."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


BROWSERS = {
    "safari", "google chrome", "chrome", "zen", "arc", "firefox",
    "brave browser", "microsoft edge",
}
_COMMS = {"send_message", "compose_email", "draft_email", "compose_text"}
_REDACTED = "[message body redacted]"


def site_for_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = (urlsplit(str(url)).hostname or "").casefold().rstrip(".")
    except ValueError:
        return None
    while host.startswith(("www.", "m.", "en.")):
        host = host.split(".", 1)[1]
    if not host:
        return None
    if host == "google.com" and urlsplit(str(url)).path.startswith("/maps"):
        return "maps.google.com"
    if host in {"maps.google.com", "mail.google.com",
                "developer.mozilla.org", "news.ycombinator.com",
                "docs.python.org"}:
        return host
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) > 1 else host


def _safe_args(skill: str, args: dict | None) -> dict:
    result = dict(args or {})
    keys = {"body", "text", "message", "content"}
    for key in keys:
        result.pop(key, None)
    return result


def _safe_turn_text(value: str, skill: str, private: bool = False) -> str:
    if private:
        return "[text redacted]"
    if skill in _COMMS:
        return f"{skill} {_REDACTED}"
    if skill == "type_text":
        return "type_text [text redacted]"
    if re.match(r"^(?:send|text|message|email|mail|compose|tell)\b",
                value.strip(), re.IGNORECASE):
        return f"[communication request redacted]"
    return value


@dataclass
class Turn:
    t: float
    utterance: str
    resolved: str
    skill: str | None
    args: dict = field(default_factory=dict)
    ok: bool = False
    said: str | None = None
    app: str | None = None
    window_title: str | None = None
    url: str | None = None
    site: str | None = None
    result: dict = field(default_factory=dict)


class WorkingMemory:
    def __init__(self, maxlen: int = 8, ttl_s: float = 600.0,
                 path: Path | None = None):
        self.maxlen = maxlen
        self.ttl_s = ttl_s
        self.path = Path(path) if path is not None else None
        self.turns: deque[Turn] = deque(maxlen=maxlen)
        self._focus: dict[str, tuple[object, float]] = {}

    def record(self, utterance: str, resolved: str, skill: str | None,
               args: dict | None, ok: bool, ctx: dict, said: str | None = None,
               t: float | None = None, result: dict | None = None) -> None:
        now = float(time.time() if t is None else t)
        skill = skill or None
        stored_args = dict(args or {})
        turn_result = {
            k: v for k, v in (result or {}).items()
            if k in {"previous", "level_before"}
        }
        url = str((ctx or {}).get("url") or "")
        if skill == "open_url" and ok:
            url = str(stored_args.get("url") or url)
        app = (ctx or {}).get("app")
        title = (ctx or {}).get("window_title")
        turn = Turn(
            t=now, utterance=str(utterance), resolved=str(resolved),
            skill=skill, args=stored_args, ok=bool(ok),
            said=str(said) if said else None,
            app=str(app) if app is not None else None,
            window_title=str(title) if title is not None else None,
            url=url or None, site=site_for_url(url), result=turn_result)
        self.turns.append(turn)

        if ok:
            def put(key, value):
                if value is not None and value != "":
                    self._focus[key] = (value, now)

            if skill == "open_url" and url:
                put("url", url)
                put("site", site_for_url(url))
            elif app and str(app).casefold() not in BROWSERS:
                self._focus.pop("url", None)
                self._focus.pop("site", None)
            elif url:
                put("url", url)
                put("site", site_for_url(url))
            if skill == "web_search":
                put("query", stored_args.get("query"))
            if skill in _COMMS:
                put("contact", stored_args.get("to"))
                put("contact_skill", skill)
            if skill in {"open_file", "open_folder", "find_file",
                         "new_folder"}:
                put("file", stored_args.get("path"))
            if skill in {"open_app", "quit_app", "hide_app"}:
                put("app", stored_args.get("app"))
        self.save()

    def focus(self, now: float, ctx: dict | None = None) -> dict:
        live = {
            key: value for key, (value, stamp) in self._focus.items()
            if now - stamp <= self.ttl_s
        }
        app = (ctx or {}).get("app")
        browser_or_unknown = not app or str(app).casefold() in BROWSERS
        if not browser_or_unknown:
            live.pop("url", None)
            live.pop("site", None)
        current_url = (ctx or {}).get("url")
        if current_url and browser_or_unknown:
            live["url"] = str(current_url)
            live["site"] = site_for_url(str(current_url))
        return live

    def last(self, now: float) -> Turn | None:
        for turn in reversed(self.turns):
            if 0 <= now - turn.t <= self.ttl_s:
                return turn
        return None

    def recent_lines(self, n: int = 5, now: float | None = None) -> list[str]:
        return self._recent_lines(n, now, private=False)

    def recent_detail_lines(self, n: int = 5,
                            now: float | None = None) -> list[str]:
        return self._recent_lines(n, now, private=True)

    def _recent_lines(self, n: int, now: float | None,
                      private: bool) -> list[str]:
        if n <= 0:
            return []
        now = time.time() if now is None else now
        turns = [turn for turn in self.turns
                 if 0 <= now - turn.t <= self.ttl_s]
        lines = []
        for turn in turns[-max(0, n):]:
            content_keys = {"body", "text", "message", "content"}
            has_private = any(key in content_keys for key in turn.args)
            args_dict = (turn.args if private else
                         _safe_args(turn.skill or "", turn.args))
            args = " ".join(f"{key}={value}"
                            for key, value in args_dict.items())
            action = " ".join(part for part in (turn.skill, args) if part)
            utterance = (turn.utterance if private else
                         _safe_turn_text(turn.utterance, turn.skill or "",
                                         has_private))
            line = f"{utterance} → {action} {'ok' if turn.ok else 'failed'}"
            lines.append(line[:400 if private else 80])
        return lines

    def save(self) -> None:
        if self.path is None:
            return
        tmp_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "turns": [self._safe_turn(turn) for turn in self.turns],
                "focus": {
                    key: {"value": value, "t": stamp}
                    for key, (value, stamp) in self._focus.items()
                },
            }
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self.path.parent,
                    prefix=f".{self.path.name}.", suffix=".tmp",
                    delete=False) as f:
                tmp_path = Path(f.name)
                json.dump(payload, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _safe_turn(turn: Turn) -> dict:
        row = asdict(turn)
        has_private = any(key in {"body", "text", "message", "content"}
                          for key in turn.args)
        row["utterance"] = _safe_turn_text(
            turn.utterance, turn.skill or "", has_private)
        row["resolved"] = _safe_turn_text(
            turn.resolved, turn.skill or "", has_private)
        row["said"] = (_safe_turn_text(
            turn.said, turn.skill or "", has_private)
            if turn.said else None)
        row["args"] = _safe_args(turn.skill or "", turn.args)
        return row

    @classmethod
    def from_history(cls, history: list[dict], now_ctx: dict):
        memory = cls()
        for item in history:
            ctx = dict(item.get("ctx") or {})
            outcome = item.get("outcome") or {}
            memory.record(
                item.get("utterance", ""),
                item.get("resolved", item.get("utterance", "")),
                outcome.get("skill"), outcome.get("args", {}),
                bool(outcome.get("ok")), ctx,
                said=outcome.get("said"), t=ctx.get("t", 0.0),
                result=outcome.get("result"))
        return memory
