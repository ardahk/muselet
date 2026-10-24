"""Category spend (debits minus refunds) and the budget table's Actual / Remaining / over-budget."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .categorize import INCOME, UNCATEGORIZED
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


def _sum(ts) -> Decimal:
    return sum((t.amount for t in ts), ZERO).quantize(CENT)


def pending(txns: list[Txn], cats: Mapping[int, object]) -> dict:
    """Unresolved ("ask") rows, grouped by what they would change once answered.

    {rows, debits, credits (positive totals), credit_rows,
     by_category: {guessed category: {rows, amount}}   (model guess below the threshold; amount = spend effect)
     income: {rows, amount}                            (credits the model guessed as Income)
     unassigned: {rows, debits, credits}}              (no guess: could belong anywhere)
    """
    rows = [t for t in txns if _is_ask(cats[t.row])]
    by_cat: dict[str, list[Txn]] = {}
    income, unassigned = [], []
    for t in rows:
        guess = _cat(cats[t.row])
        if guess == INCOME:
            income.append(t)
        elif guess in (UNCATEGORIZED, None, ""):
            unassigned.append(t)
        else:
            by_cat.setdefault(guess, []).append(t)
    return {"rows": [t.row for t in rows],
            "debits": -_sum(t for t in rows if t.amount < 0),
            "credits": _sum(t for t in rows if t.amount > 0),
            "credit_rows": [t.row for t in rows if t.amount > 0],
            "by_category": {c: {"rows": [t.row for t in ts], "amount": -_sum(ts)} for c, ts in by_cat.items()},
            "income": {"rows": [t.row for t in income], "amount": _sum(income)},
            "unassigned": {"rows": [t.row for t in unassigned],
                           "debits": -_sum(t for t in unassigned if t.amount < 0),
                           "credits": _sum(t for t in unassigned if t.amount > 0)}}


def budget_report(spend: Mapping[str, Decimal], budget: Mapping[str, Decimal], pending: Mapping | None = None) -> dict:
    """{actual, remaining, over_budget} over the budget's categories in budget order.

    Spend in categories the budget does not list is reported under `unbudgeted` (only when present). With
    `pending` (unresolved rows), `actual` covers resolved rows only. `partial` / `needs_review` name exactly the
    categories an unresolved row was tentatively guessed into (their Actual is partial); rows with no guess are
    `pending.unassigned` and are shown as their own "Needs review" line rather than smeared over categories.
    """
    actual = {c: Decimal(spend.get(c, ZERO)).quantize(CENT) for c in budget}
    remaining = {c: (Decimal(budget[c]) - actual[c]).quantize(CENT) for c in budget}
    rep = {"actual": actual, "remaining": remaining, "over_budget": [c for c in budget if remaining[c] < 0]}
    if pending and pending.get("rows"):
        rep["pending"] = dict(pending)
        by_cat = pending.get("by_category", {})
        rep["partial"] = {c: by_cat[c] for c in budget if c in by_cat}
        rep["needs_review"] = list(rep["partial"])
    extra = {c: v for c, v in spend.items() if c not in budget}
    if extra:
        rep["unbudgeted"] = extra
    return rep
