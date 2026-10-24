"""One-page meeting brief. Every number comes from `prep`; `phrasing` may add short sentences, never numbers."""

from __future__ import annotations

import datetime as dt
import html
import re
from decimal import Decimal

PHRASING_KEYS = ("headline", "lake_house", "charitable", "closing")
_NUMERIC = re.compile(r"[0-9$%]")

DEFAULT_PHRASING = {
    "headline": "",
    "lake_house": "Confirm timing; the reserve stays in savings, outside the market.",
    "charitable": "Giving long-held stock instead of cash avoids the capital gain.",
    "closing": "",
}


def usd(x: str | Decimal) -> str:
    d = Decimal(x)
    return ("-" if d < 0 else "") + f"${abs(d):,.2f}"


def pp(x: str) -> str:
    d = Decimal(x)
    return f"{'+' if d > 0 else ''}{d} pp"


def clean_phrasing(phrasing: dict | None) -> dict:
    """Keep known keys with short, number-free text; anything else falls back to the default."""
    out = dict(DEFAULT_PHRASING)
    for k, v in (phrasing or {}).items():
        if k in PHRASING_KEYS and isinstance(v, str):
            v = " ".join(v.split())
            if v and len(v) <= 160 and not _NUMERIC.search(v):
                out[k] = v
    return out


def _meeting_line(prep: dict) -> str:
    m = prep.get("meeting") or {}
    parts = []
    if m.get("start"):
        start = dt.datetime.fromisoformat(m["start"])
        when = f"{start:%a %b} {start.day}, {start.year}, {start:%H:%M}"
        if m.get("end"):
            when += f"-{dt.datetime.fromisoformat(m['end']):%H:%M}"
        parts.append(f"{m.get('summary', 'Meeting')}, {when}")
    parts.append(f"data as of {prep['as_of']}, computed on this Mac")
    return " · ".join(parts)


def _lot(lot: dict) -> str:
    return f"{lot['ticker']} ({lot['lot_date']})"


def _opportunity_lines(prep: dict) -> dict[str, str]:
    reb, tlh, cash, roth, don = (prep[k] for k in ("rebalance", "tlh", "cash", "roth", "donation"))
    lines = {}
    sells = [t for t in reb["trades"] if t["side"] == "sell"]
    buys = [t for t in reb["trades"] if t["side"] == "buy"]
    if reb["trades"]:
        accts = sorted({t["account"] for t in reb["trades"]})
        txt = (f"Sell {' and '.join(f'{usd(t['amount'])} {t['ticker']}' for t in sells)}; "
               f"buy {' and '.join(f'{usd(t['amount'])} {t['ticker']}' for t in buys)} "
               f"in {', '.join(accts)}.")
        swaps = [t for t in buys if t.get("instead_of")]
        if swaps:
            txt += " " + " ".join(f"{t['ticker']} instead of {t['instead_of']} keeps the "
                                  f"{t['instead_of']} harvest clean." for t in swaps)
        txt += f" Realized gain {usd(reb['realized_gain'])}."
        lines["rebalance"] = txt
    lines["cash_excess"] = (f"Savings {usd(cash['savings'])} minus {cash['months']}-month reserve "
                            f"{usd(cash['emergency_reserve'])} minus lake house {usd(cash['lake_house_reserve'])}.")
    lines["roth_conversion"] = (f"22% bracket top {usd(roth['bracket_top'])} minus taxable income "
                                f"{usd(roth['taxable_income'])} ({roth['year']}, IRS Rev. Proc. 2025-32).")
    ok = [e for e in tlh["lots"] if e["status"] == "ok"]
    blocked = [e for e in tlh["lots"] if e["status"] != "ok"]
    txt = "; ".join(f"{_lot(e['lot'])} {usd(e['loss'])} → {e['replacement']}" for e in ok) + "."
    for e in blocked:
        txt += (f" {_lot(e['lot'])} {usd(e['loss'])} is wash-sale blocked by the "
                f"{e['blocking_buys'][-1]['date']} buy in {e['blocking_buys'][-1]['account']}; "
                f"clean from {e['earliest_clean_sale']}.")
    lines["tax_loss_harvest"] = txt
    lines["donate_appreciated"] = (", ".join(f"{_lot(c['lot'])} +{c['gain_pct']}%" for c in don["candidates"])
                                   + f"; {usd(don['market_value_total'])} market value.")
    return lines


