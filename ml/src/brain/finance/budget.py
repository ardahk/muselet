"""Category spend (debits minus refunds) and the budget table's Actual / Remaining / over-budget."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .categorize import INCOME
from .statement import CENT, Txn

ZERO = Decimal("0.00")


def _cat(v) -> str:
    return v[0] if isinstance(v, tuple) else v


def category_spend(txns: list[Txn], cats: Mapping[int, object]) -> dict[str, Decimal]:
    """{category: spend}; debits add, credits in a spending category (refunds) subtract. Income is excluded.

    `cats` is row -> category, or the row -> (category, confidence, source) map from `categorize`.
    """
    out: dict[str, Decimal] = {}
    for t in txns:
        c = _cat(cats[t.row])
        if c == INCOME:
            continue
        out[c] = (out.get(c, ZERO) - t.amount).quantize(CENT)
    return out


def budget_report(spend: Mapping[str, Decimal], budget: Mapping[str, Decimal]) -> dict:
    """{actual, remaining, over_budget} over the budget's categories in budget order.

    Spend in categories the budget does not list is reported under `unbudgeted` (only when present).
    """
    actual = {c: Decimal(spend.get(c, ZERO)).quantize(CENT) for c in budget}
    remaining = {c: (Decimal(budget[c]) - actual[c]).quantize(CENT) for c in budget}
    rep = {"actual": actual, "remaining": remaining, "over_budget": [c for c in budget if remaining[c] < 0]}
    extra = {c: v for c, v in spend.items() if c not in budget}
    if extra:
        rep["unbudgeted"] = extra
    return rep
