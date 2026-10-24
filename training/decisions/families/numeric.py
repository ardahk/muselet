from __future__ import annotations

import random

from .core import NAMES, article, choose_domain, question_specs, record


def fee_after_discount(price: float, discount_pct: float, fee_pct: float) -> float:
    return round(price * (1 - discount_pct / 100) * (1 + fee_pct / 100), 2)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    price = rng.choice((120.0, 375.0, 840.0, 1250.0))
    discount = rng.choice((5.0, 10.0, 15.0, 20.0))
    fee = rng.choice((2.5, 4.0, 7.5))
    total = fee_after_discount(price, discount, fee)
    cap = round(total + rng.choice((-1, 1)), 2)
    change = abs((total - price) / price * 100)
    invoice = f"INV-{rng.randint(20000, 99999)}"
    layout = rng.choice(("approval email", "purchase form", "invoice note"))
    if layout == "approval email":
        state = (
            f"Subject: Approval for {invoice}\nFrom: {name}\n"
            f"Please review {article(domain)} {domain} purchase. The listed amount is ${price:.2f}; apply a "
            f"{discount:g}% discount before adding the {fee:g}% service fee. The fee is calculated on the "
            f"discounted subtotal. The authorized ceiling is ${cap:.2f}, inclusive."
        )
    elif layout == "purchase form":
        state = (
            f"PURCHASE AUTHORIZATION — {invoice}\nRequester: {name}\nSupplier category: {domain}\n"
            f"List amount: ${price:.2f}\nDiscount: {discount:g}%\nService fee: {fee:g}% of discounted subtotal\n"
            f"Approval ceiling: ${cap:.2f} (inclusive)"
        )
    else:
        state = (
            f"Invoice review for {invoice}, prepared by {name}. Category: {domain}. "
            f"Subtotal ${price:.2f}; discount {discount:g}% is applied first; then the ${fee:g}% service fee "
            f"is assessed on the reduced amount. The approval limit is ${cap:.2f}, and equality is allowed."
        )
    amount_options = {}
    for offset in range(-12, 14):
        amount = round(total + offset * 0.75, 2)
        key = f"usd_{amount:.2f}".replace(".", "_")
        amount_options[key] = f"The invoice total is ${amount:.2f} after discount and service fee."
    score = min(3, int(change // 5))
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((
                kind, f"What total should be approved for {invoice} after the stated calculation?",
                f"usd_{total:.2f}".replace(".", "_"), amount_options, None,
            ))
        elif kind == "noul":
            specs.append((
                kind, f"Is {invoice}'s calculated total within the inclusive authorization ceiling?",
                "true" if total <= cap else "false",
                {"false": f"The ${total:.2f} total exceeds the ${cap:.2f} authorization ceiling.",
                 "true": f"The ${total:.2f} total is at or below the ${cap:.2f} authorization ceiling."},
                None,
            ))
        else:
            specs.append((
                kind, f"Which band contains the absolute change from {invoice}'s listed amount?",
                str(score), None,
                ["The total changes by less than 5% from the listed amount.",
                 "The total changes by 5% to under 10% from the listed amount.",
                 "The total changes by 10% to under 15% from the listed amount.",
                 "The total changes by at least 15% from the listed amount."],
            ))
    return record(rng, "numeric", domain, state, specs)
