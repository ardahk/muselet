"""Brain tool `finance_review` (catalog executor "brain"; contract in cloud/tools_interface.md).

Reads the bank statement from the front Numbers document, runs the deterministic `brain.finance` engine,
writes the results back (Category column, highlights, budget Actual/Remaining) and reconciles receipt images
OCR'd on the Mac. The LLM never computes or matches anything here; `decide` (the on-device decision model) is
only consulted for merchants the keyword rules don't know, and rows it is unsure about stay "Needs review".

Script calls: list every open table with its header row, one read of the statement + budget tables, one write
of everything (plus `open_file` when the statement or budget is not open yet). The statement and the budget are
found by their headers (Date/Description/Amount, Category/Budget) or the statement's file name, never by which
document happens to be in front. Receipt OCR runs concurrently with the Numbers read.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from brain.finance import numbers_script as ns
from brain.finance.categorize import Decide
from brain.finance.evidence import receipt_label, usd
from brain.finance.receipts import parse_receipt_text
from brain.finance.report import NEEDS_REVIEW, analyze, jsonable
from brain.finance.statement import load_budget, load_statement

TASKS = ("categorize", "duplicates", "receipts", "over_budget", "all")
STATEMENT_FILE = "bank_statement_oct2026.csv"
BUDGET_FILE = "budget_oct2026.xlsx"
RECEIPTS_DIR = "Receipts"
STATEMENT_HEADERS = frozenset({"date", "description", "amount"})
BUDGET_HEADERS = frozenset({"category", "budget"})
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".heic", ".tiff", ".pdf")
# Numbers opens a document asynchronously: after `open_file`, poll the open tables until the one we need exists.
POLL_S = 0.15
POLL_TIMEOUT_S = 4.0


def finance_dir() -> Path:
    return Path(os.environ.get("MUSELET_FINANCE_DIR", Path.home() / "Documents" / "Finance")).expanduser()


class ToolError(Exception):
    def __init__(self, say: str, raw: str):
        super().__init__(raw)
        self.say, self.raw = say, raw


async def _rpc(orch, method: str, params: dict, fail_say: str, timeout: float = 30) -> dict:
    t = time.perf_counter()
    try:
        res = await orch.server.rpc(method, params, timeout=timeout)
    except RuntimeError as e:
        orch.tracer.rpc(method, params, {"error": str(e)}, (time.perf_counter() - t) * 1000)
        raise ToolError(fail_say, str(e)) from None
    orch.tracer.rpc(method, params, res, (time.perf_counter() - t) * 1000)
    if not isinstance(res, dict) or not res.get("ok", False):
        raise ToolError(fail_say, str(res.get("error") if isinstance(res, dict) else res))
    return res


async def _script(orch, code: str, fail_say: str) -> str:
    res = await _rpc(orch, "act", {"op": "script", "lang": "applescript", "code": code}, fail_say)
    return str(res.get("output") or "")


def _tables(output: str) -> list[dict]:
    """list_tables output -> [{document, sheet, table, header}] (front document first)."""
    out = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0]:
            header = parts[3].split("|") if len(parts) > 3 else []
            out.append({"document": parts[0], "sheet": parts[1], "table": parts[2], "header": header})
    return out


def _has(t: dict, need: frozenset) -> bool:
    return need <= {h.strip().lower() for h in t["header"]}


def find_statement(tables: list[dict]) -> dict | None:
    """The table whose header has Date/Description/Amount; else the first table of a document named like the
    statement file. Never just the front document (it may be the budget or another client's portfolio)."""
    hit = next((t for t in tables if _has(t, STATEMENT_HEADERS)), None)
    stem = Path(STATEMENT_FILE).stem.lower()
    return hit or next((t for t in tables if t["document"].lower().removesuffix(".csv") == stem), None)


def find_budget(tables: list[dict]) -> dict | None:
    return next((t for t in tables if _has(t, BUDGET_HEADERS)), None)


def _ref(t: dict) -> str:
    return ns.table_ref(table=t["table"], sheet=t["sheet"], document=t["document"])


class Steps:
    """Wall time of each step into the trace as `finance_<step>` stages (ms)."""

    def __init__(self, orch):
        self.orch = orch

    def __call__(self, name: str):
        return _Step(self.orch, name)


class _Step:
    def __init__(self, orch, name):
        self.orch, self.name = orch, name

    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.orch.tracer.stage(f"finance_{self.name}", (time.perf_counter() - self.t) * 1000)
        return False


async def _list(orch, fail_say: str) -> list[dict]:
    return _tables(await _script(orch, ns.list_tables(), fail_say))


async def wait_for_table(orch, find, what: str, fail_say: str) -> list[dict]:
    """Poll every POLL_S for up to POLL_TIMEOUT_S until `find(tables)` matches (every sheet and table of every
    open document is listed each time). Returns the tables listing; raises ToolError on timeout."""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    polls = 0
    t0 = time.perf_counter()
    while True:
        tables = await _list(orch, fail_say)
        polls += 1
        if find(tables) is not None:
            break
        if time.monotonic() + POLL_S > deadline:
            orch.tracer.decision({"tool": "finance_review", "wait": what, "polls": polls, "found": False})
            raise ToolError(fail_say, f"no {what} table after {POLL_TIMEOUT_S:.1f} s ({polls} polls): {tables}")
        await asyncio.sleep(POLL_S)
    orch.tracer.decision({"tool": "finance_review", "wait": what, "polls": polls, "found": True,
                          "ms": round((time.perf_counter() - t0) * 1000, 1)})
    return tables


async def _open(orch, path: Path, bubble: str, fail_say: str, find, what: str) -> list[dict]:
    await orch.server.ui("acting", bubble)
    await _rpc(orch, "skill", {"name": "open_file", "args": {"path": str(path)}}, fail_say)
    return await wait_for_table(orch, find, what, fail_say)


async def _ocr_all(orch, folder: Path) -> list[dict]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT) if folder.is_dir() else []
    if not files:
        raise ToolError("Couldn't find any receipts", f"no receipt images in {folder}")
    t = time.perf_counter()
    results = await asyncio.gather(*(_rpc(orch, "ocr", {"path": str(p)}, "Couldn't read the receipts")
                                     for p in files))
    orch.tracer.stage("finance_ocr", (time.perf_counter() - t) * 1000)
    # Unreadable receipts (no merchant/date/total) stay in the list; reconcile reports them as "unreadable".
    return [{"id": p.name, **parse_receipt_text(res.get("text") or "", res.get("lines"))}
            for p, res in zip(files, results, strict=True)]


