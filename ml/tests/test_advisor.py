"""Advisor mode: engine == truth.json to the cent, evidence attached, brief and AppleScript goldens.

Run: PYTHONPATH=ml/src python -m pytest ml/tests/test_advisor.py
Regenerate goldens after an intended change: UPDATE_GOLDEN=1 PYTHONPATH=ml/src python -m pytest ml/tests/test_advisor.py
"""

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from brain import advisor
from brain.advisor import brief, core, scripts

ROOT = Path(__file__).resolve().parents[2]
HOUSEHOLD = ROOT / "evals/fixtures/advisor/henderson"
GOLDEN = Path(__file__).resolve().parent / "golden/advisor"
TRUTH = json.loads((HOUSEHOLD / "truth.json").read_text())


@pytest.fixture(scope="module")
def h():
    return advisor.load_household(HOUSEHOLD)


@pytest.fixture(scope="module")
def prep(h):
    return advisor.prep(h)


def run_cli(*args):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "ml/src")}
    out = subprocess.run([sys.executable, "-m", "brain.advisor", *args], capture_output=True, text=True,
                         env=env, check=True, cwd=ROOT)
    return out.stdout


def test_cli_prep_equals_truth_to_the_cent():
    out = json.loads(run_cli("prep", "--household", "evals/fixtures/advisor/henderson"))
    assert advisor.strip_evidence(out["prep"]) == TRUTH
    assert out["brief_markdown"].startswith("# Henderson — annual review prep")


def test_no_load_warnings(h):
    assert h.warnings == []


@pytest.mark.parametrize("key,fn", [
    ("totals", advisor.totals), ("allocation", advisor.allocation), ("rebalance", advisor.rebalance_trades),
    ("tlh", advisor.tlh_candidates), ("cash", advisor.cash_excess), ("roth", advisor.roth_room),
    ("donation", advisor.donation_candidates),
])
def test_each_function_matches_truth_and_has_evidence(h, key, fn):
    out = fn(h)
    assert advisor.strip_evidence(out) == TRUTH[key]
    assert out["evidence"] and all("rule" in e for e in out["evidence"])


def test_planted_facts():
    cls = {c["asset_class"]: c for c in TRUTH["allocation"]["classes"]}
    assert TRUTH["allocation"]["groups"][0]["out_of_band"] and cls["Bonds"]["out_of_band"]
    assert all(t["account"] != "Joint taxable brokerage" for t in TRUTH["rebalance"]["trades"])
    assert TRUTH["rebalance"]["realized_gain"] == "0.00"
    assert set(TRUTH["rebalance"]["post_trade_pct"].values()) <= {"40.00", "20.00", "35.00", "5.00"}
    lots = TRUTH["tlh"]["lots"]
    assert [e["status"] for e in lots].count("wash_sale_blocked") == 1 and len(lots) == 3
    ok_total = sum(Decimal(e["loss"]) for e in lots if e["status"] == "ok")
    assert TRUTH["tlh"]["harvestable_loss_total"] == f"{ok_total:.2f}"
    c = TRUTH["cash"]
    assert Decimal(c["excess"]) == Decimal(c["savings"]) - 6 * Decimal("8000") - Decimal("120000")
    assert TRUTH["roth"]["bracket_top"] == "211400.00" and TRUTH["roth"]["room"] == "61400.00"
    assert [d["lot"]["ticker"] for d in TRUTH["donation"]["candidates"]] == ["AAPL", "MSFT"]


def test_rebalance_never_buys_a_harvested_ticker(prep):
    harvested = {e["lot"]["ticker"] for e in prep["tlh"]["lots"]}
    assert not {t["ticker"] for t in prep["rebalance"]["trades"] if t["side"] == "buy"} & harvested


def test_wider_band_means_no_trades(h):
    out = advisor.rebalance_trades(h, band="10")
    assert out["trades"] == [] and out["total_bought"] == "0.00"


def test_short_wash_window_unblocks_vxus(h):
    out = advisor.tlh_candidates(h, wash_days=10)
    assert all(e["status"] == "ok" for e in out["lots"])
    assert out["harvestable_loss_total"] == "34465.00"


def test_exactly_one_year_is_short_term(h):
    out = advisor.donation_candidates(h, n=5)
    assert "PLTR" not in [c["lot"]["ticker"] for c in out["candidates"]]
    assert any("short-term" in e["rule"] for e in out["evidence"])


def test_unknown_tax_year_refuses(h):
    with pytest.raises(KeyError):
        advisor.roth_room(h, 2031)


def test_brief_sections_and_numbers(prep):
    md = advisor.brief_markdown(prep)
    heads = [line for line in md.splitlines() if line.startswith("## ")]
    assert heads == ["## Snapshot", "## Opportunities", "## Talking points", "## Proposed actions"]
    for v in ("$118,151.60", "$68,480.00", "$61,400.00", "$53,472.00", "$30,825.00", "$120,000.00", "2026-11-11"):
        assert v in md
    opp = [line for line in md.splitlines() if line[:2] in {f"{i}." for i in range(1, 10)}]
    impacts = [Decimal(o["impact_usd"]) for o in prep["opportunities"]]
    assert impacts == sorted(impacts, reverse=True) and opp


