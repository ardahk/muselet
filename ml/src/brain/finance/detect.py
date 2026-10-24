"""Deterministic statement checks: duplicates, outliers, weekend charges, refunds."""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from .statement import Txn, normalize_merchant

# Outlier rule (Iglewicz & Hoaglin modified z-score), per spending category:
#   z = 0.6745 * (|amount| - median) / MAD, flagged when z >= OUTLIER_Z and |amount| >= OUTLIER_FLOOR.
# Groups with fewer than OUTLIER_MIN_GROUP debits are pooled with all discretionary debits. Fixed/recurring
# categories (income, rent, utilities, subscriptions) are never outliers; their size is expected.
OUTLIER_Z = Decimal("3.5")
OUTLIER_FLOOR = Decimal("200.00")
OUTLIER_MIN_GROUP = 5
RECURRING_CATEGORIES = frozenset({"Income", "Rent", "Utilities", "Subscriptions"})


def _dup_key(t: Txn) -> tuple:
    return t.date, normalize_merchant(t.description), t.amount


def find_duplicates(txns: list[Txn]) -> list[tuple[int, int]]:
    """Pairs (first row, repeat row) with the same date, normalized description and amount."""
    first: dict[tuple, int] = {}
    pairs = []
    for t in txns:
        k = _dup_key(t)
        if k in first:
            pairs.append((first[k], t.row))
        else:
            first[k] = t.row
    return pairs


def robust_z(values: list[Decimal]) -> list[Decimal]:
    m = median(values)
    mad = median(abs(v - m) for v in values)
    if mad == 0:
        # Fallback scale: mean absolute deviation (x 1.2533 to match sigma for normal data).
        mean_ad = sum(abs(v - m) for v in values) / len(values)
        if mean_ad == 0:
            return [Decimal(0)] * len(values)
        return [(v - m) / (Decimal("1.2533") * mean_ad) for v in values]
    return [Decimal("0.6745") * (v - m) / mad for v in values]


def outlier_scores(txns: list[Txn], cats: dict[int, str] | None = None) -> dict[int, tuple[Decimal, str]]:
    """row -> (modified z-score, group) for every discretionary debit."""
    from .categorize import rule_category

    if cats is None:
        cats = {t.row: rule_category(t.description) for t in txns}
    debits = [t for t in txns if t.amount < 0 and cats.get(t.row) not in RECURRING_CATEGORIES
              and rule_category(t.description) not in RECURRING_CATEGORIES]
    groups: dict[str, list[Txn]] = {}
    for t in debits:
        groups.setdefault(cats.get(t.row) or "Uncategorized", []).append(t)
    pooled = [t for g in groups.values() if len(g) < OUTLIER_MIN_GROUP for t in g]
    out: dict[int, tuple[Decimal, str]] = {}
    for name, g in list(groups.items()) + [("pooled", pooled)]:
        if name != "pooled" and len(g) < OUTLIER_MIN_GROUP:
            continue
        if len(g) < 3:
            continue
        for t, z in zip(g, robust_z([-t.amount for t in g])):
            out[t.row] = (z, name)
    return out


def find_outliers(txns: list[Txn], cats: dict[int, str] | None = None) -> list[int]:
    """Discretionary debits far above their category's typical charge (rule documented above)."""
    scores = outlier_scores(txns, cats)
    by_row = {t.row: t for t in txns}
    return sorted(r for r, (z, _) in scores.items() if z >= OUTLIER_Z and -by_row[r].amount >= OUTLIER_FLOOR)


def weekend_charges(txns: list[Txn]) -> list[int]:
    """Debits dated on a Saturday or Sunday."""
    return [t.row for t in txns if t.amount < 0 and t.date.weekday() >= 5]


def reversed_debit(txns: list[Txn], row: int) -> int | None:
    """The latest earlier debit with the same merchant (refund words removed) and the same absolute amount."""
    from .categorize import strip_refund_words

    by_row = {t.row: t for t in txns}
    c = by_row[row]
    key = strip_refund_words(normalize_merchant(c.description))
    best = None
    for t in txns:
        if t.row == row or t.amount != -c.amount or t.date > c.date:
            continue
        if strip_refund_words(normalize_merchant(t.description)) == key:
            best = t.row
    return best


def find_refunds(txns: list[Txn]) -> list[int]:
    """Credits whose text says REFUND/RETURN/REVERSAL, or that reverse an earlier debit of the same
    merchant and amount. Income-like credits (payroll, tax refund) are not refunds of spending."""
    from .categorize import is_income_text, is_refund_text

    return [t.row for t in txns if t.amount > 0 and not is_income_text(t.description)
            and (is_refund_text(t.description) or reversed_debit(txns, t.row) is not None)]
