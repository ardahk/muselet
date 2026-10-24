from __future__ import annotations

import random
import re
from datetime import date, timedelta
from decimal import Decimal

from ..common import finish_record, key_for_value, round_bands, score_level_for


def _money_line(label, value):
    return f"{label}: ${value:,.2f}"


def _case(rng):
    kind = rng.choice(("negation", "source_precedence", "irrelevant_number"))
    amount = Decimal(rng.randint(800, 4_500))
    dashboard = Decimal(rng.randint(12_000, 95_000))
    exception = None
    amendment_active = None
    if kind == "negation":
        cap = amount + Decimal(rng.randint(-500, 500))
        exception = bool(rng.randrange(2))
        authorized = exception and amount <= cap
        wrong = Decimal("0") if authorized else amount
        state = (
            "CASE REVIEW — Restricted Equipment Allowance\n"
            "Signed policy excerpt: “Payment is not permitted for controlled equipment unless a signed exception "
            "is on file. The exception does not raise the per-claim ceiling.”\n"
            f"Item amount: ${amount:,.2f}\n"
            f"Claim ceiling: ${cap:,.2f}\n"
            f"Signed exception: {'Yes' if exception else 'No'}\n"
            f"Dashboard reserve: ${dashboard:,.2f}\n\n"
            "The case officer is reviewing one equipment claim, not the department's quarterly spending. The signed "
            "exception register is the operative record; a quoted chat message and the dashboard are informational. "
            "The item is already classified as controlled equipment, so the exception clause applies."
        )
        decisive = amount <= cap
        source = "signed policy"
    elif kind == "source_precedence":
        effective = date(2027, rng.randint(1, 10), 1)
        service = effective + timedelta(days=rng.choice((-20, 20)))
        master = Decimal("1800.00")
        amended = Decimal("3400.00")
        amount = Decimal("2500.00")
        claimed_active = not (service >= effective)
        cap = amended if service >= effective else master
        authorized = amount <= cap
        wrong = amount if claimed_active and amount <= amended else Decimal("0")
        state = (
            "CONTRACT FILE — Supplier Invoice Authorization\n"
            "Signed agreement rule: the executed addendum controls only on and after its effective date; otherwise "
            "the signed master agreement applies. Quoted email and dashboard tiles do not amend either record.\n"
            f"Service date: {service.isoformat()}\n"
            f"Addendum effective date: {effective.isoformat()}\n"
            f"Master claim ceiling: ${master:,.2f}\n"
            f"Addendum claim ceiling: ${amended:,.2f}\n"
            f"Invoice amount: ${amount:,.2f}\n"
            f"Quoted email: {'The expanded ceiling is active.' if claimed_active else 'The prior ceiling remains.'}\n"
            f"Dashboard reserve: ${dashboard:,.2f}\n\n"
            "The executed agreement register includes the signed dates and amounts. The email is a quoted status "
            "update, and the dashboard aggregates several suppliers. Apply the record precedence stated in the "
            "signed terms to this invoice's service date."
        )
        decisive = service >= effective
        amendment_active = service >= effective
        source = "signed agreement"
    else:
        cap = Decimal(rng.randint(1_500, 4_000))
        amount = cap + Decimal(rng.choice((-250, 250)))
        dashboard_delta = Decimal(rng.randint(100, int(amount / 2)))
        dashboard = amount + rng.choice((-dashboard_delta, dashboard_delta))
        authorized = amount <= cap
        wrong = dashboard
        state = (
            "SINGLE-CLAIM REVIEW — Field Services\n"
            "Policy excerpt: an approved invoice is payable only when its individual amount is at or below the "
            "per-claim ceiling. The dashboard's highlighted reserve and quarter-to-date total summarize other files.\n"
            f"Invoice amount: ${amount:,.2f}\n"
            f"Per-claim ceiling: ${cap:,.2f}\n"
            f"Claim status: Approved\n"
            f"Dashboard reserve: ${dashboard:,.2f}\n\n"
            "The regional analyst requested a decision on this one invoice. The dashboard uses a larger portfolio "
            "roll-up and is shown because it was the most recently refreshed tile; it is not an alternate limit for "
            "this claim. The signed policy and current case record control."
        )
        decisive = authorized
        source = "signed policy"
    payable = amount if authorized else Decimal("0")
    return {"kind": kind, "state": state, "amount": amount, "cap": cap, "dashboard": dashboard,
            "authorized": authorized, "payable": payable, "wrong": wrong,
            "decisive": decisive, "source": source, "exception": exception,
            "amendment_active": amendment_active}


