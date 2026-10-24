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
from .report import analyze, jsonable
from .statement import load_budget, load_statement


def _receipts(path: str):
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = [{"id": k, **v} for k, v in data.items()]
    return [{k: r[k] for k in ("id", "merchant", "date", "total")} for r in data]


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
            "highlight": ns.highlight_flags(rep["duplicates"], rep["outliers"], rep["weekend_charges"]),
            "write_budget": ns.write_budget(rep["budget"]["actual"], rep["budget"]["remaining"]),
            "summary": ns.add_summary_table(ns.summary_rows(rep)),
        }
    json.dump(jsonable(rep), sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
