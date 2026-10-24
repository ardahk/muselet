"""One call that runs every check and returns a JSON-ready report with evidence."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from statistics import median

from . import evidence as ev
from .budget import budget_report, category_spend
from .categorize import INCOME, Decide, categorize_with_evidence, is_refund_text
from .detect import (
    OUTLIER_FLOOR,
    OUTLIER_Z,
    find_duplicates,
    find_outliers,
    find_refunds,
    outlier_scores,
    reversed_debit,
    weekend_charges,
)
from .receipts import reconcile_receipts
from .statement import CENT, Txn, balance_breaks, opening_balance


def analyze(txns: list[Txn], budget: Mapping[str, Decimal], receipts=None, decide: Decide | None = None,
            user_rules: Mapping[str, str] | None = None) -> dict:
    by_row = {t.row: t for t in txns}
    cats, why = categorize_with_evidence(txns, list(budget), decide, user_rules)
    flags: list[ev.Flag] = []

    breaks = balance_breaks(txns)
    flags += [ev.balance_break(by_row[r]) for r in breaks]

    dups = find_duplicates(txns)
    flags += [ev.duplicate(by_row[a], by_row[b]) for a, b in dups]

    cat_of = {r: c for r, (c, _, _) in cats.items()}
    outliers = find_outliers(txns, cat_of)
    scores = outlier_scores(txns, cat_of)
    for r in outliers:
        z, group = scores[r]
        members = [-by_row[x].amount for x, (_, g) in scores.items() if g == group]
        flags.append(ev.outlier(by_row[r], z, group, Decimal(median(members)).quantize(CENT), OUTLIER_Z,
                                OUTLIER_FLOOR))

    refunds = find_refunds(txns)
    flags += [ev.refund(by_row[r], reversed_debit(txns, r), is_refund_text(by_row[r].description)) for r in refunds]

    weekend = weekend_charges(txns)
    if weekend:
        flags.append(ev.weekend(weekend))

    asks: dict[str, list[int]] = {}
    for r, (c, p, src) in cats.items():
        if src == "ask":
            asks.setdefault(by_row[r].description, []).append(r)
    ask_list = []
    for desc, rows in asks.items():
        c, p, _ = cats[rows[0]]
        flags.append(ev.ask_category(desc, rows, c, p, why[rows[0]]))
        ask_list.append({"description": desc, "rows": rows, "guess": c, "p": round(p, 3), "options": list(budget)})

    spend = category_spend(txns, cats)
    spend_all = {c: spend.get(c, Decimal("0.00")) for c in budget} | {c: v for c, v in spend.items() if c not in budget}
    rep = budget_report(spend_all, budget)
    for c in rep["over_budget"]:
        rows = [r for r, (cc, _, _) in cats.items() if cc == c]
        flags.append(ev.over_budget(c, rows, budget[c], rep["actual"][c], rep["remaining"][c]))

    rec = {}
    if receipts is not None:
        rec = reconcile_receipts(receipts, txns)
        flags += [ev.receipt(rid, e) for rid, e in rec.items()]

    income = sum((t.amount for t in txns if cat_of[t.row] == INCOME), Decimal("0.00"))
    total_spend = sum(spend.values(), Decimal("0.00"))
    opening = opening_balance(txns)
    return {
        "statement": {
            "rows": len(txns),
            "total_income": income,
            "total_spend": total_spend,
            "net": income - total_spend,
            "opening_balance": opening,
            "closing_balance": txns[-1].balance if txns else opening,
            "balance_ok": not breaks and (not txns or opening + income - total_spend == txns[-1].balance),
        },
        "rows": [{"row": r, "category": c, "confidence": round(p, 3), "source": s, "rule": why[r]}
                 for r, (c, p, s) in sorted(cats.items())],
        "duplicates": [list(p) for p in dups],
        "outliers": outliers,
        "refunds": refunds,
        "weekend_charges": weekend,
        "balance_breaks": breaks,
        "category_spend": spend_all,
        "budget": {"budget": dict(budget), **rep},
        "receipts": rec,
        "ask": ask_list,
        "complete": not ask_list,
        "flags": [f.to_dict() for f in flags],
    }


def jsonable(obj):
    """Decimals -> JSON numbers (cents are exact in float's shortest repr), tuples -> lists."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, Mapping):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    return obj