def test_phrasing_never_carries_numbers(prep):
    md = advisor.brief_markdown(prep, {"headline": "Strong year; three easy wins.", "reserves": "Keep $500k aside",
                                       "charitable": "Mention 2 funds", "bogus": "x"})
    assert "Strong year; three easy wins." in md
    assert "$500k" not in md and "2 funds" not in md
    assert brief.DEFAULT_PHRASING["reserves"] in md


def test_applescript_escaping():
    assert scripts.q('a "b" \\ c') == '"a \\"b\\" \\\\ c"'
    assert scripts.q("x\ny\tz\x07") == '"x" & linefeed & "y" & tab & "z"'
    html = advisor.brief_html('# T <&> "q"\n- **b** it\'s')
    assert html == "<h1>T &lt;&amp;&gt; &quot;q&quot;</h1><ul><li><b>b</b> it&#x27;s</li></ul>"


def _golden(name, text):
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    assert text == path.read_text()


def test_golden_numbers_highlight(prep):
    _golden("numbers_highlight.applescript", advisor.numbers_highlight_script(prep))


def test_golden_numbers_review(prep):
    _golden("numbers_review.applescript", advisor.numbers_review_script(prep))


def test_golden_notes_brief(prep):
    s = advisor.notes_brief_script(prep)
    assert s.startswith('tell application id "com.apple.Notes"') and 'folder "Clients"' in s
    _golden("notes_brief.applescript", s)


def test_golden_brief_markdown(prep):
    _golden("brief.md", advisor.brief_markdown(prep))


def test_truth_is_current_with_files():
    pytest.importorskip("openpyxl")
    sys.path.insert(0, str(HOUSEHOLD.parent))
    try:
        import generate
    finally:
        sys.path.pop(0)
    assert generate.truth() == TRUTH


@pytest.mark.parametrize("sentence,label,amount", [
    ("They want to put $120,000 down on the lake house next spring (target April 2027).",
     "lake house down payment", "120000.00"),
    ("Planning a $90k down payment on a condo for their son by June.", "condo down payment", "90000.00"),
    ("Emma starts college next fall; tuition is about $38,500 a year.", "tuition", "38500.00"),
    ("Their daughter's wedding next summer will cost $45,000.", "wedding", "45000.00"),
    ("Mark wants a new car in 2027, budget $55,000.", "car purchase", "55000.00"),
    ("Kitchen remodel planned for spring: $72,500.", "home project", "72500.00"),
    ("Expect a $1.2 million home purchase next year.", "home purchase", "1200000.00"),
    ("Keep $30,000 liquid for the tax bill due in April.", "tax bill", "30000.00"),
    ("They plan to keep $25,000 liquid for emergencies this year.", "kept liquid", "25000.00"),
])
def test_planned_expenses_from_notes(sentence, label, amount):
    """finance-13: any near-term planned expense with an amount, not one lake-house sentence."""
    got = core.planned_expenses(f"Notes\n- {sentence}\n")
    assert [(r["label"], r["amount"]) for r in got] == [(label, amount)]
    assert got[0]["quote"] == sentence


@pytest.mark.parametrize("sentence", [
    "Last year they gave $5,000 in cash to their church.",
    "They paid $40,000 tuition in 2024.",
    "Mark asked again about Roth conversions before RMDs start.",
    "The car is paid off.",
])
def test_planned_expenses_ignores_past_and_amountless(sentence):
    assert core.planned_expenses(sentence) == []


def test_cash_reserves_sum_every_planned_expense_and_profile_wins(tmp_path):
    import shutil
    d = tmp_path / "h"
    shutil.copytree(HOUSEHOLD, d)
    with open(d / "last_meeting_notes.txt", "a") as f:
        f.write("- Their daughter's wedding next summer will cost $20,000.\n")
    cash = core.cash_excess(advisor.load_household(d))
    assert cash["reserves"] == [{"label": "lake house down payment", "amount": "120000.00"},
                                {"label": "wedding", "amount": "20000.00"}]
    assert cash["reserve_total"] == "140000.00" and cash["excess"] == "48480.00"
    assert sum(1 for e in cash["evidence"] if e.get("quote")) == 2
    md = advisor.brief_markdown(advisor.prep(advisor.load_household(d)))
    assert "- Wedding: $20,000.00 kept in savings." in md
    assert "minus lake house down payment $120,000.00 minus wedding $20,000.00." in md

    prof = json.loads((d / "profile.json").read_text())
    prof["liquidity_reserves"] = [{"label": "roof", "amount": "15000", "source_quote": "roof in May"}]
    (d / "profile.json").write_text(json.dumps(prof))
    cash = core.cash_excess(advisor.load_household(d))
    assert cash["reserves"] == [{"label": "roof", "amount": "15000.00"}] and cash["excess"] == "173480.00"


def test_no_reserve_no_talking_point(tmp_path):
    import shutil
    d = tmp_path / "h"
    shutil.copytree(HOUSEHOLD, d)
    (d / "last_meeting_notes.txt").write_text("Charitable giving\n- Interested in a donor-advised fund.\n")
    p = advisor.prep(advisor.load_household(d))
    assert p["cash"]["reserves"] == [] and p["cash"]["excess"] == "188480.00"
    md = advisor.brief_markdown(p)
    assert "Lake house" not in md and "kept in savings." not in md
