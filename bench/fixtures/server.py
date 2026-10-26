"""LH-v1 fixture web server: local-only stand-ins the agent drives through a browser.

Serves four sites plus a JSON state/grading API, Python stdlib only:

- Muselet Mart   /mart     (catalog, cart, checkout; POST -> 303 PRG)
- Muselet Mail   /mail     (inbox, read, compose reply/forward, sent, search)
- Lorepedia      /wiki     (articles, infoboxes, quizzes that never reveal correctness)
- Forms          /forms    (volunteer signup with server-side validation)
- Harborline     /bank     (paginated October 2026 statement)
- API            /api/*    (health, state, reset, grade, milestone, grade_json)

Everything is server-rendered HTML with real labels so the macOS AX tree exposes
meaningful controls; no JavaScript, no external resources. All mutations are
POST + 303 so refresh/back can never duplicate an order, message or submission.

Run from the repo root:  uv run --project ml python -m bench.fixtures.server --port 8777
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.fixtures.seed import SEED
from bench.fixtures.graders import GRADERS

_LOCK = threading.RLock()

PRODUCTS = {str(p["id"]): p for p in SEED["products"]}
CATEGORIES: list[str] = []
for _p in SEED["products"]:
    if _p["category"] not in CATEGORIES:
        CATEGORIES.append(_p["category"])
EMAILS = {str(m["id"]): m for m in SEED["emails"]}
ARTICLES = {str(a["slug"]): a for a in SEED["articles"]}
QUIZZES = {str(q["id"]): q for q in SEED["quizzes"]}
CART_PRESETS = SEED.get("cart_presets", {})
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
STATEMENT_PAGE_SIZE = 15


def _fresh_state(case: str | None = None, preset: str | None = None) -> dict:
    cart = dict(CART_PRESETS.get(preset, {})) if preset else {}
    return {
        "case": case,
        "reset_at": time.time(),
        "visits": [],
        "mart": {"cart": cart, "orders": [], "events": []},
        "mail": {"sent": []},
        "wiki": {"answers": []},
        "forms": {"submissions": []},
    }


STATE = _fresh_state()


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def _tokens(text) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).casefold())


def _matches(query: str, *fields) -> bool:
    """Every alnum query token is a prefix of some haystack token."""
    haystack = _tokens(" ".join(str(field) for field in fields))
    return all(
        any(token.startswith(needle) for token in haystack)
        for needle in _tokens(query)
    )


def _category_slug(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", category.casefold()).strip("-")


def _product_category(slug: str) -> str | None:
    for category in CATEGORIES:
        if _category_slug(category) == slug:
            return category
    return None


def _money(amount: str) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return esc(amount)
    return f"{value:,.2f}"


def _signed_money(amount: str) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return esc(amount)
    return f"{'-' if value < 0 else '+'}${abs(value):,.2f}"


def _short_date(iso: str) -> str:
    try:
        year, month, day = (int(part) for part in str(iso)[:10].split("-"))
        return f"{MONTHS[month - 1]} {day}"
    except (ValueError, IndexError):
        return esc(iso)


def _long_date(iso: str) -> str:
    try:
        year, month, day = (int(part) for part in str(iso)[:10].split("-"))
        return f"{MONTHS[month - 1]} {day}, {year}"
    except (ValueError, IndexError):
        return esc(iso)


def _page(title: str, header: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>
body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 0; color: #1d1d1f; }}
header {{ display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; padding: .6rem 1rem;
         background: #f5f5f7; border-bottom: 1px solid #d9d9de; }}
header a.brand {{ font-weight: 700; font-size: 1.1rem; }}
main {{ padding: 1rem 1.2rem; max-width: 62rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #e6e6ea; vertical-align: top; }}
.banner {{ background: #e5f6e5; border: 1px solid #9dcf9d; padding: .5rem .8rem; border-radius: 6px; }}
.error  {{ background: #fdecec; border: 1px solid #e5a1a1; padding: .5rem .8rem; border-radius: 6px; }}
.field  {{ margin: .55rem 0; }}
label   {{ display: inline-block; min-width: 7rem; }}
input[type=text], input[type=number], input[type=email], textarea, select {{ font: inherit; }}
textarea {{ width: 34rem; max-width: 100%; height: 9rem; }}
nav a {{ margin-right: .8rem; }}
.price {{ white-space: nowrap; }}
.quote {{ border-left: 3px solid #ccc; margin: 1rem 0; padding: .3rem .8rem; color: #444;
         background: #fafafa; }}
.infobox {{ border: 1px solid #d9d9de; float: right; margin: 0 0 1rem 1rem; background: #fafafa; }}
.infobox th {{ text-align: left; }}
ul.results {{ padding-left: 1.2rem; }}
.pager a {{ margin-right: .6rem; }}
</style></head><body>{header}<main>{body}</main></body></html>"""


# ---------------------------------------------------------------- mart

