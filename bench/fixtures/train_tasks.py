"""Training-only fixture tasks (lead-authored). Disjoint from LH-v1 eval cases: different products/carts, mail
threads and wiki entities. Families `forms` and `bank` and all native-app tasks are held out entirely so the
eval can measure transfer. Each task is graded by a generic spec grader (`grade_spec`).
"""

import re

from bench.fixtures.gradeutil import BANANAS, _cart, _digits, _norm, _plain, _result, _street


def T(tid, start, utterance, expect, preset=None):
    return {"id": tid, "start": start, "utterance": utterance, "expect": expect, "preset": preset}


TRAIN_TASKS = [
    # ---- mart: add to cart ----
    T("tr-mart-01", "/mart", "Add a bag of gala apples and a pound of strawberries to my cart.",
      {"cart": {"apples-gala": 1, "strawberries": 1}}),
    T("tr-mart-02", "/mart", "Put four bananas in my cart.", {"cart_group": {"bananas": 4}}),
    T("tr-mart-03", "/mart", "Add two loaves of sourdough to my cart.", {"cart": {"bread-sourdough": 2}}),
    T("tr-mart-04", "/mart", "Add the cheapest milk you can find to my cart.", {"cart": {"milk-whole-half": 1}}),
    T("tr-mart-05", "/mart", "Add an eight pack of double A batteries and a USB-C cable to my cart.",
      {"cart": {"batt-aa-8": 1, "usb-c-cable": 1}}),
    T("tr-mart-06", "/mart", "Add green tea and a box of coffee filters to my cart.",
      {"cart": {"tea-green": 1, "coffee-filters": 1}}),
    T("tr-mart-07", "/mart", "I need breakfast stuff. Add bagels, cheddar cheese and Greek yogurt to my cart.",
      {"cart": {"bagels": 1, "cheddar": 1, "yogurt-greek": 1}}),
    T("tr-mart-08", "/mart", "Add the most expensive coffee beans to my cart.", {"cart": {"beans-colombian": 1}}),
    T("tr-mart-09", "/mart", "Add three bottles of dish soap to my cart.", {"cart": {"dish-soap": 3}}),
    T("tr-mart-10", "/mart/cart", "Remove the paper towels from my cart.",
      {"cart": {"banana": 3, "milk-oat": 1}}, preset="a"),
    T("tr-mart-11", "/mart/cart", "Change the bananas in my cart to six.",
      {"cart": {"paper-towels": 1, "banana": 6, "milk-oat": 1}}, preset="a"),
    T("tr-mart-12", "/mart", "Buy a wireless mouse and ship it to Maria Lopez, 400 Oak Avenue, Portland, 97205.",
      {"order": {"items": {"mouse-wireless": 1}, "name": "maria lopez", "street": "400 oak avenue",
                 "city": "portland", "zip": "97205"}}),
    T("tr-mart-13", "/mart", "Order two packs of the 18 count large eggs and ship them to Ken Adams, 9 Pine Road, "
                             "Austin, 73301.",
      {"order": {"items": {"eggs-large-18": 2}, "name": "ken adams", "street": "9 pine road", "city": "austin",
                 "zip": "73301"}}),
    T("tr-mart-14", "/mart", "Add salted butter and a bag of all-purpose flour to my cart.",
      {"cart": {"butter-salted": 1, "flour": 1}}),
    T("tr-mart-15", "/mart", "Add a 20 watt charger to my cart.", {"cart": {"charger-20w": 1}}),
    T("tr-mart-16", "/mart/cart", "Take the instant coffee out of my cart and add a box of coffee filters instead.",
      {"cart": {"beans-dark": 2, "coffee-filters": 1}}, preset="b"),
    T("tr-mart-17", "/mart", "Add two packs of nine volt batteries and paper towels to my cart.",
      {"cart": {"batt-9v": 2, "paper-towels": 1}}),
    T("tr-mart-18", "/mart", "Add the cheapest bread to my cart.", {"cart": {"bread-wheat": 1}}),
    # ---- mail: reply / compose / forward ----
    T("tr-mail-01", "/mail", "Reply to Arya's email and say yes, Saturday at ten works.",
      {"sent": {"in_reply_to": "m6", "to": "arya@winterfell.example", "body_has": ["saturday"],
                "body_any": ["ten", "10"]}}),
    T("tr-mail-02", "/mail", "Reply to Sansa and tell her I'll bring a cheesecake.",
      {"sent": {"in_reply_to": "m10", "to": "sansa@winterfell.example", "body_has": ["cheesecake"]}}),
    T("tr-mail-03", "/mail", "Reply to Dana's email saying Monday at 2 works for me.",
      {"sent": {"in_reply_to": "m9", "to": "dana.kim@northwind.example", "body_has": ["monday"],
                "body_any": ["2", "two"]}}),
    T("tr-mail-04", "/mail", "Email priya dot patel at northwind dot example with the subject RSVP and say I'll be "
                             "at the offsite.",
      {"sent": {"to": "priya.patel@northwind.example", "subject_has": ["rsvp"], "body_has": ["offsite"]}}),
    T("tr-mail-05", "/mail", "Forward the email about my shipped order to sam at example dot com.",
      {"sent": {"forward_of": "m5", "to": "sam@example.com"}}),
    T("tr-mail-06", "/mail", "Reply to Sam's notes email and say thanks, I'll take a look.",
      {"sent": {"in_reply_to": "m3", "to": "sam@example.com", "body_has": ["thank"]}}),
    T("tr-mail-07", "/mail", "Send an email to dana dot kim at northwind dot example with the subject budget "
                             "slides, saying I'll send the slides tonight.",
      {"sent": {"to": "dana.kim@northwind.example", "subject_has": ["budget", "slides"],
                "body_has": ["slides", "tonight"]}}),
    T("tr-mail-08", "/mail", "Reply to the GitHub email saying I'll look into it.",
      {"sent": {"in_reply_to": "m12", "to": "noreply@github.example", "body_has": ["look into"]}}),
    T("tr-mail-09", "/mail", "Forward Priya's team lunch email to sam at example dot com.",
      {"sent": {"forward_of": "m2", "to": "sam@example.com"}}),
    # ---- wiki quizzes (training cluster only) ----
    T("tr-wiki-01", "/wiki/quiz/t1", "Answer the question on this page. You can look it up on this wiki.",
      {"quiz": {"id": "t1", "has": ["teodor", "vale"]}}),
    T("tr-wiki-02", "/wiki/quiz/t2", "Answer the question on this page. You can look it up on this wiki.",
      {"quiz": {"id": "t2", "digits": "1688"}}),
    T("tr-wiki-03", "/wiki/quiz/t3", "Answer the question on this page. You can look it up on this wiki.",
      {"quiz": {"id": "t3", "has": ["halden"], "not": ["brask"]}}),
    T("tr-wiki-04", "/wiki/quiz/t4", "Answer the question on this page. You can look it up on this wiki.",
      {"quiz": {"id": "t4", "digits": "9", "word": "nine"}}),
    T("tr-wiki-05", "/wiki/quiz/t5", "Answer the question on this page. You can look it up on this wiki.",
      {"quiz": {"id": "t5", "has": ["lighthouse"], "not": ["observatory", "halden"]}}),
]

