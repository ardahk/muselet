from __future__ import annotations

import random

from .core import NAMES, choose_domain, question_specs, record


def lookup_sla(ticket: str, tickets: dict, customers: dict, plans: dict) -> int:
    customer = tickets[ticket]["customer"]
    plan = customers[customer]["plan"]
    return plans[plan]["sla_hours"]


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    owner = rng.choice(NAMES)
    ticket = f"INC-{rng.randint(2000, 9999)}"
    account = f"C-{rng.randint(100, 999)}"
    plan = rng.choice(("silver", "gold", "platinum"))
    tickets = {ticket: {"customer": account}}
    customers = {account: {"plan": plan}}
    plans = {"silver": {"sla_hours": 48}, "gold": {"sla_hours": 24}, "platinum": {"sla_hours": 8}}
    target = lookup_sla(ticket, tickets, customers, plans)
    layout = rng.choice(("handoff email", "service ticket", "lookup log"))
    if layout == "handoff email":
        state = (
            f"Subject: {ticket} response target\nFrom: {owner}\n"
            f"The {domain} ticket register links {ticket} to account {account}. The account directory lists "
            f"{account} on the {plan} plan. The entitlement table assigns {plans[plan]['sla_hours']} response hours "
            f"to {plan}. Severity affects triage order only; it does not change the contracted response target."
        )
    elif layout == "service ticket":
        state = (
            f"SERVICE DESK RECORD\nIncident: {ticket}\nCategory: {domain}\nAssigned analyst: {owner}\n"
            f"Customer reference: {account}\nEntitlement lookup: {account} → {plan}\n"
            f"Plan response table: silver=48h; gold=24h; platinum=8h.\n"
            "Resolve the linked account before reading the entitlement; urgency is not a substitute for the plan."
        )
    else:
        state = (
            f"Directory lookup audit / operator {owner} / queue {domain}\n"
            f"ticket[{ticket}].customer = {account}\ncustomer[{account}].plan = {plan}\n"
            f"plan[{plan}].response_hours = {plans[plan]['sla_hours']}\n"
            "The response target comes from the linked plan record, not from the ticket's display priority."
        )
    hours_options = {
        f"hours_{hours}": f"The linked {plan} entitlement sets a response target of {hours} hours."
        for hours in range(1, 49)
    }
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((kind, f"What response target applies to incident {ticket}?",
                          f"hours_{target}", hours_options, None))
        elif kind == "noul":
            specs.append((kind, f"Is incident {ticket}'s linked response target no more than 24 hours?",
                          "true" if target <= 24 else "false",
                          {"false": f"The {plan} entitlement for {account} allows more than 24 response hours.",
                           "true": f"The {plan} entitlement for {account} allows 24 response hours or less."}, None))
        else:
            score = "0" if target <= 8 else "1" if target <= 24 else "2"
            specs.append((kind, f"Which response-time tier applies to incident {ticket}?",
                          score, None,
                          [f"The linked {plan} plan allows 8 response hours or less.",
                           f"The linked {plan} plan allows 9–24 response hours.",
                           f"The linked {plan} plan allows more than 24 response hours."]))
    return record(rng, "multi_hop", domain, state, specs)
