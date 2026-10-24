# finance digest (pass 10, 2026-10-24T09:20Z; no lane changes since pass 8)
Open P0/P1: none.

Open P2: finance-23 (advisor doc-by-path; now degrades to 'skipped Numbers'), finance-25 (4 s Numbers table poll on cold open), finance-24 (merchant prefix over-match), finance-15 (single filers / 401k-HSA-checking as taxable), finance-17 (numbers written as words pass the phrasing filter).

Next moves:
- Lead, on the Mac: with portfolio.xlsx open, run `osascript -e 'tell application id "com.apple.Numbers" to POSIX path of ((file of front document) as alias)'`.
- Rehearse both segments once with Numbers not running; read finance_open_* and advisor numbers_ready ms from the traces and set the timeouts from them.
- Receipts: limit prefix matching to known abbreviations.
- Advisor: account_kind for 401(k)/403(b)/HSA/checking; clear refusal for non-MFJ.
