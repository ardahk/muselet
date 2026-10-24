from __future__ import annotations

import csv
import io
import random
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from ..common import choice_options, finish_record, key_for_value, round_bands, score_level_for

GROUPS = (
    "airport_services", "archive_storage", "building_access", "care_supplies",
    "claims_review", "client_events", "courier_ops", "data_services",
    "education_support", "equipment_rental", "field_repairs", "fleet_fuel",
    "food_services", "grant_admin", "identity_checks", "lab_operations",
    "legal_filings", "mailroom", "network_support", "office_supplies",
    "payroll_ops", "records_scanning", "safety_training", "site_cleaning",
    "translation", "travel_desk",
)
ACTIVE_GROUPS = ("courier_ops", "lab_operations", "travel_desk", "records_scanning")
DISPLAY_TO_GROUP = {group.replace("_", " ").title(): group for group in GROUPS}
MISTAKES = {
    "posting status": "the posting-status check (counting void entries)",
    "reporting window": "the reporting-window check (including a late entry)",
    "service group": "the approved-group check (including another service group)",
    "minimum amount": "the minimum-amount check (including a below-floor entry)",
    "duplicate upload": "duplicate resolution (counting the later upload)",
    "linked reversal": "the reversal check (keeping a reversed original)",
}
MISTAKE_COMMENTS = {
    "posting status": "I counted void entries as payable transactions.",
    "reporting window": "I kept a posted transaction dated after period close.",
    "service group": "I included a transaction from an unapproved service group.",
    "minimum amount": "I kept an entry below the minimum dollar amount.",
    "duplicate upload": "I counted a later upload for a transaction already listed.",
    "linked reversal": "I left the original transaction in after its later reversal.",
}


def _display(group: str) -> str:
    return group.replace("_", " ").title()


def _calculate(rows, start, end, minimum, included_groups, *, dropped=frozenset()):
    reversed_transactions = {
        row["reverses"] for row in rows
        if row["status"] == "reversal" and row["reverses"]
    }
    seen = set()
    eligible = []
    for row in rows:
        if row["status"] == "reversal":
            continue
        if "posting status" not in dropped and row["status"] != "posted":
            continue
        transaction = row["transaction"]
        if "duplicate upload" not in dropped:
            if transaction in seen:
                continue
            seen.add(transaction)
        if "linked reversal" not in dropped and transaction in reversed_transactions:
            continue
        day = date.fromisoformat(row["date"])
        if "reporting window" not in dropped and not start <= day <= end:
            continue
        if "service group" not in dropped and row["group"] not in included_groups:
            continue
        if "minimum amount" not in dropped and Decimal(row["amount"]) < minimum:
            continue
        eligible.append(row)
    return eligible


def _sum(rows):
    return sum((Decimal(row["amount"]) for row in rows), Decimal("0"))


def _totals(rows):
    totals = defaultdict(lambda: Decimal("0"))
    for row in rows:
        totals[row["group"]] += Decimal(row["amount"])
    return totals


def _largest_group(rows, included_groups):
    totals = _totals(rows)
    return min(included_groups, key=lambda group: (-totals[group], _display(group)))


def _render_csv(rows):
    stream = io.StringIO()
    columns = ("Record", "Transaction reference", "Date", "Posting status",
               "Service group", "Amount (USD)", "Reverses", "Work order")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "Record": row["row"],
            "Transaction reference": row["transaction"],
            "Date": row["date"],
            "Posting status": row["status"].title(),
            "Service group": _display(row["group"]),
            "Amount (USD)": row["amount"],
            "Reverses": row["reverses"] or "—",
            "Work order": row["work_order"],
        })
    return stream.getvalue().rstrip()


