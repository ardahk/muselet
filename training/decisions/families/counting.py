from __future__ import annotations

import random

from .core import NAMES, choose_domain, question_specs, record


def count_eligible(rows: list[dict]) -> int:
    return sum(row["active"] and row["region"] == "north" and row["days"] >= 3 for row in rows)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    analyst = rng.choice(NAMES)
    batch = f"B-{rng.randint(300, 999)}"
    rows = [{
        "ticket": f"R-{rng.randint(2000, 9999)}",
        "region": rng.choice(("north", "south")),
        "active": rng.choice((True, False)),
        "days": rng.randint(1, 7),
    } for _ in range(rng.randint(7, 10))]
    rows[0].update(region="north", active=True, days=4)
    eligible_count = count_eligible(rows)
    threshold = rng.randint(2, max(3, len(rows) - 1))
    layout = rng.choice(("audit worksheet", "queue export", "case table"))
    if layout == "audit worksheet":
        entries = "\n".join(
            f"| {row['ticket']} | {row['region'].title()} | {'Active' if row['active'] else 'Suspended'} | "
            f"{row['days']} |" for row in rows
        )
        state = (
            f"{domain.title()} referral audit — batch {batch}\nAnalyst: {analyst}\n"
            "Count a referral only when its account is active, its region is North, and it has at least 3 open days.\n"
            "| Referral | Region | Account status | Open days |\n|---|---|---|---|\n"
            f"{entries}\nEscalation is required when eligible referrals reach {threshold}."
        )
    elif layout == "queue export":
        entries = "\n".join(
            f"{row['ticket']},{row['region']},{str(row['active']).lower()},{row['days']}" for row in rows
        )
        state = (
            f"Queue export / batch={batch} / analyst={analyst} / category={domain}\n"
            "Eligibility filter: active=true AND region=north AND open_days>=3.\n"
            f"Escalate at {threshold} qualifying rows.\n"
            "ticket,region,active,open_days\n" + entries
        )
    else:
        entries = "\n".join(
            f"{row['ticket']}: region {row['region']}; account {'active' if row['active'] else 'suspended'}; "
            f"{row['days']} open days." for row in rows
        )
        state = (
            f"{analyst} is reviewing {domain} referrals in batch {batch}. The review rule requires an active account, "
            "North region, and at least 3 open days; every condition must hold for the same row. "
            f"Raise an escalation at {threshold} eligible referrals.\n{entries}"
        )
    count_options = {
        f"count_{value}": f"Exactly {value} referrals in batch {batch} meet all three stated eligibility filters."
        for value in range(26)
    }
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((kind, f"How many referrals in batch {batch} meet every eligibility filter?",
                          f"count_{eligible_count}", count_options, None))
        elif kind == "noul":
            specs.append((kind, f"Does batch {batch} contain at least {threshold} eligible referrals?",
                          "true" if eligible_count >= threshold else "false",
                          {"false": f"Fewer than {threshold} rows in batch {batch} satisfy all three filters.",
                           "true": f"At least {threshold} rows in batch {batch} satisfy all three filters."}, None))
        else:
            score = "0" if eligible_count <= 1 else "1" if eligible_count <= 3 else "2"
            specs.append((kind, f"What eligible-referral band applies to batch {batch}?",
                          score, None,
                          [f"Batch {batch} has 0–1 eligible referrals.",
                           f"Batch {batch} has 2–3 eligible referrals.",
                           f"Batch {batch} has 4 or more eligible referrals."]))
    return record(rng, "counting", domain, state, specs)
