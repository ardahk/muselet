"""Finance engine tests (stdlib only): PYTHONPATH=ml/src python -m pytest ml/tests/test_finance.py"""

import contextlib
import datetime as dt
import io
import json
import random
from decimal import Decimal
from pathlib import Path

import pytest
from brain import finance as fin
from brain.finance import numbers_script as ns
from brain.finance.__main__ import main as cli_main
from brain.finance.categorize import rule_category

FIX = Path(__file__).resolve().parents[2] / "evals" / "fixtures" / "finance"
STATEMENT = FIX / "bank_statement_oct2026.csv"
BUDGET_TRUTH = json.loads((FIX / "budget_oct2026.truth.json").read_text())
ST_TRUTH = json.loads((FIX / "bank_statement_oct2026.truth.json").read_text())
RC_TRUTH = json.loads((FIX / "receipts.truth.json").read_text())
CATS = list(BUDGET_TRUTH["budget"])
D = Decimal
ANSWERS = {"BERKELEY BOWL": "Groceries", "VENMO FROM SAM": "Income"}  # what the user answers to the two asks


def cents(x) -> Decimal:
    return D(str(x)).quantize(D("0.01"))


@pytest.fixture(scope="module")
def txns():
    return fin.load_statement(STATEMENT.read_text())


@pytest.fixture(scope="module")
def budget():
    return fin.load_budget(FIX / "budget_oct2026.xlsx")


def ocr_receipts():
    return [{"id": k, "merchant": v["merchant"], "date": v["date"], "total": v["total"]} for k, v in RC_TRUTH.items()]


# --- loading ---------------------------------------------------------------------------------------------

def test_load_statement(txns):
    assert len(txns) == 120 and [t.row for t in txns] == list(range(1, 121))
    assert all(isinstance(t.amount, Decimal) and isinstance(t.date, dt.date) for t in txns)
    assert fin.balance_breaks(txns) == []
    assert txns[0].balance - txns[0].amount == D("3120.55")


def test_load_statement_tsv_and_formatted_money():
    tsv = "Date\tDescription\tAmount\tBalance\n10/01/2026\tPAYROLL ACME LABS\t$2,400.00\t$2,500.00\n" \
          "10/02/2026\tTRADER JOE'S #552\t($23.10)\t$2,476.90\n"
    t = fin.load_statement(tsv)
    assert [x.amount for x in t] == [D("2400.00"), D("-23.10")]
    assert t[1].date == dt.date(2026, 10, 2) and fin.balance_breaks(t) == []


@pytest.mark.parametrize("text,want", [("$1,650.00", "1650.00"), ("(23.47)", "-23.47"), ("-0.5", "-0.50"),
                                        ("\u221264.99", "-64.99"), ("12", "12.00"), ("23.47-", "-23.47")])
def test_parse_money(text, want):
    assert fin.parse_money(text) == D(want)


def test_load_budget_all_sources(budget):
    want = {c: D(v).quantize(D("0.01")) for c, v in BUDGET_TRUTH["budget"].items()}
    assert budget == want and list(budget) == CATS
    assert fin.load_budget(FIX / "budget_oct2026.truth.json") == want
    numbers_csv = "\ufeffBudget\nCategory,Budget,Actual,Remaining\n" + "".join(
        f'{c},"${v:,}.00",,\n' for c, v in BUDGET_TRUTH["budget"].items()) + "Total,\"$2,970.00\",,\n"
    got = fin.load_budget(numbers_csv)
    assert {k: v for k, v in got.items() if k != "Total"} == want
    assert fin.load_budget([["Category", "Budget"], *[[c, v] for c, v in BUDGET_TRUTH["budget"].items()]]) == want
    assert fin.load_budget([{"Category": c, "Budget": v} for c, v in BUDGET_TRUTH["budget"].items()]) == want
    assert fin.load_budget([[c, str(v)] for c, v in BUDGET_TRUTH["budget"].items()]) == want


# --- detection -----------------------------------------------------------------------------------------

def test_duplicates_outliers_refunds_match_truth(txns):
    assert [list(p) for p in fin.find_duplicates(txns)] == ST_TRUTH["duplicates"]
    assert fin.find_outliers(txns) == ST_TRUTH["outliers"]
    assert fin.find_refunds(txns) == ST_TRUTH["refunds"]
    assert fin.weekend_charges(txns) == ST_TRUTH["weekend_charges"]
    assert json.loads(json.dumps(fin.jsonable(fin.duplicate_status(txns)))) == ST_TRUTH["duplicate_status"]


