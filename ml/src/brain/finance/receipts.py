"""Receipt <-> statement reconciliation. OCR happens on the Mac; this gets {id, merchant, date, total}."""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping

from .statement import Txn, normalize_merchant, parse_date, parse_money

POSTING_DELAY_DAYS = 3  # card charges can post a few days after the receipt date
MERCHANT_RATIO = 0.85


def merchant_match(a: str, b: str) -> bool:
    """Same merchant despite case, punctuation, store numbers and processor prefixes."""
    x, y = normalize_merchant(a), normalize_merchant(b)
    if not x or not y:
        return False
    if x == y or x.replace(" ", "") == y.replace(" ", ""):
        return True
    tx, ty = x.split(), y.split()
    short, long_ = (tx, ty) if len(tx) <= len(ty) else (ty, tx)
    if long_[:len(short)] == short and len("".join(short)) >= 4:
        return True
    return difflib.SequenceMatcher(None, x, y).ratio() >= MERCHANT_RATIO


def is_adjacent_swap(a, b) -> bool:
    """True when the digit strings of two amounts differ by exactly one swap of adjacent digits."""
    x = str(abs(parse_money(a))).replace(".", "")
    y = str(abs(parse_money(b))).replace(".", "")
    if len(x) != len(y):
        return False
    diff = [i for i in range(len(x)) if x[i] != y[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and x[diff[0]] == y[diff[1]] and x[diff[1]] == y[diff[0]]


def _as_list(receipts) -> list[dict]:
    if isinstance(receipts, Mapping):
        return [{"id": k, **v} for k, v in receipts.items()]
    return [dict(r) for r in receipts]


def reconcile_receipts(receipts: Iterable[dict] | Mapping[str, dict], txns: list[Txn]) -> dict[str, dict]:
    """{receipt id: {match_row, status, total, merchant, date, ...}} with status
    matched | amount_mismatch | no_match.

    Passes, each over all receipts, each statement row used at most once:
    1. matched: same merchant, same date, same amount.
    2. matched with `posting_delay_days`: same merchant and amount, posted 1-3 days after the receipt date.
    3. amount_mismatch: same merchant and date (or within the posting window when the digits are a single
       adjacent swap), different amount; `statement_amount` and `transposed_digits` say how. With several
       candidates, prefer a digit swap, then the closest amount.
    4. no_match otherwise.
    """
    recs = _as_list(receipts)
    parsed = [(r, parse_date(r["date"]), parse_money(r["total"])) for r in recs]
    debits = [t for t in txns if t.amount < 0]
    used: set[int] = set()
    result: dict[str, dict] = {}

    def base(r, total):
        return {"match_row": None, "status": "no_match", "total": total, "merchant": r["merchant"],
                "date": parse_date(r["date"]).isoformat()}

    def cands(r, d, lo, hi):
        return [t for t in debits if t.row not in used and 0 <= (t.date - d).days - lo <= hi - lo
                and merchant_match(r["merchant"], t.description)]

    for r, d, total in parsed:  # pass 1
        hit = next((t for t in cands(r, d, 0, 0) if -t.amount == total), None)
        if hit:
            used.add(hit.row)
            result[r["id"]] = {**base(r, total), "match_row": hit.row, "status": "matched"}
    for r, d, total in parsed:  # pass 2
        if r["id"] in result:
            continue
        hit = next((t for t in cands(r, d, 1, POSTING_DELAY_DAYS) if -t.amount == total), None)
        if hit:
            used.add(hit.row)
            result[r["id"]] = {**base(r, total), "match_row": hit.row, "status": "matched",
                               "posting_delay_days": (hit.date - d).days}
    for r, d, total in parsed:  # pass 3
        if r["id"] in result:
            continue
        same_day = cands(r, d, 0, 0)
        swapped = [t for t in cands(r, d, 0, POSTING_DELAY_DAYS) if is_adjacent_swap(total, -t.amount)]
        pool = swapped or same_day
        if pool:
            hit = min(pool, key=lambda t: ((t.date - d).days, abs(-t.amount - total)))
            used.add(hit.row)
            entry = {**base(r, total), "match_row": hit.row, "status": "amount_mismatch",
                     "statement_amount": -hit.amount, "transposed_digits": is_adjacent_swap(total, -hit.amount)}
            if hit.date != d:
                entry["posting_delay_days"] = (hit.date - d).days
            result[r["id"]] = entry
        else:
            result[r["id"]] = base(r, total)
    return {r["id"]: result[r["id"]] for r, _, _ in parsed}
