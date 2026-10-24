"""finance_review brain tool with a fake orch: PYTHONPATH=ml/src python -m pytest ml/tests/test_tool_finance_review.py"""

import asyncio
import datetime as dt
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from brain.finance import numbers_script as ns
from brain.tools import finance_review as fr

FIX = Path(__file__).resolve().parents[2] / "evals" / "fixtures" / "finance"
RC_TRUTH = json.loads((FIX / "receipts.truth.json").read_text())
BUDGET_TRUTH = json.loads((FIX / "budget_oct2026.truth.json").read_text())
STMT_DOC, BUDGET_DOC = "bank_statement_oct2026", "budget_oct2026"
STMT = f"{STMT_DOC}\tbank_statement_oct2026\tTable 1\tDate|Description|Amount|Balance"
BUDGET = f"{BUDGET_DOC}\tBudget\tTable 1\tCategory|Budget|Actual|Remaining"
PORTFOLIO = "portfolio\tHoldings\tTable 1\tTicker|Shares|Price|Value"
STMT_REF = ns.table_ref(table="Table 1", sheet="bank_statement_oct2026", document=STMT_DOC)
BUDGET_REF = ns.table_ref(table="Table 1", sheet="Budget", document=BUDGET_DOC)


def numbers_tsv() -> str:
    """What read_tables returns: the statement as Numbers shows it, then the budget sheet."""
    lines = (FIX / "bank_statement_oct2026.csv").read_text().strip().split("\n")
    stmt = "\n".join(ln.replace(",", "\t") for ln in lines)  # no commas inside fields in the fixture
    budget = "Category\tBudget\tActual\tRemaining\n" + "\n".join(
        f"{c}\t${v:,}\t\t" for c, v in BUDGET_TRUTH["budget"].items())
    return stmt + "\x1e" + budget


def ocr_text(e: dict) -> str:
    d = dt.date.fromisoformat(e["date"])
    total = f"{Decimal(str(e['total'])):.2f}"
    return (f"{e['merchant']}\n2020 Oregon St, Berkeley, CA 94703\n{d:%m/%d/%Y}  12:41\nITEM\nSUBTOTAL\nTAX\nTOTAL\n"
            f"{total}\n{total}\n0.00\n{total}\nVISA **** 4417\nTHANK YOU!\n")


class FakeTracer:
    def __init__(self):
        self.rpcs, self.stages, self.decisions = [], {}, []

    def rpc(self, method, params, result, ms):
        self.rpcs.append(method)

    def stage(self, name, ms):
        self.stages[name] = ms

    def decision(self, info):
        self.decisions.append(info)


class FakeServer:
    def __init__(self, docs=(STMT, BUDGET), fail=None, ocr=None):
        self.calls, self.bubbles, self.said, self.moods = [], [], [], []
        self.docs = list(docs)
        self.fail = fail or {}
        self.opened = []
        self.ocr = ocr or {}

    async def rpc(self, method, params, timeout=30):
        self.calls.append((method, params))
        if method == "act":
            code = params["code"]
            kind = "list" if "repeat with d in documents" in code else "read" if "on cellText" in code else "write"
            if kind in self.fail:
                return self.fail[kind]
            out = {"list": "\n".join(self.docs), "read": numbers_tsv(), "write": "8"}[kind]
            return {"ok": True, "output": out}
        if method == "skill":
            path = params["args"]["path"]
            self.opened.append(Path(path).name)
            self.docs.insert(0, STMT if path.endswith(".csv") else BUDGET)  # opened doc comes to the front
            return {"ok": True}
        if method == "ocr":
            await asyncio.sleep(0)
            name = Path(params["path"]).name
            return {"ok": True, "text": self.ocr.get(name, ocr_text(RC_TRUTH[name])), "lines": [], "ms": 40}
        raise AssertionError(method)

    async def say(self, text):
        self.said.append(text)

    async def ui(self, mood, bubble=None):
        self.moods.append(mood)
        if bubble:
            self.bubbles.append(bubble)


