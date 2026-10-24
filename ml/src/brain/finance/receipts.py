"""Receipt <-> statement reconciliation. OCR happens on the Mac (Apple Vision); `parse_receipt_text` turns its
text into {merchant, date, total} and `reconcile_receipts` matches those to statement rows."""

from __future__ import annotations

import datetime as dt
import difflib
import re
from collections.abc import Iterable, Mapping
from decimal import Decimal

from .statement import CENT, Txn, normalize_merchant, parse_date, parse_money

POSTING_DELAY_DAYS = 3  # card charges can post a few days after the receipt date
MERCHANT_RATIO = 0.85  # OCR typos: difflib ratio of the distinctive words
# A changed amount (tip added, fuel/hotel hold) is still the same purchase within this tolerance.
MISMATCH_ABS = Decimal("1.00")
MISMATCH_REL = Decimal("0.25")
NEAREST_DAYS = 7

# Words that never identify a merchant on their own.
GENERIC = frozenset(["COFFEE", "STORE", "STORES", "MKTP", "MARKETPLACE", "TRIP", "RIDE", "CO", "COMPANY", "INC", "LLC", "LTD", "CORP", "THE", "AND", "OF", "SHOP", "MARKET", "MKT", "US", "USA"])
# Extra words that may follow a merchant name without making it a different merchant (store/location noise).
NOISE = GENERIC | frozenset(["BERKELEY", "OAKLAND", "EMERYVILLE", "ALBANY", "ELCERRITO", "RICHMOND", "SF", "SAN", "FRANCISCO", "CA", "DOWNTOWN", "NORTH", "SOUTH", "EAST", "WEST", "AVE", "ST", "BLVD", "WAY", "PL", "RD"])


def _tokens(name: str) -> list[str]:
    return normalize_merchant(name).split()


def _distinctive(toks: list[str]) -> list[str]:
    return [t for t in toks if t not in GENERIC and len(t) > 1]


