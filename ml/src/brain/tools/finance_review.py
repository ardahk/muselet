"""Brain tool `finance_review` (catalog executor "brain"; contract in cloud/tools_interface.md).

Reads the bank statement from the front Numbers document, runs the deterministic `brain.finance` engine,
writes the results back (Category column, highlights, budget Actual/Remaining) and reconciles receipt images
OCR'd on the Mac. The LLM never computes or matches anything here; `decide` (the on-device decision model) is
only consulted for merchants the keyword rules don't know, and rows it is unsure about stay "Needs review".

Script calls: list documents, one read of every table, one write of everything (plus `open_file` when the
statement or budget is not open yet). Receipt OCR runs concurrently with the Numbers read.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from brain.finance import numbers_script as ns
from brain.finance.categorize import Decide
from brain.finance.receipts import parse_receipt_text
from brain.finance.report import NEEDS_REVIEW, analyze, jsonable
from brain.finance.statement import load_budget, load_statement

TASKS = ("categorize", "duplicates", "receipts", "over_budget", "all")
STATEMENT_FILE = "bank_statement_oct2026.csv"
BUDGET_FILE = "budget_oct2026.xlsx"
RECEIPTS_DIR = "Receipts"
BUDGET_SHEET = "Budget"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".heic", ".tiff", ".pdf")
SHOW_PAUSE_S = 0.3  # let the viewer see an app that was just brought forward


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


def _docs(output: str) -> list[tuple[str, list[str]]]:
    out = []
    for line in output.splitlines():
        if line.strip():
            name, _, sheets = line.partition("\t")
            out.append((name, [s for s in sheets.split("|") if s]))
    return out


def _budget_doc(docs) -> str | None:
    return next((n for n, sheets in docs if any(s.lower() == BUDGET_SHEET.lower() for s in sheets)), None)


async def _open(orch, path: Path, bubble: str, fail_say: str) -> list:
    await orch.server.ui("acting", bubble)
    await _rpc(orch, "skill", {"name": "open_file", "args": {"path": str(path)}}, fail_say)
    await asyncio.sleep(SHOW_PAUSE_S)
    return _docs(await _script(orch, ns.list_documents(), fail_say))


async def _ocr_all(orch, folder: Path) -> list[dict]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT) if folder.is_dir() else []
    if not files:
        raise ToolError("Couldn't find any receipts", f"no receipt images in {folder}")
    t = time.perf_counter()
    results = await asyncio.gather(*(_rpc(orch, "ocr", {"path": str(p)}, "Couldn't read the receipts")
                                     for p in files))
    orch.tracer.stage("finance_ocr", (time.perf_counter() - t) * 1000)
    out = []
    for p, res in zip(files, results, strict=True):
        parsed = parse_receipt_text(res.get("text", ""), res.get("lines"))
        out.append({"id": p.name, **parsed})
    return out


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
        mm, nm = st.count("amount_mismatch"), st.count("no_match")
        if task == "receipts":
            parts.append(f"{st.count('matched')} receipts match")
        if mm:
            parts.append(f"{mm} receipt mismatch{'es' if mm != 1 else ''}")
        if nm:
            parts.append(f"{nm} unmatched")
        if not mm and not nm and task == "all":
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


def write_blocks(task: str, rep: dict, header: list[str], statement_table: str, budget_table: str | None) -> list:
    blocks = []
    stmt_body: list[str] = []
    if task in ("all", "categorize"):
        col = next((i + 1 for i, h in enumerate(header) if h.strip().lower() == "category"), len(header) + 1)
        values = [NEEDS_REVIEW if r["source"] == "ask" else r["category"] for r in rep["rows"]]
        stmt_body += ns.category_body(col, values)
    if task in ("all", "duplicates"):
        resolved = [r for d in rep["duplicate_status"] if d["status"] == "refunded"
                    for r in d["rows"] + [d["refund_row"]]]
        stmt_body += ns.color_body(ns.highlight_colors([d["rows"] for d in rep["duplicate_status"]],
                                                       rep["outliers"], resolved=resolved))
    if stmt_body:
        blocks.append((statement_table, stmt_body))
    if budget_table and task in ("all", "categorize", "over_budget"):
        b = rep["budget"]
        notes = {c: NEEDS_REVIEW for c in b.get("needs_review", [])} if not rep["complete"] else None
        blocks.append((budget_table, ns.budget_body(b["actual"], b["remaining"], notes=notes)))
    return blocks


async def run(orch, args: dict, utterance: str, decide: Decide | None = None) -> str:
    task = (args or {}).get("task") or "all"
    if task not in TASKS:
        task = "all"
    t0 = time.perf_counter()
    ocr_task: asyncio.Task | None = None
    try:
        root = finance_dir()
        await orch.server.ui("acting", "Looking for your statement in Numbers...")
        docs = _docs(await _script(orch, ns.list_documents(), "Couldn't reach Numbers"))
        if not docs:
            docs = await _open(orch, root / STATEMENT_FILE, "Opening your bank statement...",
                               "Couldn't open the bank statement")
            if not docs:
                raise ToolError("Couldn't open the bank statement", "Numbers has no document after open_file")
        statement_doc = docs[0][0]
        if task in ("receipts", "all"):
            ocr_task = asyncio.ensure_future(_ocr_all(orch, root / RECEIPTS_DIR))
        budget_doc = _budget_doc(docs)
        if budget_doc is None and task in ("all", "categorize", "over_budget"):
            docs = await _open(orch, root / BUDGET_FILE, "Opening your budget...", "Couldn't open the budget")
            budget_doc = _budget_doc(docs)
            if budget_doc is None:
                raise ToolError("Couldn't find the budget sheet", f"no '{BUDGET_SHEET}' sheet in {docs}")

        await orch.server.ui("acting", "Reading your statement...")
        statement_table = ns.table_ref(document=statement_doc)
        budget_table = ns.table_ref(sheet=BUDGET_SHEET, document=budget_doc) if budget_doc else None
        t = time.perf_counter()
        out = await _script(orch, ns.read_tables([statement_table] + ([budget_table] if budget_table else [])),
                            "Couldn't read the statement")
        orch.tracer.stage("finance_read", (time.perf_counter() - t) * 1000)
        tables = out.split("\x1e")
        try:
            txns = load_statement(tables[0])
            budget = load_budget(tables[1]) if budget_table and len(tables) > 1 else (
                load_budget(root / BUDGET_FILE) if (root / BUDGET_FILE).exists() else {})
        except (ValueError, IndexError) as e:
            raise ToolError("Couldn't read the statement", f"parse: {e}") from None
        if not txns:
            raise ToolError("The statement looks empty", "no rows")
        header = tables[0].split("\n", 1)[0].split("\t")

        await orch.server.ui("thinking", f"Checking {len(txns)} transactions...")
        receipts = None
        if ocr_task is not None:
            await orch.server.ui("thinking", "Matching receipts to the statement...")
            receipts = [r for r in await ocr_task if r["merchant"] and r["date"] and r["total"] is not None]
            ocr_task = None
        t = time.perf_counter()
        rep = analyze(txns, budget, receipts, decide=decide)
        orch.tracer.stage("finance_analyze", (time.perf_counter() - t) * 1000)
        orch.tracer.decision({"tool": "finance_review", "task": task, "complete": rep["complete"],
                              "flags": jsonable(rep["flags"])})

        n_review = len(rep["budget"].get("pending", {}).get("rows", []))
        if n_review and task in ("all", "categorize", "over_budget"):
            await orch.server.ui("thinking", f"{n_review} rows need your review; marking them...")
        blocks = write_blocks(task, rep, header, statement_table, budget_table)
        if blocks:
            await orch.server.ui("acting", "Writing results to Numbers...")
            t = time.perf_counter()
            await _script(orch, ns.multi(blocks), "Couldn't write to Numbers")
            orch.tracer.stage("finance_write", (time.perf_counter() - t) * 1000)

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