def _mart_header() -> str:
    categories = " ".join(
        f'<a href="/mart/c/{_category_slug(c)}">{esc(c)}</a>' for c in CATEGORIES
    )
    count = sum(int(qty) for qty in STATE["mart"]["cart"].values())
    return f"""<header>
<a class="brand" href="/mart">Muselet Mart</a>
<form method="get" action="/mart/search">
<label for="mart-q">Search products</label>
<input id="mart-q" name="q" type="text">
<button type="submit">Search</button>
</form>
<nav>{categories}</nav>
<a href="/mart/cart">Cart ({count})</a>
</header>"""


def _mart_page(title: str, body: str) -> str:
    return _page(f"Muselet Mart — {title}", _mart_header(), body)


def _product_row(product: dict) -> str:
    return (f'<li><a href="/mart/p/{quote(str(product["id"]))}">{esc(product["name"])}</a>'
            f' <span class="price">${esc(product["price"])}</span> {esc(product["size"])}</li>')


def _mart_home() -> str:
    cats = "".join(
        f'<li><a href="/mart/c/{_category_slug(c)}">{esc(c)}</a></li>' for c in CATEGORIES
    )
    featured = "".join(
        _product_row(PRODUCTS[pid]) for pid in SEED["featured"] if pid in PRODUCTS
    )
    return _mart_page("Groceries", f"""
<h1>Muselet Mart</h1>
<h2>Categories</h2>
<ul>{cats}</ul>
<h2>Featured products</h2>
<ul class="results">{featured}</ul>""")


def _mart_category(category: str) -> str:
    rows = "".join(
        _product_row(p) for p in SEED["products"] if p["category"] == category
    )
    return _mart_page(category, f"<h1>{esc(category)}</h1>\n<ul class=\"results\">{rows}</ul>")


def _mart_search(query: dict) -> str:
    q = (query.get("q") or [""])[0]
    sort = (query.get("sort") or ["relevance"])[0]
    results = [
        p for p in SEED["products"]
        if _matches(q, p["name"], p["category"], " ".join(p["tags"]))
    ]
    if sort == "price-low":
        results = sorted(results, key=lambda p: float(p["price"]))
    elif sort == "price-high":
        results = sorted(results, key=lambda p: -float(p["price"]))
    options = "".join(
        f'<option value="{value}"{" selected" if value == sort else ""}>{label}</option>'
        for value, label in (
            ("relevance", "Relevance"), ("price-low", "Price: low to high"),
            ("price-high", "Price: high to low"),
        )
    )
    body = f"""<h1>Search results</h1>
<form method="get" action="/mart/search">
<input type="hidden" name="q" value="{esc(q)}">
<label for="mart-sort">Sort by</label>
<select id="mart-sort" name="sort">{options}</select>
<button type="submit">Apply</button>
</form>
"""
    if results:
        body += f'<ul class="results">{"".join(_product_row(p) for p in results)}</ul>'
    else:
        body += f'<p>No results for &ldquo;{esc(q)}&rdquo;</p>'
    return _mart_page("Search", body)


def _mart_product(product: dict, added: str | None) -> str:
    banner = ""
    if added is not None:
        banner = (f'<p class="banner">Added {esc(added)} &times; {esc(product["name"])} '
                  "to your cart.</p>")
    pid = esc(str(product["id"]))
    return _mart_page(str(product["name"]), f"""{banner}
<h1>{esc(product["name"])}</h1>
<p class="price">${esc(product["price"])}</p>
<p>{esc(product["size"])}</p>
<p>{esc(product["desc"])}</p>
<form method="post" action="/mart/cart/add">
<input type="hidden" name="pid" value="{pid}">
<label for="qty-{pid}">Quantity</label>
<input id="qty-{pid}" name="qty" type="number" value="1" min="1" max="20">
<button type="submit">Add to cart</button>
</form>""")


def _cart_rows() -> tuple[str, float]:
    rows = ""
    subtotal = 0.0
    for pid, qty in STATE["mart"]["cart"].items():
        product = PRODUCTS.get(pid)
        qty = int(qty)
        if product is None or qty <= 0:
            continue
        unit = float(product["price"])
        line = unit * qty
        subtotal += line
        name = esc(product["name"])
        rows += f"""<tr>
<td><a href="/mart/p/{quote(str(pid))}">{name}</a></td>
<td class="price">${unit:.2f}</td>
<td><form method="post" action="/mart/cart/update">
<input type="hidden" name="pid" value="{esc(str(pid))}">
<label for="uq-{esc(str(pid))}">Quantity for {name}</label>
<input id="uq-{esc(str(pid))}" name="qty" type="number" value="{qty}" min="0" max="99">
<button type="submit">Update</button>
</form></td>
<td class="price">${line:.2f}</td>
<td><form method="post" action="/mart/cart/remove">
<input type="hidden" name="pid" value="{esc(str(pid))}">
<button type="submit" aria-label="Remove {name}">Remove</button>
</form></td>
</tr>"""
    return rows, subtotal


