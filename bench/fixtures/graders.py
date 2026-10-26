"""LH-v1 graders over the fixture server state (lead-authored eval logic).

Each grader is `fn(state, seed) -> {"passed": bool, "reason": str, "milestones": {name: bool}}`.
`passed` is the strict final-state verdict; milestones are diagnostics (partial credit) only.
Cases whose verdict lives in a native app (TextEdit, ...) use these graders for milestones only;
their strict check is in `evals/lh_v1.jsonl`.
"""

import re

EGGS = {"eggs-large-dozen", "eggs-large-18", "eggs-brown-dozen"}
WHOLE_MILK = {"milk-whole-gal", "milk-whole-half"}
BUTTER = {"butter-unsalted", "butter-salted"}
BANANAS = {"banana", "banana-organic"}
AAA = {"batt-aaa-4", "batt-aaa-8", "batt-aaa-recharge"}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()


def _plain(s) -> str:
    """Lowercase, punctuation removed, single spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9@. ]+", " ", _norm(s))).strip()


def _digits(s) -> str:
    return re.sub(r"\D+", "", str(s or ""))


def _cart(state) -> dict:
    return {k: int(v) for k, v in state["mart"]["cart"].items() if int(v) > 0}


def _visited(state, prefix: str) -> bool:
    return any(str(v.get("path", "")).startswith(prefix) for v in state.get("visits", []))


def _result(passed: bool, reason: str, milestones: dict) -> dict:
    return {"passed": bool(passed), "reason": reason if not passed else "ok",
            "milestones": {k: bool(v) for k, v in milestones.items()}}


def _qty(cart: dict, ids) -> int:
    return sum(q for p, q in cart.items() if p in ids)


def _extras(cart: dict, allowed) -> list:
    return sorted(p for p in cart if p not in allowed)


def mart_two_items(state, seed):
    cart, orders = _cart(state), state["mart"]["orders"]
    bananas, milk = _qty(cart, BANANAS), cart.get("milk-whole-gal", 0)
    extras = _extras(cart, BANANAS | {"milk-whole-gal"})
    ms = {"bananas_added": bananas > 0, "bananas_qty_2": bananas == 2, "milk_gallon_added": milk > 0,
          "milk_qty_1": milk == 1, "no_extras": not extras, "no_order": not orders}
    return _result(all(ms.values()), f"cart={cart} orders={len(orders)}", ms)


def mart_aaa(state, seed):
    cart, orders = _cart(state), state["mart"]["orders"]
    aaa, extras = _qty(cart, AAA), _extras(cart, AAA)
    ms = {"aaa_added": aaa > 0, "aaa_qty_2": aaa == 2, "no_extras": not extras, "no_order": not orders}
    return _result(all(ms.values()), f"cart={cart} orders={len(orders)}", ms)


def mart_cheapest_beans(state, seed):
    cart, orders = _cart(state), state["mart"]["orders"]
    ms = {"browsed_coffee": _visited(state, "/mart/search") or _visited(state, "/mart/c/"),
          "breakfast_added": cart.get("beans-breakfast", 0) > 0,
          "qty_1": cart.get("beans-breakfast", 0) == 1,
          "no_extras": not _extras(cart, {"beans-breakfast"}), "no_order": not orders}
    return _result(all(v for k, v in ms.items() if k != "browsed_coffee"), f"cart={cart} orders={len(orders)}", ms)


def mart_pancakes(state, seed):
    cart, orders = _cart(state), state["mart"]["orders"]
    eggs, milk, butter = _qty(cart, EGGS), _qty(cart, WHOLE_MILK), _qty(cart, BUTTER)
    ms = {"eggs_1": eggs == 1, "whole_milk_1": milk == 1, "butter_1": butter == 1,
          "no_extras": not _extras(cart, EGGS | WHOLE_MILK | BUTTER), "no_order": not orders}
    return _result(all(ms.values()), f"cart={cart} orders={len(orders)}", ms)


def _street(s: str) -> str:
    s = _plain(s)
    s = re.sub(r"\bst\b\.?", "street", s)
    return re.sub(r"\s+", " ", s).strip(" .")


def mart_checkout(state, seed):
    orders = state["mart"]["orders"]
    o = orders[-1] if orders else None
    ship = (o or {}).get("ship", {})
    items = {k: int(v) for k, v in ((o or {}).get("items") or {}).items() if int(v) > 0}
    added = any(e.get("t") == "add" and e.get("pid") == "eggs-large-dozen" for e in state["mart"]["events"])
    ms = {"eggs_added": added or items.get("eggs-large-dozen", 0) > 0,
          "reached_checkout": _visited(state, "/mart/checkout"),
          "order_placed": len(orders) == 1,
          "items_ok": items == {"eggs-large-dozen": 1},
          "name_ok": _plain(ship.get("name")) == "jane doe",
          "address_ok": _street(ship.get("street")) == "12 main street"
                        and _plain(ship.get("city")) == "springfield" and _digits(ship.get("zip")) == "62704"}
    return _result(all(ms.values()), f"orders={orders}", ms)


def mart_followup(state, seed):
    cart, orders = _cart(state), state["mart"]["orders"]
    first_add = any(e.get("t") == "add" and e.get("pid") == "beans-house" for e in state["mart"]["events"])
    ms = {"turn1_house_blend": first_add, "beans_qty_2": cart.get("beans-house", 0) == 2,
          "filters_1": cart.get("coffee-filters", 0) == 1,
          "no_extras": not _extras(cart, {"beans-house", "coffee-filters"}), "no_order": not orders}
    return _result(all(ms.values()), f"cart={cart} orders={len(orders)}", ms)


def forms_volunteer(state, seed):
    subs = [s for s in state["forms"]["submissions"] if s.get("form") == "volunteer"]
    f = subs[-1]["fields"] if subs else {}
    days = f.get("days") or []
    days = {days} if isinstance(days, str) else set(days)
    ms = {"submitted": bool(subs), "single_submission": len(subs) == 1,
          "first_name": _plain(f.get("first_name")) == "alex",
          "last_name": _plain(f.get("last_name")) == "rivera",
          "email": _norm(f.get("email")).replace(" ", "") == "alex.rivera@example.com",
          "phone": _digits(f.get("phone")).endswith("5550142"),
          "shirt_size": f.get("shirt_size") == "M",
          "shift": f.get("shift") == "morning",
          "days": days == {"sat", "sun"}}
    return _result(all(ms.values()), f"submissions={subs}", ms)


def mail_reply(state, seed):
    sent = state["mail"]["sent"]
    m = sent[-1] if sent else {}
    ms = {"opened_latest": _visited(state, "/mail/m/m11"),
          "sent_one": len(sent) == 1,
          "right_thread": m.get("in_reply_to") == "m11",
          "to_ok": "jon.snow@winterfell.example" in _norm(m.get("to")),
          "body_ok": "winter is not coming" in _plain(m.get("body"))}
    return _result(all(v for k, v in ms.items() if k != "opened_latest"), f"sent={sent}", ms)


def mail_compose(state, seed):
    sent = state["mail"]["sent"]
    m = sent[-1] if sent else {}
    subject, body = _plain(m.get("subject")), _plain(m.get("body"))
    ms = {"sent_one": len(sent) == 1,
          "to_ok": _norm(m.get("to")).replace(" ", "") == "sam@example.com",
          "subject_ok": "lunch" in subject and "friday" in subject,
          "body_ok": "lunch" in body and "friday" in body and ("noon" in body or "12" in body)}
    return _result(all(ms.values()), f"sent={sent}", ms)


def _last_answer(state, qid):
    rows = [a for a in state["wiki"]["answers"] if a.get("quiz") == qid]
    return (rows[-1].get("answer") if rows else None), len(rows)


def wiki_founder(state, seed):
    ans, n = _last_answer(state, "q1")
    ms = {"visited_city": _visited(state, "/wiki/a/lumen-harbor"),
          "visited_founder": _visited(state, "/wiki/a/ines-calder"),
          "answered": n > 0, "correct": _digits(ans) == "1742"}
    return _result(ms["answered"] and ms["correct"], f"answer={ans!r} n={n}", ms)


def wiki_taller(state, seed):
    ans, n = _last_answer(state, "q2")
    a = _plain(ans)
    ms = {"visited_varn": _visited(state, "/wiki/a/varn-spire"),
          "visited_oskel": _visited(state, "/wiki/a/oskel-tower"),
          "answered": n > 0, "correct": "varn" in a and "oskel" not in a}
    return _result(ms["answered"] and ms["correct"], f"answer={ans!r} n={n}", ms)


def bank_starbucks(state, seed):
    # strict verdict is the TextEdit check in the case file; these are navigation milestones
    ms = {"page2": _visited(state, "/bank/statement?page=2"), "page3": _visited(state, "/bank/statement?page=3")}
    return _result(all(ms.values()), "milestones only (strict check is TextEdit)", ms)


def mail_offsite(state, seed):
    ms = {"opened_offsite": _visited(state, "/mail/m/m7"), "no_mail_sent": not state["mail"]["sent"]}
    return _result(all(ms.values()), "milestones only (strict check is TextEdit)", ms)


GRADERS = {
    "lh-mart-two-items": mart_two_items,
    "lh-mart-aaa": mart_aaa,
    "lh-mart-cheapest-beans": mart_cheapest_beans,
    "lh-mart-pancakes": mart_pancakes,
    "lh-mart-checkout": mart_checkout,
    "lh-mart-followup": mart_followup,
    "lh-forms-volunteer": forms_volunteer,
    "lh-mail-reply": mail_reply,
    "lh-mail-compose": mail_compose,
    "lh-wiki-founder": wiki_founder,
    "lh-wiki-taller": wiki_taller,
    "lh-bank-starbucks-textedit": bank_starbucks,
    "lh-mail-offsite-textedit": mail_offsite,
}