class FakeOrch:
    def __init__(self, server):
        self.server, self.tracer = server, FakeTracer()


@pytest.fixture
def finance_dir(tmp_path, monkeypatch):
    shutil.copy(FIX / "bank_statement_oct2026.csv", tmp_path)
    shutil.copy(FIX / "budget_oct2026.xlsx", tmp_path)
    shutil.copytree(FIX / "receipts", tmp_path / "Receipts")
    monkeypatch.setenv("MUSELET_FINANCE_DIR", str(tmp_path))
    monkeypatch.setattr(fr, "SHOW_PAUSE_S", 0)
    return tmp_path


def run(server, task=None, **kw):
    orch = FakeOrch(server)
    args = {} if task is None else {"task": task}
    return asyncio.run(fr.run(orch, args, "categorize my October transactions", **kw)), orch


def scripts(server):
    return [p["code"] for m, p in server.calls if m == "act"]


def test_all_rpc_sequence_bubbles_and_outcome(finance_dir):
    srv = FakeServer()
    outcome, orch = run(srv)
    assert outcome == "ok"
    methods = [m for m, _ in srv.calls]
    assert methods.count("ocr") == 8 and "skill" not in methods
    assert [m for m in methods if m != "ocr"] == ["act", "act", "act"]  # list, read, write
    list_s, read_s, write_s = scripts(srv)
    assert list_s == ns.list_tables()
    assert read_s == ns.read_tables([STMT_REF, BUDGET_REF])
    assert all(p["lang"] == "applescript" and p["op"] == "script" for m, p in srv.calls if m == "act")
    assert sorted(Path(p["path"]).name for m, p in srv.calls if m == "ocr") == sorted(RC_TRUTH)
    # One write: Category column (7 rows need review), Receipt column, open duplicate red, outlier orange,
    # refunded pair green, budget Actual/Remaining (resolved only) + a "Needs review" line for the 7 rows.
    assert write_s.count("\ttell ") == 2 and f"tell {BUDGET_REF}" in write_s and f"tell {STMT_REF}" in write_s
    assert 'set value of cell 1 of column "E" to "Category"' in write_s
    assert 'set value of cell 1 of column "F" to "Receipt"' in write_s and '"Receipt 7: $16.46 vs bank $16.64"' in write_s
    cats = write_s.split("set vals to {", 1)[1].split("}", 1)[0]
    assert cats.count('"Needs review"') == 7
    assert 'set notes to {"", "", "", "", "", "", "", ""}' in write_s  # no model guess -> no category is partial
    assert "set value of cell pendRow of column \"C\" to 95.09" in write_s
    assert '"7 rows without a category (incl. $45.00 in credits)"' in write_s
    assert "repeat with r in {19, 20}\n\t\t\tset background color of row (contents of r) to {65535, 49087, 49087}" \
        in write_s
    assert "repeat with r in {86}\n\t\t\tset background color of row (contents of r) to {65535, 52428, 30840}" in write_s
    assert "repeat with r in {67, 68, 106}\n\t\t\tset background color of row (contents of r) to {52428, 65535, 52428}" \
        in write_s
    assert "set acts to {1625.00, 203.61, 347.21, 121.06, 1480.34, 42.97, 149.07, 47.91}" in write_s
    assert srv.bubbles == ["Looking for your statement in Numbers...", "Reading your statement...",
                           "Checking 120 transactions...", "Matching receipts to the statement...",
                           "7 rows need your review; marking them...", "Writing results to Numbers..."]
    assert srv.said == ["Over on Dining and Shopping; 2 duplicates (1 refunded); 1 receipt mismatch."]
    assert srv.moods[-1] == "success" and all(len(b.split()) <= 12 for b in srv.bubbles + srv.said)
    ev = orch.tracer.decisions[-1]
    assert ev["tool"] == "finance_review" and ev["complete"] is False
    assert all(f["rule"] and f["say"] for f in ev["flags"])
    assert {"finance_read", "finance_analyze", "finance_write", "finance_ocr", "finance_review"} <= set(orch.tracer.stages)


