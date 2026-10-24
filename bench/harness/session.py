"""Fail-closed session precondition for live benchmark cases."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable


def probe_session(
    hands_bin: str,
    *,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    try:
        result = run(
            [hands_bin, "probe", "session"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "skip_reason": "session_unverifiable",
            "session_probe": None,
            "session_probe_error": str(exc),
        }

    try:
        session = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        session = None

    if result.returncode != 0:
        return {
            "skip_reason": "session_unverifiable",
            "session_probe": session if isinstance(session, dict) else None,
            "session_probe_error": f"probe exited {result.returncode}",
        }
    if not isinstance(session, dict) or not isinstance(session.get("screen_locked"), bool):
        return {
            "skip_reason": "session_unverifiable",
            "session_probe": session if isinstance(session, dict) else None,
            "session_probe_error": "invalid session probe JSON",
        }
    if session["screen_locked"] is True or session.get("main_display_asleep") is True:
        return {"skip_reason": "screen_locked", "session_probe": session}
    return {"skip_reason": None, "session_probe": session}
