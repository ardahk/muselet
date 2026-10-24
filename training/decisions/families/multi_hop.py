from __future__ import annotations

import random

from .core import NAMES, choose_domain, question_specs, record


def lookup_sla(ticket: str, tickets: dict, customers: dict, plans: dict) -> int:
    customer = tickets[ticket]["customer"]
    plan = customers[customer]["plan"]
    return plans[plan]["sla_hours"]


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    ticket = f"INC-{rng.randint(2000, 9999)}"
    customer = f"C-{rng.randint(100, 999)}"
    plan = rng.choice(("silver", "gold", "platinum"))
    tickets = {ticket: {"customer": customer}}
    customers = {customer: {"plan": plan}}
    plans = {"silver": {"sla_hours": 48}, "gold": {"sla_hours": 24}, "platinum": {"sla_hours": 8}}
    expected = lookup_sla(ticket, tickets, customers, plans)
    if rng.randrange(2):
        state = (
            f"{name} is triaging {domain} incident {ticket}. Ticket register: {ticket} belongs to customer {customer}. "
            f"Customer register: {customer} has plan {plan}. Plan table: silver=48 response hours, gold=24 response "
            f"hours, platinum=8 response hours. Use the linked ticket, then customer, then plan row; do not infer a "
            "service level from the incident severity."
        )
    else:
        state = (
            f"Service desk lookup for {domain}: start with ticket {ticket}; its account field is {customer}. "
            f"The account directory maps {customer} to {plan}. Entitlement table: silver—48 hours, gold—24 hours, "
            f"platinum—8 hours. {name} must return the entitlement attached to the referenced account, not a "
            "neighboring customer's entitlement or the incident's urgency."
        )
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            answer = f"{expected}_hours"
            opts = {f"{hours}_hours": f"Respond within {hours} hours." for hours in (8, 24, 48)}
            specs.append((kind, f"What is the response target for {ticket}?", answer, opts, None))
        elif kind == "noul":
            specs.append((kind, f"Is the response target for {ticket} no more than 24 hours?",
                          "true" if expected <= 24 else "false", None, None))
        else:
            score = "0" if expected <= 8 else "1" if expected <= 24 else "2"
            specs.append((kind, "Which response-time tier applies?", score, None,
                          ["8 hours or less", "9-24 hours", "More than 24 hours"]))
    return record(rng, "multi_hop", domain, state, specs)
