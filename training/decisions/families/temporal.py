from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .core import NAMES, choose_domain, near_miss_values, question_specs, record


def business_days_after(start: date, count: int, holidays: set[date], *, include_start: bool = False) -> date:
    current = start
    remaining = count
    while remaining:
        if current.weekday() < 5 and current not in holidays and (current != start or include_start):
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


def _date_key(value: date) -> str:
    return value.strftime("date_%Y_%m_%d")


def _amount_key(value: float) -> str:
    return f"usd_{value:.2f}".replace(".", "_")


def _deadline(rng: random.Random, domain: str, name: str):
    year = rng.choice((2024, 2025, 2026, 2027))
    start = date(year, rng.choice((1, 2, 3, 11, 12)), rng.randint(10, 22))
    holidays = {date(start.year, 12, 25)} if start.month == 12 else {date(start.year, 1, 1)}
    count = rng.randint(3, 8)
    due = business_days_after(start, count, holidays)
    arrived = due + timedelta(days=rng.choice((-2, -1, 1, 2, 3)))
    inclusive = bool(rng.randrange(2))
    days_late = late_days(arrived, due, inclusive_deadline=inclusive)
    boundary = "inclusive" if inclusive else "exclusive"
    holiday_text = ", ".join(day.isoformat() for day in sorted(holidays))
    state = rng.choice((
        f"CASE-MANAGEMENT TICKET — {domain}\nOwner: {name}\nOpened: {start.isoformat()}\n"
        f"Response window: {count} business days; excluded dates: {holiday_text}, Saturdays, and Sundays.\n"
        f"Notice received: {arrived.isoformat()}. Boundary: {boundary}; delivery on the deadline "
        f"{'is' if inclusive else 'is not'} permitted.",
        f"From: {name}\nSubject: {domain} filing calendar\nThe filing window starts after {start.isoformat()} "
        f"and lasts {count} business days. Do not count weekends or {holiday_text}. The cutoff is {boundary}; "
        f"receipt on the cutoff {'qualifies' if inclusive else 'does not qualify'}. The notice arrived "
        f"{arrived.isoformat()}.",
    ))
    candidates = [due + timedelta(days=delta) for delta in (-2, -1, 0, 1, 2)]
    date_options = {_date_key(value): f"The filing deadline is {value.isoformat()}." for value in candidates}
    specs = [
        ("choice", f"What is the business-day filing deadline for {name}?",
         _date_key(due), date_options, None),
        ("noul", f"Did the notice satisfy the {boundary} receipt rule?",
         "true" if (arrived <= due if inclusive else arrived < due) else "false",
         {"false": "The notice falls outside the permitted receipt boundary.",
          "true": "The notice falls within the permitted receipt boundary."}, None),
        ("score", f"How late was the notice under the {boundary} rule?",
         str(min(3, days_late)), None,
         ["The notice is on time under the rule.",
          "The notice is 1 day late.",
          "The notice is 2 days late.",
          "The notice is at least 3 days late."]),
    ]
    return state, specs, (f"business-day count {count}", f"holiday rule {holiday_text}")


