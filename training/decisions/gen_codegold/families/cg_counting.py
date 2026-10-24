from __future__ import annotations

import csv
import io
import random
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

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
DISPLAY_TO_GROUP = {group.replace("_", " ").title(): group for group in GROUPS}
MISTAKES = (
    "posting status", "reporting window", "service group",
    "minimum amount", "duplicate upload", "linked reversal",
)
DISQUALIFIERS = ("posting status", "reporting window", "minimum amount")


def _display(group: str) -> str:
    return group.replace("_", " ").title()


def _new_reference(rng: random.Random, used: set[str], prefix: str = "TX") -> str:
    while True:
        reference = f"{prefix}-{rng.randint(100000, 999999)}"
        if reference not in used:
            used.add(reference)
            return reference


def _random_amount(
    rng: random.Random,
    used: set[Decimal],
    low_cents: int,
    high_cents: int,
) -> Decimal:
    for _ in range(500):
        value = Decimal(rng.randint(low_cents, high_cents)) / Decimal(100)
        if value not in used:
            used.add(value)
            return value
    raise ValueError("unable to sample a distinct ledger amount")


def _random_day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _random_received(rng: random.Random, day: date) -> datetime:
    return datetime.combine(
        day,
        time(hour=rng.randint(7, 18), minute=rng.choice((0, 7, 13, 22, 31, 46, 54))),
    )


def _row(
    rng: random.Random,
    used_references: set[str],
    *,
    day: date,
    status: str,
    group: str,
    amount: Decimal,
    trap_kind: str | None = None,
    transaction: str | None = None,
    received: datetime | None = None,
    reverses: str = "",
) -> dict:
    return {
        "record": "",
        "transaction": transaction or _new_reference(rng, used_references),
        "date": day.isoformat(),
        "received": (received or _random_received(rng, day)).isoformat(sep=" ", timespec="minutes"),
        "status": status,
        "group": group,
        "amount": f"{amount:.2f}",
        "reverses": reverses,
        "work_order": "",
        "trap_kind": trap_kind,
    }


def _eligible_rows(
    rows,
    start: date,
    end: date,
    minimum: Decimal,
    included_groups: set[str],
    *,
    dropped: str | None = None,
) -> list[dict]:
    reversal_targets = {
        row["reverses"] for row in rows
        if row["status"] == "reversal" and row["reverses"]
    }
    candidates = [
        row for row in rows
        if row["status"] == "posted" or dropped == "posting status" and row["status"] == "void"
    ]
    if dropped != "duplicate upload":
        first_uploads = {}
        for row in sorted(candidates, key=lambda item: (item["received"], item["record"])):
            first_uploads.setdefault(row["transaction"], row)
        candidates = list(first_uploads.values())

    eligible = []
    for row in candidates:
        if dropped != "linked reversal" and row["transaction"] in reversal_targets:
            continue
        row_date = date.fromisoformat(row["date"])
        if dropped != "reporting window" and not start <= row_date <= end:
            continue
        if dropped != "service group" and row["group"] not in included_groups:
            continue
        if dropped != "minimum amount" and Decimal(row["amount"]) < minimum:
            continue
        eligible.append(row)
    return eligible


def _sum(rows) -> Decimal:
    return sum((Decimal(row["amount"]) for row in rows), Decimal("0"))


def _group_totals(rows) -> dict[str, Decimal]:
    totals = defaultdict(lambda: Decimal("0"))
    for row in rows:
        totals[row["group"]] += Decimal(row["amount"])
    return totals


def _largest_group(rows, groups: set[str]) -> str:
    totals = _group_totals(rows)
    return min(groups, key=lambda group: (-totals[group], _display(group)))


def _render_export(rows) -> str:
    columns = (
        "Record", "Transaction reference", "Service date", "Received at",
        "Posting status", "Service group", "Amount (USD)", "Reverses",
        "Work order",
    )
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "Record": row["record"],
            "Transaction reference": row["transaction"],
            "Service date": row["date"],
            "Received at": row["received"],
            "Posting status": row["status"].title(),
            "Service group": _display(row["group"]),
            "Amount (USD)": row["amount"],
            "Reverses": row["reverses"] or "—",
            "Work order": row["work_order"],
        })
    return stream.getvalue().rstrip()


