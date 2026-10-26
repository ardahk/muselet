"""LH-v1 graders: one correct end state and the closest wrong ones per case (a grader bug corrupts every score)."""

import copy

import pytest

from bench.fixtures.graders import GRADERS
from bench.fixtures.seed import SEED

BASE = {"case": None, "reset_at": 0, "visits": [],
        "mart": {"cart": {}, "orders": [], "events": []}, "mail": {"sent": []},
        "wiki": {"answers": []}, "forms": {"submissions": []}}


def st(cart=None, orders=(), events=(), sent=(), answers=(), subs=(), visits=()):
    s = copy.deepcopy(BASE)
    s["mart"].update(cart=dict(cart or {}), orders=list(orders), events=list(events))
    s["mail"]["sent"] = list(sent)
    s["wiki"]["answers"] = list(answers)
    s["forms"]["submissions"] = list(subs)
    s["visits"] = [{"path": p, "ts": 0} for p in visits]
    return s


def passed(case, state):
    return GRADERS[case](state, SEED)["passed"]


def order(items, name="Jane Doe", street="12 Main St.", city="Springfield", zip_="62704"):
    return {"id": "1001", "items": items, "ship": {"name": name, "street": street, "city": city, "zip": zip_}}


def mail(to, subject, body, reply=None):
    return {"to": to, "subject": subject, "body": body, "in_reply_to": reply, "forward_of": None}


VOL = {"first_name": "Alex", "last_name": "Rivera", "email": "alex.rivera@example.com", "phone": "(555) 0142",
       "shirt_size": "M", "shift": "morning", "days": ["sat", "sun"], "comments": ""}

CASES = [
    ("lh-mart-two-items", st({"banana": 2, "milk-whole-gal": 1}), True),
    ("lh-mart-two-items", st({"banana": 1, "banana-organic": 1, "milk-whole-gal": 1}), True),
    ("lh-mart-two-items", st({"banana": 2, "milk-whole-half": 1}), False),
    ("lh-mart-two-items", st({"banana": 2, "milk-whole-gal": 1, "bagels": 1}), False),
    ("lh-mart-aaa", st({"batt-aaa-4": 2}), True),
    ("lh-mart-aaa", st({"batt-aa-4": 2}), False),
    ("lh-mart-aaa", st({"batt-aaa-4": 1}), False),
    ("lh-mart-cheapest-beans", st({"beans-breakfast": 1}), True),
    ("lh-mart-cheapest-beans", st({"coffee-instant": 1}), False),
    ("lh-mart-cheapest-beans", st({"beans-breakfast": 1}, orders=[order({"beans-breakfast": 1})]), False),
    ("lh-mart-pancakes", st({"eggs-large-18": 1, "milk-whole-half": 1, "butter-salted": 1}), True),
    ("lh-mart-pancakes", st({"eggs-large-dozen": 1, "milk-whole-gal": 1, "butter-unsalted": 1, "pancake-mix": 1}),
     False),
    ("lh-mart-pancakes", st({"eggs-large-dozen": 1, "milk-2pct-gal": 1, "butter-unsalted": 1}), False),
    ("lh-mart-checkout", st(orders=[order({"eggs-large-dozen": 1})], visits=["/mart/checkout"],
                            events=[{"t": "add", "pid": "eggs-large-dozen", "qty": 1}]), True),
    ("lh-mart-checkout", st(orders=[order({"eggs-large-18": 1})], visits=["/mart/checkout"]), False),
    ("lh-mart-checkout", st(orders=[order({"eggs-large-dozen": 1}, street="12 Main Street, Springfield")],
                            visits=["/mart/checkout"]), False),
    ("lh-mart-checkout", st({"eggs-large-dozen": 1}, visits=["/mart/checkout"]), False),
    ("lh-mart-followup", st({"beans-house": 2, "coffee-filters": 1},
                            events=[{"t": "add", "pid": "beans-house", "qty": 1}]), True),
    ("lh-mart-followup", st({"beans-house": 1, "coffee-filters": 1},
                            events=[{"t": "add", "pid": "beans-house", "qty": 1}]), False),
    ("lh-forms-volunteer", st(subs=[{"form": "volunteer", "fields": VOL}]), True),
    ("lh-forms-volunteer", st(subs=[{"form": "volunteer", "fields": dict(VOL, days=["sat"])}]), False),
    ("lh-forms-volunteer", st(subs=[{"form": "volunteer", "fields": VOL}] * 2), False),
    ("lh-forms-volunteer", st(subs=[{"form": "volunteer", "fields": dict(VOL, email="alexrivera@example.com")}]),
     False),
    ("lh-mail-reply", st(sent=[mail("jon.snow@winterfell.example", "Re: Are you ready for winter?",
                                    "Winter is not coming.", "m11")]), True),
    ("lh-mail-reply", st(sent=[mail("jon.snow@winterfell.example", "Re: Night's Watch schedule",
                                    "Winter is not coming.", "m4")]), False),
    ("lh-mail-compose", st(sent=[mail("sam@example.com", "Lunch on Friday",
                                      "Hi Sam, are you free for lunch on Friday at noon?")]), True),
    ("lh-mail-compose", st(sent=[mail("sam@example.com", "Re: Notes from Tuesday",
                                      "Are you free for lunch on Friday at noon?", "m3")]), False),
    ("lh-wiki-founder", st(answers=[{"quiz": "q1", "answer": "1742"}]), True),
    ("lh-wiki-founder", st(answers=[{"quiz": "q1", "answer": "1745"}]), False),
    ("lh-wiki-founder", st(answers=[{"quiz": "q1", "answer": "1781"}]), False),
    ("lh-wiki-taller", st(answers=[{"quiz": "q2", "answer": "The Varn Spire"}]), True),
    ("lh-wiki-taller", st(answers=[{"quiz": "q2", "answer": "Oskel Tower"}]), False),
]


@pytest.mark.parametrize("case,state,want", CASES)
def test_grader(case, state, want):
    assert passed(case, state) is want


def test_seed_fixed_facts():
    """The graders assume these seed facts; changing the seed must fail loudly."""
    prices = {p["id"]: float(p["price"]) for p in SEED["products"]}
    beans = [p for p in SEED["products"] if "Coffee Beans" in p["name"]]
    assert min(beans, key=lambda p: float(p["price"]))["id"] == "beans-breakfast"
    assert prices["coffee-instant"] < prices["beans-breakfast"]          # decoy stays cheaper but is not beans
    sbux = [t for t in SEED["transactions"] if t["desc"].startswith("STARBUCKS")]
    assert round(-sum(float(t["amount"]) for t in sbux), 2) == 30.15
    rows = sorted(SEED["transactions"], key=lambda t: t["date"])
    pages = [rows[i:i + 15] for i in range(0, len(rows), 15)]
    assert [sum(t["desc"].startswith("STARBUCKS") for t in p) for p in pages] == [2, 1, 2]
    jon = [m for m in SEED["emails"] if m["from_name"] == "Jon Snow"]
    assert max(jon, key=lambda m: m["date"])["id"] == "m11"