GROUPS = {"bananas": BANANAS}


def grade_spec(task):
    exp = task["expect"]

    def fn(state, seed):
        cart, orders, sent = _cart(state), state["mart"]["orders"], state["mail"]["sent"]
        if "cart" in exp:
            ms = {"cart_ok": cart == exp["cart"], "no_order": not orders}
            return _result(all(ms.values()), f"cart={cart} orders={len(orders)}", ms)
        if "cart_group" in exp:
            ms = {}
            for g, q in exp["cart_group"].items():
                ms[f"{g}_qty"] = sum(v for k, v in cart.items() if k in GROUPS[g]) == q
            ms["no_extras"] = all(any(k in GROUPS[g] for g in exp["cart_group"]) for k in cart)
            ms["no_order"] = not orders
            return _result(all(ms.values()), f"cart={cart}", ms)
        if "order" in exp:
            o = exp["order"]
            last = orders[-1] if orders else {}
            ship = last.get("ship", {})
            items = {k: int(v) for k, v in (last.get("items") or {}).items() if int(v) > 0}
            ms = {"order_placed": len(orders) == 1, "items_ok": items == o["items"],
                  "name_ok": _plain(ship.get("name")) == o["name"],
                  "address_ok": _street(ship.get("street")) == _street(o["street"])
                                and _plain(ship.get("city")) == o["city"] and _digits(ship.get("zip")) == o["zip"]}
            return _result(all(ms.values()), f"orders={orders}", ms)
        if "sent" in exp:
            s = exp["sent"]
            m = sent[-1] if sent else {}
            subject, body = _plain(m.get("subject")), _plain(m.get("body"))
            ms = {"sent_one": len(sent) == 1,
                  "to_ok": _norm(m.get("to")).replace(" ", "") == s["to"]}
            if "in_reply_to" in s:
                ms["thread_ok"] = m.get("in_reply_to") == s["in_reply_to"]
            if "forward_of" in s:
                ms["forward_ok"] = m.get("forward_of") == s["forward_of"]
            if s.get("subject_has"):
                ms["subject_ok"] = all(w in subject for w in s["subject_has"])
            if s.get("body_has") or s.get("body_any"):
                ms["body_ok"] = all(w in body for w in s.get("body_has", [])) and (
                    not s.get("body_any") or any(re.search(rf"\b{re.escape(w)}\b", body) for w in s["body_any"]))
            return _result(all(ms.values()), f"sent={sent}", ms)
        if "quiz" in exp:
            q = exp["quiz"]
            rows = [a for a in state["wiki"]["answers"] if a.get("quiz") == q["id"]]
            ans = rows[-1].get("answer") if rows else ""
            a = _plain(ans)
            ok = True
            if "digits" in q:
                ok = _digits(ans) == q["digits"] or (q.get("word") is not None and q["word"] in a.split())
            ok = ok and all(w in a for w in q.get("has", [])) and not any(w in a for w in q.get("not", []))
            ms = {"answered": bool(rows), "correct": bool(rows) and ok}
            return _result(all(ms.values()), f"answer={ans!r}", ms)
        raise ValueError(f"unknown expect {exp}")
    return fn


TRAIN_GRADERS = {t["id"]: grade_spec(t) for t in TRAIN_TASKS}