def _mart_cart() -> str:
    rows, subtotal = _cart_rows()
    if not rows:
        return _mart_page("Cart", "<h1>Your cart</h1>\n<p>Your cart is empty.</p>")
    return _mart_page("Cart", f"""<h1>Your cart</h1>
<table>
<tr><th>Item</th><th>Price</th><th>Quantity</th><th>Total</th><th></th></tr>
{rows}
<tr><td colspan="3"><strong>Subtotal</strong></td><td class="price"><strong>${subtotal:.2f}</strong></td><td></td></tr>
</table>
<p><a href="/mart/checkout">Proceed to checkout</a></p>""")


def _checkout_form(values: dict, errors: list[str]) -> str:
    error_block = ""
    if errors:
        error_block = '<ul class="error">' + "".join(
            f"<li>{esc(e)}</li>" for e in errors) + "</ul>"
    fields = "".join(
        f"""<div class="field"><label for="co-{name}">{label}</label>
<input id="co-{name}" name="{name}" type="text" value="{esc(values.get(name, ""))}"></div>"""
        for name, label in (
            ("name", "Full name"), ("street", "Street address"),
            ("city", "City"), ("zip", "ZIP code"),
        )
    )
    return f"""{error_block}
<form method="post" action="/mart/checkout/place">
{fields}
<button type="submit">Place order</button>
</form>"""


def _mart_checkout(values: dict | None = None, errors: list[str] | None = None) -> str:
    rows, subtotal = _cart_rows()
    summary = "<p>Your cart is empty.</p>" if not rows else f"""<table>
<tr><th>Item</th><th>Price</th><th>Quantity</th><th>Total</th><th></th></tr>
{rows}
<tr><td colspan="3"><strong>Subtotal</strong></td><td class="price"><strong>${subtotal:.2f}</strong></td><td></td></tr>
</table>"""
    return _mart_page("Checkout", f"""<h1>Checkout</h1>
{summary}
<h2>Shipping address</h2>
{_checkout_form(values or {}, errors or [])}""")


def _mart_order(order: dict) -> str:
    items = "".join(
        f"<li>{int(qty)} &times; {esc(PRODUCTS.get(pid, {}).get('name', pid))}</li>"
        for pid, qty in order["items"].items()
    )
    ship = order["ship"]
    return _mart_page(f"Order {order['id']}", f"""<h1>Order #{esc(order["id"])} placed</h1>
<p>Thank you for your order.</p>
<ul>{items}</ul>
<p>Ship to: {esc(ship["name"])}, {esc(ship["street"])}, {esc(ship["city"])} {esc(ship["zip"])}</p>""")


# ---------------------------------------------------------------- mail

def _mail_header() -> str:
    return """<header>
<a class="brand" href="/mail">Muselet Mail</a>
<form method="get" action="/mail/search">
<label for="mail-q">Search mail</label>
<input id="mail-q" name="q" type="text">
<button type="submit">Search</button>
</form>
<nav><a href="/mail">Inbox</a><a href="/mail/sent">Sent</a><a href="/mail/compose">Compose</a></nav>
</header>"""


def _mail_page(title: str, body: str) -> str:
    return _page(f"Muselet Mail — {title}", _mail_header(), body)


def _mail_row(message: dict) -> str:
    return (f'<li><a href="/mail/m/{quote(str(message["id"]))}">'
            f'{esc(message["from_name"])} &mdash; {esc(message["subject"])}</a>'
            f' {esc(_short_date(message["date"]))}</li>')


def _mail_inbox() -> str:
    inbox = sorted(SEED["emails"], key=lambda m: str(m["date"]), reverse=True)
    rows = "".join(_mail_row(m) for m in inbox)
    return _mail_page("Inbox", f'<h1>Inbox</h1>\n<ul class="results">{rows}</ul>')


def _mail_message(message: dict) -> str:
    mid = quote(str(message["id"]))
    body = "".join(
        f"<p>{esc(paragraph)}</p>" for paragraph in str(message["body"]).split("\n\n")
    )
    return _mail_page(str(message["subject"]), f"""<h1>{esc(message["subject"])}</h1>
<p><strong>From:</strong> {esc(message["from_name"])} &lt;{esc(message["from_addr"])}&gt;</p>
<p><strong>To:</strong> {esc(message["to"])}</p>
<p><strong>Date:</strong> {esc(_long_date(message["date"]))}</p>
{body}
<p>
<a href="/mail/compose?reply_to={mid}">Reply</a> &middot;
<a href="/mail/compose?forward={mid}">Forward</a> &middot;
<a href="/mail">Back to Inbox</a>
</p>""")


