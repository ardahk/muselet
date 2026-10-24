from __future__ import annotations

import random

from .core import NAMES, choose_domain, near_miss_values, question_specs, record


def resolve_response_hours(ticket: str, tickets: dict, accounts: dict, agreements: dict,
                           plan_hours: dict, region_buffers: dict) -> int:
    account = tickets[ticket]["account"]
    contract = accounts[account]["contract"]
    plan = agreements[contract]["plan"]
    region = accounts[account]["region"]
    return plan_hours[plan] + region_buffers[region]


def lookup_sla(ticket: str, tickets: dict, customers: dict, plans: dict) -> int:
    customer = tickets[ticket]["customer"]
    plan = customers[customer]["plan"]
    return plans[plan]["sla_hours"]


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    owner = rng.choice(NAMES)
    index = rng.randrange(5)
    tickets = {f"INC-41{i:02d}": {"account": f"AC-22{i:02d}"} for i in range(5)}
    plans = ("Core", "Core Plus", "Priority", "Priority Plus")
    plan_hours = dict(zip(plans, (10, 20, 30, 40)))
    regions = ("North", "Central", "Coastal", "Inland")
    region_buffers = dict(zip(regions, (3, 5, 7, 6)))
    accounts, agreements = {}, {}
    for i in range(5):
        contract = f"AGR-31{i:02d}"
        accounts[f"AC-22{i:02d}"] = {
            "contract": contract,
            "region": regions[(i + 1) % len(regions)],
        }
        agreements[contract] = {"plan": plans[(i + (i // 2)) % len(plans)]}
    target_ticket = f"INC-41{index:02d}"
    answer_hours = resolve_response_hours(
        target_ticket, tickets, accounts, agreements, plan_hours, region_buffers
    )
    neighbors = [
        resolve_response_hours(ticket, tickets, accounts, agreements, plan_hours, region_buffers)
        for ticket in (f"INC-41{(index - 1) % 5:02d}", f"INC-41{(index + 1) % 5:02d}")
    ]
    target_account = tickets[target_ticket]["account"]
    base_hours = plan_hours[agreements[accounts[target_account]["contract"]]["plan"]]
    possible = near_miss_values(
        answer_hours, (base_hours, *neighbors, answer_hours - 1, answer_hours + 1),
        minimum=5, lower=1, upper=50,
    )
    options = {
        f"hours_{hours}": f"The response target is {hours} hours."
        for hours in possible
    }
    ticket_rows = "\n".join(f"| {ticket} | {row['account']} |" for ticket, row in tickets.items())
    agreement_rows = "\n".join(
        f"| {contract} | {row['plan']} |" for contract, row in agreements.items()
    )
    sla_rows = "\n".join(f"| {plan} | {hours} |" for plan, hours in plan_hours.items())
    account_rows = "\n".join(
        f"{account}: support agreement {row['contract']}; service region {row['region']}."
        for account, row in accounts.items()
    )
    state = (
        f"SUPPORT HANDOFF — {domain}\nPrepared by: {owner}\n"
        f"Ticket register\n| Incident | Account |\n|---|---|\n{ticket_rows}\n\n"
        f"Customer operations email:\n\"The account directory has been refreshed. Use its service-region entry "
        f"for regional handling; contract assignments are maintained separately.\"\n{account_rows}\n\n"
        f"Agreement ledger\n| Agreement | Support plan |\n|---|---|\n{agreement_rows}\n\n"
        f"Plan service table\n| Support plan | Base response hours |\n|---|---|\n{sla_rows}\n\n"
        "Regional handling register\n| Region | Additional handling hours |\n|---|---|\n"
        + "\n".join(f"| {region} | {hours} |" for region, hours in region_buffers.items())
    )
    limit = rng.choice((18, 24, 28, 36))
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((
                kind, f"What response target applies to incident {target_ticket}?",
                f"hours_{answer_hours}", options, None,
            ))
        elif kind == "noul":
            specs.append((
                kind, f"Is the response target for {target_ticket} no more than {limit} hours?",
                "true" if answer_hours <= limit else "false",
                {"false": "The response target is above the stated limit.",
                 "true": "The response target is within the stated limit."}, None,
            ))
        else:
            specs.append((
                kind, f"Which response-time tier applies to incident {target_ticket}?",
                "0" if answer_hours <= 16 else "1" if answer_hours <= 28 else "2", None,
                ["The response target is 16 hours or less.",
                 "The response target is 17–28 hours.",
                 "The response target exceeds 28 hours."],
            ))
    return record(
        rng, "multi_hop", domain, state, specs,
        intermediate_values=(
            target_account,
            accounts[target_account]["contract"],
            agreements[accounts[target_account]["contract"]]["plan"],
            accounts[target_account]["region"],
        ),
    )
