from __future__ import annotations

import random

from .core import NAMES, choose_domain, question_specs, record


def count_eligible(rows: list[dict]) -> int:
    return sum(row["active"] and row["region"] == "north" and row["days"] >= 3 for row in rows)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    rows = []
    for i in range(7):
        rows.append({
            "ticket": f"T-{rng.randint(200, 999)}",
            "region": rng.choice(("north", "south")),
            "active": rng.choice((True, False)),
            "days": rng.randint(1, 6),
        })
    rows[0].update(region="north", active=True, days=4)
    count = count_eligible(rows)
    threshold = rng.choice((2, 4, 5))
    if rng.randrange(2):
        state = (
            f"{name} audits {domain} records. Eligibility requires region=north, active=true, and at least 3 open days. "
            f"A review flag requires at least {threshold} eligible records. Register:\n"
        )
    else:
        state = (
            f"Batch audit / {domain} / analyst {name}. Count a row only if it is active, belongs to the north region, "
            f"and has 3 or more open days. Escalate when eligible rows reach {threshold}. Intake register:\n"
        )
    state += "\n".join(
        f"{r['ticket']}: region={r['region']}, active={str(r['active']).lower()}, open_days={r['days']}."
        for r in rows
    )
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            answer = f"count_{count}"
            options = {f"count_{i}": f"Exactly {i} records meet every eligibility condition."
                       for i in sorted({max(0, count - 1), count, count + 1})}
            specs.append((kind, "How many records are eligible?", answer, options, None))
        elif kind == "noul":
            specs.append((kind, f"Are at least {threshold} records eligible?",
                          "true" if count >= threshold else "false", None, None))
        else:
            band = "0" if count <= 1 else "1" if count <= 3 else "2"
            specs.append((kind, "What is the eligible-record count band?", band, None,
                          ["0-1 records", "2-3 records", "4 or more records"]))
    return record(rng, "counting", domain, state, specs)