def test_refunded_duplicate_is_not_open(txns):
    st = {d["status"]: d for d in fin.duplicate_status(txns)}
    assert st["refunded"]["refund_row"] == ST_TRUTH["refunds"][0] and st["open"]["refund_row"] is None
    flags = [f for f in fin.analyze(txns, dict.fromkeys(CATS, D(100)))["flags"] if f["kind"] == "duplicate"]
    refunded = next(f for f in flags if f["detail"]["status"] == "refunded")
    assert refunded["say"] == "Charged twice: AMAZON MKTP $64.99 Oct 21, refunded Oct 28."
    assert refunded["rows"][-1] == ST_TRUTH["refunds"][0] and "refunded_by_row" in refunded["rule"]


def test_weekend_charges(txns):
    wk = fin.weekend_charges(txns)
    assert wk == [t.row for t in txns if t.amount < 0 and t.date.weekday() >= 5]
    assert ST_TRUTH["outliers"][0] in wk  # the Apple Store charge was on a Saturday


def test_duplicates_normalize_description():
    rows = "Date,Description,Amount,Balance\n2026-10-03,Uber *Trip,-12.00,88.00\n2026-10-03,UBER TRIP,-12.00,76.00\n" \
           "2026-10-04,UBER TRIP,-12.00,64.00\n"
    assert fin.find_duplicates(fin.load_statement(rows)) == [(1, 2)]


def synthetic_statement(seed: int, extra: list[tuple[int, str, int]] = ()) -> list[fin.Txn]:
    """A different month: other merchants, wide sampling ranges, no planted anomalies."""
    rng = random.Random(seed)
    spec = {
        "WHOLE FOODS MKT": (1200, 9500), "SAFEWAY #1444": (1200, 9500), "STARBUCKS STORE 123": (450, 900),
        "TAQUERIA CANCUN": (900, 2500), "DOORDASH*DASHPASS": (1800, 4200), "LYFT RIDE": (700, 5800),
        "BART CLIPPER": (250, 600), "SHELL OIL 5741": (2500, 5800), "TARGET T-2187": (800, 12000),
        "AMZN Mktp US": (800, 12000), "BEST BUY 112": (1500, 12000), "WALGREENS #3100": (1000, 4500),
    }
    rows = [(1, "PAYROLL ACME LABS", 240000), (1, "RENT OAKLAND PROPERTIES", -165000),
            (15, "PAYROLL ACME LABS", 240000), (rng.randint(1, 30), "PG&E WEB ONLINE", -rng.randint(6000, 11000)),
            (rng.randint(1, 30), "NETFLIX.COM", -1549), (rng.randint(1, 30), "SPOTIFY USA", -1199)]
    names = list(spec)
    seen = set()
    while len(rows) < 120 - len(extra):
        m = rng.choice(names)
        r = (rng.randint(1, 30), m, -rng.randint(*spec[m]))
        if (r[0], r[1]) not in seen:
            seen.add((r[0], r[1]))
            rows.append(r)
    rows += list(extra)
    rows.sort(key=lambda r: r[0])
    bal, out = 100000, ["Date,Description,Amount,Balance"]
    for d, m, c in rows:
        bal += c
        out.append(f"2026-11-{d:02d},{m},{c / 100:.2f},{bal / 100:.2f}")
    return fin.load_statement("\n".join(out) + "\n")


@pytest.mark.parametrize("seed", range(1, 31))
def test_outliers_none_on_synthetic_statements(seed):
    t = synthetic_statement(seed)
    assert fin.find_outliers(t) == []
    assert fin.find_duplicates(t) == []
    assert fin.find_refunds(t) == []


def test_outlier_found_on_synthetic_statement_with_planted_charge():
    t = synthetic_statement(7, extra=[(20, "BEST BUY 112", -184999)])
    assert [r.description for r in t if r.row in fin.find_outliers(t)] == ["BEST BUY 112"]


