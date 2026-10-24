# finance digest (pass 3, 2026-10-24)
Open P0/P1, ranked:
1. finance-9 P1 Budget written to Numbers while asks are unresolved (Groceries 203.61 vs 298.70); ml/src/brain/finance/__main__.py
2. finance-14 P1 Advisor deletes the 'Review' sheet and the prior prep note without confirm; ml/src/brain/advisor/scripts.py
3. finance-13 P1 Cash reserve only parses 'lake house down'; other needs -> $0 reserve; ml/src/brain/advisor/core.py
4. finance-4 P1 Refunded Amazon duplicate still says 'Charged twice'; ml/src/brain/finance/evidence.py
5. finance-10 P1 Receipt mismatch unbounded; tip posted later -> false 'No bank charge'; ml/src/brain/finance/receipts.py

Verified: the advisor truth.json matches my own recompute, and the IRS 2026 MFJ brackets match Rev. Proc. 2025-32 p.10 and IR-2025-103.
Next moves:
- Gate finance write_budget on complete (pending rows/amount until the ask is answered).
- Advisor: write to Muselet-owned sheet/note names, or ask_confirm before deleting.
- Make liquidity reserves a profile input; derive them from notes only as a confirmable suggestion.
- Link refund to duplicate in finance report.analyze (reversed_debit already finds row 67).
- Add single/HoH 22% tops from the same Rev. Proc. and map 401(k)/HSA/checking account types before a second household demo.
