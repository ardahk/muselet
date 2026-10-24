"""Deterministic household analytics for advisor meeting prep (stdlib only, Decimal money).

Every function returns plain JSON-able values (money as 2-decimal strings) plus an `evidence` list:
`{"rule": <the rule that fired>, "rows": [portfolio.csv data rows, 1-based], ...}`.
Rules (also documented in evals/fixtures/advisor/README.md):
- Allocation covers the investment accounts only; the Savings account is the liquidity bucket.
- Rebalance: if any asset class drifts more than the band from target, trade every non-cash class back
  to target. Sells and buys are placed in tax-advantaged accounts first (Traditional IRA, then Roth IRA,
  taxable last) so no gains are realized; buys in an account are funded by that account's sweep cash
  and same-account sale proceeds. A buy never uses a ticker that has a TLH lot (it would wash the loss);
  it uses the replacement from PAIRS instead.
- TLH: taxable lots with unrealized loss >= min_loss. Blocked if the same ticker was bought in any
  account within wash_days before the as-of date (IRS Pub. 550; IRA buys count).
- Cash excess: savings - months x monthly expenses - lake-house reserve parsed from the last notes.
- Roth room: top of the 22% bracket (IRS Rev. Proc. 2025-32) - estimated taxable income, floor 0.
- Donation candidates: taxable lots with a gain, held more than 1 year, top n by gain percentage.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from . import tax

CENT = Decimal("0.01")
CASH = "Cash"
ASSET_CLASSES = ("US equity", "Intl equity", "Bonds", CASH)

# Replacement pairs for tax-loss harvesting (similar exposure, different index/issuer).
PAIRS = {"VTI": "ITOT", "VXUS": "IXUS", "BND": "AGG", "VNQ": "SCHH", "VOO": "IVV", "VEA": "IEFA",
         "VWO": "IEMG", "BNDX": "IAGG"}
DEFAULT_TICKER = {"US equity": "VTI", "Intl equity": "VXUS", "Bonds": "BND"}
ACCOUNT_KIND_ORDER = ("traditional_ira", "roth_ira", "taxable")


def money(x: Decimal) -> str:
    return str(x.quantize(CENT, rounding=ROUND_HALF_UP))


def account_kind(name: str) -> str:
    n = name.lower()
    if "roth" in n:
        return "roth_ira"
    if "ira" in n:
        return "traditional_ira"
    if "savings" in n:
        return "savings"
    return "taxable"


@dataclass(frozen=True)
class Lot:
    row: int
    account: str
    ticker: str
    name: str
    asset_class: str
    lot_date: dt.date | None
    shares: Decimal
    cost_basis: Decimal
    price: Decimal
    market_value: Decimal
    gain: Decimal

    @property
    def kind(self) -> str:
        return account_kind(self.account)

    def ref(self) -> dict:
        return {"row": self.row, "account": self.account, "ticker": self.ticker,
                "lot_date": self.lot_date.isoformat() if self.lot_date else "", "shares": str(self.shares)}


@dataclass(frozen=True)
class Trade:
    row: int
    date: dt.date
    account: str
    action: str
    ticker: str
    shares: Decimal
    price: Decimal
    amount: Decimal


@dataclass
class Household:
    path: Path
    name: str
    as_of: dt.date
    lots: list[Lot]
    activity: list[Trade]
    targets: dict
    profile: dict
    notes: str
    meeting: dict
    warnings: list[str] = field(default_factory=list)

    @property
    def invested(self) -> list[Lot]:
        return [x for x in self.lots if x.kind != "savings"]


def _d(s: str) -> Decimal:
    return Decimal(s.replace(",", "").replace("$", "").strip() or "0")


def _parse_ics(text: str) -> dict:
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    out: dict = {}
    for line in unfolded.splitlines():
        key, _, value = line.partition(":")
        key = key.split(";")[0]
        if key in ("SUMMARY", "DTSTART", "DTEND", "LOCATION") and key.lower() not in out:
            out[key.lower()] = value
    for k in ("dtstart", "dtend"):
        if k in out:
            v = out.pop(k).rstrip("Z")
            out["start" if k == "dtstart" else "end"] = dt.datetime.strptime(v, "%Y%m%dT%H%M%S").strftime(
                "%Y-%m-%dT%H:%M")
    return out


def load_household(directory: str | Path) -> Household:
    p = Path(directory)
    lots = []
    with (p / "portfolio.csv").open(newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=1):
            lot = Lot(row=i, account=r["Account"], ticker=r["Ticker"], name=r["Name"], asset_class=r["Asset class"],
                      lot_date=dt.date.fromisoformat(r["Lot date"]) if r["Lot date"] else None,
                      shares=_d(r["Shares"]), cost_basis=_d(r["Cost basis"]), price=_d(r["Price"]),
                      market_value=_d(r["Market value"]), gain=_d(r["Unrealized G/L"]))
            if lot.asset_class not in ASSET_CLASSES:
                raise ValueError(f"portfolio.csv row {i}: unknown asset class {lot.asset_class!r}")
            lots.append(lot)
    activity = []
    with (p / "activity_last_60d.csv").open(newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=1):
            activity.append(Trade(row=i, date=dt.date.fromisoformat(r["Date"]), account=r["Account"],
                                  action=r["Action"], ticker=r["Ticker"], shares=_d(r["Shares"]),
                                  price=_d(r["Price"]), amount=_d(r["Amount"])))
    profile = json.loads((p / "profile.json").read_text())
    targets = json.loads((p / "targets.json").read_text())
    notes_path = p / "last_meeting_notes.txt"
    ics_path = p / "annual_review.ics"
    h = Household(path=p, name=profile["household"], as_of=dt.date.fromisoformat(profile["as_of"]), lots=lots,
                  activity=activity, targets=targets, profile=profile,
                  notes=notes_path.read_text() if notes_path.exists() else "",
                  meeting=_parse_ics(ics_path.read_text()) if ics_path.exists() else {})
    for lot in lots:
        if (lot.shares * lot.price).quantize(CENT, rounding=ROUND_HALF_UP) != lot.market_value:
            h.warnings.append(f"row {lot.row}: market value != shares x price")
        if lot.market_value - lot.cost_basis != lot.gain:
            h.warnings.append(f"row {lot.row}: unrealized G/L != market value - cost basis")
    return h


def totals(h: Household) -> dict:
    by_account: dict[str, Decimal] = {}
    for x in h.lots:
        by_account[x.account] = by_account.get(x.account, Decimal(0)) + x.market_value
    return {"household": money(sum(by_account.values(), Decimal(0))),
            "invested": money(sum((x.market_value for x in h.invested), Decimal(0))),
            "by_account": {a: money(v) for a, v in by_account.items()},
            "evidence": [{"rule": "sum of Market value per account; invested excludes Savings",
                          "rows": [x.row for x in h.lots]}]}


def _class_values(lots: list[Lot]) -> dict[str, Decimal]:
    out = {k: Decimal(0) for k in ASSET_CLASSES}
    for x in lots:
        out[x.asset_class] += x.market_value
    return out


def allocation(h: Household) -> dict:
    total = sum((x.market_value for x in h.invested), Decimal(0))
    band = Decimal(h.targets["rebalance_band_pp"])
    values = _class_values(h.invested)
    classes, evidence = [], []
    for k, t in h.targets["targets_pct"].items():
        cur, t = values[k] * 100 / total, Decimal(t)
        out = abs(cur - t) > band
        classes.append({"asset_class": k, "value": money(values[k]), "current_pct": money(cur),
                        "target_pct": money(t), "drift_pp": money(cur - t), "out_of_band": out})
        if out:
            evidence.append({"rule": f"|current - target| > {band} pp band",
                             "asset_class": k, "drift_pp": money(cur - t),
                             "rows": [x.row for x in h.invested if x.asset_class == k]})
    groups = []
    for g, spec in h.targets.get("groups_pct", {}).items():
        gv = sum((values[k] for k in spec["classes"]), Decimal(0))
        cur, t = gv * 100 / total, Decimal(spec["target"])
        groups.append({"group": g, "classes": list(spec["classes"]), "value": money(gv), "current_pct": money(cur),
                       "target_pct": money(t), "drift_pp": money(cur - t), "out_of_band": abs(cur - t) > band})
    return {"invested_total": money(total), "band_pp": money(band), "classes": classes, "groups": groups,
            "rebalance_needed": any(c["out_of_band"] for c in classes), "evidence": evidence}


def _held(h: Household, account: str, klass: str) -> dict[str, Decimal]:
    held: dict[str, Decimal] = {}
    for x in h.invested:
        if x.account == account and x.asset_class == klass:
            held[x.ticker] = held.get(x.ticker, Decimal(0)) + x.market_value
    return held


def rebalance_trades(h: Household, band: Decimal | str | None = None, avoid: set[str] | None = None) -> dict:
    """Trades that restore target. `avoid` = tickers that must not be bought (default: all TLH lot tickers)."""
    if band is not None:
        h = Household(**{**h.__dict__, "targets": {**h.targets, "rebalance_band_pp": str(band)}})
    if avoid is None:
        avoid = {e["lot"]["ticker"] for e in tlh_candidates(h)["lots"]}
    alloc = allocation(h)
    total = sum((x.market_value for x in h.invested), Decimal(0))
    tgt = {k: Decimal(v) for k, v in h.targets["targets_pct"].items()}
    values = _class_values(h.invested)
    post = dict(values)
    trades: list[dict] = []
    evidence: list[dict] = []
    accounts = sorted({x.account for x in h.invested}, key=lambda a: (ACCOUNT_KIND_ORDER.index(account_kind(a)), a))
    realized = Decimal(0)
    if alloc["rebalance_needed"]:
        evidence.append({"rule": "a class is outside the band: rebalance every non-cash class to target",
                         "out_of_band": [c["asset_class"] for c in alloc["classes"] if c["out_of_band"]]})
        evidence.append({"rule": "account order: " + " > ".join(accounts)
                         + " (tax-advantaged first, so sells realize no gains)"})
        delta = {k: (total * tgt[k] / 100 - values[k]).quantize(CENT, rounding=ROUND_HALF_UP)
                 for k in tgt if k != CASH}
        funds = {a: sum((x.market_value for x in h.invested if x.account == a and x.asset_class == CASH), Decimal(0))
                 for a in accounts}
        for k in sorted((k for k in delta if delta[k] < 0), key=lambda k: delta[k]):
            need = -delta[k]
            for a in accounts:
                held = _held(h, a, k)
                for t in sorted(held, key=lambda t: (-held[t], t)):
                    if need <= 0:
                        break
                    amt = min(need, held[t])
                    tr = {"account": a, "side": "sell", "ticker": t, "asset_class": k, "amount": money(amt)}
                    if account_kind(a) == "taxable":
                        realized += _taxable_sell_gain(h, a, t, amt)
                    trades.append(tr)
                    need -= amt
                    funds[a] += amt
                    post[k] -= amt
        for k in sorted((k for k in delta if delta[k] > 0), key=lambda k: -delta[k]):
            need = delta[k]
            for a in accounts:
                if need <= 0 or funds[a] <= 0:
                    continue
                held = _held(h, a, k)
                base = sorted(held, key=lambda t: (-held[t], t))[0] if held else DEFAULT_TICKER[k]
                ticker = PAIRS.get(base, base) if base in avoid else base
                amt = min(need, funds[a])
                tr = {"account": a, "side": "buy", "ticker": ticker, "asset_class": k, "amount": money(amt)}
                if ticker != base:
                    tr["instead_of"] = base
                    evidence.append({"rule": f"{base} has a tax-loss-harvest lot; buying it within 30 days would "
                                             f"wash the loss, so buy the pair {ticker}", "ticker": base})
                trades.append(tr)
                need -= amt
                funds[a] -= amt
                post[k] += amt
        post[CASH] = total - sum((post[k] for k in tgt if k != CASH), Decimal(0))
    else:
        evidence.append({"rule": "every class within the band: no trades"})
    return {"rule": "full rebalance to target when any class is outside the band; IRAs first",
            "trades": trades,
            "post_trade_pct": {k: money(post[k] * 100 / total) for k in tgt},
            "realized_gain": money(realized),
            "total_bought": money(sum((Decimal(t["amount"]) for t in trades if t["side"] == "buy"), Decimal(0))),
            "total_sold": money(sum((Decimal(t["amount"]) for t in trades if t["side"] == "sell"), Decimal(0))),
            "evidence": evidence}


def _taxable_sell_gain(h: Household, account: str, ticker: str, amount: Decimal) -> Decimal:
    """Gain realized selling `amount` of a taxable position, highest-cost lots first (HIFO)."""
    lots = sorted((x for x in h.invested if x.account == account and x.ticker == ticker),
                  key=lambda x: (-(x.cost_basis / x.shares), x.row))
    gain, left = Decimal(0), amount
    for x in lots:
        take = min(left, x.market_value)
        gain += x.gain * take / x.market_value
        left -= take
        if left <= 0:
            break
    return gain


def _long_term(lot_date: dt.date, as_of: dt.date) -> bool:
    """Held more than 1 year (IRS Pub. 550: the holding period starts the day after the trade date)."""
    try:
        anniversary = lot_date.replace(year=lot_date.year + 1)
    except ValueError:
        anniversary = dt.date(lot_date.year + 1, 3, 1)
    return as_of > anniversary


def tlh_candidates(h: Household, min_loss: Decimal | str = Decimal(1000), wash_days: int = tax.WASH_SALE_DAYS) -> dict:
    min_loss = Decimal(min_loss)
    lots, evidence = [], []
    for x in h.lots:
        if x.kind != "taxable" or x.lot_date is None or -x.gain < min_loss:
            continue
        buys = [a for a in h.activity
                if a.action.lower() == "buy" and a.ticker == x.ticker and 0 <= (h.as_of - a.date).days <= wash_days
                and not (a.account == x.account and a.date == x.lot_date and a.shares == x.shares)]
        entry = {"lot": x.ref(), "cost_basis": money(x.cost_basis), "market_value": money(x.market_value),
                 "loss": money(-x.gain), "term": "long" if _long_term(x.lot_date, h.as_of) else "short",
                 "status": "wash_sale_blocked" if buys else "ok", "replacement": PAIRS.get(x.ticker)}
        ev = {"rule": f"taxable lot with unrealized loss >= {money(min_loss)}", "rows": [x.row]}
        if buys:
            last = max(a.date for a in buys)
            entry["blocking_buys"] = [{"date": a.date.isoformat(), "account": a.account, "ticker": a.ticker,
                                       "shares": str(a.shares)} for a in buys]
            entry["earliest_clean_sale"] = (last + dt.timedelta(days=wash_days + 1)).isoformat()
            ev["wash_sale"] = (f"{x.ticker} bought {', '.join(f'{a.date} in {a.account}' for a in buys)}; within "
                               f"{wash_days} days of a sale today (IRS Pub. 550, IRA purchases count)")
            ev["activity_rows"] = [a.row for a in buys]
        lots.append(entry)
        evidence.append(ev)
    lots.sort(key=lambda e: (-Decimal(e["loss"]), e["lot"]["row"]))
    total = sum((Decimal(e["loss"]) for e in lots if e["status"] == "ok"), Decimal(0))
    evidence.append({"rule": "harvestable total excludes wash-sale-blocked lots", "source": tax.PUB_550})
    return {"min_loss": money(min_loss), "wash_days": wash_days, "lots": lots,
            "harvestable_loss_total": money(total), "evidence": evidence}


_DOLLARS = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


def lake_house_reserve(notes: str) -> tuple[Decimal, str | None]:
    for sentence in re.split(r"(?<=[.!?])\s+|\n", notes):
        low = sentence.lower()
        if "lake house" in low and "down" in low:
            m = _DOLLARS.search(sentence)
            if m:
                return _d(m.group(1)), sentence.strip()
    return Decimal(0), None


def cash_excess(h: Household, months: int | None = None) -> dict:
    months = int(months if months is not None else h.profile.get("emergency_fund_months", 6))
    savings_lots = [x for x in h.lots if x.kind == "savings"]
    savings = sum((x.market_value for x in savings_lots), Decimal(0))
    monthly = Decimal(h.profile["monthly_expenses"])
    lake, sentence = lake_house_reserve(h.notes)
    excess = savings - months * monthly - lake
    evidence = [{"rule": f"excess = savings - {months} x monthly expenses - lake-house reserve (kept liquid)",
                 "rows": [x.row for x in savings_lots]}]
    if sentence:
        evidence.append({"rule": "lake-house reserve parsed from last meeting notes", "quote": sentence})
    return {"savings": money(savings), "months": months, "monthly_expenses": money(monthly),
            "emergency_reserve": money(months * monthly), "lake_house_reserve": money(lake),
            "excess": money(max(excess, Decimal(0))), "evidence": evidence}


def roth_room(h: Household, year: int | None = None) -> dict:
    year = int(year if year is not None else h.profile["tax_year"])
    status = h.profile["filing_status"]
    key = (year, status)
    if key not in tax.BRACKET_TOPS:
        raise KeyError(f"no verified bracket table for {year} {status}")  # TODO(lead): add verified figures
    top = tax.BRACKET_TOPS[key]["22%"]
    ti = Decimal(h.profile["estimated_taxable_income"])
    return {"year": year, "filing_status": status, "bracket_rate": "22%", "bracket_top": money(top),
            "taxable_income": money(ti), "room": money(max(top - ti, Decimal(0))), "source": tax.SOURCES[key],
            "evidence": [{"rule": "room = top of 22% bracket - estimated taxable income before conversion",
                          "source": tax.SOURCES[key], "bracket_top": money(top),
                          "profile_field": "estimated_taxable_income"}]}


def donation_candidates(h: Household, n: int = 2) -> dict:
    pool = [x for x in h.lots if x.kind == "taxable" and x.lot_date is not None and x.gain > 0
            and _long_term(x.lot_date, h.as_of)]
    skipped = [x for x in h.lots if x.kind == "taxable" and x.lot_date is not None and x.gain > 0
               and not _long_term(x.lot_date, h.as_of)]
    pool.sort(key=lambda x: (-(x.gain / x.cost_basis), x.row))
    picks = pool[:n]
    cands = [{"lot": x.ref(), "cost_basis": money(x.cost_basis), "market_value": money(x.market_value),
              "unrealized_gain": money(x.gain), "gain_pct": money(x.gain * 100 / x.cost_basis)} for x in picks]
    evidence = [{"rule": f"top {n} taxable lots by unrealized gain % held more than 1 year (gifting long-term "
                         "appreciated stock to a donor-advised fund avoids the gain)", "rows": [x.row for x in picks]}]
    if skipped:
        evidence.append({"rule": "excluded: held 1 year or less (short-term)", "rows": [x.row for x in skipped]})
    return {"n": n, "candidates": cands,
            "market_value_total": money(sum((x.market_value for x in picks), Decimal(0))),
            "gain_avoided_total": money(sum((x.gain for x in picks), Decimal(0))), "evidence": evidence}


def prep(h: Household) -> dict:
    tlh = tlh_candidates(h)
    reb = rebalance_trades(h, avoid={e["lot"]["ticker"] for e in tlh["lots"]})
    cash = cash_excess(h)
    roth = roth_room(h)
    don = donation_candidates(h, 2)
    opps = [
        {"key": "rebalance", "title": "Rebalance back to target", "impact_usd": reb["total_bought"],
         "impact_kind": "to move"},
        {"key": "cash_excess", "title": "Invest excess savings", "impact_usd": cash["excess"],
         "impact_kind": "idle in savings"},
        {"key": "roth_conversion", "title": "Roth conversion window", "impact_usd": roth["room"],
         "impact_kind": "convertible at 22% or less"},
        {"key": "tax_loss_harvest", "title": "Tax-loss harvesting", "impact_usd": tlh["harvestable_loss_total"],
         "impact_kind": "losses harvestable now"},
        {"key": "donate_appreciated", "title": "Gift appreciated stock to a donor-advised fund",
         "impact_usd": don["gain_avoided_total"], "impact_kind": "capital gains avoided"},
    ]
    opps = [o for o in opps if Decimal(o["impact_usd"]) > 0]
    opps.sort(key=lambda o: (-Decimal(o["impact_usd"]), o["key"]))
    out = {"household": h.name, "as_of": h.as_of.isoformat(),
           "meeting": {k: h.meeting[k] for k in ("summary", "start", "end") if k in h.meeting},
           "totals": totals(h), "allocation": allocation(h), "rebalance": reb, "tlh": tlh, "cash": cash,
           "roth": roth, "donation": don, "opportunities": opps}
    if h.warnings:
        out["warnings"] = list(h.warnings)
    return out


def strip_evidence(obj):
    """`prep()` output without evidence lists: the shape of truth.json."""
    if isinstance(obj, dict):
        return {k: strip_evidence(v) for k, v in obj.items() if k != "evidence"}
    if isinstance(obj, list):
        return [strip_evidence(v) for v in obj]
    return obj