def _parse(state):
    kind = ("negation" if "CASE REVIEW — Restricted Equipment Allowance" in state else
            "source_precedence" if "CONTRACT FILE — Supplier Invoice Authorization" in state else "irrelevant_number")
    def amount(pattern):
        return Decimal(re.search(pattern, state).group(1).replace(",", ""))
    dashboard = amount(r"Dashboard reserve: \$([\d,]+\.\d{2})")
    exception = None
    amendment_active = None
    if kind == "negation":
        value = amount(r"Item amount: \$([\d,]+\.\d{2})")
        cap = amount(r"Claim ceiling: \$([\d,]+\.\d{2})")
        exception = re.search(r"Signed exception: (Yes|No)", state).group(1) == "Yes"
        authorized = exception and value <= cap
        wrong = Decimal("0") if exception and value <= cap else value
        decisive = value <= cap
        source = "signed policy"
    elif kind == "source_precedence":
        service = date.fromisoformat(re.search(r"Service date: (\d{4}-\d{2}-\d{2})", state).group(1))
        effective = date.fromisoformat(re.search(r"Addendum effective date: (\d{4}-\d{2}-\d{2})", state).group(1))
        master = amount(r"Master claim ceiling: \$([\d,]+\.\d{2})")
        amended = amount(r"Addendum claim ceiling: \$([\d,]+\.\d{2})")
        value = amount(r"Invoice amount: \$([\d,]+\.\d{2})")
        claimed = "expanded ceiling is active" in state
        cap = amended if service >= effective else master
        authorized = value <= cap
        wrong = value if claimed else Decimal("0")
        decisive = service >= effective
        amendment_active = service >= effective
        source = "signed agreement"
    else:
        value = amount(r"Invoice amount: \$([\d,]+\.\d{2})")
        cap = amount(r"Per-claim ceiling: \$([\d,]+\.\d{2})")
        authorized = value <= cap
        wrong = dashboard
        decisive = authorized
        source = "signed policy"
    return {"kind": kind, "amount": value, "cap": cap, "dashboard": dashboard,
            "authorized": authorized, "payable": value if authorized else Decimal("0"),
            "wrong": wrong, "decisive": decisive, "source": source,
            "exception": exception, "amendment_active": amendment_active}


def verify_rendered(record):
    try:
        case = _parse(record["state"])
        for qid, question in record["questions"].items():
            instruction = question["instructions"]
            if instruction == "Is a signed exception on file?":
                expected = "true" if case["exception"] else "false"
            elif instruction == "Does the signed addendum cover the service date?":
                expected = "true" if case["amendment_active"] else "false"
            elif instruction == "Is the dashboard reserve greater than the invoice amount?":
                expected = "true" if case["dashboard"] > case["amount"] else "false"
            elif instruction == "Which record controls this claim review?":
                expected = key_for_value("source", case["source"])
            elif instruction == "Is the individual claim within its printed ceiling?":
                expected = "true" if case["amount"] <= case["cap"] else "false"
            elif instruction == "Which band contains the submitted claim amount?":
                expected = score_level_for(case["amount"], question["criteria"])
            elif instruction == "Which band contains the controlling per-claim ceiling?":
                expected = score_level_for(case["cap"], question["criteria"])
            elif instruction == "What is the claim disposition?":
                expected = "authorized" if case["authorized"] else "held"
            else:
                return False
            if record["gold"][qid] != expected:
                return False
        return True
    except (ValueError, KeyError, AttributeError, TypeError):
        return False
    return True


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    case = _case(rng)
    amount_bands, amount_level = round_bands(
        case["amount"], "$", [Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100")],
        rng, metric="The submitted claim amount",
    )
    cap_bands, cap_level = round_bands(
        case["cap"], "$", [Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100")],
        rng, metric="The controlling per-claim ceiling",
    )
    sources = {
        "negation": ("signed policy", "quoted chat message", "dashboard"),
        "source_precedence": ("signed agreement", "quoted email", "dashboard"),
        "irrelevant_number": ("signed policy", "dashboard", "current case record"),
    }[case["kind"]]
    source_options = {
        key_for_value("source", source): f"The controlling record is the {source}."
        for source in sources
    }
    extra_question = {
        "negation": (
            "Is a signed exception on file?",
            "true" if case["exception"] else "false",
            {
                "false": "A signed exception is on file: No.",
                "true": "A signed exception is on file: Yes.",
            },
        ),
        "source_precedence": (
            "Does the signed addendum cover the service date?",
            "true" if case["amendment_active"] else "false",
            {
                "false": "The signed addendum covers the service date: No.",
                "true": "The signed addendum covers the service date: Yes.",
            },
        ),
        "irrelevant_number": (
            "Is the dashboard reserve greater than the invoice amount?",
            "true" if case["dashboard"] > case["amount"] else "false",
            {
                "false": "The dashboard reserve is greater than the invoice amount: No.",
                "true": "The dashboard reserve is greater than the invoice amount: Yes.",
            },
        ),
    }[case["kind"]]
    pool = [
        ("choice", "What is the claim disposition?",
         "authorized" if case["authorized"] else "held",
         {"authorized": "The claim is authorized.", "held": "The claim is held."}),
        ("score", "Which band contains the submitted claim amount?", str(amount_level), amount_bands),
        ("score", "Which band contains the controlling per-claim ceiling?", str(cap_level), cap_bands),
        ("choice", "Which record controls this claim review?",
         key_for_value("source", case["source"]), source_options),
        ("noul", "Is the individual claim within its printed ceiling?",
         "true" if case["amount"] <= case["cap"] else "false",
         {"false": "The individual claim is within its printed ceiling: No.",
          "true": "The individual claim is within its printed ceiling: Yes."}),
        ("noul", *extra_question),
    ]
    selected = rng.sample(pool, n_questions)
    note = None
    if rng.random() < 0.65:
        correct = rng.random() < 0.30
        amount = case["payable"] if correct else case["wrong"]
        note = (f"Mira (AP): I have ${amount:,.2f} as the cleared amount for this claim.", correct)
    record = finish_record(
        rng, "cg_trap", case["kind"], case["state"], selected,
        facts={"case": case}, traps=["negation", "source_precedence", "salient_irrelevant_number"],
        note=note,
    )
    record["_meta"]["trap_type"] = case["kind"]
    record["_meta"]["quantity_kinds"] = {
        f"q{index}": item[1] for index, item in enumerate(selected, start=1)
    }
    return record
