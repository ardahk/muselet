"""Evidence: every flag names its rows, the rule that fired, the numbers, and a <= 12-word mascot line."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from .statement import Txn


@dataclass
class Flag:
    kind: str
    rows: list[int]
    rule: str
    say: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def usd(v) -> str:
    v = Decimal(v)
    return f"{'-' if v < 0 else ''}${abs(v):,.2f}"


def short(desc: str, words: int = 3) -> str:
    return " ".join(desc.split()[:words])


def day(t: Txn) -> str:
    return f"{t.date:%b} {t.date.day}"


def receipt_label(rid: str) -> str:
    m = re.search(r"(\d+)", str(rid))
    return f"Receipt {int(m.group(1))}" if m else f"Receipt {rid}"


def duplicate(a: Txn, b: Txn, refund: Txn | None = None) -> Flag:
    """An open duplicate invites a dispute; a refunded one only says it was already settled."""
    rule = "duplicate:same_date+description+amount"
    detail = {"date": a.date.isoformat(), "description": a.description, "amount": a.amount,
              "status": "refunded" if refund else "open", "refund_row": refund.row if refund else None}
    if refund:
        return Flag("duplicate", [a.row, b.row, refund.row], f"{rule};refunded_by_row{refund.row}",
                    f"Charged twice: {short(a.description)} {usd(-a.amount)} {day(a)}, refunded {day(refund)}.",
                    detail)
    return Flag("duplicate", [a.row, b.row], rule,
                f"Charged twice: {short(a.description)} {usd(-a.amount)} on {day(a)}.", detail)


def outlier(t: Txn, z: Decimal, group: str, group_median: Decimal, z_min: Decimal, floor: Decimal) -> Flag:
    ratio = int(-t.amount / group_median) if group_median else 0
    say = (f"{short(t.description)} {usd(-t.amount)} is {ratio}x your usual {group}."
           if ratio >= 2 else f"{short(t.description)} {usd(-t.amount)} is unusually large.")
    return Flag("outlier", [t.row], f"outlier:modified_z>={z_min}&amount>={floor}", say,
                {"amount": t.amount, "z": z.quantize(Decimal("0.1")), "group": group, "group_median": group_median})


def refund(t: Txn, orig: int | None, by_text: bool) -> Flag:
    rule = f"refund:reverses_row{orig}" if orig else "refund:text"
    if by_text and orig:
        rule = f"refund:text+reverses_row{orig}"
    rows = [t.row] + ([orig] if orig else [])
    return Flag("refund", rows, rule, f"{short(strip_refund(t.description))} refunded {usd(t.amount)}.",
                {"amount": t.amount, "reverses_row": orig})


def strip_refund(desc: str) -> str:
    return re.sub(r"\b(REFUND|RETURN|REVERSAL)\b", "", desc, flags=re.IGNORECASE).strip() or desc


def weekend(rows: list[int]) -> Flag:
    return Flag("weekend", rows, "weekend:debit_on_sat_or_sun", f"{len(rows)} weekend charges highlighted.",
                {"count": len(rows)})


def over_budget(cat: str, rows: list[int], budget: Decimal, actual: Decimal, remaining: Decimal) -> Flag:
    return Flag("over_budget", rows, "budget:actual>budget", f"{cat} is {usd(-remaining)} over budget.",
                {"category": cat, "budget": budget, "actual": actual, "remaining": remaining})


def pending_budget(rows: list[int], debits: Decimal, credits: Decimal, needs_review: list[str]) -> Flag:
    n = len(rows)
    return Flag("budget_pending", rows, "budget:unresolved_rows_not_counted",
                f"{n} row{'s' if n != 1 else ''} need a category before the budget is final.",
                {"debits": debits, "credits": credits, "needs_review": needs_review})


def ask_category(desc: str, rows: list[int], guess: str, p: float, rule: str) -> Flag:
    say = f"Is {short(desc)} {guess}?" if p > 0 else f"Which category is {short(desc)}?"
    return Flag("ask_category", rows, rule, say, {"description": desc, "guess": guess, "p": round(p, 3)})


def receipt(rid: str, e: dict) -> Flag:
    label = receipt_label(rid)
    rows = [e["match_row"]] if e["match_row"] else []
    delay = e.get("posting_delay_days")
    if e["status"] == "unreadable":
        return Flag("receipt_unreadable", [], "receipt:ocr_missing_" + "+".join(e.get("missing", [])),
                    f"Couldn't read {label.lower()}; check it?", {"receipt": rid, **e})
    if e["status"] == "matched":
        rule = "receipt:merchant+amount+date" + (f"+{delay}d_posting" if delay else "")
        say = f"{label} matches row {e['match_row']}."
    elif e["status"] == "amount_mismatch":
        swap = e.get("transposed_digits")
        rule = "receipt:merchant+date,amount_differs" + (",adjacent_digit_swap" if swap else "")
        say = (f"{label}: {usd(e['total'])} vs bank {usd(e['statement_amount'])}"
               + (", digits swapped." if swap else "."))
    else:
        rule = "receipt:no_statement_row_with_merchant+date+amount"
        say = f"No bank charge for {label.lower()}, {short(e['merchant'], 2)}."
    return Flag(f"receipt_{e['status']}", rows, rule, say, {"receipt": rid, **e})


def balance_break(t: Txn) -> Flag:
    return Flag("balance_break", [t.row], "balance:prev+amount!=balance", f"Balance doesn't add up at row {t.row}.",
                {"balance": t.balance, "amount": t.amount})