def test_refund_by_reversal_without_refund_word():
    text = "Date,Description,Amount,Balance\n2026-10-02,TARGET T-2187,-42.10,57.90\n" \
           "2026-10-06,TARGET T-2187,42.10,100.00\n2026-10-07,VENMO FROM SAM,45.00,145.00\n" \
           "2026-10-08,IRS TREAS 310 TAX REFUND,80.00,225.00\n"
    t = fin.load_statement(text)
    assert fin.find_refunds(t) == [2]
    cats = fin.categorize(t, CATS)
    # A P2P credit is not assumed to be income (finance-12); a tax refund is income, not a spending refund.
    assert cats[2] == ("Shopping", 1.0, "rule") and cats[3] == (fin.UNCATEGORIZED, 0.0, "ask")
    assert cats[4] == ("Income", 1.0, "rule")
    assert fin.category_spend(t, cats) == {"Shopping": D("0.00")}
    probs = {}
    fin.categorize(t, CATS, decide=lambda text, opts: probs.setdefault(text, opts) and {"Income": 0.9})
    assert [o for o in probs.values()] == [["Income", *CATS]]


# --- categorization ----------------------------------------------------------------------------------------

def rules_only_accuracy(txns):
    truth = {r["row"]: r["category"] for r in ST_TRUTH["rows"]}
    cats = fin.categorize(txns, CATS)
    ruled = [r for r, (_, _, s) in cats.items() if s == "rule"]
    correct = sum(cats[r][0] == truth[r] for r in ruled)
    return cats, len(ruled), correct


def test_categorize_rules_only_accuracy(txns):
    cats, n_rule, correct = rules_only_accuracy(txns)
    acc_all, coverage = correct / len(txns), n_rule / len(txns)
    print(f"\nrules-only: coverage {n_rule}/120 = {coverage:.1%}, accuracy on ruled rows {correct}/{n_rule}, "
          f"overall {acc_all:.1%}")
    assert correct == n_rule  # rules never guess wrong
    assert coverage >= 0.9
    asks = {txns[r - 1].description for r, (_, _, s) in cats.items() if s == "ask"}
    assert asks == {"BERKELEY BOWL", "VENMO FROM SAM"}  # unknown grocer + a P2P credit -> escalate
    assert all(c == (fin.UNCATEGORIZED, 0.0, "ask") for c in cats.values() if c[2] == "ask")


def test_categorize_with_decision_model(txns):
    calls = []

    def decide(text, options):
        calls.append(text)
        if "VENMO" in text:
            assert options == ["Income", *CATS] and "credit" in text
            return {"Income": 0.91, "Dining": 0.09}
        assert options == CATS and "BERKELEY BOWL" in text
        return {"Groceries": 0.82, "Dining": 0.12, "Shopping": 0.06}

    truth = {r["row"]: r["category"] for r in ST_TRUTH["rows"]}
    cats = fin.categorize(txns, CATS, decide=decide)
    assert len(calls) == 2  # once per unknown merchant, not per row
    assert all(cats[r][0] == truth[r] for r in cats)  # 120/120
    assert {s for c, p, s in cats.values()} == {"rule", "model"}
    assert {p for c, p, s in cats.values() if s == "model"} == {0.82, 0.91}


def test_categorize_low_confidence_asks(txns):
    cats = fin.categorize(txns, CATS, decide=lambda text, opts: {"Groceries": 0.55, "Dining": 0.45})
    bowl = [c for t, c in zip(txns, cats.values()) if t.description == "BERKELEY BOWL"]
    assert bowl and all(c == ("Groceries", 0.55, "ask") for c in bowl)


def test_user_rules_resolve_asks(txns):
    cats = fin.categorize(txns, CATS, user_rules={"Berkeley Bowl": "Groceries", "venmo from sam": "Income"})
    assert all(s == "rule" for _, _, s in cats.values())


@pytest.mark.parametrize("desc,cat", [
    ("UBER EATS PENDING", "Dining"), ("UBER *TRIP HELP.UBER.COM", "Transport"), ("APPLE.COM/BILL ICLOUD", "Subscriptions"),
    ("APPLE STORE #R123", "Shopping"), ("AMAZON PRIME*2K4", "Subscriptions"), ("AMZN Mktp US*1A2B", "Shopping"),
    ("SQ *PHILZ COFFEE", "Dining"), ("CHEVRON 0091234", "Transport"), ("WALGREENS #3100", "Health"),
    ("PG&E WEB ONLINE", "Utilities"), ("WHOLEFDS BKL 10234", "Groceries"), ("CORNER BOOKSHOP", None),
    # finance-11: ambiguous single words, ties, COSTCO
    ("RENT THE RUNWAY", None), ("RENT", "Rent"), ("RENT PAYMENT OCT", "Rent"), ("KEY LIME CAFE", "Dining"),
    ("LIME*RIDE", "Transport"), ("COSTCO WHSE #123", "Groceries"), ("COSTCO GAS #123", "Transport"),
    ("SHELL SERVICE STATION", "Transport"), ("SHELL 57444", "Transport"), ("SHELL SHACK", None),
    ("PARKMOBILE", "Transport"), ("TOLLHOUSE BAKERY", "Dining"), ("TRANSFER FROM SAVINGS", None),
])
def test_rule_table_is_general(desc, cat):
    assert rule_category(desc) == cat


