from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .core import NAMES, choose_domain, question_specs, record


def business_days_after(start: date, count: int, holidays: set[date], *, include_start: bool = False) -> date:
    current = start
    remaining = count
    while remaining:
        if current.weekday() < 5 and current not in holidays:
            if current != start or include_start:
                remaining -= 1
                if not remaining:
                    break
        current += timedelta(days=1)
    return current


def prorate_monthly(amount: float, year: int, month: int, days: int) -> float:
    return round(amount * days / calendar.monthrange(year, month)[1], 2)


def late_days(arrived: date, due: date, *, inclusive_deadline: bool) -> int:
    difference = (arrived - due).days
    return max(0, difference if inclusive_deadline else difference + 1)


def _money_options(answer: float, description: str) -> dict[str, str]:
    options = {}
    for offset in range(-12, 14):
        amount = round(answer + offset * 0.5, 2)
        key = f"usd_{amount:.2f}".replace(".", "_")
        options[key] = f"The {description} is ${amount:.2f}."
    return options


def _scenario(rng: random.Random, domain: str, name: str) -> tuple[str, list[tuple]]:
    kind = rng.choice(("deadline", "appointment", "proration", "leap"))
    if kind == "deadline":
        start = date(rng.choice((2024, 2025, 2026, 2027)), 12, rng.randint(18, 23))
        holidays = {date(start.year, 12, 25)}
        count = rng.randint(3, 8)
        due = business_days_after(start, count, holidays)
        offset = rng.randint(-1, 6)
        arrived = due + timedelta(days=offset)
        inclusive = bool(rng.randrange(2))
        days_late = late_days(arrived, due, inclusive_deadline=inclusive)
        boundary = "inclusive" if inclusive else "exclusive"
        layout = rng.choice(("case note", "intake ticket", "email"))
        if layout == "email":
            state = (
                f"Subject: {domain} response deadline\nFrom: {name}\n"
                f"The request entered the service queue on {start.isoformat()}. Its agreement allows {count} business "
                f"days, excluding weekends and the Christmas closure on {date(start.year, 12, 25).isoformat()}; "
                f"the recorded due date is {due.isoformat()}. The notice was received on {arrived.isoformat()}. "
                f"The contract calls the deadline {boundary}: a filing on the due date is "
                f"{'on time' if inclusive else 'late'}."
            )
        elif layout == "intake ticket":
            state = (
                f"INTAKE TICKET — {domain}\nOwner: {name}\nOpened: {start.isoformat()}\n"
                f"Response window: {count} business days; excluded dates: {date(start.year, 12, 25).isoformat()} "
                f"and Saturdays/Sundays.\nSystem due date: {due.isoformat()}\nNotice received: {arrived.isoformat()}\n"
                f"Boundary policy: {boundary}; delivery on the due date is "
                f"{'permitted' if inclusive else 'outside the window'}."
            )
        else:
            state = (
                f"{name} added a {domain} filing to the calendar desk. The clock began {start.isoformat()} and "
                f"counts {count} business days, skipping weekends and {date(start.year, 12, 25).isoformat()}. "
                f"The due date shown on the register is {due.isoformat()}; the notice arrived {arrived.isoformat()}. "
                f"The controlling deadline is {boundary}, so same-day delivery is "
                f"{'allowed' if inclusive else 'late'}."
            )
        date_options = {
            f"date_{(due + timedelta(days=delta)):%Y_%m_%d}":
                f"The agreement sets {due + timedelta(days=delta):%Y-%m-%d} as the response deadline."
            for delta in range(-12, 14)
        }
        return state, [
            ("choice", f"What is the recorded business-day deadline for {name}'s filing?",
             f"date_{due:%Y_%m_%d}", date_options, None),
            ("noul", f"Did the notice arrive outside the {boundary} deadline for this filing?",
             "true" if (arrived > due if inclusive else arrived >= due) else "false",
             {"false": f"The {arrived.isoformat()} arrival falls within the permitted {boundary} boundary at {due.isoformat()}.",
              "true": f"The {arrived.isoformat()} arrival falls outside the permitted {boundary} boundary at {due.isoformat()}."},
             None),
            ("score", f"How late was the notice under the {boundary} rule?",
             str(min(3, days_late)), None,
             [f"On time under the {boundary} rule.", "1 day late under the stated boundary.",
              "2 days late under the stated boundary.", "3 or more days late under the stated boundary."]),
        ]

    if kind == "appointment":
        zone = rng.choice(("America/Los_Angeles", "America/New_York", "Europe/London"))
        local_day = rng.choice((date(2026, 3, 9), date(2026, 11, 2), date(2026, 7, 14)))
        local = datetime(local_day.year, local_day.month, local_day.day, rng.choice((1, 22)), 30,
                         tzinfo=ZoneInfo(zone))
        utc = local.astimezone(ZoneInfo("UTC"))
        is_dst = local.dst() != timedelta(0)
        offset_hours = int(abs(local.utcoffset().total_seconds()) // 3600)
        state = rng.choice((
            f"CALENDAR INVITATION\nHost: {name}\nPurpose: {domain} review\n"
            f"Start: {local.isoformat()} ({zone})\nUTC display: {utc.strftime('%Y-%m-%d %H:%M UTC')}\n"
            "The scheduling system stores the local zone and applies its daylight-saving rules.",
            f"{name} scheduled a {domain} appointment for {local.isoformat()} in {zone}. "
            f"The calendar export converts that instant to {utc.strftime('%Y-%m-%d %H:%M UTC')}. "
            "Use the named zone's offset on the appointment date, not its winter offset.",
        ))
        time_options = {
            (utc + timedelta(hours=delta)).strftime("utc_%Y_%m_%d_%H_%M"):
                f"The appointment instant converts to {(utc + timedelta(hours=delta)).strftime('%Y-%m-%d %H:%M UTC')}."
            for delta in range(-12, 14)
        }
        answer = utc.strftime("utc_%Y_%m_%d_%H_%M")
        return state, [
            ("choice", f"What UTC time should the calendar display for {name}'s appointment?",
             answer, time_options, None),
            ("noul", f"Was daylight-saving time in effect in {zone} at the appointment?",
             "true" if is_dst else "false",
             {"false": f"The {local_day.isoformat()} appointment uses standard time in {zone}.",
              "true": f"The {local_day.isoformat()} appointment uses daylight-saving time in {zone}."}, None),
            ("score", f"Which band describes the local-to-UTC offset for {zone} on {local_day.isoformat()}?",
             "0" if offset_hours <= 3 else "1" if offset_hours <= 6 else "2", None,
             ["The absolute zone offset is 0–3 hours on the appointment date.",
              "The absolute zone offset is 4–6 hours on the appointment date.",
              "The absolute zone offset is more than 6 hours on the appointment date."]),
        ]

    if kind == "proration":
        year = rng.choice((2024, 2025, 2026, 2027))
        month = rng.randint(1, 12)
        month_days = calendar.monthrange(year, month)[1]
        period_days = rng.randint(max(1, month_days // 3), month_days)
        monthly = float(rng.choice((900, 1200, 2400)))
        amount = prorate_monthly(monthly, year, month, period_days)
        cap = round(amount + rng.choice((-10, 10)), 2)
        fraction = period_days / month_days
        state = rng.choice((
            f"INVOICE REVIEW — {domain}\nAccount contact: {name}\nMonthly service allowance: ${monthly:.2f}\n"
            f"Billable service dates: {year}-{month:02d}-01 through {year}-{month:02d}-{period_days:02d} "
            f"({period_days} calendar days). The month has {month_days} days. Proration uses actual calendar days; "
            f"the approved ceiling is ${cap:.2f}.",
            f"{name} is checking the {domain} invoice for {year}-{month:02d}. The monthly allowance is ${monthly:.2f}; "
            f"service covered {period_days} of the month's {month_days} calendar days. The contract prorates by "
            f"actual days, and charges at or below ${cap:.2f} are within the approval ceiling.",
        ))
        return state, [
            ("choice", f"What allowance is due for the {period_days}-day service period in {year}-{month:02d}?",
             f"usd_{amount:.2f}".replace(".", "_"), _money_options(amount, "prorated allowance"), None),
            ("noul", f"Is the prorated allowance within the ${cap:.2f} approval ceiling?",
             "true" if amount <= cap else "false",
             {"false": f"The ${amount:.2f} prorated allowance exceeds the ${cap:.2f} ceiling.",
              "true": f"The ${amount:.2f} prorated allowance is at or below the ${cap:.2f} ceiling."}, None),
            ("score", f"Which band describes the share of {year}-{month:02d} billed for this service period?",
             "0" if fraction < 0.34 else "1" if fraction < 0.67 else "2", None,
             ["The service period is under 34% of the month's calendar days.",
              "The service period is 34% to under 67% of the month's calendar days.",
              "The service period is at least 67% of the month's calendar days."]),
        ]

    year = rng.choice((2024, 2025, 2026, 2028))
    last_day = calendar.monthrange(year, 2)[1]
    renewal_day = date(year, 2, last_day)
    is_leap = calendar.isleap(year)
    state = rng.choice((
        f"RENEWAL FORM — {domain}\nSubmitted by: {name}\nCoverage window: "
        f"{year}-02-01 through {renewal_day.isoformat()}, inclusive.\n"
        f"The calendar's February entry for {year} has {last_day} days. Renewal coverage follows the Gregorian "
        "calendar; a February 29 is included only when that date exists.",
        f"{name} is processing a {domain} renewal covering February {year}. The coverage starts on "
        f"{year}-02-01 and ends on the final calendar day, {renewal_day.isoformat()}, inclusive. "
        f"February has {last_day} days in this year.",
    ))
    date_options = {
        f"date_{(renewal_day + timedelta(days=delta)):%Y_%m_%d}":
            f"The inclusive renewal window ends on {renewal_day + timedelta(days=delta):%Y-%m-%d}."
        for delta in range(-12, 14)
    }
    return state, [
        ("choice", f"What is the final date of {name}'s inclusive February {year} coverage window?",
         f"date_{renewal_day:%Y_%m_%d}", date_options, None),
        ("noul", f"Does the February {year} coverage window include February 29?",
         "true" if is_leap else "false",
         {"false": f"February {year} has no February 29, so the coverage window contains 28 calendar days.",
          "true": f"February {year} includes February 29 within its {last_day}-day coverage window."}, None),
        ("score", f"How many calendar days does the February {year} coverage window contain?",
         "0" if last_day < 28 else "1" if last_day == 28 else "2", None,
         ["The coverage window contains fewer than 28 calendar days.",
          "The coverage window contains exactly 28 calendar days.",
          "The coverage window contains 29 calendar days."]),
    ]


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    state, specs = _scenario(rng, domain, name)
    selected_types = question_specs(types, n_questions)
    by_kind = {spec[0]: spec for spec in specs}
    return record(rng, "temporal", domain, state, [
        (kind, *by_kind[kind][1:]) for kind in selected_types
    ])
