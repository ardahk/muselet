"""python -m brain.finance analyze --statement X.csv --budget B.csv|B.xlsx|truth.json [--receipts R.json]
                                   [--rules merchant_rules.json] [--scripts]

Prints one JSON report. `--rules` maps merchant -> category (answers the user already gave). `--scripts` adds
the Numbers AppleScript (highlight rows, fill the budget, summary table) under `numbers_scripts`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import numbers_script as ns
from .report import NEEDS_REVIEW, analyze, jsonable
from .statement import load_budget, load_statement


def _receipts(path: str):
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = [{"id": k, **v} for k, v in data.items()]
    return [{k: r[k] for k in ("id", "merchant", "date", "total")} for r in data]


def ns_resolved(rep: dict) -> list[int]:
    return [r for d in rep["duplicate_status"] if d["status"] == "refunded" for r in d["rows"] + [d["refund_row"]]]


def budget_notes(rep: dict) -> dict[str, str]:
    """"Needs review" on every category an unresolved row could still flip; empty note elsewhere."""
    return {c: NEEDS_REVIEW for c in rep["budget"].get("needs_review", [])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m brain.finance")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="run every check and print one JSON report")
    a.add_argument("--statement", required=True)
    a.add_argument("--budget", required=True)
    a.add_argument("--receipts")
    a.add_argument("--rules")
    a.add_argument("--scripts", action="store_true")
    args = ap.parse_args(argv)

    txns = load_statement(Path(args.statement).read_text())
    budget = load_budget(Path(args.budget))
    receipts = _receipts(args.receipts) if args.receipts else None
    rules = json.loads(Path(args.rules).read_text()) if args.rules else None
    rep = analyze(txns, budget, receipts, user_rules=rules)
    if args.scripts:
        rep["numbers_scripts"] = {
            "highlight": ns.highlight_flags([d["rows"] for d in rep["duplicate_status"]], rep["outliers"],
                                            resolved=ns_resolved(rep)),
            # Unresolved rows: the budget is written with a "Needs review" note on the categories they could
            # still flip (finance-9), never as if it were final.
            "write_budget": ns.write_budget(rep["budget"]["actual"], rep["budget"]["remaining"],
                                            notes=budget_notes(rep) if not rep["complete"] else None),
            "summary": ns.add_summary_table(ns.summary_rows(rep)),
        }
    json.dump(jsonable(rep), sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