def _read_export(state):
    start_line = next(line for line in state.splitlines() if line.startswith("Review window: "))
    start_text, end_text = start_line.removeprefix("Review window: ").removesuffix(" (inclusive)").split(" through ")
    start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    minimum = Decimal(next(line for line in state.splitlines()
                           if line.startswith("Minimum eligible amount: ")).split("$", 1)[1])
    included = {
        DISPLAY_TO_GROUP[name.strip()]
        for name in next(line for line in state.splitlines()
                         if line.startswith("Eligible service groups: ")).split(": ", 1)[1].split(", ")
    }
    cap = Decimal(next(line for line in state.splitlines()
                       if line.startswith("Review cap: ")).split("$", 1)[1].replace(",", ""))
    raw = state.split("LEDGER EXPORT\n", 1)[1].split("\nEND EXPORT", 1)[0]
    rows = []
    for record in csv.DictReader(io.StringIO(raw)):
        rows.append({
            "row": record["Record"],
            "transaction": record["Transaction reference"],
            "date": record["Date"],
            "status": record["Posting status"].lower(),
            "group": DISPLAY_TO_GROUP[record["Service group"]],
            "amount": record["Amount (USD)"],
            "reverses": "" if record["Reverses"] == "—" else record["Reverses"],
        })
    return rows, start, end, minimum, included, cap


def verify_rendered(record: dict) -> bool:
    try:
        state = record["state"]
        rows, start, end, minimum, included, cap = _read_export(state)
        reversed_references = {
            row["reverses"] for row in rows
            if row["status"] == "reversal" and row["reverses"]
        }

        def reparse(ignore=None):
            seen_references = set()
            selected = []
            for row in rows:
                if row["status"] == "reversal":
                    continue
                if row["status"] != "posted" and not (
                    ignore == "posting status" and row["status"] == "void"
                ):
                    continue
                reference = row["transaction"]
                if ignore != "duplicate upload":
                    if reference in seen_references:
                        continue
                    seen_references.add(reference)
                if ignore != "linked reversal" and reference in reversed_references:
                    continue
                day = date.fromisoformat(row["date"])
                if ignore != "reporting window" and not start <= day <= end:
                    continue
                if ignore != "service group" and row["group"] not in included:
                    continue
                if ignore != "minimum amount" and Decimal(row["amount"]) < minimum:
                    continue
                selected.append(row)
            return selected

        eligible = reparse()
        total = _sum(eligible)
        group_totals = _totals(eligible)
        largest = _largest_group(eligible, included)
        unreversed = reparse("linked reversal")
        reversal_amount = _sum(unreversed) - total
        below_minimum = reparse("minimum amount")
        below_minimum_amount = _sum(below_minimum) - total
        note_lines = [line for line in state.splitlines()
                      if line.startswith("Message from Mira, finance review:")]
        if len(note_lines) > 1:
            return False
        note_meta = record.get("_meta", {}).get("staff_note", {})
        if bool(note_lines) != bool(note_meta.get("included")):
            return False
        if note_lines:
            note_line = note_lines[0]
            match = re.search(r"\$([\d,]+\.\d{2})", note_line)
            if match is None:
                return False
            claimed = Decimal(match.group(1).replace(",", ""))
            if "Applying the posted-status" in note_line:
                note_expected = total
            else:
                mistake = next((rule for rule, phrase in MISTAKE_COMMENTS.items()
                                if phrase in note_line), None)
                if mistake is None:
                    return False
                note_expected = _sum(reparse(mistake))
            if claimed != note_expected or note_meta.get("correct") != (claimed == total):
                return False
        for qid, question in record["questions"].items():
            instructions = question["instructions"].lower()
            kind = question["type"]
            if instructions.startswith("how many eligible ledger transactions"):
                expected = key_for_value("result", len(eligible))
                if expected not in question["criteria"] or record["gold"][qid] != expected:
                    return False
            elif instructions.startswith("how many eligible transactions belong to "):
                group_name = instructions.split("belong to ", 1)[1].split(" group", 1)[0]
                group_name = group_name.removeprefix("the ").title()
                group = DISPLAY_TO_GROUP[group_name]
                count = sum(row["group"] == group for row in eligible)
                expected = key_for_value("result", count)
                if expected not in question["criteria"] or record["gold"][qid] != expected:
                    return False
            elif instructions.startswith("which group has the highest filtered ledger total"):
                expected = f"group_{largest}"
                if expected not in question["criteria"] or record["gold"][qid] != expected:
                    return False
            elif instructions.startswith("does the filtered ledger total exceed the cap"):
                if record["gold"][qid] != ("true" if total > cap else "false"):
                    return False
            elif instructions.startswith("is the eligible transaction count at least "):
                threshold = int(instructions.rsplit(" ", 1)[1].rstrip("?"))
                if record["gold"][qid] != ("true" if len(eligible) >= threshold else "false"):
                    return False
            elif instructions.startswith("does the filtered total exceed the comparison amount"):
                threshold = Decimal(instructions.rsplit("$", 1)[1].rstrip("?").replace(",", ""))
                if record["gold"][qid] != ("true" if total > threshold else "false"):
                    return False
            elif instructions.startswith("which band contains the sum of eligible ledger amounts"):
                if kind != "score" or record["gold"][qid] != score_level_for(total, question["criteria"]):
                    return False
            elif instructions.startswith("which band contains the amount removed by reversal notices"):
                if kind != "score" or record["gold"][qid] != score_level_for(reversal_amount, question["criteria"]):
                    return False
            elif instructions.startswith("which band contains the amount below the minimum"):
                if kind != "score" or record["gold"][qid] != score_level_for(below_minimum_amount, question["criteria"]):
                    return False
            else:
                return False
        return True
    except (IndexError, ValueError, KeyError, ArithmeticError, StopIteration):
        return False


