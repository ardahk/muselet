from __future__ import annotations

import calendar
import random
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..common import finish_record, key_for_value, round_bands, score_level_for

TRANSITIONS = (
    datetime(2027, 3, 14, 10, 0, tzinfo=timezone.utc),
    datetime(2027, 11, 7, 9, 0, tzinfo=timezone.utc),
    datetime(2028, 3, 12, 10, 0, tzinfo=timezone.utc),
    datetime(2028, 11, 5, 9, 0, tzinfo=timezone.utc),
)
TIME_ZONES = ("America/Los_Angeles", "America/New_York")


def _add_months(start: date, months: int) -> date:
    index = start.year * 12 + start.month - 1 + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _subtract_months(target: date, months: int) -> date:
    index = target.year * 12 + target.month - 1 - months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(target.day, calendar.monthrange(year, month)[1]))


def _business_deadline(start: date, count: int, holidays: set[date]) -> date:
    cursor = start
    remaining = count
    while remaining:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5 and cursor not in holidays:
            remaining -= 1
    return cursor


def _next_weekday(day: date) -> date:
    cursor = day + timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor += timedelta(days=1)
    return cursor


def _make_dates(rng: random.Random, transition_day: date):
    months = rng.randint(1, 36)
    if rng.random() < 0.35:
        start = rng.choice((date(2024, 2, 29), date(2024, 1, 31), date(2025, 8, 31)))
        anniversary = _add_months(start, months)
    else:
        anniversary = transition_day - timedelta(days=rng.choice((2, 3, 4)))
        start = _subtract_months(anniversary, months)
        anniversary = _add_months(start, months)

    business_days = rng.randint(2, 7)
    first_holiday = _next_weekday(anniversary)
    holidays = {first_holiday}
    cursor = first_holiday + timedelta(days=1)
    while len(holidays) < 2:
        if cursor.weekday() < 5:
            holidays.add(cursor)
        cursor += timedelta(days=1)
    if rng.random() < 0.5:
        holidays.add(anniversary + timedelta(days=rng.randint(18, 30)))
    deadline = _business_deadline(anniversary, business_days, holidays)
    return start, months, anniversary, business_days, holidays, deadline


