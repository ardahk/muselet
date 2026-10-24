from __future__ import annotations

import random
from datetime import date

from .core import NAMES, choose_domain, question_specs, record


def eligible(*, active: bool, amount: float, filed: date, start: date, end: date,
             exception: bool, region: str) -> bool:
    return active and start <= filed <= end and amount <= 5000 and (region == "north" or exception)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    amount = float(rng.choice((3200, 4800, 5200)))
    filed = date(rng.choice((2025, 2026, 2027)), rng.randint(1, 12), rng.randint(1, 25))
    start, end = date(2026, 1, 1), date(2026, 12, 31)
    active = rng.random() >= 0.15
    exception, region = bool(rng.randrange(2)), rng.choice(("north", "south"))
    allowed = eligible(active=active, amount=amount, filed=filed, start=start, end=end,
                       exception=exception, region=region)
    rules = [
        "Rule 1 — Effective date. This policy governs claims filed from 1 January 2026 through 31 December 2026, inclusive.",
        "Rule 2 — Eligible account. The account must be active on the filing date. A suspended account is not active.",
        "Rule 3 — Standard region. North-region claims may be considered under the ordinary route.",
        "Rule 4 — Exception. A south-region claim is eligible only when the signed regional exception is recorded before filing.",
        "Rule 5 — Amount. The eligible amount must be no more than $5,000; exactly $5,000 is permitted.",
        "Rule 6 — Interaction. All date, account, region, and amount requirements apply together; satisfying one does not waive another.",
        "Definition — Filing date is the timestamp accepted by the intake register, not the date a reviewer opens the case.",
        "Exception precedence — A signed regional exception changes only the region requirement and does not waive the account, date, or amount rules.",
    ]
    paragraphs = []
    for i in range(rng.randint(42, 62)):
        rule = rules[i % len(rules)]
        paragraphs.append(
            f"Operations note {i+1:02d}. {rule} Case owner {rng.choice(NAMES)} must preserve the register entry, "
            f"review the effective date, and record the reason for any referral. The current review batch is "
            f"{rng.choice(('Aster', 'Birch', 'Cedar', 'Delta'))}; no verbal approval overrides a written condition."
        )
    facts = (
        f"account active={str(active).lower()}, region={region}, signed regional exception recorded before filing="
        f"{str(exception).lower()}, eligible amount=${amount:.2f}, filing date={filed.isoformat()}."
    )
    heading = ("POLICY EXCERPTS" if rng.randrange(2) else "CLAIMS OPERATIONS MANUAL — CONTROLLED COPY")
    state = (
        f"{name} is reviewing a {domain} reimbursement. Facts: {facts}\n{heading}\n"
        + "\n".join(paragraphs)
    )
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            answer = "approve" if allowed else "refer"
            opts = {"approve": "Approve because every applicable requirement is met.",
                    "refer": "Refer because at least one applicable requirement is not met.",
                    "deny": "Deny permanently even if the exception or missing condition can be reviewed."}
            specs.append((kind, "What disposition follows the policy?", answer, opts, None))
        elif kind == "noul":
            specs.append((kind, "Does this case satisfy every applicable eligibility condition?",
                          "true" if allowed else "false", None, None))
        else:
            score = "0" if not active else "1" if not allowed else "2"
            specs.append((kind, "What eligibility tier applies?", score, None,
                          ["Ineligible account", "At least one policy condition fails", "All conditions satisfied"]))
    return record(rng, "long_policy", domain, state, specs)