def test_needs_review_is_written_not_guessed(finance_dir):
    srv = FakeServer()
    run(srv, "categorize")
    write_s = scripts(srv)[-1]
    cats = write_s.split('set vals to {', 1)[1].split("}", 1)[0]
    assert cats.count('"Needs review"') == 7 and cats.count('"Groceries"') == 16  # 22 grocery rows - 6 Berkeley Bowl
    assert "if column count < 5 then set column count to 5" in write_s.split(f"tell {BUDGET_REF}")[1]


def test_with_decision_model_budget_is_final(finance_dir):
    def decide(text, options):
        return {"Income": 0.93} if "VENMO" in text else {"Groceries": 0.88}

    srv = FakeServer()
    outcome, orch = run(srv, "all", decide=decide)
    write_s = scripts(srv)[-1]
    acts = ", ".join(f"{Decimal(str(v)):.2f}" for v in BUDGET_TRUTH["actual"].values())
    assert outcome == "ok" and f"set acts to {{{acts}}}" in write_s
    cats = write_s.split("set vals to {", 1)[1].split("}", 1)[0]
    assert '"Needs review"' not in cats and "if pendRow > 0 then delete row pendRow" in write_s
    assert 'set notes to {"", "", "", "", "", "", "", ""}' in write_s  # clears notes from an earlier run
    assert srv.said == ["Over on Dining and Shopping; 2 duplicates (1 refunded); 1 receipt mismatch."]
    assert orch.tracer.decisions[-1]["complete"] is True


def test_low_confidence_guess_marks_exactly_that_category_partial(finance_dir):
    def decide(text, options):
        return {"Income": 0.5, "Dining": 0.5} if "VENMO" in text else {"Groceries": 0.55, "Dining": 0.45}

    srv = FakeServer()
    run(srv, "categorize", decide=decide)
    write_s = scripts(srv)[-1]
    assert 'set notes to {"", "Partial: 6 rows ($95.09) need review", "", "", "", "", "", ""}' in write_s
    assert "if pendRow > 0 then delete row pendRow" in write_s  # nothing unassigned: Venmo was guessed Income
    assert "set acts to {1625.00, 203.61," in write_s  # Groceries Actual excludes the 6 pending rows


@pytest.mark.parametrize("docs", [(BUDGET, STMT), (PORTFOLIO, BUDGET, STMT)])
def test_statement_found_by_header_not_front_document(finance_dir, docs):
    srv = FakeServer(docs=docs)
    outcome, _ = run(srv, "all")
    assert outcome == "ok" and "skill" not in [m for m, _ in srv.calls]
    assert scripts(srv)[1] == ns.read_tables([STMT_REF, BUDGET_REF])


def test_only_budget_open_opens_statement(finance_dir):
    srv = FakeServer(docs=(PORTFOLIO, BUDGET))
    outcome, _ = run(srv, "receipts")
    assert outcome == "ok"
    assert [p for m, p in srv.calls if m == "skill"] == [
        {"name": "open_file", "args": {"path": str(finance_dir / "bank_statement_oct2026.csv")}}]
    assert scripts(srv)[2] == ns.read_tables([STMT_REF, BUDGET_REF])  # list, list after open, read


def test_unreadable_receipt_is_reported(finance_dir):
    srv = FakeServer(ocr={"receipt_08.png": "~~ 4 ~~\n"})
    outcome, orch = run(srv, "receipts")
    assert outcome == "ok"
    assert srv.said == ["6 receipts match, 1 receipt mismatch, 1 unreadable."]
    flag = next(f for f in orch.tracer.decisions[-1]["flags"] if f["kind"] == "receipt_unreadable")
    assert flag["say"] == "Couldn't read receipt 8; check it?" and flag["detail"]["missing"] == ["merchant", "date", "total"]


