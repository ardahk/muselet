# finance digest (pass 5, 2026-10-24T08:00Z; no new lane commits since pass 4)
Open P0/P1, ranked:
1. finance-18 P0 finance_review reads the front Numbers doc as the statement; demo setup -> 'Couldn't read the statement'; ml/src/brain/tools/finance_review.py
2. finance-19 P1 Budget 'Note' written to column E of a 4-column table (pending rows) -> write fails; ml/src/brain/finance/numbers_script.py
3. finance-16 P1 Mascot says '$332,329 total impact' (sum of non-comparable amounts); ml/src/brain/tools/advisor_prep.py
4. finance-20 P1 merchant_match rejects Shell/SHELL OIL, Whole Foods/WHOLEFDS, Costco/COSTCO WHSE...; ml/src/brain/finance/receipts.py
5. finance-21 P1 Unreadable receipts silently dropped; ml/src/brain/tools/finance_review.py
6. finance-14 P1 Advisor deletes 'Review' sheet / prior note without confirm; ml/src/brain/advisor/scripts.py
7. finance-9 P1 Pending budget: Note on wrong categories, Groceries understated with no marker; ml/src/brain/finance/budget.py
8. finance-13 P1 Cash reserve only parses 'lake house down'; ml/src/brain/advisor/core.py
9. finance-22 P1 Advisor targets Numbers doc by 'portfolio' prefix, not path; ml/src/brain/advisor/scripts.py

Next moves:
- Select the statement doc by header, and align demo_script.md setup with finance setup_mac.sh paths.
- Grow the budget table before writing Note; write pending as its own row.
- Replace 'total impact' sum in the advisor bubble with the top opportunity.
- Keep unreadable receipts as flagged 'unreadable'; broaden merchant_match first-token/alias rule.
- Advisor: Muselet-owned sheet/note names, and target the portfolio by file path.

Risk (data lane, not a finance finding): cloud/data-pipeline@8f0b9bc training/reports/phase1_pilot-lr{2e-4,4e-4}.md report finance_review val acc 0.000 / 0.250 (advisor_prep 1.000). Unless this improves, the 'reconcile receipts / update budget' utterances won't route to the finance tool. Small val n likely; check finance_review teacher/val coverage.