# --- budget ------------------------------------------------------------------------------------------------

def test_category_spend_and_budget_match_truth(txns, budget):
    cats = fin.categorize(txns, CATS, user_rules=ANSWERS)
    spend = fin.category_spend(txns, cats)
    assert spend == {c: cents(v) for c, v in ST_TRUTH["category_spend"].items()}
    rep = fin.budget_report(spend, budget)
    assert rep["actual"] == {c: cents(v) for c, v in BUDGET_TRUTH["actual"].items()}
    assert rep["remaining"] == {c: cents(v) for c, v in BUDGET_TRUTH["remaining"].items()}
    assert rep["over_budget"] == BUDGET_TRUTH["over_budget"] == ["Dining", "Shopping"]
    assert "unbudgeted" not in rep and "pending" not in rep


def test_unresolved_rows_are_pending_not_guessed(txns, budget):
    # finance-9: a low-confidence guess must not count toward Groceries; the budget says what is pending.
    cats = fin.categorize(txns, CATS, decide=lambda text, opts: {"Groceries": 0.55, "Income": 0.4})
    spend = fin.category_spend(txns, cats)
    bowl = sum(-t.amount for t in txns if t.description == "BERKELEY BOWL")
    assert spend["Groceries"] == cents(ST_TRUTH["category_spend"]["Groceries"]) - bowl
    pend = fin.pending(txns, cats)
    assert pend["debits"] == bowl and pend["credits"] == D("45.00") and len(pend["rows"]) == 7
    rep = fin.budget_report(spend, budget, pend)
    assert rep["over_budget"] == ["Dining", "Shopping"]  # certain: pending debits only add spend
    # Categories that unresolved debits could push over budget (remaining < pending debits).
    assert rep["needs_review"] == [c for c in CATS if D(0) <= rep["remaining"][c] < bowl]
    assert "Groceries" not in rep["needs_review"] and "Rent" in rep["needs_review"]


# --- receipts ----------------------------------------------------------------------------------------------

def test_reconcile_matches_truth(txns):
    got = fin.reconcile_receipts(ocr_receipts(), txns)
    assert json.loads(json.dumps(fin.jsonable(got))) == RC_TRUTH


def stmt(*rows):
    out, bal = ["Date,Description,Amount,Balance"], D("500.00")
    for d, m, a in rows:
        bal += D(a)
        out.append(f"{d},{m},{a},{bal}")
    return fin.load_statement("\n".join(out) + "\n")


def test_reconcile_edge_cases():
    t = stmt(("2026-10-05", "TRADER JOE'S #552", "-18.40"), ("2026-10-05", "TRADER JOE'S #552", "-7.15"),
             ("2026-10-08", "SQ *BLUE BOTTLE COFFEE", "-6.25"), ("2026-10-09", "CHIPOTLE 1234", "-14.20"),
             ("2026-10-10", "SAFEWAY #1444", "-30.00"), ("2026-10-12", "PEET'S COFFEE", "-5.10"))
    rec = fin.reconcile_receipts([
        {"id": "a", "merchant": "Trader Joe's", "date": "10/05/2026", "total": "7.15"},  # same merchant twice/day
        {"id": "b", "merchant": "TRADER JOES", "date": "2026-10-05", "total": 18.4},
        {"id": "c", "merchant": "Blue Bottle Coffee", "date": "2026-10-07", "total": "6.25"},  # posted a day later
        {"id": "d", "merchant": "CHIPOTLE", "date": "2026-10-09", "total": "14.35"},  # not one adjacent swap
        {"id": "e", "merchant": "SAFEWAY", "date": "2026-10-09", "total": "30.00"},  # posted +1, exact
        {"id": "f", "merchant": "PHILZ COFFEE", "date": "2026-10-12", "total": "5.10"},  # other coffee shop
    ], t)
    assert (rec["a"]["status"], rec["a"]["match_row"]) == ("matched", 2)
    assert (rec["b"]["status"], rec["b"]["match_row"]) == ("matched", 1)
    assert rec["c"] | {} == {**rec["c"], "status": "matched", "match_row": 3, "posting_delay_days": 1}
    assert rec["d"]["status"] == "amount_mismatch" and rec["d"]["transposed_digits"] is False  # 15c apart
    assert rec["d"]["statement_amount"] == D("14.20")
    assert (rec["e"]["status"], rec["e"]["posting_delay_days"]) == ("matched", 1)
    assert rec["f"] == {"match_row": None, "status": "no_match", "total": D("5.10"), "merchant": "PHILZ COFFEE",
                        "date": "2026-10-12"}


