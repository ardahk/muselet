"""Category spend (debits minus refunds) and the budget table's Actual / Remaining / over-budget."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .categorize import INCOME
from .statement import CENT, Txn

ZERO = Decimal("0.00")


def _cat(v) -> str:
    return v[0] if isinstance(v, tuple) else v


def _is_ask(v) -> bool:
    return isinstance(v, tuple) and len(v) > 2 and v[2] == "ask"


def category_spend(txns: list[Txn], cats: Mapping[int, object]) -> dict[str, Decimal]:
    """{category: spend}; debits add, credits in a spending category (refunds) subtract. Income is excluded.

    `cats` is row -> category, or the row -> (category, confidence, source) map from `categorize`. Rows whose
    source is "ask" are unresolved: they are left out (see `pending`), never counted on a guess.
    """
    out: dict[str, Decimal] = {}
    for t in txns:
        c = _cat(cats[t.row])
        if c == INCOME or _is_ask(cats[t.row]):
            continue
        out[c] = (out.get(c, ZERO) - t.amount).quantize(CENT)
    return out


def pending(txns: list[Txn], cats: Mapping[int, object]) -> dict:
    """Unresolved ("ask") rows: {rows, debits, credits} (debits as a positive total)."""
    rows = [t for t in txns if _is_ask(cats[t.row])]
    return {"rows": [t.row for t in rows],
            "debits": sum((-t.amount for t in rows if t.amount < 0), ZERO).quantize(CENT),
            "credits": sum((t.amount for t in rows if t.amount > 0), ZERO).quantize(CENT)}


def budget_report(spend: Mapping[str, Decimal], budget: Mapping[str, Decimal], pending: Mapping | None = None) -> dict:
    """{actual, remaining, over_budget} over the budget's categories in budget order.

    Spend in categories the budget does not list is reported under `unbudgeted` (only when present). With
    `pending` (unresolved rows), `actual` covers resolved rows only, and `needs_review` lists the categories
    whose over/under status could still change: resolved remaining - pending debits < 0 <= remaining + pending
    credits (any unresolved row could belong to any category).
    """
    actual = {c: Decimal(spend.get(c, ZERO)).quantize(CENT) for c in budget}
    remaining = {c: (Decimal(budget[c]) - actual[c]).quantize(CENT) for c in budget}
    rep = {"actual": actual, "remaining": remaining, "over_budget": [c for c in budget if remaining[c] < 0]}
    if pending and pending.get("rows"):
        up, down = Decimal(pending["debits"]), Decimal(pending["credits"])
        rep["pending"] = dict(pending)
        rep["needs_review"] = [c for c in budget if remaining[c] - up < 0 <= remaining[c] + down]
    extra = {c: v for c, v in spend.items() if c not in budget}
    if extra:
        rep["unbudgeted"] = extra
    return rep