def _quoted_original(message: dict) -> str:
    body = "".join(
        f"<p>{esc(paragraph)}</p>" for paragraph in str(message["body"]).split("\n\n")
    )
    return f"""<div class="quote">
<p><strong>Original message</strong></p>
<p><strong>From:</strong> {esc(message["from_name"])} &lt;{esc(message["from_addr"])}&gt;</p>
<p><strong>Subject:</strong> {esc(message["subject"])}</p>
{body}
</div>"""


def _quote_text(message: dict) -> str:
    return (f'On {_long_date(message["date"])}, {message["from_name"]} wrote:\n\n'
            f'{message["body"]}')


def _mail_compose(values: dict, quoted: dict | None, error: str | None = None) -> str:
    error_block = f'<p class="error">{esc(error)}</p>' if error else ""
    # A forward fills the textarea with the quoted original; a reply shows it read-only below the form.
    quote_block = (
        _quoted_original(quoted)
        if quoted is not None and not values.get("forward")
        else ""
    )
    return _mail_page("Compose", f"""{error_block}
<h1>Compose</h1>
<form method="post" action="/mail/send">
<div class="field"><label for="mail-to">To</label>
<input id="mail-to" name="to" type="text" value="{esc(values.get("to", ""))}"></div>
<div class="field"><label for="mail-subject">Subject</label>
<input id="mail-subject" name="subject" type="text" value="{esc(values.get("subject", ""))}"></div>
<div class="field"><label for="mail-body">Message</label><br>
<textarea id="mail-body" name="body">{esc(values.get("body", ""))}</textarea></div>
<input type="hidden" name="reply_to" value="{esc(values.get("reply_to", ""))}">
<input type="hidden" name="forward" value="{esc(values.get("forward", ""))}">
<button type="submit">Send</button>
<a href="/mail">Discard</a>
</form>
{quote_block}""")


def _mail_sent(ok: bool) -> str:
    banner = '<p class="banner">Message sent.</p>' if ok else ""
    rows = "".join(
        f'<li><strong>{esc(m["subject"])}</strong> to {esc(m["to"])}'
        f' {esc(_short_date(time.strftime("%Y-%m-%d", time.localtime(m["ts"]))))}</li>'
        for m in STATE["mail"]["sent"]
    ) or "<li>No sent messages.</li>"
    return _mail_page("Sent", f"{banner}<h1>Sent</h1>\n<ul class=\"results\">{rows}</ul>")


def _mail_search(q: str) -> str:
    results = [
        m for m in SEED["emails"]
        if _matches(q, m["from_name"], m["from_addr"], m["subject"], m["body"])
    ]
    rows = "".join(_mail_row(m) for m in results)
    if not rows:
        rows = f'<li>No results for &ldquo;{esc(q)}&rdquo;</li>'
    return _mail_page("Search", f'<h1>Search results</h1>\n<ul class="results">{rows}</ul>')


# ---------------------------------------------------------------- wiki

def _wiki_header() -> str:
    return """<header>
<a class="brand" href="/wiki">Lorepedia</a>
<form method="get" action="/wiki/search">
<label for="wiki-q">Search Lorepedia</label>
<input id="wiki-q" name="q" type="text">
<button type="submit">Search</button>
</form>
<nav><a href="/wiki">Main page</a></nav>
</header>"""


def _wiki_page(title: str, body: str) -> str:
    return _page(f"Lorepedia — {title}", _wiki_header(), body)


def _wikify(text: str) -> str:
    escaped = esc(text)
    return re.sub(
        r"\[\[([a-z0-9-]+)\|([^\]]+)\]\]",
        lambda m: f'<a href="/wiki/a/{quote(m.group(1))}">{m.group(2)}</a>',
        escaped,
    )


def _wiki_home() -> str:
    rows = "".join(
        f'<li><a href="/wiki/a/{quote(slug)}">{esc(ARTICLES[slug]["title"])}</a></li>'
        for slug in SEED["featured_articles"] if slug in ARTICLES
    )
    return _wiki_page("Main page", f"""<h1>Lorepedia</h1>
<p>The free encyclopedia of the Selwyn world.</p>
<h2>Featured articles</h2>
<ul class="results">{rows}</ul>""")


def _wiki_article(article: dict) -> str:
    infobox_rows = "".join(
        f"<tr><th>{esc(key)}</th><td>{_wikify(value)}</td></tr>"
        for key, value in article["infobox"]
    )
    infobox = f'<table class="infobox">{infobox_rows}</table>' if infobox_rows else ""
    body = "".join(f"<p>{_wikify(paragraph)}</p>" for paragraph in article["body"])
    return _wiki_page(str(article["title"]),
                      f"<h1>{esc(article['title'])}</h1>\n{infobox}\n{body}")