def test_reconcile_mismatch_is_bounded_and_survives_posting_delay():
    # finance-10: far-off amounts are no_match (with a hint); a tip that posts the next day is a mismatch.
    t = stmt(("2026-10-05", "SAFEWAY #1444", "-12.00"), ("2026-10-06", "CHIPOTLE 1234", "-18.00"),
             ("2026-10-07", "SAFEWAY FUEL 1444", "-40.00"), ("2026-10-08", "UBER EATS", "-31.00"))
    rec = fin.reconcile_receipts([
        {"id": "a", "merchant": "SAFEWAY", "date": "2026-10-05", "total": "5.00"},
        {"id": "b", "merchant": "CHIPOTLE", "date": "2026-10-05", "total": "15.00"},
        {"id": "c", "merchant": "SAFEWAY", "date": "2026-10-07", "total": "40.00"},
        {"id": "d", "merchant": "UBER", "date": "2026-10-08", "total": "31.00"},
    ], t)
    assert rec["a"]["status"] == "no_match" and rec["a"]["nearest"] == {"row": 1, "date": "2026-10-05",
                                                                        "amount": D("12.00")}
    assert rec["b"] | {} == {**rec["b"], "status": "amount_mismatch", "match_row": 2, "posting_delay_days": 1,
                             "statement_amount": D("18.00"), "transposed_digits": False}
    assert rec["c"]["status"] == "no_match" and rec["c"]["nearest"]["row"] == 1  # SAFEWAY FUEL is not SAFEWAY
    assert rec["d"]["status"] == "no_match"


def test_receipt_8_stays_no_match_next_to_other_coffee_shops(txns):
    rec = fin.reconcile_receipts(ocr_receipts(), txns)["receipt_08.png"]
    assert rec["status"] == "no_match" and "nearest" not in rec


@pytest.mark.parametrize("a,b,want", [("16.46", "16.64", True), ("12.30", "13.20", True), ("51.2", "15.20", True),
                                      ("1.05", "10.5", False), ("14.02", "14.20", True), ("9.81", "9.81", False),
                                      ("14.35", "14.20", False), ("12.34", "14.32", False),
                                      ("123.45", "132.45", True), ("12.34", "21.43", False)])
def test_is_adjacent_swap(a, b, want):
    assert fin.is_adjacent_swap(a, b) is want


@pytest.mark.parametrize("a,b,want", [("TRADER JOE'S", "Trader Joes #552", True), ("SQ *PHILZ COFFEE", "Philz Coffee", True),
                                      ("PHILZ COFFEE", "PEET'S COFFEE", False), ("PHILZ COFFEE", "BLUE BOTTLE COFFEE", False),
                                      ("CVS/PHARMACY #9921", "CVS PHARMACY", True), ("APPLE STORE", "APPLE ICLOUD", False),
                                      ("SAFEWAY", "SAFEWAY FUEL 1444", False), ("APPLE", "APPLE ICLOUD", False),
                                      ("UBER", "UBER EATS", False), ("Blue Bottle Coffee Co.", "BLUE BOTTLE COFFEE", True),
                                      ("sweetgreen Berkeley", "SWEETGREEN", True), ("Target T-2187", "TARGET", True),
                                      ("TRADER JOFS", "TRADER JOE'S", True), ("COFFEE", "PEET'S COFFEE", False),
                                      ("Safeway Store #1444", "SAFEWAY", True), ("PEETS", "PHILZ", False)])
