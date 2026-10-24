# finance digest (pass 26, 2026-10-24T12:08Z; no lane code changes since pass 13; it2 router routes finance/advisor 100% on val)
Open P0/P1: none.

Open P2: finance-23 (advisor doc-by-path; now degrades to 'skipped Numbers'), finance-25 (4 s Numbers table poll on cold open), finance-24 (merchant prefix over-match), finance-15 (single filers / 401k-HSA-checking as taxable), finance-17 (numbers written as words pass the phrasing filter).

Next moves:
- Lead, on the Mac: with portfolio.xlsx open, run `osascript -e 'tell application id "com.apple.Numbers" to POSIX path of ((file of front document) as alias)'`.
- Rehearse both segments once with Numbers not running; read finance_open_* and advisor numbers_ready ms from the traces and set the timeouts from them.
- Receipts: limit prefix matching to known abbreviations.
- Advisor: account_kind for 401(k)/403(b)/HSA/checking; clear refusal for non-MFJ.
- Routing (outside lane): cloud/data-pipeline a6b229a main run has finance_review val acc 1.000 (n=36), advisor_prep 1.000 (n=24); parity_300 finance/advisor 17/17. The pilot 0%/25% risk is cleared.
- Routing data (outside lane): data-pipeline 70b7d1b finance_check narrows finance_review to the 4 catalog tasks; 'update my budget' style asks will go to the planner, so keep the demo line on 'Reconcile my receipts'.