def _make_timestamps(rng: random.Random, transition: datetime):
    gap = rng.choice((30, 45, 60, 75, 90))
    before = transition - timedelta(minutes=gap // 2)
    after = before + timedelta(minutes=gap)
    if rng.randrange(2):
        receipt_utc, cutoff_utc = before, after
    else:
        receipt_utc, cutoff_utc = after, before
    receipt_zone, cutoff_zone = TIME_ZONES if rng.randrange(2) else TIME_ZONES[::-1]
    receipt = receipt_utc.astimezone(ZoneInfo(receipt_zone))
    cutoff = cutoff_utc.astimezone(ZoneInfo(cutoff_zone))
    return receipt, receipt_zone, cutoff, cutoff_zone, gap


def _date_options(stem: str, value: date, radius: int = 4):
    options = {}
    for offset in range(-radius, radius + 1):
        candidate = value + timedelta(days=offset)
        key = key_for_value(stem, candidate.strftime("%Y_%m_%d"))
        options[key] = f"The calculated date is {candidate.isoformat()}."
    answer = key_for_value(stem, value.strftime("%Y_%m_%d"))
    return answer, options


def _timestamp_options(value: datetime):
    options = {}
    for offset in range(-4, 5):
        candidate = value + timedelta(minutes=15 * offset)
        key = key_for_value("receipt_utc", candidate.strftime("%Y_%m_%d_%H_%M"))
        options[key] = f"The receipt time in UTC is {candidate.strftime('%Y-%m-%d %H:%M')}."
    answer = key_for_value("receipt_utc", value.strftime("%Y_%m_%d_%H_%M"))
    return answer, options


def _render_state(
    start: date,
    months: int,
    anniversary: date,
    business_days: int,
    holidays: set[date],
    deadline: date,
    arrival_date: date,
    inclusive: bool,
    receipt: datetime,
    receipt_zone: str,
    cutoff: datetime,
    cutoff_zone: str,
) -> str:
    holiday_text = ", ".join(day.isoformat() for day in sorted(holidays))
    boundary_text = "on or before" if inclusive else "strictly before"
    return (
        "SERVICE CALENDAR REVIEW — Renewal and Receipt Timing\n"
        "The member file is being checked against the renewal cycle and the regional intake clock. "
        "Dates in the cycle record are local calendar dates; receipt and cutoff stamps retain their "
        "original named-zone offsets so the audit can be reproduced without a workstation setting.\n\n"
        "CYCLE RECORD\n"
        f"Cycle opened: {start.isoformat()}\n"
        f"Renewal interval: {months} calendar months after opening\n"
        "Anniversary instruction: retain the numbered day when it exists; otherwise use the final "
        "calendar day of that month. The opening date itself is not counted as a later anniversary.\n"
        f"Response window: {business_days} business days after the anniversary date\n"
        "Calendar instruction: a business day is Monday through Friday; do not count the anniversary "
        "date itself. Exclude every date printed in the published holiday schedule.\n"
        f"Published holiday schedule: {holiday_text}\n"
        f"Notice received on: {arrival_date.isoformat()}\n"
        f"Date boundary: receipt must be {boundary_text} the computed response deadline.\n\n"
        "INTAKE CLOCK RECORD\n"
        f"Receipt timestamp: {receipt.isoformat(timespec='minutes')} [{receipt_zone}]\n"
        f"Receipt clock: {receipt.strftime('%Z')} local time, recorded by the intake portal.\n"
        f"Daily cutoff timestamp: {cutoff.isoformat(timespec='minutes')} [{cutoff_zone}]\n"
        f"Cutoff clock: {cutoff.strftime('%Z')} local time, copied from the regional service desk.\n"
        "Clock instruction: compare the two instants after applying the named IANA time zones, not by "
        "subtracting the displayed wall-clock digits. The timestamps were logged around a seasonal "
        "clock change; their numeric UTC offsets are part of each record.\n\n"
        "CASEWORKER SUMMARY\n"
        f"The monthly cycle opened on {start.strftime('%B')} {start.day}, {start.year}, and the file "
        f"requests a {months}-month renewal. The published calendar is attached because the response "
        "window crosses ordinary weekends and local nonworking dates. Intake staff should retain both "
        "the date-level filing result and the separate clock comparison in the case note.\n"
        f"The computed anniversary is {anniversary.isoformat()}; the service desk will use the "
        f"{business_days}-business-day window ending on {deadline.isoformat()}. The monthly date "
        "rule is applied before the business calendar, and the named-zone timestamps are evaluated "
        "as absolute instants. A previous desk card listed a different cutoff convention and is "
        "retained only as an archival reference."
    )


def _read_state(state: str):
    def capture(pattern: str) -> str:
        match = re.search(pattern, state, re.MULTILINE)
        if not match:
            raise ValueError(f"missing rendered field: {pattern}")
        return match.group(1)

    start = date.fromisoformat(capture(r"^Cycle opened: (\d{4}-\d{2}-\d{2})$"))
    months = int(capture(r"^Renewal interval: (\d+) calendar months"))
    business_days = int(capture(r"^Response window: (\d+) business days"))
    holiday_text = capture(r"^Published holiday schedule: (.+)$")
    holidays = {
        date.fromisoformat(item)
        for item in re.findall(r"\d{4}-\d{2}-\d{2}", holiday_text)
    }
    arrival_date = date.fromisoformat(capture(r"^Notice received on: (\d{4}-\d{2}-\d{2})$"))
    inclusive = (
        capture(r"^Date boundary: receipt must be (.+) the computed response deadline\.$")
        == "on or before"
    )
    receipt_match = re.search(
        r"^Receipt timestamp: (.+) \[([A-Za-z_]+/[A-Za-z_]+)\]$", state, re.MULTILINE
    )
    cutoff_match = re.search(
        r"^Daily cutoff timestamp: (.+) \[([A-Za-z_]+/[A-Za-z_]+)\]$", state, re.MULTILINE
    )
    if not receipt_match or not cutoff_match:
        raise ValueError("missing named-zone timestamps")
    receipt = datetime.fromisoformat(receipt_match.group(1))
    cutoff = datetime.fromisoformat(cutoff_match.group(1))
    receipt_zone, cutoff_zone = receipt_match.group(2), cutoff_match.group(2)
    for stamp, zone_name in ((receipt, receipt_zone), (cutoff, cutoff_zone)):
        zone_stamp = stamp.astimezone(ZoneInfo(zone_name))
        if zone_stamp.replace(tzinfo=None) != stamp.replace(tzinfo=None):
            raise ValueError("rendered offset does not match its named zone")
    anniversary = _add_months(start, months)
    deadline = _business_deadline(anniversary, business_days, holidays)
    return {
        "start": start,
        "months": months,
        "anniversary": anniversary,
        "business_days": business_days,
        "holidays": holidays,
        "deadline": deadline,
        "arrival_date": arrival_date,
        "inclusive": inclusive,
        "receipt": receipt.astimezone(timezone.utc),
        "cutoff": cutoff.astimezone(timezone.utc),
    }


def verify_rendered(record: dict) -> bool:
    try:
        data = _read_state(record["state"])
        timely_date = (
            data["arrival_date"] <= data["deadline"]
            if data["inclusive"]
            else data["arrival_date"] < data["deadline"]
        )
        timely_clock = data["receipt"] <= data["cutoff"]
        gap_minutes = abs(int((data["receipt"] - data["cutoff"]).total_seconds() // 60))
        for qid, question in record["questions"].items():
            instruction = question["instructions"]
            if instruction == "What date is the next renewal anniversary?":
                expected = key_for_value(
                    "renewal_date", data["anniversary"].strftime("%Y_%m_%d")
                )
            elif instruction == "What date ends the business-day response window?":
                expected = key_for_value(
                    "business_deadline", data["deadline"].strftime("%Y_%m_%d")
                )
            elif instruction == "What UTC timestamp corresponds to the logged receipt?":
                expected = key_for_value(
                    "receipt_utc", data["receipt"].strftime("%Y_%m_%d_%H_%M")
                )
            elif instruction == "Was the receipt recorded by the cross-zone cutoff?":
                expected = "true" if timely_clock else "false"
            elif instruction == "Was the notice received within the business-day boundary?":
                expected = "true" if timely_date else "false"
            elif instruction == "Which band contains the absolute receipt-to-cutoff separation?":
                expected = score_level_for(Decimal(gap_minutes), question["criteria"])
            else:
                return False
            if record["gold"][qid] != expected:
                return False

        note_meta = record["_meta"]["staff_note"]
        note = re.search(
            r"Mira \(operations\): I have the notice marked (within|outside) the filing window\.",
            record["state"],
        )
        if note_meta["included"] != bool(note):
            return False
        if note:
            claim = note.group(1) == "within"
            if note_meta["correct"] is not (claim == timely_date):
                return False
    except (ValueError, KeyError, IndexError, OverflowError, ZoneInfoNotFoundError):
        return False
    return True


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    transition = rng.choice(TRANSITIONS)
    start, months, anniversary, business_days, holidays, deadline = _make_dates(
        rng, transition.date()
    )
    receipt, receipt_zone, cutoff, cutoff_zone, gap = _make_timestamps(rng, transition)
    arrival_date = deadline
    inclusive = bool(rng.randrange(2))
    date_timely = inclusive
    clock_timely = receipt.astimezone(timezone.utc) <= cutoff.astimezone(timezone.utc)
    specs = []

    answer, options = _date_options("renewal_date", anniversary)
    specs.append((
        "choice", "What date is the next renewal anniversary?", answer, options,
    ))
    answer, options = _date_options("business_deadline", deadline)
    specs.append((
        "choice", "What date ends the business-day response window?", answer, options,
    ))
    receipt_utc = receipt.astimezone(timezone.utc)
    answer, options = _timestamp_options(receipt_utc)
    specs.append((
        "choice", "What UTC timestamp corresponds to the logged receipt?", answer, options,
    ))
    specs.append((
        "noul", "Was the receipt recorded by the cross-zone cutoff?",
        "true" if clock_timely else "false",
        {
            "false": "The receipt was recorded by the cross-zone cutoff: No.",
            "true": "The receipt was recorded by the cross-zone cutoff: Yes.",
        },
    ))
    specs.append((
        "noul", "Was the notice received within the business-day boundary?",
        "true" if date_timely else "false",
        {
            "false": "The notice was received within the business-day boundary: No.",
            "true": "The notice was received within the business-day boundary: Yes.",
        },
    ))
    bands, level = round_bands(
        Decimal(gap), "minutes",
        [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50")],
        rng, metric="The absolute receipt-to-cutoff separation",
    )
    specs.append((
        "score", "Which band contains the absolute receipt-to-cutoff separation?",
        str(level), bands,
    ))
    selected = rng.sample(specs, n_questions)

    note = None
    if rng.random() < 0.65:
        correct = rng.random() < 0.30
        claim_within = date_timely if correct else not date_timely
        note = (
            "Mira (operations): I have the notice marked "
            f"{'within' if claim_within else 'outside'} the filing window.",
            correct,
        )

    state = _render_state(
        start, months, anniversary, business_days, holidays, deadline,
        arrival_date, inclusive, receipt, receipt_zone, cutoff, cutoff_zone,
    )
    record_rng = random.Random(rng.getrandbits(64))
    record = finish_record(
        record_rng, "cg_temporal", "renewal_business_day_zone_cutoff", state, selected,
        facts={
            "cycle_opened": start.isoformat(),
            "renewal_months": months,
            "anniversary": anniversary.isoformat(),
            "business_days": business_days,
            "holidays": sorted(day.isoformat() for day in holidays),
            "deadline": deadline.isoformat(),
            "arrival_date": arrival_date.isoformat(),
            "inclusive": inclusive,
            "receipt_utc": receipt_utc.isoformat(),
            "cutoff_utc": cutoff.astimezone(timezone.utc).isoformat(),
        },
        traps=[
            "month_end_clamp", "holiday_calendar", "business_day_count",
            "dst_zone_conversion", "boundary_comparison",
        ],
        note=note,
        intermediate_values=[f"{anniversary.isoformat()}::{deadline.isoformat()}::{gap}"],
    )
    record["_meta"]["quantity_kinds"] = {
        f"q{index}": question["instructions"]
        for index, question in enumerate(record["questions"].values(), start=1)
    }
    record["_meta"]["timestamp_gap_minutes"] = gap
    return record