def merchant_match(a: str, b: str) -> bool:
    """Same merchant despite case, punctuation, store numbers, processor prefixes, location words and OCR typos.

    At least one distinctive (non-generic) word must agree, so PHILZ COFFEE != PEETS COFFEE; extra words on one
    side are allowed only when they are store/location noise, so SAFEWAY != SAFEWAY FUEL and UBER != UBER EATS.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    if ta == tb or "".join(ta) == "".join(tb):
        return True
    da, db = _distinctive(ta), _distinctive(tb)
    if not da or not db:
        return False
    short, long_ = (ta, tb) if len(da) <= len(db) else (tb, ta)
    ds = _distinctive(short)
    if ds and all(t in long_ for t in ds):
        extra = [t for t in long_ if t not in short]
        if all(t in NOISE or len(t) == 1 for t in extra):
            return True
    if len(da) == len(db):
        return difflib.SequenceMatcher(None, " ".join(da), " ".join(db)).ratio() >= MERCHANT_RATIO
    return False


def is_adjacent_swap(a, b) -> bool:
    """True when the digit strings of two amounts differ by exactly one swap of adjacent digits."""
    x = str(abs(parse_money(a))).replace(".", "")
    y = str(abs(parse_money(b))).replace(".", "")
    if len(x) != len(y):
        return False
    diff = [i for i in range(len(x)) if x[i] != y[i]]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and x[diff[0]] == y[diff[1]] and x[diff[1]] == y[diff[0]]


def within_tolerance(total: Decimal, charged: Decimal) -> bool:
    return abs(charged - total) <= max(MISMATCH_ABS, (abs(total) * MISMATCH_REL).quantize(CENT))


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
    3. amount_mismatch: same merchant, posted 0-3 days after the receipt date, and either the digits are a
       single adjacent swap (`transposed_digits`) or the amounts differ by at most max($1, 25%) (a tip or a
       hold). Prefer a digit swap, then the earliest, then the closest amount.
    4. no_match otherwise. A same-merchant charge within 7 days is reported as `nearest` (a hint, not a match).
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
        return [t for t in debits if t.row not in used and lo <= (t.date - d).days <= hi
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
        window = cands(r, d, 0, POSTING_DELAY_DAYS)
        swapped = [t for t in window if is_adjacent_swap(total, -t.amount)]
        pool = swapped or [t for t in window if within_tolerance(total, -t.amount)]
        if pool:
            hit = min(pool, key=lambda t: ((t.date - d).days, abs(-t.amount - total)))
            used.add(hit.row)
            entry = {**base(r, total), "match_row": hit.row, "status": "amount_mismatch",
                     "statement_amount": -hit.amount, "transposed_digits": is_adjacent_swap(total, -hit.amount)}
            if hit.date != d:
                entry["posting_delay_days"] = (hit.date - d).days
            result[r["id"]] = entry
            continue
        entry = base(r, total)
        near = [t for t in debits if abs((t.date - d).days) <= NEAREST_DAYS and merchant_match(r["merchant"], t.description)]
        if near:
            t = min(near, key=lambda t: (abs((t.date - d).days), abs(-t.amount - total)))
            entry["nearest"] = {"row": t.row, "date": t.date.isoformat(), "amount": -t.amount}
        result[r["id"]] = entry
    return {r["id"]: result[r["id"]] for r, _, _ in parsed}


# --- OCR text -> {merchant, date, total} ---------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
                                       "NOV", "DEC"], 1)}
# OCR confusions inside numbers: O->0, l/I/|->1, S->5 (only applied to number-like tokens).
_DIGITISH = str.maketrans({"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"})
_MONEY = re.compile(r"(?<![\w.])[$S]?\s?(-?[0-9OolI|]{1,5}(?:,[0-9]{3})*\s?[.,]\s?[0-9Oo]{2})(?![\w.%])")
_NUM_DATE = re.compile(r"(?<!\d)([0-9OolI]{1,2})\s?[/.-]\s?([0-9OolI]{1,2})\s?[/.-]\s?((?:2[0Oo])?[0-9OolI]{2})(?!\d)")
_ISO_DATE = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
_TEXT_DATE = re.compile(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\s+(\d{1,2}),?\s+(20\d\d)\b", re.IGNORECASE)
_TOTAL = re.compile(r"\bT\s?[O0]\s?T\s?A\s?L\b", re.IGNORECASE)
_NOT_TOTAL = re.compile(r"SUB\s?-?\s?T[O0]TAL|TOTAL\s+(SAVINGS|ITEMS|DISCOUNT)|TAX|TIP|CHANGE|CASH|TEND", re.IGNORECASE)
_TENDER = re.compile(r"CHANGE|CASH|TEND", re.IGNORECASE)
_SKIP_MERCHANT = re.compile(r"^(WELCOME|RECEIPT|THANK|STORE\s*#|TEL|PHONE|WWW\.|HTTP)", re.IGNORECASE)
_ADDRESS = re.compile(r"^\d+\s+\w+|\b[A-Z]{2}\s+\d{5}\b|\(\d{3}\)|\d{3}-\d{3}-\d{4}")


def _money(token: str) -> Decimal | None:
    s = token.translate(_DIGITISH).replace(" ", "")
    if re.fullmatch(r"-?\d{1,5}(,\d{3})*[.,]\d{2}", s):
        s = s[:-3].replace(",", "") + "." + s[-2:]
        return Decimal(s).quantize(CENT)
    return None


def _amounts(line: str) -> list[Decimal]:
    out = []
    for m in _MONEY.finditer(line):
        v = _money(m.group(1))
        if v is not None:
            out.append(v)
    return out


def _date(text: str) -> dt.date | None:
    m = _ISO_DATE.search(text)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    for m in _NUM_DATE.finditer(text):
        mo, d, y = (int(g.translate(_DIGITISH)) for g in m.groups())
        y = y + 2000 if y < 100 else y
        try:
            return dt.date(y, mo, d)
        except ValueError:
            continue
    m = _TEXT_DATE.search(text)
    if m:
        try:
            return dt.date(int(m[3]), _MONTHS[m[1][:3].upper()], int(m[2]))
        except ValueError:
            pass
    return None


def parse_receipt_text(text: str, lines: list[dict] | None = None) -> dict:
    """OCR text -> {merchant, date (ISO or None), total (Decimal or None)}. Deterministic, no model.

    merchant: the first line with 3+ letters that is not a greeting, address, phone or date.
    total: the amount on the TOTAL line (not SUBTOTAL/TAX/TIP/CHANGE); OCR often puts the label and the amount
    on separate lines, so with `lines` (Vision observations with `frame` [x, y, w, h]) the amount on the same
    visual row is used; otherwise the largest amount on the receipt (a total is never below its parts).
    """
    raw = [ln.strip() for ln in text.replace("\r", "\n").split("\n")]
    raw = [ln for ln in raw if ln]
    merchant = None
    for ln in raw:
        if (len(re.findall(r"[A-Za-z]", ln)) >= 3 and not _SKIP_MERCHANT.search(ln) and not _ADDRESS.search(ln)
                and _date(ln) is None and not set(ln) <= set("-=*_ ")):
            merchant = re.sub(r"\s{2,}", " ", ln)
            break
    total = None
    for ln in raw:
        if _TOTAL.search(ln) and not _NOT_TOTAL.search(ln):
            amts = _amounts(ln)
            if amts:
                total = amts[-1]
                break
    if total is None and lines:
        total = _total_from_frames(lines)
    if total is None:
        amts = [a for ln in raw if not _TENDER.search(ln) for a in _amounts(ln)]
        total = max(amts) if amts else None
    d = _date("\n".join(raw))
    return {"merchant": merchant, "date": d.isoformat() if d else None, "total": total}


def _total_from_frames(lines: list[dict]) -> Decimal | None:
    labels = [ln for ln in lines if _TOTAL.search(ln.get("text", "")) and not _NOT_TOTAL.search(ln.get("text", ""))]
    best = None
    for lab in labels:
        x, y, _w, h = lab["frame"]
        cy = y + h / 2
        for ln in lines:
            if ln is lab:
                continue
            fx, fy, _fw, fh = ln["frame"]
            amts = _amounts(ln.get("text", ""))
            if amts and fx >= x and abs((fy + fh / 2) - cy) <= max(h, fh) * 0.6:
                d = abs((fy + fh / 2) - cy)
                if best is None or d < best[0]:
                    best = (d, amts[-1])
    return best[1] if best else None