def _wiki_search(q: str):
    for article in SEED["articles"]:
        if str(article["title"]).casefold() == q.strip().casefold():
            return f"/wiki/a/{quote(str(article['slug']))}"
    results = [
        a for a in SEED["articles"]
        if _matches(q, a["title"], " ".join(a["body"]))
    ]
    rows = "".join(
        f'<li><a href="/wiki/a/{quote(str(a["slug"]))}">{esc(a["title"])}</a>'
        f' &mdash; {_wikify(str(a["body"][0])[:140])}&hellip;</li>'
        for a in results
    )
    if not rows:
        rows = f'<li>No results for &ldquo;{esc(q)}&rdquo;</li>'
    return _wiki_page("Search", f'<h1>Search results</h1>\n<ul class="results">{rows}</ul>')


def _wiki_quiz(quiz: dict, submitted: str | None) -> str:
    banner = ""
    if submitted is not None:
        banner = f'<p class="banner">Answer recorded: {esc(submitted)}</p>'
    qid = esc(str(quiz["id"]))
    return _wiki_page("Quiz", f"""{banner}
<h1>{esc(quiz["question"])}</h1>
<form method="post" action="/wiki/quiz/{qid}/answer">
<label for="quiz-answer-{qid}">Your answer</label>
<input id="quiz-answer-{qid}" name="answer" type="text">
<button type="submit">Submit answer</button>
</form>""")


# ---------------------------------------------------------------- forms

def _volunteer_form(values: dict, days: list[str], errors: list[str]) -> str:
    spec = SEED["forms"]["volunteer"]
    error_block = ""
    if errors:
        error_block = '<ul class="error">' + "".join(
            f"<li>{esc(e)}</li>" for e in errors) + "</ul>"

    def text_field(name: str, label: str) -> str:
        return (f'<div class="field"><label for="f-{name}">{label}</label>'
                f'<input id="f-{name}" name="{name}" type="text" '
                f'value="{esc(values.get(name, ""))}"></div>')

    shirt_options = "".join(
        f'<option value="{esc(value)}"{" selected" if value == values.get("shirt_size", "") else ""}>'
        f'{esc(label)}</option>'
        for value, label in spec["shirt_sizes"]
    )
    shifts = "".join(
        f'<div class="field"><input id="f-shift-{esc(value)}" name="shift" type="radio" '
        f'value="{esc(value)}"{" checked" if value == values.get("shift", "") else ""}>'
        f'<label for="f-shift-{esc(value)}">{esc(label)}</label></div>'
        for value, label in spec["shifts"]
    )
    day_boxes = "".join(
        f'<div class="field"><input id="f-day-{esc(value)}" name="days" type="checkbox" '
        f'value="{esc(value)}"{" checked" if value in days else ""}>'
        f'<label for="f-day-{esc(value)}">{esc(label)}</label></div>'
        for value, label in spec["days"]
    )
    return f"""{error_block}
<form method="post" action="/forms/volunteer">
{text_field("first_name", "First name")}
{text_field("last_name", "Last name")}
{text_field("email", "Email")}
{text_field("phone", "Phone")}
<div class="field"><label for="f-shirt_size">T-shirt size</label>
<select id="f-shirt_size" name="shirt_size">{shirt_options}</select></div>
<fieldset><legend>Preferred shift</legend>{shifts}</fieldset>
<fieldset><legend>Days available</legend>{day_boxes}</fieldset>
<div class="field"><label for="f-comments">Comments</label><br>
<textarea id="f-comments" name="comments">{esc(values.get("comments", ""))}</textarea></div>
<button type="submit">Submit signup</button>
</form>"""


def _volunteer_page(values: dict | None = None, days: list[str] | None = None,
                   errors: list[str] | None = None) -> str:
    title = SEED["forms"]["volunteer"]["title"]
    return _page(title, "", f"<h1>{esc(title)}</h1>\n"
                 f"{_volunteer_form(values or {}, days or [], errors or [])}")


# ---------------------------------------------------------------- bank

def _bank_header() -> str:
    return """<header>
<a class="brand" href="/bank">Harborline Bank</a>
<nav><a href="/bank">Accounts</a><a href="/bank/statement">Statement</a></nav>
</header>"""


def _bank_page(title: str, body: str) -> str:
    return _page(f"Harborline Bank — {title}", _bank_header(), body)


def _bank_home() -> str:
    bank = SEED["bank"]
    return _bank_page("Accounts", f"""<h1>Harborline Bank</h1>
<table>
<tr><th>Account</th><td>{esc(bank["account_name"])}</td></tr>
<tr><th>Number</th><td>{esc(bank["account_number_masked"])}</td></tr>
<tr><th>Balance</th><td class="price">${esc(bank["balance"])}</td></tr>
</table>
<p><a href="/bank/statement">View statement</a></p>""")