def test_merchant_match(a, b, want):
    assert fin.merchant_match(a, b) is want


# --- report + CLI ------------------------------------------------------------------------------------------

def run_cli(*args) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli_main(list(args)) == 0
    return json.loads(buf.getvalue())


@pytest.mark.parametrize("budget_file", ["budget_oct2026.truth.json", "budget_oct2026.xlsx"])
def test_cli_report_equals_truth(tmp_path, budget_file):
    (tmp_path / "r.json").write_text(json.dumps(ocr_receipts()))
    (tmp_path / "rules.json").write_text(json.dumps(ANSWERS))
    rep = run_cli("analyze", "--statement", str(STATEMENT), "--budget", str(FIX / budget_file),
                  "--receipts", str(tmp_path / "r.json"), "--rules", str(tmp_path / "rules.json"))
    for k in ("duplicates", "duplicate_status", "outliers", "refunds", "weekend_charges", "category_spend"):
        assert rep[k] == ST_TRUTH[k], k
    for k in ("total_income", "total_spend", "net", "opening_balance", "closing_balance"):
        assert cents(rep["statement"][k]) == cents(ST_TRUTH[k]), k
    assert rep["statement"]["balance_ok"] is True
    assert [{"row": r["row"], "category": r["category"]} for r in rep["rows"]] == ST_TRUTH["rows"]
    for k in ("budget", "actual", "remaining", "over_budget"):
        assert rep["budget"][k] == BUDGET_TRUTH[k], k
    assert rep["receipts"] == RC_TRUTH
    assert rep["complete"] is True and rep["ask"] == []


def test_cli_without_answers_escalates(tmp_path):
    rep = run_cli("analyze", "--statement", str(STATEMENT), "--budget", str(FIX / "budget_oct2026.xlsx"), "--scripts")
    assert rep["complete"] is False
    assert sorted(a["description"] for a in rep["ask"]) == ["BERKELEY BOWL", "VENMO FROM SAM"]
    venmo = next(a for a in rep["ask"] if a["description"] == "VENMO FROM SAM")
    assert venmo["options"][0] == "Income"
    assert "unbudgeted" not in rep["budget"] and len(rep["budget"]["pending"]["rows"]) == 7
    assert cents(rep["statement"]["total_income"]) == cents(ST_TRUTH["total_income"]) - D("45.00")
    assert rep["statement"]["balance_ok"] is True
    assert set(rep["numbers_scripts"]) == {"highlight", "write_budget", "summary"}
    assert all(s.startswith('tell application id "com.apple.Numbers"') for s in rep["numbers_scripts"].values())
    wb = rep["numbers_scripts"]["write_budget"]
    assert 'set value of cell 1 of column "E" to "Note"' in wb and '"Needs review"' in wb


def test_every_flag_carries_evidence(txns, budget):
    rep = fin.analyze(txns, budget, ocr_receipts())
    kinds = {f["kind"] for f in rep["flags"]}
    assert {"duplicate", "outlier", "refund", "weekend", "over_budget", "ask_category", "receipt_matched",
            "receipt_amount_mismatch", "receipt_no_match", "budget_pending"} <= kinds
    for f in rep["flags"]:
        assert f["rule"] and f["say"] and len(f["say"].split()) <= 12, f
        assert f["rows"] or f["kind"] == "receipt_no_match", f
    out = next(f for f in rep["flags"] if f["kind"] == "outlier")
    assert out["rows"] == ST_TRUTH["outliers"] and out["detail"]["z"] >= D("3.5")
    mm = next(f for f in rep["flags"] if f["kind"] == "receipt_amount_mismatch")
    assert "swap" in mm["rule"] and "digits swapped" in mm["say"]


# --- Numbers AppleScript (golden strings; no Mac here) -------------------------------------------------------

def test_quote_escapes():
    assert ns.q('say "hi"\\now\n\tx') == '"say \\"hi\\"\\\\now\\n\\tx"'
    assert ns.lit(D("-97.21")) == "-97.21" and ns.lit(None) == '""' and ns.lit("TRADER JOE'S") == '"TRADER JOE\'S"'


