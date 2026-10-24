"""Shared builder for synthetic planner demo states (same Screen builder + sc() fields as evals/planner_v2_*)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "evals"))
import planner_v2_lib as L  # noqa: E402
import planner_v2_screens as S  # noqa: E402

Screen, q = L.Screen, L.q
STATES: list[dict] = []
ND = [r"^done\b"]
ASK = [r"^ask\b"]


def st(family: str, cat: str, goal: str, screen, **kw) -> dict:
    """Register one state (validated later by build.py). kw = planner_v2_lib.sc kwargs (accept, reject, gold, ...)."""
    n = sum(s["family"] == family for s in STATES)
    L.sc(f"{family}-{n:04d}", cat, goal, screen, **kw)
    s = L.SCENARIOS.pop()
    s["id"] = f"syn-{family}-{n:04d}"
    s["family"], s["source"] = family, "synthetic"
    STATES.append(s)
    return s


def ci(text: str) -> str:
    """case-insensitive regex for literal text (letters only; everything else escaped)"""
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() and c.lower() != c.upper() else re.escape(c) for c in text)


LOCS = {"Desktop": "desktop", "Documents": "documents", "Downloads": "downloads", "Pictures": "pictures",
        "Movies": "movies", "Music": "music"}


def path_rx(loc: str, *sub: str) -> str:
    """a path value for ~/<loc>/<sub...> in any spelling the brain normalizes (~/X, /Users/u/X, x, my x)"""
    rest = "".join("/" + ci(s) for s in sub)
    core = rf"(?:~/|/Users/[^/\"\s]+/|(?:my |the )?){ci(loc)}{rest}/?"
    return rf'(?:"{core}"|{core}(?=\s|$))' if " " not in "".join(sub) else rf'"{core}"'


def dsl_q(text: str) -> str:
    """text as it appears inside a DSL "..." string (newline -> \\n, quote -> \\")"""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