def summary_sentence(task: str, rep: dict) -> str:
    """The one closing sentence (<= 12 words), most important finding first."""
    b = rep["budget"]
    parts = []
    if task in ("all", "over_budget", "categorize"):
        over = b["over_budget"]
        if task == "categorize":
            done = len(rep["rows"]) - len(b.get("pending", {}).get("rows", []))
            parts.append(f"Categorized {done} rows")
        elif over:
            parts.append("Over on " + (" and ".join(over) if len(over) <= 2 else f"{len(over)} categories"))
        else:
            parts.append("Under budget everywhere")
    if task in ("all", "duplicates"):
        ds = rep["duplicate_status"]
        refunded = sum(d["status"] == "refunded" for d in ds)
        if not ds:
            parts.append("no duplicates")
        else:
            parts.append(f"{len(ds)} duplicate{'s' if len(ds) != 1 else ''}"
                         + (f" ({refunded} refunded)" if refunded else ""))
    if task in ("all", "receipts") and rep.get("receipts") is not None:
        st = [e["status"] for e in rep["receipts"].values()]
        mm, nm, ur = st.count("amount_mismatch"), st.count("no_match"), st.count("unreadable")
        if task == "receipts":
            parts.append(f"{st.count('matched')} receipts match")
        if mm:
            parts.append(f"{mm} receipt mismatch{'es' if mm != 1 else ''}")
        if ur:
            parts.append(f"{ur} unreadable")
        if nm:
            parts.append(f"{nm} unmatched")
        if not mm and not nm and not ur and task == "all":
            parts.append("receipts all match")
    n_review = len(b.get("pending", {}).get("rows", []))
    if n_review and task in ("all", "categorize", "over_budget"):
        parts.append(f"{n_review} need review")
    words, out = 0, []
    for p in parts:
        if words + len(p.split()) > 12:
            break
        out.append(p)
        words += len(p.split())
    s = "; ".join(out) if task != "receipts" else ", ".join(out)
    return s[0].upper() + s[1:] + "."


def receipt_column(rep: dict) -> list[str]:
    """Per statement row: which receipt matched it, and how (written next to the statement)."""
    out = {}
    for rid, e in (rep.get("receipts") or {}).items():
        if e["match_row"] is None:
            continue
        label = receipt_label(rid)
        out[e["match_row"]] = (f"{label} matches" if e["status"] == "matched"
                               else f"{label}: {usd(e['total'])} vs bank {usd(e['statement_amount'])}")
    return [out.get(r["row"], "") for r in rep["rows"]]