def brief_markdown(prep: dict, phrasing: dict | None = None) -> str:
    ph = clean_phrasing(phrasing)
    alloc, cash, don, tlh, roth = (prep[k] for k in ("allocation", "cash", "donation", "tlh", "roth"))
    out = [f"# {prep['household']} — annual review prep", _meeting_line(prep), ""]
    if ph["headline"]:
        out += [ph["headline"], ""]

    savings = sum((Decimal(v) for a, v in prep["totals"]["by_account"].items() if a.lower() == "savings"),
                  Decimal(0))
    out += ["## Snapshot",
            f"- Household assets {usd(prep['totals']['household'])}: invested {usd(prep['totals']['invested'])}, "
            f"savings {usd(savings)}.",
            f"- Allocation vs target (band ±{Decimal(alloc['band_pp']).normalize()} pp):"]
    for c in alloc["classes"] + alloc["groups"]:
        name = c.get("asset_class") or f"{c['group']} total"
        flag = ", outside band" if c["out_of_band"] else ""
        out.append(f"  - {name} {c['current_pct']}% vs {c['target_pct']}% ({pp(c['drift_pp'])}{flag})")
    out.append("")

    lines = _opportunity_lines(prep)
    out.append("## Opportunities")
    for i, o in enumerate(prep["opportunities"], start=1):
        out.append(f"{i}. **{o['title']}**: {usd(o['impact_usd'])} {o['impact_kind']}. {lines[o['key']]}")
    out.append("")

    out += ["## Talking points",
            f"- Lake house: {usd(cash['lake_house_reserve'])} down payment next spring. {ph['lake_house']}",
            f"- Charitable giving: gift {' and '.join(_lot(c['lot']) for c in don['candidates'])} to a "
            f"donor-advised fund. {ph['charitable']}", ""]

    acts = []
    reb = prep["rebalance"]
    if reb["trades"]:
        acts.append("Rebalance: " + "; ".join(f"{t['side']} {usd(t['amount'])} {t['ticker']} ({t['account']})"
                                               for t in reb["trades"]) + ".")
    ok = [e for e in tlh["lots"] if e["status"] == "ok"]
    if ok:
        acts.append("Harvest " + "; ".join(f"{_lot(e['lot'])} → buy {e['replacement']}" for e in ok)
                    + f" (total {usd(tlh['harvestable_loss_total'])} loss).")
    for e in tlh["lots"]:
        if e["status"] != "ok":
            acts.append(f"Hold {_lot(e['lot'])} harvest until {e['earliest_clean_sale']}; no {e['lot']['ticker']} "
                        "buys in any account before then.")
    if Decimal(roth["room"]) > 0:
        trad = next((a for a in prep["totals"]["by_account"] if "traditional ira" in a.lower()), "the Traditional IRA")
        acts.append(f"Convert up to {usd(roth['room'])} from {trad} to Roth before Dec 31, {roth['year']}.")
    if Decimal(cash["excess"]) > 0:
        acts.append(f"Move {usd(cash['excess'])} of excess savings to the brokerage and invest at target.")
    if don["candidates"]:
        acts.append(f"Open a donor-advised fund; gift {' and '.join(_lot(c['lot']) for c in don['candidates'])} "
                    f"({usd(don['market_value_total'])}).")
    out.append("## Proposed actions")
    out += [f"{i}. {a}" for i, a in enumerate(acts, start=1)]
    if ph["closing"]:
        out += ["", ph["closing"]]
    return "\n".join(out) + "\n"


def _inline(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text, quote=True))


def brief_html(markdown: str) -> str:
    """Render the brief's small Markdown subset (#, ##, -, nested -, 1., **bold**) as Notes-friendly HTML."""
    out: list[str] = []
    stack: list[str] = []

    def close_to(depth: int) -> None:
        while len(stack) > depth:
            out.append(f"</{stack.pop()}>")

    for line in markdown.splitlines():
        m = re.match(r"^( *)(- |\d+\. )(.*)$", line)
        if m:
            depth = len(m.group(1)) // 2 + 1
            tag = "ul" if m.group(2) == "- " else "ol"
            close_to(depth)
            if len(stack) < depth:
                stack.append(tag)
                out.append(f"<{tag}>")
            out.append(f"<li>{_inline(m.group(3))}</li>")
            continue
        close_to(0)
        if line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<div>{_inline(line)}</div>")
    close_to(0)
    return "".join(out)
