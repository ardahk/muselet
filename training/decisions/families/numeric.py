from __future__ import annotations

import random

from .core import NAMES, choose_domain, question_specs, record


def fee_after_discount(price: float, discount_pct: float, fee_pct: float) -> float:
    return round(price * (1 - discount_pct / 100) * (1 + fee_pct / 100), 2)


def tiered_fee(amount: float) -> float:
    return round(min(amount, 100) * 0.02 + max(0, amount - 100) * 0.05, 2)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    price = rng.choice((120.0, 375.0, 840.0, 1250.0))
    discount = rng.choice((5.0, 10.0, 15.0, 20.0))
    fee = rng.choice((2.5, 4.0, 7.5))
    fee_on_discounted = bool(rng.randrange(2))
    total = (fee_after_discount(price, discount, fee) if fee_on_discounted else
             round(price * (1 - discount / 100) + price * fee / 100, 2))
    cap = round(total + rng.choice((-1.0, 1.0)), 2)
    change = round((total - price) / price * 100, 1)
    kilograms = rng.choice((2.0, 5.0, 12.0))
    pounds = round(kilograms * 2.20462, 2)
    tier_fee = tiered_fee(price)
    template = rng.randrange(2)
    if template == 0:
        state = (
            f"{name} is reviewing a {domain} purchase. The listed price is ${price:.2f}. Apply the "
            f"{discount:g}% discount, then add a {fee:g}% service fee to "
            f"{'the discounted amount' if fee_on_discounted else 'the original list price'}. "
            f"The authorized cap is ${cap:.2f}; requests at or below the cap are permitted, and a separate trigger "
            f"fires only above the cap. Percentage change "
            f"is measured from list price. Shipping uses 1 kg = 2.20462 lb. For a separate handling charge, "
            f"the first $100 is assessed at 2% and any remainder at 5%; on ${price:.2f} that fee is ${tier_fee:.2f}. "
            f"This parcel weighs {kilograms:g} kg."
        )
    else:
        state = (
            f"PURCHASE REVIEW — {domain}; reviewer {name}. Price=${price:.2f}; discount={discount:g}%; "
            f"service fee={fee:g}% on {'discounted subtotal' if fee_on_discounted else 'original price'}; "
            f"maximum authorized total=${cap:.2f}, inclusive; review trigger is strictly above the cap. "
            "Compute percent change from the original price. Conversion rule: 1 kg = 2.20462 lb. "
            f"Handling schedule: 2% on the first $100 and 5% on the balance; applicable charge on "
            f"${price:.2f} is ${tier_fee:.2f}. Package mass={kilograms:g} kg."
        )
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            focus = rng.choice(("cap", "unit", "tier"))
            if focus == "unit":
                answer = f"{pounds:g}_lb"
                choices = {answer: "The converted parcel mass.",
                           f"{pounds + 1:g}_lb": "A conversion one pound too high.",
                           f"{pounds - 1:g}_lb": "A conversion one pound too low."}
                instructions = f"What is the parcel mass in pounds, rounded to two decimals?"
            elif focus == "tier":
                answer = f"${tier_fee:.2f}"
                choices = {answer: "The fee applying 2% to the first $100 and 5% to the remainder.",
                           f"${round(tier_fee + 5, 2):.2f}": "A fee that overcharges the applicable tiers.",
                           f"${round(tier_fee - 5, 2):.2f}": "A fee that undercharges the applicable tiers."}
                instructions = "What is the handling charge under the tiered schedule?"
            else:
                answer = "within_cap" if total <= cap else "over_cap"
                choices = {"within_cap": "The computed charge does not exceed the cap.",
                           "over_cap": "The computed charge exceeds the cap."}
                instructions = f"Is the final charge of ${total:.2f} within the authorization cap?"
            specs.append((kind, instructions, answer, choices, None))
        elif kind == "noul":
            check = rng.choice(("order", "weight"))
            if check == "weight":
                specs.append((kind, f"Is the package at least {kilograms:g} kg?", "true", None, None))
            else:
                specs.append((kind, "Is the service fee applied to the discounted subtotal?",
                              "true" if fee_on_discounted else "false", None, None))
        else:
            score = min(3, max(0, int(abs(change) // 5)))
            levels = ["0-4.9% change", "5-9.9% change", "10-14.9% change", "15% or greater change"]
            specs.append((kind, "Which band contains the absolute percentage change from list price?", str(score), None, levels))
    return record(rng, "numeric", domain, state, specs)
