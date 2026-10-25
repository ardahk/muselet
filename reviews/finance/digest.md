# finance digest (Pass 64, 2026-10-25; main 4150ecb; finance-31 still open at cloud/fallback 2ef5805; new: finance-32)
Open P0: none.
Open P1:
- finance-31 (cloud/fallback 6e40c3e, not on main): finance_review is risk=safe, so _with_fallback hands every recoverable failure ("Couldn't open the bank statement", including the 4 s cold-open poll from finance-25; "Couldn't read the receipts"; "Couldn't write to Numbers" after a partial write) to the planner with FALLBACK_PLANNER=1 by default. proxy.drop() removes the escalation bubble, and the 4B planner then does the categorize/duplicate/receipt math itself (ml/src/brain/orchestrator.py:98-115,1150-1190; tools/finance_review.py:322-326; tools/serve_brain.sh:53).

- finance-27: by default, planner retrieval now puts rule-8-violating Numbers demos (per-cell loops, `tell application "Numbers"`, cell press/type) into every Numbers planner prompt (ml/src/brain/plan_bank.py, tools/serve_brain.sh:31, evals/planner_scenarios_v2.jsonl:193,217,239).

- finance-30: verified-done never sees Numbers script results, so answer goals are likely rejected (ml/src/brain/orchestrator.py:1633-1690, 2655-2700).

Open P2: finance-32 (the new acceptance gate on cloud/test-strategy has no 'Reconcile my receipts.' case, so the OCR/receipt beat is ungated), finance-29 (W9 script gate confirms the prompt's SUMIF recipe, 'Duplicate' cell text and `set n to row count`), finance-28 (the 'all' summary drops the unmatched receipt and need-review count at the 12-word cap), finance-26 (both finance demo live cases skipped by default as 'pending'), finance-23 (advisor doc-by-path), finance-25 (4 s Numbers table poll on cold open), finance-24 (merchant prefix over-match), finance-15 (single filers / 401k-HSA-checking taxed), finance-17 (numbers written as words pass the phrasing filter).

Next moves:
- finance-32: add acc-demo-finance-receipts (checks for 6 matched, 1 mismatch, PHILZ unmatched) to build_acceptance.py.
- finance-31: before merging cloud/fallback, exempt finance_review/advisor_prep from _with_fallback and keep the fail_say bubble. Add a test where a finance_review ToolError with fallback on makes no planner call.
- Rewrite the 3 v2-tune Numbers golds to a bulk `tell application id "com.apple.Numbers"` range read, or filter them out of the bank in `_filter_demos` plus a test. Until then, run with RETRIEVAL_K=0 for Numbers. planner-lora SFT will not fix this (1/1,194 demos are Numbers, and SFT renders prompts without retrieval while serving keeps k=1).
- The demo script (builder_docs_demo.md:9) includes finance review and advisor prep: clear the stale pending keys, or run `run_live.py --id t2-finance-dupes --id t2-advisor-prep --run-pending` with Numbers not running (this also settles finance-23/25).
- Rehearse the finance demo cold once. Read finance_open_* ms from the traces and set the table-poll timeout from them.
- finance-27 + finance-29 together: safety-bench28 already has the plan_bank denylist hook (UNSAFE_APPEND_IDS); adding the 3 v2 Numbers ids there is a one-line fix. Strip string literals before the Numbers branch of script_needs_confirm.
- finance-30: put the script result and the done summary into the _verify_done state, and measure p_yes on one 'average of column C' run on the Mac.
- it3 default: before recording, on the Mac run evals/router_check.py --router it3 filtered to the 43 finance_review/advisor_prep rows of route_v2, plus the 3 demo phrases (pitch/demo_script.md beats 8-9). Check label and task arg; no per-skill it3 number exists in the repo.
- Receipts: limit prefix matching to known abbreviations (finance-24).
