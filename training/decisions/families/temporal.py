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


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    start = date(rng.randint(2024, 2028), rng.randint(1, 12), 1)
    holidays = {date(start.year, 1, 1), date(start.year, 7, 4), date(start.year, 12, 25)}
    business_day_count = rng.randint(3, 8)
    due = business_days_after(start, business_day_count, holidays)
    month = rng.choice((2, rng.randint(1, 12)))
    days = rng.randint(1, calendar.monthrange(start.year, month)[1])
    amount = rng.choice((900.0, 1200.0, 2400.0))
    charge = prorate_monthly(amount, start.year, month, days)
    zone = rng.choice(("America/Los_Angeles", "America/New_York", "Europe/London"))
    local = datetime(start.year, 4, 10, 9, 30)
    local_zone = local.replace(tzinfo=ZoneInfo(zone))
    utc = local_zone.astimezone(ZoneInfo("UTC"))
    late_offset = rng.randint(0, 6)
    arrived = due + timedelta(days=late_offset)
    inclusive = bool(rng.randrange(2))
    counted_late = late_days(arrived, due, inclusive_deadline=inclusive)
    template = rng.randrange(2)
    if template == 0:
        state = (
            f"{name} administers a {domain} request. The service clock starts on {start.isoformat()} and excludes "
            f"weekends and holidays {', '.join(sorted(x.isoformat() for x in holidays))}. A response is due after "
            f"{business_day_count} business days, on {due.isoformat()}. The notice arrived on {arrived.isoformat()}; "
            f"the deadline is {'inclusive' if inclusive else 'exclusive'}, so delivery on the due date is "
            f"{'on time' if inclusive else 'late'}. The monthly allowance is ${amount:.2f}; a {days}-day "
            f"service period in {start.year}-{month:02d} is prorated by actual days in that month. "
            f"The appointment is {local.isoformat()} in {zone}, equal to {utc.isoformat()} UTC during daylight time. "
            "February has 29 days in a leap year and 28 otherwise. All dates use local civil dates unless UTC is named."
        )
    else:
        state = (
            f"Calendar desk / {domain} / case owner {name}. Clock begins: {start.isoformat()}. Excluded days: "
            f"weekends plus {', '.join(sorted(x.isoformat() for x in holidays))}. Contract response window: "
            f"{business_day_count} business days; computed due date: {due.isoformat()}. Received: {arrived.isoformat()}. "
            f"Boundary is {'inclusive' if inclusive else 'exclusive'} ({'due date is on time' if inclusive else 'due date is late'}). "
            f"Monthly allowance: ${amount:.2f}; charge for {days} service days in {start.year}-{month:02d} uses "
            f"actual month length. Appointment: {local.isoformat()} {zone} = {utc.isoformat()} UTC; the zone observes "
            "daylight saving time. February is 29 days in leap years and 28 in ordinary years."
        )
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            focus = rng.choice(("due", "utc", "proration", "leap"))
            if focus == "utc":
                answer = utc.strftime("%Y-%m-%d %H:%M UTC")
                choices = {answer: "The converted UTC appointment time.",
                           (utc + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M UTC"): "One hour later than the conversion.",
                           (utc - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M UTC"): "One hour earlier than the conversion."}
                instructions = f"What is the UTC time of the appointment in {zone}?"
            elif focus == "proration":
                answer = f"${charge:.2f}"
                choices = {answer: "The allowance prorated using the actual days in the month.",
                           f"${round(charge + 10, 2):.2f}": "A charge that incorrectly adds ten dollars.",
                           f"${round(charge - 10, 2):.2f}": "A charge that incorrectly subtracts ten dollars."}
                instructions = "What is the prorated allowance for the stated service period?"
            elif focus == "leap":
                answer = "29" if calendar.isleap(start.year) else "28"
                choices = {"29": "February has 29 days in this year.",
                           "28": "February has 28 days in this year."}
                instructions = f"How many days does February have in {start.year}?"
            else:
                answer = due.isoformat()
                choices = {
                    answer: "The deadline after the specified number of eligible business days.",
                    (due - timedelta(days=1)).isoformat(): "The preceding calendar date.",
                    (due + timedelta(days=1)).isoformat(): "The following calendar date.",
                }
                instructions = "On what date is the response due?"
            specs.append((kind, instructions, answer, choices, None))
        elif kind == "noul":
            truth = arrived > due if inclusive else arrived >= due
            instructions = f"Does the notice count as late under the {('inclusive' if inclusive else 'exclusive')} rule?"
            specs.append((kind, instructions, "true" if truth else "false", None, None))
        else:
            gold = str(min(3, counted_late))
            levels = ["On time", "1 day late", "2 days late", "3 or more days late"]
            specs.append((kind, "How many days late was the notice, binned by the stated rule?", gold, None, levels))
    return record(rng, "temporal", domain, state, specs)
