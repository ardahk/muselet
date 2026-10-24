from __future__ import annotations

import random

from .core import NAMES, article, choose_domain, near_miss_values, question_specs, record


def fee_after_discount(price: float, discount_pct: float, fee_pct: float) -> float:
    return round(price * (1 - discount_pct / 100) * (1 + fee_pct / 100), 2)


def _key(amount: float) -> str:
    return f"usd_{amount:.2f}".replace(".", "_")


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    price = rng.choice((120.0, 375.0, 840.0, 1250.0))
    discount = rng.choice((5.0, 10.0, 15.0, 20.0))
    fee = rng.choice((2.5, 4.0, 7.5))
    subtotal = round(price * (1 - discount / 100), 2)
    total = fee_after_discount(price, discount, fee)
    wrong_fee_base = round(subtotal + price * fee / 100, 2)
    fee_omitted = subtotal
    discount_omitted = round(price * (1 + fee / 100), 2)
    discount_error = round(price * (1 - max(0, discount - 5) / 100) * (1 + fee / 100), 2)
    mistakes = (wrong_fee_base, fee_omitted, discount_omitted, discount_error)
    candidates = near_miss_values(
        total, mistakes, minimum=26, lower=round(price * 0.7, 2), upper=round(price * 1.15, 2), step=0.25
    )
    amount_options = {_key(value): f"The invoice total is ${value:.2f}." for value in candidates}
    cap = round(price * rng.choice((0.85, 0.95, 1.0, 1.05)), 2)
    if cap == total:
        cap = round(cap + 2.5, 2)
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
            f"Subtotal starts at ${price:.2f}; apply a {discount:g}% reduction before a {fee:g}% service fee "
            f"on the reduced amount. The approval limit is ${cap:.2f}, and equality is allowed."
        )

    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((
                kind, f"What total should be approved for {invoice} after the stated calculation?",
                _key(total), amount_options, None,
            ))
        elif kind == "noul":
            specs.append((
                kind, f"Is {invoice}'s calculated total within the inclusive authorization ceiling?",
                "true" if total <= cap else "false",
                {"false": "The calculated invoice total exceeds the authorization ceiling.",
                 "true": "The calculated invoice total is within the authorization ceiling."},
                None,
            ))
        else:
            score = min(3, int(change // 5))
            specs.append((
                kind, f"Which band contains the absolute change from {invoice}'s listed amount?",
                str(score), None,
                ["The total changes by less than 5% from the listed amount.",
                 "The total changes by 5% to under 10% from the listed amount.",
                 "The total changes by 10% to under 15% from the listed amount.",
                 "The total changes by at least 15% from the listed amount."],
            ))
    return record(
        rng, "numeric", domain, state, specs,
        intermediate_values=(
            f"discounted subtotal ${subtotal:.2f}",
            f"fee on original amount ${wrong_fee_base:.2f}",
            f"subtotal without service fee ${fee_omitted:.2f}",
            f"undiscounted fee-inclusive amount ${discount_omitted:.2f}",
        ),
    )
