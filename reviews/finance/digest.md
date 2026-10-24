# finance digest (pass 6, 2026-10-24T08:20Z)
Open P0/P1, ranked:
1. finance-23 P1 Advisor doc-by-path assumes Numbers exposes an imported xlsx's file (needs a 1-line Mac check); ml/src/brain/advisor/scripts.py

Open P2: finance-24 (merchant prefix over-match), finance-15 (single filers / 401k-HSA-checking as taxable), finance-17 (numbers written as words pass the phrasing filter).

Next moves:
- Lead, on the Mac: with portfolio.xlsx open, run `osascript -e 'tell application id "com.apple.Numbers" to POSIX path of ((file of front document) as alias)'`.
- Rehearse the finance segment once on the Mac: list_tables over every table, then the Receipt column write.
- Advisor: account_kind for 401(k)/403(b)/HSA/checking; a clear refusal for non-MFJ instead of KeyError.
- Receipts: limit prefix matching to known abbreviations.
