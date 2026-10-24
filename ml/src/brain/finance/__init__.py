"""Deterministic finance engine (stdlib only, Decimal money). The LLM never does arithmetic or matching here;
the on-device decision model is only injected into `categorize` for merchants the rules don't know."""

from .budget import budget_report, category_spend, pending
from .categorize import CONFIDENCE_THRESHOLD, INCOME, UNCATEGORIZED, categorize, categorize_with_evidence
from .detect import duplicate_status, find_duplicates, find_outliers, find_refunds, weekend_charges
from .evidence import Flag
from .receipts import is_adjacent_swap, merchant_match, parse_receipt_text, reconcile_receipts
from .report import analyze, jsonable
from .statement import Txn, balance_breaks, load_budget, load_statement, normalize_merchant, parse_money

__all__ = [
    "CONFIDENCE_THRESHOLD",
    "INCOME",
    "UNCATEGORIZED",
    "Flag",
    "Txn",
    "analyze",
    "balance_breaks",
    "budget_report",
    "categorize",
    "categorize_with_evidence",
    "category_spend",
    "duplicate_status",
    "find_duplicates",
    "find_outliers",
    "find_refunds",
    "is_adjacent_swap",
    "jsonable",
    "load_budget",
    "load_statement",
    "merchant_match",
    "normalize_merchant",
    "parse_money",
    "parse_receipt_text",
    "pending",
    "reconcile_receipts",
    "weekend_charges",
]