def test_read_table_tsv_golden():
    assert ns.read_table_tsv("A1:D121", table="Statement", sheet="Oct") == '''tell application id "com.apple.Numbers"
	tell table "Statement" of sheet "Oct" of document 1
		set r to range "A1:D121"
		set ncols to count of columns of r
		set vals to formatted value of cells of r
	end tell
end tell
set out to {}
set rowVals to {}
repeat with v in vals
	set v to contents of v
	if v is missing value then set v to ""
	set end of rowVals to (v as text)
	if (count of rowVals) = ncols then
		set end of out to rowVals
		set rowVals to {}
	end if
end repeat
set lines_ to {}
set AppleScript's text item delimiters to tab
repeat with rv in out
	set end of lines_ to ((contents of rv) as text)
end repeat
set AppleScript's text item delimiters to linefeed
set tsv to lines_ as text
set AppleScript's text item delimiters to ""
return tsv
'''
    assert "set r to cell range" in ns.read_table_tsv()
    assert "tell table 1 of active sheet of document 1" in ns.read_table_tsv()


def test_write_column_golden():
    assert ns.write_column("E", ["Dining", "Say \"x\"", None, D("1.50")], table="T", document="Oct.numbers") == \
        '''tell application id "com.apple.Numbers"
	tell table "T" of active sheet of document "Oct.numbers"
		set vals to {"Dining", "Say \\"x\\"", "", 1.50}
		repeat with i from 1 to count of vals
			set value of cell (i + 1) of column "E" to item i of vals
		end repeat
	end tell
end tell
'''


def test_write_budget_golden():
    s = ns.write_budget({"Rent": D("1625.00"), "Dining": D("347.21")}, {"Rent": D("25.00"), "Dining": D("-97.21")},
                        table="Budget", sheet="Budget")
    assert s == '''tell application id "com.apple.Numbers"
	tell table "Budget" of sheet "Budget" of document 1
		set names to {"Rent", "Dining"}
		set acts to {1625.00, 347.21}
		set rems to {25.00, -97.21}
		set cats to value of cells of column "A"
		set written to 0
		repeat with r from 1 to count of cats
			set c to item r of cats
			if c is not missing value then
				repeat with k from 1 to count of names
					if (c as text) is (item k of names) then
						set value of cell r of column "C" to item k of acts
						set value of cell r of column "D" to item k of rems
						set written to written + 1
					end if
				end repeat
			end if
		end repeat
		return written
	end tell
end tell
'''
    f = ns.write_budget({"Rent": D("1")}, {"Rent": D("0")}, remaining_formula=True)
    assert 'set value of cell r of column "D" to ("=B" & r & "-C" & r)' in f


def test_highlight_golden():
    assert ns.highlight_flags([(18, 19)], [85], [5, 18, 85]) == '''tell application id "com.apple.Numbers"
	tell table 1 of active sheet of document 1
		repeat with r in {6}
			set background color of row (contents of r) to {61166, 61166, 65535}
		end repeat
		repeat with r in {19, 20}
			set background color of row (contents of r) to {65535, 49087, 49087}
		end repeat
		repeat with r in {86}
			set background color of row (contents of r) to {65535, 52428, 30840}
		end repeat
	end tell
end tell
'''


def test_summary_table_golden():
    assert ns.add_summary_table([["Item", "Value"], ["Net", D("732.74")], ["Note"]], name='Sum "1"') == \
        '''tell application id "com.apple.Numbers"
	tell active sheet of document 1
		if exists table "Sum \\"1\\"" then delete table "Sum \\"1\\""
		set t to make new table with properties {name:"Sum \\"1\\"", row count:3, column count:2, header row count:1, header column count:0}
		set grid to {{"Item", "Value"}, {"Net", 732.74}, {"Note", ""}}
		tell t
			repeat with i from 1 to count of grid
				set rowVals to item i of grid
				repeat with j from 1 to count of rowVals
					set value of cell j of row i to item j of rowVals
				end repeat
			end repeat
		end tell
	end tell
end tell
'''


def test_summary_rows_from_report(txns, budget):
    rep = fin.analyze(txns, budget, ocr_receipts(), user_rules=ANSWERS)
    rows = {r[0]: r[1] for r in ns.summary_rows(rep)}
    assert rows["Duplicate charges"] == "rows 18 & 19; rows 66 & 67 (refunded, row 105)"
    assert rows["Weekend charges"] == 32 and "Needs review" not in rows
    assert rows["Net"] == D("732.74") and rows["Over budget"] == "Dining, Shopping"
    assert rows["Receipts matched"] == 6 and rows["Receipts amount mismatch"] == 1 and rows["Receipts no match"] == 1
