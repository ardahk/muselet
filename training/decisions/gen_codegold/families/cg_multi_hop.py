from __future__ import annotations

import csv
import io
import random
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..common import choice_options, finish_record, key_for_value, round_bands, score_level_for

CENT = Decimal("0.01")
CURRENCIES = ("CAD", "CHF", "EUR", "GBP")
CURRENT_RATES = {
    "CAD": Decimal("0.74"),
    "CHF": Decimal("1.12"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.27"),
}
TIERS = ("Review", "Manager", "Director", "Executive")


def _csv_text(rows, columns) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().rstrip()


def _key(stem, value, places=0):
    return key_for_value(stem, value, places=places if isinstance(value, Decimal) else 0)


def _choice(stem, answer, alternatives, describe, *, places=0):
    answer_key = _key(stem, answer, places)
    options = {answer_key: describe(answer)}
    origins = {answer_key: "correct"}
    for value, mistake in alternatives:
        option_key = _key(stem, value, places)
        if option_key != answer_key and option_key not in options:
            options[option_key] = describe(value)
            origins[option_key] = mistake
    if len(options) < 2:
        raise ValueError(f"{stem} has no computed alternative")
    return answer_key, options, origins


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def _tier_for(amount: Decimal, matrix) -> str:
    for row in matrix:
        lower = Decimal(row["Lower USD"])
        upper = Decimal(row["Upper USD"])
        if lower <= amount < upper:
            return row["Approval band"]
    raise ValueError("no approval band covers the converted amount")


def _valid_on(row, day: date, start_field: str, end_field: str) -> bool:
    return (
        date.fromisoformat(row[start_field]) <= day
        <= date.fromisoformat(row[end_field])
    )


def _vendor_number(rng, used):
    while True:
        value = f"VN-{rng.randint(30000, 99999)}"
        if value not in used:
            used.add(value)
            return value


def _parse_table(state: str, heading: str):
    section = state.split(f"{heading}\n", 1)[1].split("\n\n", 1)[0]
    return list(csv.DictReader(io.StringIO(section)))


def _read_documents(state: str):
    requested = re.search(r"Supplier trading name: (.+)", state).group(1)
    invoice_day = date.fromisoformat(
        re.search(r"Invoice date: (\d{4}-\d{2}-\d{2})", state).group(1)
    )
    amount_text = re.search(r"Amount submitted: ([\d,]+\.\d{2})", state).group(1)
    amount = Decimal(amount_text.replace(",", ""))
    return {
        "requested": requested,
        "invoice_day": invoice_day,
        "invoice_amount": amount,
        "entities": _parse_table(state, "ENTITY DIRECTORY"),
        "agreements": _parse_table(state, "AGREEMENT REGISTER"),
        "rates": _parse_table(state, "FX RATE BULLETIN"),
        "matrix": _parse_table(state, "APPROVAL MATRIX"),
    }


def _resolve(documents):
    requested = documents["requested"]
    vendor = next(
        row for row in documents["entities"]
        if row["Trading name"] == requested
    )
    invoice_day = documents["invoice_day"]
    agreement = next(
        row for row in documents["agreements"]
        if row["Vendor number"] == vendor["Vendor number"]
        and row["Status"] == "Signed"
        and _valid_on(row, invoice_day, "Valid from", "Valid through")
    )
    rate = next(
        row for row in documents["rates"]
        if row["Currency"] == agreement["Payment currency"]
        and _valid_on(row, invoice_day, "Effective from", "Effective through")
    )
    converted = (
        documents["invoice_amount"] * Decimal(rate["USD per unit"])
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    tier = _tier_for(converted, documents["matrix"])
    return vendor, agreement, rate, converted, tier


def _alternative_conversion(amount, agreement, rates, day):
    rate = next(
        row for row in rates
        if row["Currency"] == agreement["Payment currency"]
        and _valid_on(row, day, "Effective from", "Effective through")
    )
    return (amount * Decimal(rate["USD per unit"])).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def _relation(amount: Decimal, limit: Decimal) -> str:
    return "within" if amount <= limit else "above"


def verify_rendered(record: dict) -> bool:
    try:
        documents = _read_documents(record["state"])
        vendor, agreement, rate, converted, tier = _resolve(documents)
        limit = Decimal(agreement["Authorization limit (USD)"])
        currencies = {row["Currency"] for row in documents["rates"]}
        old_rates = [
            row for row in documents["rates"]
            if row["Currency"] == agreement["Payment currency"]
            and date.fromisoformat(row["Effective through"]) < documents["invoice_day"]
        ]
        if not old_rates or not currencies:
            return False

        for qid, question in record["questions"].items():
            instruction = question["instructions"]
            answer = record["gold"][qid]
            if instruction == "Which approval tier applies to the converted invoice amount?":
                wanted = _key("approval_tier", tier)
            elif instruction == "What amount in US dollars results from applying the active exchange rate?":
                wanted = _key("usd_amount", converted, places=2)
            elif instruction == "Which band contains the converted invoice amount?":
                wanted = score_level_for(converted, question["criteria"])
            elif instruction == "Does the invoice date fall in the second half of its month?":
                wanted = "true" if documents["invoice_day"].day >= 16 else "false"
            elif instruction == "Which currency is specified by the active agreement?":
                wanted = _key("payment_currency", agreement["Payment currency"])
            elif instruction == "Does the converted invoice amount stay within the active authorization limit?":
                wanted = "true" if converted <= limit else "false"
            else:
                return False
            if answer != wanted:
                return False

        return True
    except (ValueError, KeyError, IndexError, StopIteration, InvalidOperation, AttributeError):
        return False
    return True


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    invoice_day = date(2027, rng.randint(1, 12), rng.randint(5, 25))
    active_from = invoice_day.replace(day=1)
    prior_through = active_from - timedelta(days=1)
    service_names = (
        "Cedar Ridge Analytics", "Northstar Field Services",
        "Pine Harbor Mobility", "Silverline Data Group",
    )
    requested = rng.choice(service_names)
    legal_suffixes = ("LLC", "Ltd.", "GmbH", "Inc.")
    suffix = rng.choice(legal_suffixes)
    near_suffix = rng.choice([item for item in legal_suffixes if item != suffix])
    vendor_ids = set()
    vendor_id = _vendor_number(rng, vendor_ids)
    near_id = _vendor_number(rng, vendor_ids)
    old_vendor_id = _vendor_number(rng, vendor_ids)
    decoy_names = [
        f"{requested} {rng.choice(('Europe', 'North', 'Holdings'))}",
        requested[:-1] if requested.endswith("s") else f"{requested} Service",
        f"{requested} Group",
        "Harborlight Technical Partners",
        "West Vale Service Collective",
    ]
    entities = [
        {
            "Vendor number": vendor_id,
            "Registered legal name": f"{requested} {suffix}",
            "Trading name": requested,
            "Registered country": rng.choice(("Canada", "Switzerland", "Germany", "United Kingdom")),
            "Directory note": "Primary supplier profile",
        },
        {
            "Vendor number": near_id,
            "Registered legal name": f"{requested} {near_suffix}",
            "Trading name": decoy_names[0],
            "Registered country": "United States",
            "Directory note": "Separate regional entity",
        },
        {
            "Vendor number": old_vendor_id,
            "Registered legal name": f"{requested.removesuffix('s')} {rng.choice(('LLC', 'Ltd.'))}",
            "Trading name": decoy_names[1],
            "Registered country": "Ireland",
            "Directory note": "Legacy naming variant",
        },
    ]
    for name in decoy_names[2:]:
        entities.append({
            "Vendor number": _vendor_number(rng, vendor_ids),
            "Registered legal name": f"{name} {rng.choice(('LLC', 'Ltd.', 'GmbH'))}",
            "Trading name": name,
            "Registered country": rng.choice(("Canada", "Germany", "Ireland", "United States")),
            "Directory note": rng.choice(("Operations vendor", "Regional billing profile", "Archive import")),
        })

    currency = rng.choice(CURRENCIES)
    old_currency = rng.choice([item for item in CURRENCIES if item != currency])
    target_amount = Decimal(rng.choice(("2550.00", "4950.00", "9950.00", "10050.00")))
    old_factor = Decimal("0.80") if target_amount == Decimal("2550.00") else (
        Decimal("1.10") if target_amount in (Decimal("4950.00"), Decimal("9950.00"))
        else Decimal("0.85")
    )
    current_rate = CURRENT_RATES[currency]
    old_rate_for_currency = (current_rate * old_factor).quantize(Decimal("0.0001"))
    invoice_amount = (target_amount / current_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    converted = (invoice_amount * current_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    authorization_limit = converted + Decimal("250.00") if rng.randrange(2) else converted - Decimal("250.00")
    agreement_rows = [
        {
            "Agreement reference": f"AG-{rng.randint(10000, 99999)}",
            "Vendor number": vendor_id,
            "Payment currency": old_currency,
            "Valid from": "2025-01-01",
            "Valid through": prior_through.isoformat(),
            "Authorization limit (USD)": f"{converted + Decimal('900.00'):.2f}",
            "Status": "Superseded",
        },
        {
            "Agreement reference": f"AG-{rng.randint(10000, 99999)}",
            "Vendor number": vendor_id,
            "Payment currency": currency,
            "Valid from": active_from.isoformat(),
            "Valid through": "2028-12-31",
            "Authorization limit (USD)": f"{authorization_limit:.2f}",
            "Status": "Signed",
        },
    ]
    for entity in entities[1:]:
        agreement_rows.append({
            "Agreement reference": f"AG-{rng.randint(10000, 99999)}",
            "Vendor number": entity["Vendor number"],
            "Payment currency": rng.choice(CURRENCIES),
            "Valid from": "2026-01-01",
            "Valid through": "2028-12-31",
            "Authorization limit (USD)": f"{rng.randint(2500, 18000):.2f}",
            "Status": "Signed",
        })
    for _ in range(3):
        entity = rng.choice(entities[1:])
        agreement_rows.append({
            "Agreement reference": f"AG-{rng.randint(10000, 99999)}",
            "Vendor number": entity["Vendor number"],
            "Payment currency": rng.choice(CURRENCIES),
            "Valid from": "2024-01-01",
            "Valid through": "2025-12-31",
            "Authorization limit (USD)": f"{rng.randint(1500, 12000):.2f}",
            "Status": "Archived",
        })

    rates = []
    for code in CURRENCIES:
        active_rate = CURRENT_RATES[code]
        if code == currency:
            previous_rate = old_rate_for_currency
        else:
            factor = rng.choice((Decimal("0.84"), Decimal("1.16")))
            previous_rate = (active_rate * factor).quantize(Decimal("0.0001"))
        rates.extend((
            {
                "Currency": code,
                "USD per unit": f"{previous_rate:.4f}",
                "Effective from": "2025-01-01",
                "Effective through": prior_through.isoformat(),
                "Bulletin": f"FX-{rng.randint(1000, 9999)} (replaced)",
            },
            {
                "Currency": code,
                "USD per unit": f"{active_rate:.4f}",
                "Effective from": active_from.isoformat(),
                "Effective through": "2028-12-31",
                "Bulletin": f"FX-{rng.randint(1000, 9999)}",
            },
        ))
    approval_matrix = [
        {"Approval band": "Review", "Lower USD": "0.00", "Upper USD": "2500.00"},
        {"Approval band": "Manager", "Lower USD": "2500.00", "Upper USD": "5000.00"},
        {"Approval band": "Director", "Lower USD": "5000.00", "Upper USD": "10000.00"},
        {"Approval band": "Executive", "Lower USD": "10000.00", "Upper USD": "9999999.00"},
    ]
    old_fx_amount = (invoice_amount * old_rate_for_currency).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    tier = _tier_for(converted, approval_matrix)
    old_fx_tier = _tier_for(old_fx_amount, approval_matrix)
    old_agreement_rate = CURRENT_RATES[old_currency]
    old_agreement_amount = (invoice_amount * old_agreement_rate).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    old_agreement_tier = _tier_for(old_agreement_amount, approval_matrix)

    near_entity = entities[1]
    near_agreement = next(
        row for row in agreement_rows
        if row["Vendor number"] == near_entity["Vendor number"] and row["Status"] == "Signed"
    )
    near_rate = CURRENT_RATES[near_agreement["Payment currency"]]
    near_amount = (invoice_amount * near_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    near_tier = _tier_for(near_amount, approval_matrix)

    question_pool = []
    tier_answer, tier_options, tier_origins = _choice(
        "approval_tier", tier,
        [
            (old_fx_tier, "superseded_fx"),
            (old_agreement_tier, "superseded_agreement"),
            (near_tier, "near_duplicate_entity"),
        ],
        lambda value: f"The applicable approval tier is {value}.",
    )
    question_pool.append({
        "quantity": "approval_tier",
        "spec": (
            "choice", "Which approval tier applies to the converted invoice amount?",
            tier_answer, tier_options,
        ),
        "origins": tier_origins,
    })

    amount_choice = _choice(
        "usd_amount", converted,
        [
            (old_fx_amount, "superseded_fx"),
            (old_agreement_amount, "superseded_agreement"),
            (near_amount, "near_duplicate_entity"),
            (invoice_amount, "unconverted_invoice_amount"),
        ],
        lambda value: f"The converted invoice amount is {_money(value)}.",
        places=2,
    )
    use_amount_score = rng.random() < 0.5
    score_rng = random.Random(rng.getrandbits(64))
    amount_bands = round_bands(
        converted, "$",
        [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50"),
         Decimal("100"), Decimal("250"), Decimal("500")],
        score_rng, levels=(3, 3), metric="The converted invoice amount",
    )
    if use_amount_score:
        amount_question = {
            "quantity": "converted_invoice_amount",
            "spec": (
                "score", "Which band contains the converted invoice amount?",
                str(amount_bands[1]), amount_bands[0],
            ),
            "origins": {},
        }
    else:
        amount_question = {
            "quantity": "converted_invoice_amount",
            "spec": (
                "choice", "What amount in US dollars results from applying the active exchange rate?",
                amount_choice[0], amount_choice[1],
            ),
            "origins": amount_choice[2],
        }
    question_pool.append(amount_question)

    invoice_in_second_half = invoice_day.day >= 16
    question_pool.append({
        "quantity": "invoice_month_half",
        "spec": (
            "noul", "Does the invoice date fall in the second half of its month?",
            "true" if invoice_in_second_half else "false",
            {
                "false": "The invoice date falls in the second half of its month: No.",
                "true": "The invoice date falls in the second half of its month: Yes.",
            },
        ),
        "origins": {},
    })

    currency_alternatives = [
        (old_currency, "superseded_agreement"),
        *[(code, "wrong_currency") for code in CURRENCIES if code != currency],
    ]
    currency_answer, currency_options, currency_origins = _choice(
        "payment_currency", currency, currency_alternatives,
        lambda value: f"The active agreement uses {value}.",
    )
    question_pool.append({
        "quantity": "agreement_currency",
        "spec": (
            "choice", "Which currency is specified by the active agreement?",
            currency_answer, currency_options,
        ),
        "origins": currency_origins,
    })

    question_pool.append({
        "quantity": "within_authorization",
        "spec": (
            "noul",
            "Does the converted invoice amount stay within the active authorization limit?",
            "true" if converted <= authorization_limit else "false",
            {
                "false": "The converted amount is within the active authorization limit: No.",
                "true": "The converted amount is within the active authorization limit: Yes.",
            },
        ),
        "origins": {},
    })
    selected = rng.sample(question_pool, n_questions)
    specs = [item["spec"] for item in selected]

    note = None
    note_correct = False
    note_mistake = None
    note_amount, note_tier = converted, tier
    if rng.random() < 0.65:
        if rng.random() < 0.30:
            note_correct = True
        else:
            note_amount, note_tier = old_fx_amount, old_fx_tier
            note_mistake = "superseded_fx"
        note = (
            f"Mira (procurement): I get {_money(note_amount)} for the converted invoice, "
            f"which places it in the {note_tier} approval band.",
            note_correct,
        )

    state = (
        "SUPPLIER SETTLEMENT REVIEW\n"
        f"Supplier trading name: {requested}\n"
        f"Invoice date: {invoice_day.isoformat()}\n"
        f"Amount submitted: {invoice_amount:,.2f} (in the payment currency on the active agreement)\n\n"
        "Review instructions: Match the trading name exactly in the directory; similar registered legal "
        "suffixes do not identify the same supplier. Use the signed agreement whose validity dates include "
        "the invoice date. The agreement sets the payment currency and authorization limit. Select the FX "
        "bulletin for that currency and date, multiply the submitted amount, and round half up to cents. "
        "Approval bands include their lower boundary and exclude their upper boundary.\n\n"
        "ENTITY DIRECTORY\n" + _csv_text(entities, (
            "Vendor number", "Registered legal name", "Trading name",
            "Registered country", "Directory note",
        )) + "\n\n"
        "AGREEMENT REGISTER\n" + _csv_text(agreement_rows, (
            "Agreement reference", "Vendor number", "Payment currency",
            "Valid from", "Valid through", "Authorization limit (USD)", "Status",
        )) + "\n\n"
        "FX RATE BULLETIN\n" + _csv_text(rates, (
            "Currency", "USD per unit", "Effective from", "Effective through", "Bulletin",
        )) + "\n\n"
        "APPROVAL MATRIX\n" + _csv_text(approval_matrix, (
            "Approval band", "Lower USD", "Upper USD",
        )) + "\n\n"
        "Finance desk note: Archived agreements and replaced bulletins remain visible for audit history. "
        "A supplier may use a different payment currency after an amendment, so do not carry an old currency "
        "forward without checking the effective agreement. The matrix is applied only after conversion."
    )
    facts = {
        "requested": requested,
        "invoice_day": invoice_day.isoformat(),
        "invoice_amount": str(invoice_amount),
        "entities": entities,
        "agreements": agreement_rows,
        "rates": rates,
        "matrix": approval_matrix,
        "hop_count": 3,
    }
    record = finish_record(
        rng, "cg_multi_hop", "supplier_fx_approval_chain", state, specs,
        facts=facts,
        traps=["near_duplicate_legal_entity", "superseded_agreement", "superseded_fx", "approval_boundary"],
        note=note,
    )
    record["_meta"]["hop_count"] = 3
    record["_meta"]["quantity_kinds"] = {
        f"q{index}": item["quantity"] for index, item in enumerate(selected, start=1)
    }
    record["_meta"]["option_provenance"] = {
        f"q{index}": {
            key: origin for key, origin in item["origins"].items()
            if key in record["questions"][f"q{index}"]["criteria"]
        }
        for index, item in enumerate(selected, start=1) if item["origins"]
    }
    record["_meta"]["note_mistake"] = note_mistake
    return record
