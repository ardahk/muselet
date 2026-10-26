"""Shared helpers for LH fixture graders (lead-authored)."""

import re

EGGS = {"eggs-large-dozen", "eggs-large-18", "eggs-brown-dozen"}
WHOLE_MILK = {"milk-whole-gal", "milk-whole-half"}
BUTTER = {"butter-unsalted", "butter-salted"}
BANANAS = {"banana", "banana-organic"}
AAA = {"batt-aaa-4", "batt-aaa-8", "batt-aaa-recharge"}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


def _plain(s) -> str:
    """Lowercase, punctuation removed, single spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9@. ]+", " ", _norm(s))).strip()


def _digits(s) -> str:
    return re.sub(r"\D+", "", str(s or ""))


def _cart(state) -> dict:
    return {k: int(v) for k, v in state["mart"]["cart"].items() if int(v) > 0}


def _visited(state, prefix: str) -> bool:
    return any(str(v.get("path", "")).startswith(prefix) for v in state.get("visits", []))


def _result(passed: bool, reason: str, milestones: dict) -> dict:
    return {"passed": bool(passed), "reason": reason if not passed else "ok",
            "milestones": {k: bool(v) for k, v in milestones.items()}}


def _qty(cart: dict, ids) -> int:
    return sum(q for p, q in cart.items() if p in ids)


def _extras(cart: dict, allowed) -> list:
    return sorted(p for p in cart if p not in allowed)


def _street(s: str) -> str:
    s = _plain(s)
    for short, full in (("st", "street"), ("ave", "avenue"), ("rd", "road")):
        s = re.sub(rf"\b{short}\b\.?", full, s)
    return re.sub(r"\s+", " ", s).strip(" .")