def _read_export(state: str):
    lines = state.splitlines()
    window = next(line for line in lines if line.startswith("Review window: "))
    start_text, end_text = window.removeprefix("Review window: ").removesuffix(
        " (inclusive)"
    ).split(" through ")
    start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    minimum_line = next(line for line in lines if line.startswith("Minimum eligible amount: "))
    minimum = Decimal(re.search(r"\$([\d,]+\.\d{2})", minimum_line).group(1).replace(",", ""))
    groups_line = next(line for line in lines if line.startswith("Eligible service groups: "))
    included = {
        DISPLAY_TO_GROUP[name.strip()]
        for name in groups_line.split(": ", 1)[1].split(", ")
    }
    cap_line = next(line for line in lines if line.startswith("Review cap: "))
    cap = Decimal(re.search(r"\$([\d,]+\.\d{2})", cap_line).group(1).replace(",", ""))
    raw = state.split("LEDGER EXPORT\n", 1)[1].split("\nEND EXPORT", 1)[0]
    rows = []
    for exported in csv.DictReader(io.StringIO(raw)):
        rows.append({
            "record": exported["Record"],
            "transaction": exported["Transaction reference"],
            "date": exported["Service date"],
            "received": exported["Received at"],
            "status": exported["Posting status"].lower(),
            "group": DISPLAY_TO_GROUP[exported["Service group"]],
            "amount": exported["Amount (USD)"],
            "reverses": "" if exported["Reverses"] == "—" else exported["Reverses"],
        })
    return rows, start, end, minimum, included, cap


def _option_key(stem: str, value, places: int = 0) -> str:
    return key_for_value(stem, value, places=places if isinstance(value, Decimal) else 0)


def _choice_spec(stem, answer_value, alternatives, describe, *, places=0):
    answer = _option_key(stem, answer_value, places)
    options = {answer: describe(answer_value)}
    provenance = {answer: "correct"}
    for value, mistake in alternatives:
        key = _option_key(stem, value, places)
        if key != answer and key not in options:
            options[key] = describe(value)
            provenance[key] = mistake
    if len(options) < 2:
        raise ValueError(f"{stem} has no distinct computed distractor")
    return answer, options, provenance


def _cap_relation(amount: Decimal, cap: Decimal) -> str:
    if amount > cap:
        return "over"
    if amount < cap:
        return "under"
    return "right at"


