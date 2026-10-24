from __future__ import annotations

import csv
import io
import random
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..common import choice_options, finish_record, key_for_value, round_bands, score_level_for

CENT = Decimal("0.01")
CURRENCIES = ("CAD", "EUR", "GBP")
RATES = {"CAD": Decimal("0.74"), "EUR": Decimal("1.08"), "GBP": Decimal("1.27")}


def _table(rows, columns):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().rstrip()


def _key(stem, value, places=0):
    return key_for_value(stem, value, places=places if isinstance(value, Decimal) else 0)


def _choice(stem, answer, alternatives, render, places=0):
    gold = _key(stem, answer, places)
    options = {gold: render(answer)}
    provenance = {gold: "correct"}
    for value, mistake in alternatives:
        key = _key(stem, value, places)
        if key != gold and key not in options:
            options[key] = render(value)
            provenance[key] = mistake
    if len(options) < 2:
        raise ValueError(f"{stem} has no computed distractor")
    return gold, options, provenance


def _parse_table(state, heading):
    text = state.split(f"{heading}\n", 1)[1].split("\n\n", 1)[0]
    return list(csv.DictReader(io.StringIO(text)))


def _read_state(state):
    amount_match = re.search(r"Amount due: ([\d,]+\.\d{2}) ([A-Z]{3})", state)
    day_match = re.search(r"Invoice date: (\d{4}-\d{2}-\d{2})", state)
    comparison = re.search(r"Fee test: (at least|strictly greater than) \$(.+)", state)
    baseline = re.search(r"Baseline service rate: ([\d.]+)%", state)
    review_point = re.search(r"Rate review point: ([\d.]+)%", state)
    threshold = Decimal(comparison.group(2).replace(",", "")) if comparison else None
    return {
        "amount": Decimal(amount_match.group(1).replace(",", "")),
        "currency": amount_match.group(2),
        "day": date.fromisoformat(day_match.group(1)),
        "fx": _parse_table(state, "FX RATE BULLETIN"),
        "tiers": _parse_table(state, "MARGINAL FEE SCHEDULE"),
        "threshold": threshold,
        "comparison": comparison.group(1) if comparison else None,
        "baseline": Decimal(baseline.group(1)) if baseline else None,
        "review_point": Decimal(review_point.group(1)) if review_point else None,
        "mode": re.search(r"Closeout method: (.+)", state).group(1),
    }


