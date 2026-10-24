# Cloud builder: finance engine + fixture rebalance (Muselet)

Repo `ardahk/muselet`. Read `AGENTS.md` first (architecture, contracts), then `evals/fixtures/finance/README.md`
and `generate.py`. Muselet is a fully on-device macOS voice agent (Apple Silicon, MLX). For the Cal Hacks finance
track (Hyphenate: "autonomous systems for finance": act when confident, escalate when not, every action carries
evidence) the demo is: "categorize my October transactions into the budget, find duplicate charges, reconcile my
receipts" in **Apple Numbers**, fully offline. The LLM must never do arithmetic or matching; deterministic code
does, and the on-device decision model only picks categories for merchants the rules don't know.

Work on branch `cloud/finance` (from `main`), commit often, push, and open one PR to `main` when done. Do not
modify `ml/src/brain/{decision,orchestrator,server,cli,catalog}.py`, `app/`, `evals/route_v1.jsonl` or `skills/`:
other agents own them. You have no API keys and need none.

## Part 1: rebalance the fixtures (lead decision; do this first)
Today the statement spends $6,885 on $4,845 income (net -$2,040) and 5 of 8 categories are over budget: not a
credible budget story. Change `generate.py` sampling (amounts and row mix only) so that:
- Still exactly 120 rows, same columns, same persona, opening balance 3,120.55, deterministic `Random(1337)`.
- Total income unchanged at 4,845.00. Total spend (debits minus refunds) between 3,900 and 4,300, so net is
  positive and closing balance > opening balance.
- Budgets unchanged (Rent 1650, Groceries 400, Dining 250, Transport 150, Shopping 200, Subscriptions 60,
  Utilities 180, Health 80).
- `over_budget` is exactly [Dining, Shopping]: Shopping over mostly because of the $1,299 outlier, Dining over
  by $40-$120. Every other category under budget with remaining >= $15 (nothing borderline).
- Every planted anomaly stays exactly as documented (duplicate UBER TRIP -23.47 on 10-09, duplicate AMAZON MKTP
  -64.99 on 10-21, outlier APPLE STORE -1299.00 on Sat 10-24, refund AMAZON MKTP REFUND +64.99 on 10-28, no other
  exact duplicates, receipts 1-6 exact matches, 7 transposed-digit total, 8 PHILZ COFFEE no match).
- Add assertions in `generate.py` that fail generation if any rule above is violated. All truth files are
  recomputed by code; never hand-edit them. Update the README numbers and the over-budget note.

## Part 2: deterministic finance engine `ml/src/brain/finance/` (stdlib only, `Decimal` money)
Interface (keep these names and shapes; the planner and skills will call them):
- `load_statement(csv_text) -> list[Txn]`; `Txn(row:int 1-based, date:date, description:str, amount:Decimal,
  balance:Decimal)`. Also `load_budget(path_or_rows)` for the xlsx-derived `Category,Budget` table (accept CSV
  text as exported from Numbers, and a list of rows).
- `find_duplicates(txns) -> list[tuple[int,int]]`: same date + normalized description + amount.
- `find_outliers(txns) -> list[int]`: a documented, general rule (e.g. robust MAD z-score per category plus an
  absolute floor), excluding payroll/rent/recurring. No row ids or merchant names hardcoded. Add a test on a
  second, synthetic statement (different seed, no planted outlier) that it flags nothing.
- `weekend_charges(txns) -> list[int]`; `find_refunds(txns) -> list[int]` (credits that reverse an earlier
  debit of the same merchant and amount, or contain REFUND).
- `categorize(txns, categories, decide=None) -> dict[int, tuple[str, float, str]]` (row -> category, confidence,
  source "rule"|"model"|"ask"). First a general merchant-keyword rule table (UBER/LYFT/BART/CHEVRON -> Transport,
  etc.; written as general knowledge, not tuned to row ids). For unmatched rows call
  `decide(text, options) -> {option: prob}` (injected; at runtime it is the on-device decision model). If the top
  probability < 0.6 the source is "ask" (escalate, don't guess). Report accuracy vs the truth categories in tests.
- `category_spend(txns, cats) -> dict[str, Decimal]` (debits minus refunds), `budget_report(spend, budget) ->
  {actual, remaining, over_budget}`.
- `reconcile_receipts(receipts, txns) -> dict` where receipts are `{id, merchant, date, total}` (OCR happens on the
  Mac): matched / amount_mismatch (same merchant+date, total differs; flag `transposed_digits: true` when the digits
  are a single adjacent swap) / no_match. Fuzzy merchant match (case, punctuation, store numbers).
- `evidence`: every flag carries the row ids and the rule that fired, so the mascot can say why.
- `numbers_script.py`: functions that return AppleScript source using `tell application id "com.apple.Numbers"`:
  read a table range as TSV in one call, write a whole column, write the budget Actual/Remaining cells, set
  background color on rows (duplicates red, outlier orange, weekend light), add a summary table. Escape all
  strings. Golden-string tests only (no Mac here).
- CLI: `python -m brain.finance analyze --statement X.csv --budget B.csv|truth.json --receipts R.json` -> one JSON
  report. Test: report equals the truth files exactly (to the cent), for duplicates, outliers, refunds,
  category_spend, budget actual/remaining/over_budget, receipts.
Tests in `ml/tests/test_finance.py`. The module is stdlib-only, so run them with a plain venv + pytest
(`PYTHONPATH=ml/src python -m pytest ml/tests/test_finance.py`); `uv sync --project ml` may fail on Linux
because of mlx, which is fine.

When done, reply with: the PR link, the new totals (income, spend, net, over_budget), test results, the
categorize accuracy with rules only, and any rule you were unsure about.