def _choice(answer, answer_description, alternatives):
    options = {key_for_value("result", answer): answer_description}
    for value, mistake_description in alternatives:
        if value != answer:
            options.setdefault(key_for_value("result", value), mistake_description)
    return key_for_value("result", answer), options


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    row_count = rng.randint(25, 60)
    start = date(2027, rng.randint(1, 9), rng.randint(2, 20))
    end = start + timedelta(days=rng.randint(8, 24))
    minimum = Decimal(rng.choice(("18.00", "25.00", "32.00", "41.00")))
    included = set(rng.sample(ACTIVE_GROUPS, 3))
    rows = []
    for index, group in enumerate(sorted(included, key=_display)):
        amount = Decimal(220 + index * 130 + rng.randint(0, 60))
        rows.append({
            "row": f"L{len(rows) + 1:03d}", "transaction": f"TX-{rng.randint(10000, 99999)}",
            "date": (start + timedelta(days=rng.randint(0, (end - start).days))).isoformat(),
            "status": "posted", "group": group, "amount": f"{amount:.2f}", "reverses": "",
        })
    base_rows = list(rows)
    for base in base_rows:
        duplicate = dict(base)
        duplicate.update(
            row="L-DUP", amount=f"{Decimal(base['amount']) + Decimal('500.00'):.2f}"
        )
        rows.append(duplicate)
    for group in sorted(included, key=_display):
        rows.extend((
            {
                "row": "L-VOID", "transaction": f"TX-{rng.randint(10000, 99999)}",
                "date": start.isoformat(), "status": "void", "group": group,
                "amount": "990.00", "reverses": "",
            },
            {
                "row": "L-LATE", "transaction": f"TX-{rng.randint(10000, 99999)}",
                "date": (end + timedelta(days=2)).isoformat(), "status": "posted",
                "group": group, "amount": "1120.00", "reverses": "",
            },
            {
                "row": "L-LOW", "transaction": f"TX-{rng.randint(10000, 99999)}",
                "date": start.isoformat(), "status": "posted", "group": group,
                "amount": f"{minimum - Decimal('2.00'):.2f}", "reverses": "",
            },
        ))
    excluded_group = next(group for group in GROUPS if group not in included)
    excluded_row = {
        "row": "L-OTHER", "transaction": f"TX-{rng.randint(10000, 99999)}",
        "date": start.isoformat(), "status": "posted", "group": excluded_group,
        "amount": "12400.00", "reverses": "",
    }
    rows.append(excluded_row)
    rows.append({
        "row": "L-REV", "transaction": f"RV-{rng.randint(10000, 99999)}",
        "date": (end + timedelta(days=3)).isoformat(), "status": "reversal",
        "group": rows[0]["group"], "amount": "0.00", "reverses": rows[0]["transaction"],
    })
    while len(rows) < row_count:
        group = rng.choice(GROUPS)
        status = rng.choices(("posted", "void"), weights=(0.78, 0.22))[0]
        day = start + timedelta(days=rng.randint(-3, (end - start).days + 3))
        rows.append({
            "row": f"L{len(rows) + 1:03d}", "transaction": f"TX-{rng.randint(10000, 99999)}",
            "date": day.isoformat(), "status": status, "group": group,
            "amount": f"{rng.randint(10, 920)}.00", "reverses": "",
        })
    for index, row in enumerate(rows, 1):
        row["row"] = f"L{index:03d}"
        row["work_order"] = f"Service log {rng.randint(1400, 9899)} — {rng.choice(('vehicle repair', 'equipment check', 'site visit', 'courier run'))}"

    eligible = _calculate(rows, start, end, minimum, included)
    total = _sum(eligible)
    largest = _largest_group(eligible, included)
    unreversed = _calculate(rows, start, end, minimum, included, dropped={"linked reversal"})
    reversal_amount = _sum(unreversed) - total
    below_minimum = _calculate(rows, start, end, minimum, included, dropped={"minimum amount"})
    below_minimum_amount = _sum(below_minimum) - total
    count = len(eligible)
    count_is_at_least = bool(rng.randrange(2))
    count_threshold = max(1, count if count_is_at_least else count + 1)
    total_exceeds_amount = bool(rng.randrange(2))
    amount_threshold = total - Decimal("25.00") if total_exceeds_amount else total + Decimal("25.00")
    cap_exceeded = bool(rng.randrange(2))
    cap = total - Decimal("25.00") if cap_exceeded else total + Decimal("25.00")

    error_results = {
        mistake: _calculate(rows, start, end, minimum, included, dropped={mistake})
        for mistake in MISTAKES
    }
    correct_count = count
    count_alternatives = [
        (len(result), mistake) for mistake, result in error_results.items()
    ]
    count_answer, count_options = _choice(
        correct_count,
        f"{correct_count} ledger transactions satisfy the complete review rules.",
        [(value, f"{value} transactions if the review omits {MISTAKES[mistake]}.")
         for value, mistake in count_alternatives],
    )
    group = rng.choice(sorted(included))
    group_count = sum(row["group"] == group for row in eligible)
    group_alternatives = []
    for mistake, result in error_results.items():
        group_alternatives.append((
            sum(row["group"] == group for row in result),
            f"the review omits {MISTAKES[mistake]}",
        ))
    group_answer, group_options = _choice(
        group_count,
        f"{group_count} eligible transactions belong to {_display(group)}.",
        [(value, f"{value} transactions if {mistake}.") for value, mistake in group_alternatives],
    )
    largest_alternatives = [
        (f"group_{_largest_group(result, GROUPS if mistake == 'service group' else included)}", mistake)
        for mistake, result in error_results.items()
    ]
    largest_options = {
        f"group_{largest}": f"{_display(largest)} has the highest total after applying every rule."
    }
    for key, mistake in largest_alternatives:
        if key != f"group_{largest}":
            largest_options.setdefault(
                key, f"{_display(key.removeprefix('group_'))} leads if the review omits {MISTAKES[mistake]}."
            )
    bands_sum, score_sum = round_bands(
        total, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100")], rng
    )
    bands_reversals, score_reversals = round_bands(
        reversal_amount, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50")], rng
    )
    bands_floor, score_floor = round_bands(
        below_minimum_amount, "$", [Decimal("5"), Decimal("10"), Decimal("25")], rng
    )
    score_sum, score_reversals, score_floor = map(str, (score_sum, score_reversals, score_floor))

    pool = [
        ("choice", "How many eligible ledger transactions remain after applying every review rule?",
         count_answer, count_options),
        ("score", "Which band contains the sum of eligible ledger amounts after linked reversals?",
         score_sum, bands_sum),
        ("noul", f"Does the filtered ledger total exceed the cap of ${cap:,.2f}?",
         "true" if cap_exceeded else "false",
         {"false": "The filtered total is at or below the review cap.",
          "true": "The filtered total is strictly above the review cap."}),
        ("choice", f"How many eligible transactions belong to the {_display(group)} group?",
         group_answer, group_options),
        ("choice", "Which group has the highest filtered ledger total?",
         f"group_{largest}", largest_options),
        ("score", "Which band contains the amount removed by reversal notices?",
         score_reversals, bands_reversals),
        ("noul", f"Is the eligible transaction count at least {count_threshold}?",
         "true" if count_is_at_least else "false",
         {"false": f"The eligible transaction count is below {count_threshold}.",
          "true": f"The eligible transaction count is at least {count_threshold}."}),
        ("noul", f"Does the filtered total exceed the comparison amount of ${amount_threshold:,.2f}?",
         "true" if total_exceeds_amount else "false",
         {"false": "The filtered total does not exceed the comparison amount.",
          "true": "The filtered total is greater than the comparison amount."}),
        ("score", "Which band contains the amount below the minimum eligible threshold?",
         score_floor, bands_floor),
    ]
    specs = rng.sample(pool, n_questions)
    state = (
        f"RECONCILIATION EXPORT — {rng.choice(('Regional Services', 'Claims Processing', 'Field Operations'))}\n"
        f"Review window: {start.isoformat()} through {end.isoformat()} (inclusive)\n"
        f"Minimum eligible amount: ${minimum:.2f}\n"
        f"Eligible service groups: {', '.join(_display(name) for name in sorted(included, key=_display))}\n"
        f"Review cap: ${cap:,.2f}\n\n"
        "Review instructions: Count posted entries only. Among posted entries, retain the first upload for each "
        "transaction reference; a later upload with that reference is a duplicate. The review window includes both "
        "printed dates. Only the listed service groups and amounts at or above the minimum qualify. A reversal "
        "notice cancels its linked transaction even when the notice date falls outside the reporting window. "
        "For equal group totals, the alphabetically earlier group name ranks first.\n\n"
        "Batch memo: The export includes operational rows from several service desks. Amounts are in US dollars. "
        "Some notices were entered after the monthly close, and the ledger retains voided entries for audit history. "
        "Use the posting status and transaction reference columns rather than the upload order or the dashboard subtotal.\n\n"
        "Supporting reference: Work-order numbers link each charge to a service ticket. A late reversal is filed "
        "under the transaction it corrects, not under the accounting period in which the notice arrived.\n\n"
        "LEDGER EXPORT\n" + _render_csv(rows) + "\nEND EXPORT"
    )
    include_note = rng.random() < 0.65
    if not include_note:
        note = None
        note_mistake = None
    elif rng.random() < 0.30:
        note_text = (
            f"Message from Mira, finance review: Applying the posted-status, duplicate, window, service-group, "
            f"amount, and reversal rules leaves an eligible total of ${total:,.2f}."
        )
        note = (note_text, True)
        note_mistake = None
    else:
        note_mistake = rng.choice(tuple(MISTAKES))
        mistaken_total = _sum(error_results[note_mistake])
        note_text = (
            f"Message from Mira, finance review: {MISTAKE_COMMENTS[note_mistake]} "
            f"This gives an eligible total of ${mistaken_total:,.2f}."
        )
        note = (note_text, False)
    return finish_record(
        rng, "cg_counting", "reconciled_service_ledger", state, specs,
        facts={"rows": rows, "window_start": start.isoformat(), "window_end": end.isoformat(),
               "minimum_amount": str(minimum), "included_groups": sorted(included),
               "review_cap": str(cap)},
        traps=["status_filter", "inclusive_window", "group_filter", "minimum_amount",
               "duplicate_reference", "cross_window_reversal"],
        note=note,
        intermediate_values=[f"eligible total {total}", f"eligible transactions {count}",
                             f"note mistake {note_mistake}"],
    )