def _calculate(document):
    fx = next(
        row for row in document["fx"]
        if row["Currency"] == document["currency"]
        and date.fromisoformat(row["Valid from"]) <= document["day"]
        <= date.fromisoformat(row["Valid through"])
    )
    converted = (
        document["amount"] * Decimal(fx["USD per unit"])
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    fee_exact = Decimal("0")
    final_tier = ""
    for row in document["tiers"]:
        lower = Decimal(row["Slice begins at"])
        upper = Decimal(row["Slice ends before"])
        rate = Decimal(row["Rate"])
        portion = max(Decimal("0"), min(converted, upper) - lower)
        fee_exact += portion * rate
        if portion > 0:
            final_tier = row["Fee band"]
    fee = fee_exact.quantize(CENT, rounding=ROUND_HALF_UP)
    effective_rate = (fee / converted * Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    baseline = document["baseline"]
    points = abs(effective_rate - baseline).quantize(CENT, rounding=ROUND_HALF_UP)
    relative = (points / baseline * Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    return fx, converted, fee, final_tier, effective_rate, points, relative


def verify_rendered(record: dict) -> bool:
    try:
        document = _read_state(record["state"])
        fx, converted, fee, final_tier, effective_rate, points, relative = _calculate(document)
        for qid, question in record["questions"].items():
            instruction = question["instructions"]
            answer = record["gold"][qid]
            if instruction == "What amount in US dollars results from the invoice conversion?":
                wanted = _key("converted_amount", converted, 2)
            elif instruction == "Which band contains the converted invoice amount?":
                wanted = score_level_for(converted, question["criteria"])
            elif instruction == "What is the marginal service fee after final rounding?":
                wanted = _key("marginal_fee", fee, 2)
            elif instruction == "Which band contains the marginal service fee?":
                wanted = score_level_for(fee, question["criteria"])
            elif instruction == "Does the marginal service fee satisfy the stated closeout test?":
                passed = fee >= document["threshold"] if document["comparison"] == "at least" else fee > document["threshold"]
                wanted = "true" if passed else "false"
            elif instruction == "Which band contains the relative fee-rate change?":
                wanted = score_level_for(relative, question["criteria"])
            elif instruction == "Which band contains the fee-rate difference in percentage points?":
                wanted = score_level_for(points, question["criteria"])
            elif instruction == "What effective fee rate results from the tier schedule?":
                wanted = _key("effective_rate", effective_rate, 2)
            elif instruction == "Which fee band receives the final marginal slice?":
                wanted = _key("fee_band", final_tier)
            else:
                return False
            if answer != wanted:
                return False

        return True
    except (ValueError, KeyError, IndexError, StopIteration, InvalidOperation, AttributeError, ZeroDivisionError):
        return False
    return True


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    invoice_day = date(2027, rng.randint(1, 12), rng.randint(4, 25))
    active_from = invoice_day.replace(day=1)
    old_through = active_from - timedelta(days=1)
    currency = rng.choice(CURRENCIES)
    current_rate = RATES[currency]
    target_usd = Decimal(rng.choice(("2550.00", "5950.00", "9950.00", "10050.00")))
    old_factor = {
        Decimal("2550.00"): Decimal("0.80"),
        Decimal("5950.00"): Decimal("1.10"),
        Decimal("9950.00"): Decimal("1.10"),
        Decimal("10050.00"): Decimal("0.85"),
    }[target_usd]
    old_rate = (current_rate * old_factor).quantize(Decimal("0.0001"))
    amount = (target_usd / current_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    converted = (amount * current_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    fx = [
        {
            "Currency": code, "USD per unit": f"{old_rate if code == currency else (RATES[code] * Decimal('0.88')):.4f}",
            "Valid from": "2025-01-01", "Valid through": old_through.isoformat(),
            "Bulletin": f"FX-{rng.randint(1000, 9999)} replaced",
        }
        for code in CURRENCIES
    ] + [
        {
            "Currency": code, "USD per unit": f"{RATES[code]:.4f}",
            "Valid from": active_from.isoformat(), "Valid through": "2028-12-31",
            "Bulletin": f"FX-{rng.randint(1000, 9999)}",
        }
        for code in CURRENCIES
    ]
    tiers = [
        {"Fee band": "Base", "Slice begins at": "0.00", "Slice ends before": "2500.00", "Rate": "0.018"},
        {"Fee band": "Standard", "Slice begins at": "2500.00", "Slice ends before": "6000.00", "Rate": "0.027"},
        {"Fee band": "Elevated", "Slice begins at": "6000.00", "Slice ends before": "10000.00", "Rate": "0.041"},
        {"Fee band": "Priority", "Slice begins at": "10000.00", "Slice ends before": "9999999.00", "Rate": "0.052"},
    ]
    initial = {
        "amount": amount, "currency": currency, "day": invoice_day,
        "fx": fx, "tiers": tiers,
    }
    _, converted, fee, final_tier, effective_rate, points, relative = _calculate({
        **initial, "baseline": Decimal("3.00"),
    })
    baseline = Decimal(rng.choice(("2.50", "3.00", "4.25")))
    initial["baseline"] = baseline
    _, converted, fee, final_tier, effective_rate, points, relative = _calculate(initial)
    review_point = (relative + Decimal("5.00")).quantize(CENT) if rng.randrange(2) else max(
        Decimal("0.01"), relative - Decimal("5.00")
    ).quantize(CENT)
    mode = rng.choice(("fee threshold", "relative rate"))
    if mode == "fee threshold":
        comparison = rng.choice(("at least", "strictly greater than"))
        if rng.random() < 0.30:
            threshold = fee
        else:
            threshold = fee - Decimal("1.00") if rng.randrange(2) else fee + Decimal("1.00")
    else:
        comparison = rng.choice(("at least", "strictly greater than"))
        threshold = fee
    old_conversion = (amount * old_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    old_fee_exact = Decimal("0")
    for row in tiers:
        lower, upper = Decimal(row["Slice begins at"]), Decimal(row["Slice ends before"])
        portion = max(Decimal("0"), min(old_conversion, upper) - lower)
        old_fee_exact += portion * Decimal(row["Rate"])
    old_fee = old_fee_exact.quantize(CENT, rounding=ROUND_HALF_UP)
    old_final_tier = next(
        row["Fee band"] for row in tiers
        if Decimal(row["Slice begins at"]) <= old_conversion
        < Decimal(row["Slice ends before"])
    )
    whole_rate_fee = (converted * Decimal(tiers[-1]["Rate"])).quantize(CENT, rounding=ROUND_HALF_UP)
    per_slice_fee = Decimal("0")
    for row in tiers:
        lower, upper = Decimal(row["Slice begins at"]), Decimal(row["Slice ends before"])
        portion = max(Decimal("0"), min(converted, upper) - lower)
        per_slice_fee += (portion * Decimal(row["Rate"])).quantize(CENT, rounding=ROUND_HALF_UP)
    per_slice_fee = per_slice_fee.quantize(CENT, rounding=ROUND_HALF_UP)

    question_pool = []
    amount_choice = _choice(
        "converted_amount", converted,
        [(old_conversion, "superseded_fx"), (amount, "omitted_conversion")],
        lambda value: f"The converted invoice amount is ${value:,.2f}.", 2,
    )
    amount_bands, amount_level = round_bands(
        converted, "$", [Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100"), Decimal("250")],
        rng, metric="The converted invoice amount",
    )
    question_pool.append(rng.choice((
        {
            "quantity": "converted_invoice_amount",
            "spec": ("choice", "What amount in US dollars results from the invoice conversion?",
                     amount_choice[0], amount_choice[1]),
            "origins": amount_choice[2],
        },
        {
            "quantity": "converted_invoice_amount",
            "spec": ("score", "Which band contains the converted invoice amount?",
                     str(amount_level), amount_bands),
            "origins": {},
        },
    )))

    fee_choice = _choice(
        "marginal_fee", fee,
        [(whole_rate_fee, "whole_balance_at_final_rate"),
         (per_slice_fee, "rounding_each_tier"),
         (old_fee, "superseded_fx")],
        lambda value: f"The marginal service fee is ${value:,.2f}.", 2,
    )
    fee_bands, fee_level = round_bands(
        fee, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100")],
        rng, metric="The marginal service fee",
    )
    fee_questions = (
        {
            "quantity": "marginal_service_fee",
            "spec": ("choice", "What is the marginal service fee after final rounding?",
                     fee_choice[0], fee_choice[1]),
            "origins": fee_choice[2],
        },
        {
            "quantity": "marginal_service_fee",
            "spec": ("score", "Which band contains the marginal service fee?",
                     str(fee_level), fee_bands),
            "origins": {},
        },
    )
    if mode == "fee threshold" and threshold == fee:
        question_pool.append(fee_questions[1])
    else:
        question_pool.append(rng.choice(fee_questions))

    effective_choice = _choice(
        "effective_rate", effective_rate,
        [(whole_rate_fee / converted * Decimal(100), "whole_balance_at_final_rate"),
         (old_fee / old_conversion * Decimal(100), "superseded_fx")],
        lambda value: f"The effective fee rate is {value:.2f}%.", 2,
    )
    tier_choice = _choice(
        "fee_band", final_tier, [(old_final_tier, "superseded_fx")],
        lambda value: f"The final marginal slice uses the {value} fee band.",
    )
    question_pool.extend((
        {
            "quantity": "effective_fee_rate",
            "spec": (
                "choice", "What effective fee rate results from the tier schedule?",
                effective_choice[0], effective_choice[1],
            ),
            "origins": effective_choice[2],
        },
        {
            "quantity": "final_fee_band",
            "spec": (
                "choice", "Which fee band receives the final marginal slice?",
                tier_choice[0], tier_choice[1],
            ),
            "origins": tier_choice[2],
        },
    ))
    if mode == "fee threshold":
        question_pool.append({
            "quantity": "fee_threshold_status",
            "spec": (
                "noul", "Does the marginal service fee satisfy the stated closeout test?",
                "true" if (
                    fee >= threshold if comparison == "at least" else fee > threshold
                ) else "false",
                {
                    "false": "The service fee satisfies the closeout test: No.",
                    "true": "The service fee satisfies the closeout test: Yes.",
                },
            ),
            "origins": {},
        })
    else:
        relative_bands, relative_level = round_bands(
            relative, "%", [Decimal("0.5"), Decimal("1"), Decimal("2"), Decimal("5"),
                            Decimal("10"), Decimal("25")],
            rng, metric="The relative fee-rate change",
        )
        point_bands, point_level = round_bands(
            points, "%", [Decimal("0.05"), Decimal("0.1"), Decimal("0.25"),
                          Decimal("0.5"), Decimal("1")],
            rng, metric="The fee-rate difference in percentage points",
        )
        question_pool.extend((
            {
                "quantity": "relative_fee_rate_change",
                "spec": (
                    "score", "Which band contains the relative fee-rate change?",
                    str(relative_level), relative_bands,
                ),
                "origins": {},
            },
            {
                "quantity": "percentage_point_difference",
                "spec": (
                    "score", "Which band contains the fee-rate difference in percentage points?",
                    str(point_level), point_bands,
                ),
                "origins": {},
            },
        ))

    selected = rng.sample(question_pool, n_questions)
    specs = [item["spec"] for item in selected]
    note = None
    note_mistake = None
    if rng.random() < 0.65:
        note_correct = rng.random() < 0.30
        if mode == "fee threshold":
            note_fee = fee if note_correct else whole_rate_fee
            note_relation = (
                "clears" if (
                    note_fee >= threshold if comparison == "at least" else note_fee > threshold
                ) else "does not clear"
            )
            note_text = (
                f"Mira (finance): I get a service fee of ${note_fee:,.2f}, "
                f"which {note_relation} the approval threshold."
            )
            note_mistake = None if note_correct else "whole_balance_at_final_rate"
        else:
            old_effective_rate = (
                old_fee / old_conversion * Decimal(100)
            ).quantize(CENT, rounding=ROUND_HALF_UP)
            old_relative_change = (
                abs(old_effective_rate - baseline) / baseline * Decimal(100)
            ).quantize(CENT, rounding=ROUND_HALF_UP)
            if note_correct:
                note_change = relative
            elif old_relative_change == relative:
                note_change = points
                note_mistake = "percentage_points"
            else:
                note_change = old_relative_change
                note_mistake = "superseded_fx"
            note_relation = "above" if note_change > review_point else "below"
            note_text = (
                f"Mira (finance): I get a relative fee-rate change of {note_change:.2f}%, "
                f"which is {note_relation} the {review_point:.2f}% review point."
            )
            if note_correct:
                note_mistake = None
        note = (note_text, note_correct)

    fx_table = _table(fx, ("Currency", "USD per unit", "Valid from", "Valid through", "Bulletin"))
    tier_table = _table(tiers, ("Fee band", "Slice begins at", "Slice ends before", "Rate"))
    closeout_line = (
        f"Fee test: {comparison} ${threshold:,.2f}"
        if mode == "fee threshold"
        else "Rate review: compare the relative change against the printed review point"
    )
    state = (
        "FEE CALCULATION WORKSHEET\n"
        f"Invoice date: {invoice_day.isoformat()}\n"
        f"Amount due: {amount:,.2f} {currency}\n"
        f"Closeout method: {mode.title()}\n"
        f"{closeout_line}\n"
        f"Baseline service rate: {baseline:.2f}%\n"
        f"Rate review point: {review_point:.2f}%\n\n"
        "Calculation instructions: Select the exchange bulletin covering the invoice date and multiply the "
        "foreign-currency amount by its USD rate. Round the converted amount half up to cents. Apply each "
        "marginal rate only to the slice within its band, sum the unrounded slice charges, then round the "
        "service fee half up to cents. The lower edge of each fee slice is included; the upper edge is not.\n\n"
        "FX RATE BULLETIN\n" + fx_table + "\n\n"
        "MARGINAL FEE SCHEDULE\n" + tier_table + "\n\n"
        "Closeout memo: The approval test uses the exact comparison phrase printed above. In the relative-rate "
        "review, compare the tier schedule's effective rate with the baseline rate; a percentage-point difference "
        "is not the same quantity as a relative percentage change. A prior estimate may have used a single rate "
        "for the entire balance, so recalculate from the published slices."
    )
    facts = {
        "invoice_date": invoice_day.isoformat(),
        "amount": str(amount),
        "currency": currency,
        "fx": fx,
        "tiers": tiers,
        "threshold": str(threshold),
        "comparison": comparison,
        "baseline": str(baseline),
        "review_point": str(review_point),
        "mode": mode,
    }
    record = finish_record(
        rng, "cg_numeric", "fx_marginal_fee_closeout", state, specs,
        facts=facts,
        traps=["superseded_fx", "whole_balance_rate", "tier_boundaries", "comparison_operator", "percentage_points"],
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