def _appointment(rng: random.Random, domain: str, name: str):
    zone = rng.choice(("America/Los_Angeles", "America/New_York"))
    local_day = rng.choice((date(2026, 3, 9), date(2026, 11, 2), date(2026, 7, 14)))
    local = datetime(local_day.year, local_day.month, local_day.day, rng.choice((1, 22)), 30,
                     tzinfo=ZoneInfo(zone))
    utc = local.astimezone(timezone.utc)
    is_dst = local.dst() != timedelta(0)
    offset_hours = int(abs(local.utcoffset().total_seconds()) // 3600)
    naive = local.replace(tzinfo=None)
    winter_offset = datetime(local.year, 1, 15, tzinfo=ZoneInfo(zone)).utcoffset()
    summer_offset = datetime(local.year, 7, 15, tzinfo=ZoneInfo(zone)).utcoffset()
    wrong_offsets = {
        (naive - winter_offset).replace(tzinfo=timezone.utc),
        (naive - summer_offset).replace(tzinfo=timezone.utc),
    }
    wrong_sign = (local.replace(tzinfo=None) + local.utcoffset()).replace(tzinfo=timezone.utc)
    utc_candidates = [
        utc, *sorted(wrong_offsets - {utc}), utc - timedelta(hours=1),
        utc + timedelta(hours=1), wrong_sign,
    ]
    utc_candidates = list(dict.fromkeys(utc_candidates))
    state = (
        f"CALENDAR INVITATION\nHost: {name}\nPurpose: {domain} review\n"
        f"Appointment starts {local.isoformat()} in the named zone {zone}. The calendar stores the local "
        "zone identifier and applies its daylight-saving rules at the appointment date."
    )
    time_options = {
        value.strftime("utc_%Y_%m_%d_%H_%M"):
            f"The UTC appointment time is {value.strftime('%Y-%m-%d %H:%M UTC')}."
        for value in utc_candidates
    }
    answer = utc.strftime("utc_%Y_%m_%d_%H_%M")
    specs = [
        ("choice", f"What UTC time should the calendar display for {name}'s appointment?",
         answer, time_options, None),
        ("noul", f"Was daylight-saving time in effect in {zone} at the appointment?",
         "true" if is_dst else "false",
         {"false": "The zone is on standard time at the appointment.",
          "true": "The zone is on daylight-saving time at the appointment."}, None),
        ("score", f"Which band describes the absolute UTC offset for {zone} at the appointment?",
         "0" if offset_hours <= 3 else "1" if offset_hours <= 6 else "2", None,
         ["The zone offset is 0–3 hours.",
          "The zone offset is 4–6 hours.",
          "The zone offset is 7 hours or more."]),
    ]
    return state, specs, (f"local appointment {local.isoformat()}", f"zone offset {local.utcoffset()}")


def _proration(rng: random.Random, domain: str, name: str):
    year = rng.choice((2024, 2025, 2026, 2027))
    month = rng.randint(1, 12)
    month_days = calendar.monthrange(year, month)[1]
    period_days = rng.randint(max(2, month_days // 3), month_days - 1)
    monthly = float(rng.choice((900, 1200, 2400)))
    amount = prorate_monthly(monthly, year, month, period_days)
    cap = round(monthly * rng.choice((0.45, 0.65, 0.85)), 2)
    if cap == amount:
        cap = round(cap + 17, 2)
    daily = monthly / month_days
    one_day_short = prorate_monthly(monthly, year, month, period_days - 1)
    one_day_long = prorate_monthly(monthly, year, month, period_days + 1)
    thirty_day_base = round(monthly * period_days / 30, 2)
    values = near_miss_values(
        amount, (one_day_short, one_day_long, thirty_day_base, monthly),
        minimum=5, lower=0, upper=monthly * 1.1, step=0.5,
    )
    options = {_amount_key(value): f"The prorated allowance is ${value:.2f}." for value in values}
    start = date(year, month, 1)
    end = start + timedelta(days=period_days - 1)
    state = rng.choice((
        f"INVOICE REVIEW — {domain}\nAccount contact: {name}\nMonthly service allowance: ${monthly:.2f}\n"
        f"Billable period: {start.isoformat()} through {end.isoformat()}, inclusive. The invoice uses actual "
        f"calendar days in {year}-{month:02d}; approval is permitted up to ${cap:.2f}.",
        f"{name} is checking the {domain} invoice. The service began {start.isoformat()} and ended "
        f"{end.isoformat()} inclusive. The allowance is ${monthly:.2f} per calendar month, prorated using "
        f"the exact number of days in that month. The approval ceiling is ${cap:.2f}.",
    ))
    fraction = period_days / month_days
    specs = [
        ("choice", f"What allowance is due for the covered dates in {year}-{month:02d}?",
         _amount_key(amount), options, None),
        ("noul", f"Is the prorated allowance within the approval ceiling?",
         "true" if amount <= cap else "false",
         {"false": "The prorated charge is above the permitted ceiling.",
          "true": "The prorated charge is within the permitted ceiling."}, None),
        ("score", f"Which band describes the fraction of {year}-{month:02d} covered?",
         "0" if fraction < 0.34 else "1" if fraction < 0.67 else "2", None,
         ["The service period is under 34% of the month.",
          "The service period is 34% to under 67% of the month.",
          "The service period is at least 67% of the month."]),
    ]
    return state, specs, (f"daily rate ${daily:.4f}", f"30-day denominator amount ${thirty_day_base:.2f}")


def _leap_year(rng: random.Random, domain: str, name: str):
    year = rng.choice((2023, 2024, 2025, 2028))
    last_day = calendar.monthrange(year, 2)[1]
    renewal_day = date(year, 2, last_day)
    is_leap = calendar.isleap(year)
    state = (
        f"RENEWAL FORM — {domain}\nSubmitted by: {name}\nCoverage starts on {year}-02-01 and runs through "
        "the final calendar day of February, inclusive. The Gregorian calendar determines the month boundary."
    )
    dates = [date(year, 2, 27), date(year, 2, 28), date(year, 3, 1), date(year, 3, 2)]
    if is_leap:
        dates.insert(2, date(year, 2, 29))
    options = {
        _date_key(value): f"The inclusive renewal window ends on {value.isoformat()}."
        for value in dates
    }
    specs = [
        ("choice", f"What is the final date of {name}'s February {year} coverage window?",
         _date_key(renewal_day), options, None),
        ("noul", f"Does {year} have an additional February calendar day?",
         "true" if is_leap else "false",
         {"false": "February has no additional calendar day this year.",
          "true": "February includes an additional calendar day this year."}, None),
        ("score", f"How many calendar days are in the February coverage window for {year}?",
         "0" if last_day < 28 else "1" if last_day == 28 else "2", None,
         ["The coverage window contains fewer than 28 days.",
          "The coverage window contains exactly 28 days.",
          "The coverage window contains 29 days."]),
    ]
    return state, specs, (f"February day count {last_day}",)


def _scenario(rng: random.Random, domain: str, name: str):
    kind = rng.choice(("deadline", "appointment", "proration", "leap"))
    return {
        "deadline": _deadline,
        "appointment": _appointment,
        "proration": _proration,
        "leap": _leap_year,
    }[kind](rng, domain, name)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    state, specs, intermediate_values = _scenario(rng, domain, name)
    selected_types = question_specs(types, n_questions)
    by_kind = {spec[0]: spec for spec in specs}
    return record(
        rng, "temporal", domain, state,
        [(kind, *by_kind[kind][1:]) for kind in selected_types],
        intermediate_values=intermediate_values,
    )