def write_blocks(task: str, rep: dict, header: list[str], statement_table: str, budget_table: str | None) -> list:
    blocks = []
    stmt_body: list[str] = []
    cols = [h.strip().lower() for h in header]

    def column(name: str) -> int:
        if name.lower() not in cols:
            cols.append(name.lower())
        return cols.index(name.lower()) + 1

    if task in ("all", "categorize"):
        values = [NEEDS_REVIEW if r["source"] == "ask" else r["category"] for r in rep["rows"]]
        stmt_body += ns.category_body(column("Category"), values)
    if task in ("all", "receipts") and rep.get("receipts"):
        stmt_body += ns.category_body(column("Receipt"), receipt_column(rep), header="Receipt")
    if task in ("all", "duplicates"):
        resolved = [r for d in rep["duplicate_status"] if d["status"] == "refunded"
                    for r in d["rows"] + [d["refund_row"]]]
        stmt_body += ns.color_body(ns.highlight_colors([d["rows"] for d in rep["duplicate_status"]],
                                                       rep["outliers"], resolved=resolved))
    if stmt_body:
        blocks.append((statement_table, stmt_body))
    if budget_table and task in ("all", "categorize", "over_budget"):
        b = rep["budget"]
        notes, pending_row = ns.budget_review(b, NEEDS_REVIEW)  # complete -> clears old notes / pending line
        blocks.append((budget_table, ns.budget_body(b["actual"], b["remaining"], notes=notes,
                                                    pending_row=pending_row, pending_label=NEEDS_REVIEW)))
    return blocks


async def run(orch, args: dict, utterance: str, decide: Decide | None = None) -> str:
    task = (args or {}).get("task") or "all"
    if task not in TASKS:
        task = "all"
    t0 = time.perf_counter()
    ocr_task: asyncio.Task | None = None
    try:
        root = finance_dir()
        step = Steps(orch)
        await orch.server.ui("acting", "Looking for your statement in Numbers...")
        with step("list"):
            tables = await _list(orch, "Couldn't reach Numbers")
        if find_statement(tables) is None:
            with step("open_statement"):
                tables = await _open(orch, root / STATEMENT_FILE, "Opening your bank statement...",
                                     "Couldn't open the bank statement", find_statement, "Date/Description/Amount")
        statement = find_statement(tables)
        if task in ("receipts", "all"):
            ocr_task = asyncio.ensure_future(_ocr_all(orch, root / RECEIPTS_DIR))
        budget = find_budget(tables)
        if budget is None and task in ("all", "categorize", "over_budget"):
            with step("open_budget"):
                tables = await _open(orch, root / BUDGET_FILE, "Opening your budget...", "Couldn't open the budget",
                                     find_budget, "Category/Budget")
            budget = find_budget(tables)
            statement = find_statement(tables) or statement

        await orch.server.ui("acting", "Reading your statement...")
        statement_table = _ref(statement)
        budget_table = _ref(budget) if budget else None
        with step("read"):
            out = await _script(orch, ns.read_tables([statement_table] + ([budget_table] if budget_table else [])),
                                "Couldn't read the statement")
        tsvs = out.split("\x1e")
        try:
            txns = load_statement(tsvs[0])
            budget_amounts = load_budget(tsvs[1]) if budget_table and len(tsvs) > 1 else (
                load_budget(root / BUDGET_FILE) if (root / BUDGET_FILE).exists() else {})
        except (ValueError, IndexError) as e:
            raise ToolError("Couldn't read the statement", f"parse: {e}") from None
        if not txns:
            raise ToolError("The statement looks empty", "no rows")
        header = tsvs[0].split("\n", 1)[0].split("\t")

        await orch.server.ui("thinking", f"Checking {len(txns)} transactions...")
        receipts = None
        if ocr_task is not None:
            await orch.server.ui("thinking", "Matching receipts to the statement...")
            with step("ocr_wait"):
                receipts = await ocr_task
            ocr_task = None
        with step("analyze"):
            rep = analyze(txns, budget_amounts, receipts, decide=decide)
        orch.tracer.decision({"tool": "finance_review", "task": task, "complete": rep["complete"],
                              "flags": jsonable(rep["flags"])})

        n_review = len(rep["budget"].get("pending", {}).get("rows", []))
        if n_review and task in ("all", "categorize", "over_budget"):
            await orch.server.ui("thinking", f"{n_review} rows need your review; marking them...")
        blocks = write_blocks(task, rep, header, statement_table, budget_table)
        if blocks:
            await orch.server.ui("acting", "Writing results to Numbers...")
            with step("write"):
                await _script(orch, ns.multi(blocks), "Couldn't write to Numbers")

        await orch.server.say(summary_sentence(task, rep))
        await orch.server.ui("success")
        return "ok"
    except ToolError as e:
        orch.tracer.decision({"tool": "finance_review", "task": task, "error": e.raw})
        await orch.server.say(e.say)
        await orch.server.ui("confused")
        return "failed"
    finally:
        if ocr_task is not None:
            if ocr_task.done():
                if not ocr_task.cancelled():
                    ocr_task.exception()  # already failed alongside another error; don't warn twice
            else:
                ocr_task.cancel()
        orch.tracer.stage("finance_review", (time.perf_counter() - t0) * 1000)
