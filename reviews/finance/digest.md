# finance lane — digest (pass 1, 2026-10-24)

Reviewed main@c09dcbd, wip/local@bcd3b75, cloud/finance@6f28fa3 (fixture rebalance only; engine not pushed yet),
cloud/fixtures-docs@4bf2291. cloud/advisor: not pushed yet. All truth files on main and on cloud/finance
reconcile exactly with my own Decimal recompute (`tests/recompute_truth.py`): balance chain, totals, category
spend, remaining, over_budget, duplicates, receipts. cloud/finance generate.py is byte-stable on rerun.
Rebalanced story numbers: income 4,845.00, spend 4,112.26, net +732.74, over_budget [Dining, Shopping].

## Open P0/P1 (ranked)
1. finance-1 P0 — Numbers bundle id com.apple.Numbers is likely wrong on macOS (prompts/planner_system.md:42,71)
2. finance-2 P1 — SUMIF example doesn't match the statement's columns, sign or table name (prompts/planner_system.md:42)
3. finance-4 P1 — Already-refunded Amazon duplicate is reported as an open duplicate (generate.py / truth)
4. finance-5 P1 — Spec's MAD-per-category outlier rule flags 15 normal rows (builder_finance.md find_outliers)
5. finance-3 P1 — Numbers read recipe drops the last row and returns typed values (prompts/planner_system.md:42)

## Highest-leverage next moves
- On the Mac, run `osascript -e 'id of app "Numbers"'` (2 s) and fix the id everywhere before numbers_script.py golden tests freeze it.
- Make the sheet carry the evidence: the engine writes a Category column, Budget Actual uses -SUMIF formulas, and the agent says done only if the formulas equal the engine's Decimal totals.
- Add a `status: refunded` link from the Amazon duplicate to its refund, so the agent says "1 duplicate to dispute, 1 already refunded".
- Give find_outliers a floor (>= max($250, 5% of monthly income)) and a ratio to the category median, and test it on a second seed with and without a planted outlier.
- Add receipts with a fuzzy merchant name and a posting delay, and assert PHILZ COFFEE stays no_match despite the nearby PEET'S COFFEE rows.