def verify_rendered(record: dict) -> bool:
    try:
        rows, start, end, minimum, included, cap = _read_export(record["state"])
        reversed_references = {
            row["reverses"] for row in rows
            if row["status"] == "reversal" and row["reverses"]
        }

        def reparse(ignore: str | None = None) -> list[dict]:
            eligible_uploads = []
            for row in rows:
                if row["status"] != "posted" and not (
                    ignore == "posting status" and row["status"] == "void"
                ):
                    continue
                eligible_uploads.append(row)
            if ignore != "duplicate upload":
                earliest = {}
                for row in eligible_uploads:
                    current = earliest.get(row["transaction"])
                    if current is None or row["received"] < current["received"]:
                        earliest[row["transaction"]] = row
                eligible_uploads = list(earliest.values())

            result = []
            for row in eligible_uploads:
                reference = row["transaction"]
                if ignore != "linked reversal" and reference in reversed_references:
                    continue
                service_day = date.fromisoformat(row["date"])
                if ignore != "reporting window" and not (start <= service_day <= end):
                    continue
                if ignore != "service group" and row["group"] not in included:
                    continue
                if ignore != "minimum amount" and Decimal(row["amount"]) < minimum:
                    continue
                result.append(row)
            return result

        eligible = reparse()
        total = sum((Decimal(row["amount"]) for row in eligible), Decimal("0"))
        reversed_total = sum(
            (Decimal(row["amount"]) for row in reparse("linked reversal")), Decimal("0")
        ) - total
        below_minimum_total = sum(
            (Decimal(row["amount"]) for row in reparse("minimum amount")), Decimal("0")
        ) - total
        totals = defaultdict(lambda: Decimal("0"))
        group_counts = defaultdict(int)
        for row in eligible:
            totals[row["group"]] += Decimal(row["amount"])
            group_counts[row["group"]] += 1
        largest = min(included, key=lambda group: (-totals[group], _display(group)))

        for qid, question in record["questions"].items():
            instructions = question["instructions"]
            answer = record["gold"][qid]
            if instructions == "How many eligible transactions remain in the ledger?":
                expected = key_for_value("eligible_count", len(eligible))
                if answer != expected:
                    return False
            elif instructions == "Which band contains the eligible total after linked reversals?":
                if answer != score_level_for(total, question["criteria"]):
                    return False
            elif instructions.startswith("Does the eligible total meet or exceed the review cap of $"):
                if answer != ("true" if total >= cap else "false"):
                    return False
            elif instructions.startswith("Does the eligible total strictly exceed the review cap of $"):
                if answer != ("true" if total > cap else "false"):
                    return False
            elif instructions.startswith("What is the eligible transaction count for "):
                group_name = instructions.removeprefix(
                    "What is the eligible transaction count for "
                ).removesuffix("?")
                group = DISPLAY_TO_GROUP[group_name]
                if answer != key_for_value("group_count", group_counts[group]):
                    return False
            elif instructions == "Which group has the highest filtered ledger total?":
                if answer != key_for_value("group", largest):
                    return False
            elif instructions == "What is the total of otherwise-eligible entries cancelled by reversal notices?":
                if answer != score_level_for(reversed_total, question["criteria"]):
                    return False
            elif instructions == "What is the total of entries that pass every other rule but fall below the minimum amount?":
                if answer != score_level_for(below_minimum_total, question["criteria"]):
                    return False
            else:
                return False

        return True
    except (ValueError, KeyError, IndexError, StopIteration, InvalidOperation, AttributeError):
        return False
    return True


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    start = date(2027, rng.randint(1, 9), 1)
    end = start + timedelta(days=29)
    minimum = Decimal(rng.choice(("100.00", "125.00", "150.00", "200.00")))
    row_count = rng.randint(50, 60)
    group_count = rng.randint(5, 9)
    all_groups = rng.sample(list(GROUPS), group_count)
    included_count = rng.randint(3, min(6, group_count - 1))
    included = set(rng.sample(all_groups, included_count))
    maximum_base_count = min(
        31, int(row_count * 0.70) - included_count - 3
    )
    base_count = rng.randint(max(4, included_count), maximum_base_count)
    used_references: set[str] = set()
    used_amounts: set[Decimal] = set()
    rows = []

    base_rows = []
    included_order = sorted(included, key=_display)
    for index in range(base_count):
        group = included_order[index] if index < included_count else rng.choice(included_order)
        day = _random_day(rng, start, end)
        amount = _random_amount(
            rng, used_amounts, int(minimum * 100), 85_000
        )
        base_rows.append(_row(
            rng, used_references, day=day, status="posted", group=group, amount=amount,
        ))
    rows.extend(base_rows)

    reversed_base = rng.choice(base_rows)
    duplicate_sources = rng.sample(
        [row for row in base_rows if row is not reversed_base], 2
    )
    for original in duplicate_sources:
        original_received = datetime.fromisoformat(original["received"])
        duplicate_day = date.fromisoformat(original["date"]) + timedelta(
            days=rng.randint(-3, 3)
        )
        duplicate_day = min(end, max(start, duplicate_day))
        duplicate_amount = (
            Decimal(original["amount"])
            if rng.random() < 0.5
            else _random_amount(rng, used_amounts, int(minimum * 100), 85_000)
        )
        rows.append(_row(
            rng, used_references, day=duplicate_day, status="posted",
            group=original["group"], amount=duplicate_amount,
            trap_kind="duplicate upload", transaction=original["transaction"],
            received=original_received + timedelta(minutes=rng.randint(5, 2_880)),
        ))

    group_traps = list(DISQUALIFIERS)
    group_traps.extend(
        rng.choice(DISQUALIFIERS) for _ in range(included_count - len(group_traps))
    )
    rng.shuffle(group_traps)
    for group, mistake in zip(included_order, group_traps):
        if mistake == "posting status":
            day, status = _random_day(rng, start, end), "void"
            amount = _random_amount(rng, used_amounts, int(minimum * 100), 85_000)
            trap_kind = "voided entry"
        elif mistake == "reporting window":
            day = end + timedelta(days=rng.randint(1, 18))
            status = "posted"
            amount = _random_amount(rng, used_amounts, int(minimum * 100), 85_000)
            trap_kind = "late entry"
        else:
            day, status = _random_day(rng, start, end), "posted"
            amount = _random_amount(
                rng, used_amounts, 500, int(minimum * 100) - 1
            )
            trap_kind = "below-floor entry"
        rows.append(_row(
            rng, used_references, day=day, status=status, group=group,
            amount=amount, trap_kind=trap_kind,
        ))

    reversed_day = end + timedelta(days=rng.randint(1, 18))
    rows.append(_row(
        rng, used_references, day=reversed_day, status="reversal",
        group=reversed_base["group"], amount=-Decimal(reversed_base["amount"]),
        trap_kind="cross-window reversal", reverses=reversed_base["transaction"],
    ))

    included_row_count = sum(row["group"] in included for row in rows)
    minimum_included_rows = (row_count * 40 + 99) // 100
    maximum_included_rows = row_count * 70 // 100
    target_included_rows = rng.randint(
        max(minimum_included_rows, included_row_count), maximum_included_rows
    )
    while included_row_count < target_included_rows:
        group = rng.choice(included_order)
        mistake = rng.choice(DISQUALIFIERS)
        if mistake == "posting status":
            day, status = _random_day(rng, start, end), "void"
            amount = _random_amount(rng, used_amounts, int(minimum * 100), 85_000)
            trap_kind = "voided audit entry"
        elif mistake == "reporting window":
            day = end + timedelta(days=rng.randint(1, 18))
            status = "posted"
            amount = _random_amount(rng, used_amounts, int(minimum * 100), 85_000)
            trap_kind = "late audit entry"
        else:
            day, status = _random_day(rng, start, end), "posted"
            amount = _random_amount(rng, used_amounts, 500, int(minimum * 100) - 1)
            trap_kind = "below-floor audit entry"
        rows.append(_row(
            rng, used_references, day=day, status=status, group=group,
            amount=amount, trap_kind=trap_kind,
        ))
        included_row_count += 1

    excluded_groups = [group for group in all_groups if group not in included]
    excluded_amount = sum((Decimal(row["amount"]) for row in base_rows), Decimal("0")) + Decimal("1000")
    while excluded_amount in used_amounts:
        excluded_amount += Decimal("1000")
    used_amounts.add(excluded_amount)
    rows.append(_row(
        rng, used_references, day=_random_day(rng, start, end), status="posted",
        group=excluded_groups[0], amount=excluded_amount,
        trap_kind="unapproved service group",
    ))
    for group in excluded_groups[1:]:
        amount = _random_amount(rng, used_amounts, 10_000, 85_000)
        rows.append(_row(
            rng, used_references, day=_random_day(rng, start, end), status="posted",
            group=group, amount=amount, trap_kind="unapproved service group",
        ))
    while len(rows) < row_count:
        group = rng.choice(excluded_groups)
        amount = _random_amount(rng, used_amounts, 500, 85_000)
        rows.append(_row(
            rng, used_references, day=_random_day(rng, start, end),
            status=rng.choice(("posted", "void")), group=group, amount=amount,
            trap_kind="unapproved service group",
        ))

    rng.shuffle(rows)
    for index, row in enumerate(rows, start=1):
        row["record"] = f"L{index:03d}"
        row["work_order"] = (
            f"Service log {rng.randint(1400, 9899)} — "
            f"{rng.choice(('vehicle repair', 'equipment check', 'site visit', 'courier run', 'supply delivery'))}"
        )

    eligible = _eligible_rows(rows, start, end, minimum, included)
    total = _sum(eligible)
    count = len(eligible)
    comparison = rng.choice(("at least", "strictly greater than"))
    if rng.random() < 0.15:
        cap = total
    else:
        cap = total - Decimal("25.00") if rng.random() < 0.53 else total + Decimal("25.00")
    group_counts = defaultdict(int)
    for row in eligible:
        group_counts[row["group"]] += 1
    chosen_group = rng.choice(included_order)
    largest = _largest_group(eligible, included)
    reversed_amount = _sum(
        _eligible_rows(
            rows, start, end, minimum, included, dropped="linked reversal"
        )
    ) - total
    below_minimum_amount = _sum(
        _eligible_rows(
            rows, start, end, minimum, included, dropped="minimum amount"
        )
    ) - total

    mistake_rows = {
        mistake: _eligible_rows(
            rows, start, end, minimum, included, dropped=mistake
        )
        for mistake in MISTAKES
    }
    question_pool = []

    answer, options, origins = _choice_spec(
        "eligible_count", count,
        [(len(result), mistake) for mistake, result in mistake_rows.items()],
        lambda value: f"The eligible transaction count is {value}.",
    )
    question_pool.append({
        "quantity": "eligible_transaction_count",
        "spec": (
            "choice", "How many eligible transactions remain in the ledger?",
            answer, options,
        ),
        "provenance": origins,
    })

    total_bands, total_level = round_bands(
        total, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50"),
                     Decimal("100"), Decimal("250"), Decimal("500"), Decimal("1000")],
        rng, metric="The eligible total",
    )
    total_question = {
        "quantity": "eligible_total",
        "spec": (
            "score", "Which band contains the eligible total after linked reversals?",
            str(total_level), total_bands,
        ),
        "provenance": {},
    }
    cap_question = {
        "quantity": "eligible_total",
        "spec": (
            "noul",
            (
                f"Does the eligible total meet or exceed the review cap of ${cap:,.2f}?"
                if comparison == "at least"
                else f"Does the eligible total strictly exceed the review cap of ${cap:,.2f}?"
            ),
            "true" if (total >= cap if comparison == "at least" else total > cap) else "false",
            {
                "false": "The eligible total satisfies the cap comparison: No.",
                "true": "The eligible total satisfies the cap comparison: Yes.",
            },
        ),
        "provenance": {},
    }
    question_pool.append(rng.choices((total_question, cap_question), weights=(2, 3), k=1)[0])

    answer, options, origins = _choice_spec(
        "group_count", group_counts[chosen_group],
        [
            (sum(row["group"] == chosen_group for row in result), mistake)
            for mistake, result in mistake_rows.items()
        ],
        lambda value: f"The eligible transaction count for {_display(chosen_group)} is {value}.",
    )
    question_pool.append({
        "quantity": f"transaction_count_for_{chosen_group}",
        "spec": (
            "choice",
            f"What is the eligible transaction count for {_display(chosen_group)}?",
            answer, options,
        ),
        "provenance": origins,
    })

    largest_alternatives = [
        (
            _largest_group(
                result,
                set(all_groups) if mistake == "service group" else included,
            ),
            mistake,
        )
        for mistake, result in mistake_rows.items()
    ]
    answer, options, origins = _choice_spec(
        "group", largest, largest_alternatives,
        lambda value: f"{_display(value)} has the highest filtered total.",
    )
    question_pool.append({
        "quantity": "largest_filtered_group",
        "spec": (
            "choice", "Which group has the highest filtered ledger total?",
            answer, options,
        ),
        "provenance": origins,
    })

    reversal_bands, reversal_level = round_bands(
        reversed_amount, "$", [Decimal("5"), Decimal("10"), Decimal("25"),
                               Decimal("50"), Decimal("100"), Decimal("250")],
        rng, metric="The total of otherwise-eligible entries cancelled by reversal notices",
    )
    question_pool.append({
        "quantity": "reversed_amount",
        "spec": (
            "score", "What is the total of otherwise-eligible entries cancelled by reversal notices?",
            str(reversal_level), reversal_bands,
        ),
        "provenance": {},
    })

    below_bands, below_level = round_bands(
        below_minimum_amount, "$", [Decimal("5"), Decimal("10"), Decimal("25"),
                                    Decimal("50"), Decimal("100"), Decimal("250")],
        rng, metric="The total of entries that pass every other rule but fall below the minimum amount",
    )
    question_pool.append({
        "quantity": "below_minimum_charges",
        "spec": (
            "score", "What is the total of entries that pass every other rule but fall below the minimum amount?",
            str(below_level), below_bands,
        ),
        "provenance": {},
    })
    selected = rng.sample(question_pool, n_questions)
    specs = [item["spec"] for item in selected]

    note = None
    note_mistake = None
    if rng.random() < 0.65:
        if rng.random() < 0.30:
            note_amount = total
            is_correct = True
        else:
            note_mistake = rng.choice(MISTAKES)
            note_amount = _sum(mistake_rows[note_mistake])
            is_correct = False
        note_text = (
            f"Mira (finance): I get ${note_amount:,.2f} for the eligible total, "
            f"so we're {_cap_relation(note_amount, cap)} the cap."
        )
        note = (note_text, is_correct)

    state = (
        f"RECONCILIATION EXPORT — {rng.choice(('Regional Services', 'Claims Processing', 'Field Operations'))}\n"
        f"Review window: {start.isoformat()} through {end.isoformat()} (inclusive)\n"
        f"Minimum eligible amount: ${minimum:.2f}\n"
        f"Eligible service groups: {', '.join(_display(name) for name in included_order)}\n"
        f"Review cap: ${cap:,.2f}\n\n"
        f"Cap comparison: eligible total must be {comparison} the review cap.\n\n"
        "Review instructions: Count posted entries only. For each transaction reference, keep the entry with "
        "the earliest received time; later uploads are duplicate records. The review window includes both "
        "printed service dates. Only the listed service groups and amounts at or above the minimum qualify. "
        "A reversal notice cancels the referenced posting even when the notice date falls outside the review "
        "window. If group totals tie, the alphabetically earlier group name ranks first.\n\n"
        "Operations memo: The export combines routine service charges, audit entries, and late-filed notices. "
        "Amounts are in US dollars. A dashboard subtotal was prepared before this review window was applied, "
        "so the printed subtotal is not a payable amount. Received time is recorded separately from the "
        "service date to preserve the upload history.\n\n"
        "LEDGER EXPORT\n" + _render_export(rows) + "\nEND EXPORT"
    )
    record = finish_record(
        rng, "cg_counting", "reconciled_service_ledger", state, specs,
        facts={
            "rows": rows,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "minimum_amount": str(minimum),
            "included_groups": sorted(included),
            "review_cap": str(cap),
            "cap_comparison": comparison,
        },
        traps=list(MISTAKES),
        note=note,
    )
    record["_meta"]["quantity_kinds"] = {
        f"q{index}": item["quantity"] for index, item in enumerate(selected, start=1)
    }
    record["_meta"]["option_provenance"] = {
        f"q{index}": {
            key: origin for key, origin in item["provenance"].items()
            if key in record["questions"][f"q{index}"]["criteria"]
        }
        for index, item in enumerate(selected, start=1) if item["provenance"]
    }
    record["_meta"]["trap_rows"] = [
        row["record"] for row in rows if row["trap_kind"] is not None
    ]
    record["_meta"]["note_mistake"] = note_mistake
    return record
