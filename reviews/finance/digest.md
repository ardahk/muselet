# finance digest (pass 2, 2026-10-24)
Open P0/P1, ranked:
1. finance-1 P0 Numbers bundle id unverified; now in ml/src/brain/finance/numbers_script.py:13 and the goldens
2. finance-9 P1 Budget written to Numbers while asks are unresolved (Groceries 203.61 vs 298.70); ml/src/brain/finance/__main__.py
3. finance-4 P1 Refunded Amazon duplicate still says 'Charged twice'; ml/src/brain/finance/evidence.py
4. finance-10 P1 Receipt mismatch unbounded; tip posted later -> false 'No bank charge'; ml/src/brain/finance/receipts.py
5. finance-2 P1 Planner SUMIF example wrong columns/sign/table; prompts/planner_system.md
6. finance-3 P1 Planner Numbers read recipe drops last row and returns typed values; prompts/planner_system.md (the engine's read_table_tsv is fine)

Next moves:
- Run `osascript -e 'id of app "Numbers"'` on the Mac before the demo; fix APP in one place if it differs.
- Gate write_budget on complete; show pending rows/amount until the user answers the ask.
- Link refund to duplicate in report.analyze (data already in reversed_debit -> row 67).
- Point the planner Numbers recipe at brain.finance scripts instead of hand-written SUMIF.
- Bound the receipt amount_mismatch pass and allow a +1-3 day window for tip-sized differences.