def _bank_statement(page: int) -> str:
    transactions = sorted(SEED["transactions"], key=lambda t: str(t["date"]))
    pages = max(1, math.ceil(len(transactions) / STATEMENT_PAGE_SIZE))
    page = min(max(1, page), pages)
    start = (page - 1) * STATEMENT_PAGE_SIZE
    rows = "".join(
        f"<tr><td>{esc(_short_date(t['date']))}</td><td>{esc(t['desc'])}</td>"
        f"<td>{esc(t['category'])}</td><td class=\"price\">{_signed_money(t['amount'])}</td></tr>"
        for t in transactions[start:start + STATEMENT_PAGE_SIZE]
    )
    links = []
    if page > 1:
        links.append(f'<a href="/bank/statement?page={page - 1}">Previous</a>')
    links.extend(
        f'<a href="/bank/statement?page={n}">Page {n}</a>' for n in range(1, pages + 1)
    )
    if page < pages:
        links.append(f'<a href="/bank/statement?page={page + 1}">Next</a>')
    return _bank_page("Statement", f"""<h1>October 2026 statement</h1>
<table>
<tr><th>Date</th><th>Description</th><th>Category</th><th>Amount</th></tr>
{rows}
</table>
<p class="pager">{"".join(links)}</p>""")


def _index() -> str:
    return _page("Muselet fixtures", "", """<h1>Muselet fixtures</h1>
<ul>
<li><a href="/mart">Muselet Mart</a></li>
<li><a href="/mail">Muselet Mail</a></li>
<li><a href="/wiki">Lorepedia</a></li>
<li><a href="/forms/volunteer">Volunteer Signup — Riverside Food Bank</a></li>
<li><a href="/bank">Harborline Bank</a></li>
</ul>""")


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "MuseletFixtures/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep the nohup log readable
        sys.stderr.write("fixtures %s\n" % (fmt % args))

    # -- plumbing -----------------------------------------------------------

    def do_GET(self):
        with _LOCK:
            self._dispatch("GET")

    def do_POST(self):
        with _LOCK:
            self._dispatch("POST")

    def _dispatch(self, method: str):
        split = urlsplit(self.path)
        path, query = split.path, parse_qs(split.query)
        try:
            if path.startswith("/api/"):
                return self._api(method, path, query)
            if method == "GET":
                STATE["visits"].append({"path": self.path, "ts": time.time()})
                return self._get(path, query)
            if method == "POST":
                return self._post(path)
            self._send(405, "text/plain; charset=utf-8", "method not allowed\n")
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception as exc:
            self._send(500, "text/plain; charset=utf-8", f"error: {exc}\n")

    def _send(self, status: int, content_type: str, body: str,
              headers: dict | None = None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _html(self, body: str, status: int = 200):
        self._send(status, "text/html; charset=utf-8", body)

    def _redirect(self, location: str):
        self._send(303, "text/plain; charset=utf-8", "", {"Location": location})

    def _not_found(self, what: str = "page"):
        self._send(404, "text/plain; charset=utf-8", f"not found: {what}\n")

    def _form(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return parse_qs(raw, keep_blank_values=True)

    @staticmethod
    def _field(form: dict, name: str, default: str = "") -> str:
        values = form.get(name)
        return values[0] if values else default

    # -- api ----------------------------------------------------------------

    def _run_grader(self, case: str) -> dict | None:
        grader = GRADERS.get(case)
        if grader is None:
            return None
        try:
            result = grader(STATE, SEED)
        except Exception as exc:
            return {"passed": False, "reason": f"grader error: {exc}", "milestones": {}}
        return {
            "passed": bool(result.get("passed")),
            "reason": str(result.get("reason", "")),
            "milestones": {k: bool(v) for k, v in (result.get("milestones") or {}).items()},
        }

    def _api(self, method: str, path: str, query: dict):
        if method == "GET" and path == "/api/health":
            return self._send(200, "text/plain; charset=utf-8", "ok\n")
        if method == "GET" and path == "/api/state":
            return self._send(200, "application/json",
                              json.dumps(STATE, ensure_ascii=False, default=str))
        if path == "/api/reset":
            if method != "POST":
                return self._send(405, "text/plain; charset=utf-8", "POST required\n")
            form = self._form()
            case = self._field(form, "case") or (query.get("case") or [""])[0]
            preset = self._field(form, "preset") or (query.get("preset") or [""])[0]
            if preset and preset not in CART_PRESETS:
                return self._send(400, "text/plain; charset=utf-8",
                                  f"unknown preset: {preset}\n")
            STATE.clear()
            STATE.update(_fresh_state(case or None, preset or None))
            return self._send(200, "text/plain; charset=utf-8", "ok\n")
        if method != "GET":
            return self._send(405, "text/plain; charset=utf-8", "method not allowed\n")
        match = re.fullmatch(r"/api/grade/([^/]+)", path)
        if match:
            result = self._run_grader(match.group(1))
            if result is None:
                return self._not_found("case")
            text = "PASS" if result["passed"] else f"FAIL: {result['reason']}"
            return self._send(200, "text/plain; charset=utf-8", text + "\n")
        match = re.fullmatch(r"/api/grade_json/([^/]+)", path)
        if match:
            result = self._run_grader(match.group(1))
            if result is None:
                return self._not_found("case")
            return self._send(200, "application/json", json.dumps(result))
        match = re.fullmatch(r"/api/milestone/([^/]+)/([^/]+)", path)
        if match:
            result = self._run_grader(match.group(1))
            if result is None or match.group(2) not in result["milestones"]:
                return self._not_found("milestone")
            text = "PASS" if result["milestones"][match.group(2)] else "FAIL"
            return self._send(200, "text/plain; charset=utf-8", text + "\n")
        return self._not_found("api")

    # -- GET routes ---------------------------------------------------------

    def _get(self, path: str, query: dict):
        if path == "/":
            return self._html(_index())

        if path == "/mart":
            return self._html(_mart_home())
        match = re.fullmatch(r"/mart/c/([a-z0-9-]+)", path)
        if match:
            category = _product_category(match.group(1))
            return self._html(_mart_category(category)) if category else self._not_found("category")
        if path == "/mart/search":
            return self._html(_mart_search(query))
        match = re.fullmatch(r"/mart/p/([^/]+)", path)
        if match:
            product = PRODUCTS.get(match.group(1))
            if product is None:
                return self._not_found("product")
            return self._html(_mart_product(product, (query.get("added") or [None])[0]))
        if path == "/mart/cart":
            return self._html(_mart_cart())
        if path == "/mart/checkout":
            return self._html(_mart_checkout())
        match = re.fullmatch(r"/mart/order/([^/]+)", path)
        if match:
            order = next(
                (o for o in STATE["mart"]["orders"] if str(o["id"]) == match.group(1)),
                None,
            )
            return self._html(_mart_order(order)) if order else self._not_found("order")

        if path == "/mail":
            return self._html(_mail_inbox())
        match = re.fullmatch(r"/mail/m/([^/]+)", path)
        if match:
            message = EMAILS.get(match.group(1))
            return self._html(_mail_message(message)) if message else self._not_found("message")
        if path == "/mail/compose":
            return self._html(self._compose_get(query))
        if path == "/mail/sent":
            return self._html(_mail_sent(bool((query.get("ok") or [""])[0])))
        if path == "/mail/search":
            return self._html(_mail_search((query.get("q") or [""])[0]))

        if path == "/wiki":
            return self._html(_wiki_home())
        match = re.fullmatch(r"/wiki/a/([^/]+)", path)
        if match:
            article = ARTICLES.get(match.group(1))
            return self._html(_wiki_article(article)) if article else self._not_found("article")
        if path == "/wiki/search":
            outcome = _wiki_search((query.get("q") or [""])[0])
            if isinstance(outcome, str) and outcome.startswith("/wiki/a/"):
                return self._send(302, "text/plain; charset=utf-8", "",
                                  {"Location": outcome})
            return self._html(outcome)
        match = re.fullmatch(r"/wiki/quiz/([^/]+)", path)
        if match:
            quiz = QUIZZES.get(match.group(1))
            if quiz is None:
                return self._not_found("quiz")
            submitted = (query.get("answer") or [None])[0] if "submitted" in query else None
            return self._html(_wiki_quiz(quiz, submitted))

        if path == "/forms/volunteer":
            return self._html(_volunteer_page())
        if path == "/forms/volunteer/thanks":
            title = SEED["forms"]["volunteer"]["title"]
            return self._html(_page(title, "", f"""<h1>{esc(title)}</h1>
<p class="banner">Thank you for signing up! We will be in touch.</p>"""))

        if path == "/bank":
            return self._html(_bank_home())
        if path == "/bank/statement":
            try:
                page = int((query.get("page") or ["1"])[0])
            except ValueError:
                page = 1
            return self._html(_bank_statement(page))

        return self._not_found()

    def _compose_get(self, query: dict) -> str:
        reply_to = (query.get("reply_to") or [""])[0]
        forward = (query.get("forward") or [""])[0]
        values = {"to": "", "subject": "", "body": "", "reply_to": "", "forward": ""}
        quoted = None
        if reply_to and reply_to in EMAILS:
            original = EMAILS[reply_to]
            values.update({
                "to": original["from_addr"],
                "subject": f'Re: {original["subject"]}',
                "reply_to": reply_to,
            })
            quoted = original
        elif forward and forward in EMAILS:
            original = EMAILS[forward]
            values.update({
                "subject": f'Fwd: {original["subject"]}',
                "body": _quote_text(original),
                "forward": forward,
            })
            quoted = original
        return _mail_compose(values, quoted)

    # -- POST routes --------------------------------------------------------

    def _post(self, path: str):
        form = self._form()

        if path == "/mart/cart/add":
            pid = self._field(form, "pid")
            product = PRODUCTS.get(pid)
            if product is None:
                return self._not_found("product")
            try:
                qty = int(self._field(form, "qty") or 1)
            except ValueError:
                qty = 1
            qty = min(20, max(1, qty))
            cart = STATE["mart"]["cart"]
            cart[pid] = int(cart.get(pid, 0)) + qty
            STATE["mart"]["events"].append({"t": "add", "pid": pid, "qty": qty})
            return self._redirect(f"/mart/p/{quote(str(pid))}?added={qty}")

        if path == "/mart/cart/update":
            pid = self._field(form, "pid")
            if pid not in STATE["mart"]["cart"]:
                return self._not_found("cart item")
            try:
                qty = int(self._field(form, "qty") or 0)
            except ValueError:
                qty = 0
            qty = max(0, min(99, qty))
            STATE["mart"]["events"].append({"t": "update", "pid": pid, "qty": qty})
            if qty <= 0:
                STATE["mart"]["cart"].pop(pid, None)
            else:
                STATE["mart"]["cart"][pid] = qty
            return self._redirect("/mart/cart")

        if path == "/mart/cart/remove":
            pid = self._field(form, "pid")
            STATE["mart"]["cart"].pop(pid, None)
            STATE["mart"]["events"].append({"t": "remove", "pid": pid})
            return self._redirect("/mart/cart")

        if path == "/mart/checkout/place":
            values = {name: self._field(form, name).strip()
                      for name in ("name", "street", "city", "zip")}
            errors = []
            rows, _subtotal = _cart_rows()
            if not rows:
                errors.append("Your cart is empty.")
            labels = {"name": "Full name", "street": "Street address",
                      "city": "City", "zip": "ZIP code"}
            for name, label in labels.items():
                if not values[name]:
                    errors.append(f"{label} is required.")
            if errors:
                return self._html(_mart_checkout(values, errors), status=400)
            orders = STATE["mart"]["orders"]
            order_id = str(1000 + len(orders) + 1)
            orders.append({
                "id": order_id,
                "items": {pid: int(qty) for pid, qty in STATE["mart"]["cart"].items()
                          if int(qty) > 0},
                "ship": dict(values),
                "ts": time.time(),
            })
            STATE["mart"]["events"].append({"t": "place", "order_id": order_id})
            STATE["mart"]["cart"].clear()
            return self._redirect(f"/mart/order/{order_id}")

        if path == "/mail/send":
            values = {
                "to": self._field(form, "to"),
                "subject": self._field(form, "subject"),
                "body": self._field(form, "body"),
                "reply_to": self._field(form, "reply_to"),
                "forward": self._field(form, "forward"),
            }
            recipients = [part.strip() for part in values["to"].split(",") if part.strip()]
            if not recipients or not all("@" in part for part in recipients):
                quoted = EMAILS.get(values["reply_to"] or values["forward"])
                return self._html(
                    _mail_compose(values, quoted,
                                  "Every recipient address must contain '@'."),
                    status=400,
                )
            STATE["mail"]["sent"].append({
                "to": values["to"].strip(),
                "subject": values["subject"],
                "body": values["body"],
                "in_reply_to": values["reply_to"] or None,
                "forward_of": values["forward"] or None,
                "ts": time.time(),
            })
            return self._redirect("/mail/sent?ok=1")

        match = re.fullmatch(r"/wiki/quiz/([^/]+)/answer", path)
        if match:
            quiz = QUIZZES.get(match.group(1))
            if quiz is None:
                return self._not_found("quiz")
            answer = self._field(form, "answer").strip()
            STATE["wiki"]["answers"].append({
                "quiz": str(quiz["id"]), "answer": answer, "ts": time.time(),
            })
            return self._redirect(
                f"/wiki/quiz/{quote(str(quiz['id']))}?submitted=1&answer={quote(answer)}"
            )

        if path == "/forms/volunteer":
            fields = {
                "first_name": self._field(form, "first_name").strip(),
                "last_name": self._field(form, "last_name").strip(),
                "email": self._field(form, "email").strip(),
                "phone": self._field(form, "phone").strip(),
                "shirt_size": self._field(form, "shirt_size"),
                "shift": self._field(form, "shift"),
                "comments": self._field(form, "comments"),
            }
            days = [str(d) for d in form.get("days", [])]
            fields["days"] = days
            errors = []
            if not fields["first_name"]:
                errors.append("First name is required.")
            if not fields["last_name"]:
                errors.append("Last name is required.")
            email = fields["email"]
            if not email or "@" not in email or "." not in email:
                errors.append("A valid email address is required.")
            if not fields["shift"]:
                errors.append("Please choose a preferred shift.")
            if not days:
                errors.append("Please choose at least one day.")
            if errors:
                return self._html(_volunteer_page(fields, days, errors), status=400)
            STATE["forms"]["submissions"].append({
                "form": "volunteer", "fields": fields, "ts": time.time(),
            })
            return self._redirect("/forms/volunteer/thanks")

        return self._not_found("post")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), FixtureHandler)
    server.daemon_threads = True
    print(f"fixtures listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