def test_no_document_open_opens_statement_then_budget(finance_dir):
    srv = FakeServer(docs=())
    outcome, _ = run(srv, "categorize")
    assert outcome == "ok"
    assert [m for m, _ in srv.calls] == ["act", "skill", "act", "skill", "act", "act", "act"]
    skills = [p for m, p in srv.calls if m == "skill"]
    assert skills == [{"name": "open_file", "args": {"path": str(finance_dir / "bank_statement_oct2026.csv")}},
                      {"name": "open_file", "args": {"path": str(finance_dir / "budget_oct2026.xlsx")}}]
    assert srv.bubbles[:3] == ["Looking for your statement in Numbers...", "Opening your bank statement...",
                               "Opening your budget..."]
    assert srv.said == ["Categorized 113 rows; 7 need review."]


def test_duplicates_task_only_highlights(finance_dir):
    srv = FakeServer(docs=(STMT,))
    outcome, _ = run(srv, "duplicates")
    assert outcome == "ok" and [m for m, _ in srv.calls] == ["act", "act", "act"]
    read_s, write_s = scripts(srv)[1:]
    assert read_s == ns.read_tables([STMT_REF])  # budget comes from the file on disk
    assert write_s.count("\ttell ") == 1 and "Category" not in write_s and "background color" in write_s
    assert srv.said == ["2 duplicates (1 refunded)."]


def test_receipts_task_writes_receipt_column_only(finance_dir):
    srv = FakeServer()
    outcome, _ = run(srv, "receipts")
    assert outcome == "ok" and [m for m, _ in srv.calls if m != "ocr"] == ["act", "act", "act"]
    write_s = scripts(srv)[-1]
    assert 'column "E" to "Receipt"' in write_s and "Category" not in write_s and "background" not in write_s
    assert srv.said == ["6 receipts match, 1 receipt mismatch, 1 unmatched."]


def test_ocr_runs_concurrently(finance_dir):
    srv = FakeServer()
    started, release = [], asyncio.Event()
    base = srv.rpc

    async def rpc(method, params, timeout=30):
        if method == "ocr":
            started.append(params["path"])
            if len(started) == 8:
                release.set()
            await asyncio.wait_for(release.wait(), 2)  # deadlocks unless all 8 are in flight together
        return await base(method, params, timeout)

    srv.rpc = rpc
    outcome, _ = run(srv, "receipts")
    assert outcome == "ok" and len(started) == 8


def test_read_failure_says_why(finance_dir):
    srv = FakeServer(fail={"read": {"ok": False, "error": "Numbers got an error: Can't get table 1."}})
    outcome, orch = run(srv, "all")
    assert outcome == "failed" and srv.said == ["Couldn't read the statement"] and srv.moods[-1] == "confused"
    assert "Can't get table 1" in orch.tracer.decisions[-1]["error"]


def test_rpc_timeout_fails_cleanly(finance_dir):
    srv = FakeServer()

    async def rpc(method, params, timeout=30):
        raise RuntimeError("rpc act timed out")

    srv.rpc = rpc
    outcome, _ = run(srv, "duplicates")
    assert outcome == "failed" and srv.said == ["Couldn't reach Numbers"]


def test_missing_receipts_folder(finance_dir):
    shutil.rmtree(finance_dir / "Receipts")
    srv = FakeServer()
    outcome, _ = run(srv, "receipts")
    assert outcome == "failed" and srv.said == ["Couldn't find any receipts"]


def test_cancellation_propagates(finance_dir):
    srv = FakeServer()
    base = srv.rpc

    async def rpc(method, params, timeout=30):
        if method == "act" and "on cellText" in params["code"]:
            raise asyncio.CancelledError
        return await base(method, params, timeout)

    srv.rpc = rpc
    with pytest.raises(asyncio.CancelledError):
        run(srv, "all")


@pytest.mark.parametrize("task", fr.TASKS)
def test_summary_sentence_is_short(finance_dir, task):
    srv = FakeServer()
    run(srv, task)
    assert len(srv.said) == 1 and len(srv.said[0].split()) <= 12
