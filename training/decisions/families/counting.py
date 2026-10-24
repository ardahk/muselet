from __future__ import annotations

import random

from .core import NAMES, choose_domain, count_phrase, near_miss_values, question_specs, record


def count_eligible(rows: list[dict], *, minimum_days: int = 3) -> int:
    return sum(row["active"] and row["region"] == "north" and row["days"] >= minimum_days for row in rows)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    analyst = rng.choice(NAMES)
    batch = f"B-{rng.randint(300, 999)}"
    minimum_days = rng.choice((3, 4))
    rows = [{
        "ticket": f"R-{rng.randint(2000, 9999)}",
        "region": rng.choice(("north", "south")),
        "active": rng.choice((True, False)),
        "days": rng.randint(1, 7),
    } for _ in range(rng.randint(7, 10))]
    rows[0].update(region="north", active=True, days=minimum_days + 1)
    eligible_count = count_eligible(rows, minimum_days=minimum_days)
    threshold = rng.choice([value for value in range(2, len(rows)) if value != eligible_count])
    partial_counts = (
        sum(row["active"] and row["region"] == "north" for row in rows),
        sum(row["region"] == "north" and row["days"] >= minimum_days for row in rows),
        sum(row["active"] and row["days"] >= minimum_days for row in rows),
        sum(row["active"] for row in rows),
        sum(row["region"] == "north" for row in rows),
        sum(row["days"] >= minimum_days for row in rows),
    )
    mistakes = [
        *partial_counts,
        eligible_count - 1,
        eligible_count + 1,
        eligible_count - 2,
        eligible_count + 2,
    ]
    candidate_counts = near_miss_values(
        eligible_count, mistakes, minimum=5, lower=0, upper=len(rows)
    )
    count_options = {
        f"count_{value}": f"Exactly {value} referrals meet every eligibility filter."
        for value in candidate_counts
    }
    layout = rng.choice(("audit worksheet", "queue export", "case table"))
    if layout == "audit worksheet":
        entries = "\n".join(
            f"| {row['ticket']} | {row['region'].title()} | {'Active' if row['active'] else 'Suspended'} | "
            f"{row['days']} |" for row in rows
        )
        state = (
            f"{domain.title()} referral audit — batch {batch}\nAnalyst: {analyst}\n"
            f"Count a row only when its account is active, its region is North, and its open days reach "
            f"{minimum_days}; all three checks apply to the same row.\n"
            "| Referral | Region | Account status | Open days |\n|---|---|---|---|\n"
            f"{entries}\nEscalation threshold: {threshold} qualifying rows."
        )
    elif layout == "queue export":
        entries = "\n".join(
            f"{row['ticket']},{row['region']},{str(row['active']).lower()},{row['days']}" for row in rows
        )
        state = (
            f"Queue export / batch={batch} / analyst={analyst} / category={domain}\n"
            f"Eligibility filter: active=true AND region=north AND open_days>={minimum_days}.\n"
            f"Escalate when the qualifying-row count reaches {threshold}.\n"
            "ticket,region,active,open_days\n" + entries
        )
    else:
        entries = "\n".join(
            f"{row['ticket']}: region {row['region']}; account "
            f"{'active' if row['active'] else 'suspended'}; "
            f"{count_phrase(row['days'], 'open day')}." for row in rows
        )
        state = (
            f"{analyst} is reviewing {domain} referrals in batch {batch}. A row qualifies only when its account "
            f"is active, it is in North, and it has at least {minimum_days} open days. "
            f"The escalation threshold is {threshold} qualifying rows.\n{entries}"
        )

    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((
                kind, f"How many referrals in batch {batch} meet every eligibility filter?",
                f"count_{eligible_count}", count_options, None,
            ))
        elif kind == "noul":
            specs.append((
                kind, f"Does batch {batch} reach its escalation threshold?",
                "true" if eligible_count >= threshold else "false",
                {"false": "The batch remains below its escalation threshold.",
                 "true": "The batch reaches its escalation threshold."},
                None,
            ))
        else:
            score = "0" if eligible_count <= 1 else "1" if eligible_count <= 3 else "2"
            specs.append((
                kind, f"What eligible-referral band applies to batch {batch}?",
                score, None,
                ["The batch has 0–1 eligible referrals.",
                 "The batch has 2–3 eligible referrals.",
                 "The batch has 4 or more eligible referrals."],
            ))
    return record(
        rng, "counting", domain, state, specs,
        intermediate_values=tuple(
            f"{value} rows pass a partial filter" for value in sorted(set(partial_counts))
        ),
    )
