# finance digest (Pass 43, 2026-10-24; no lane code changes since pass 42; main 2a2c2a9)
Open P0: none.
Open P1:
- finance-27: by default, planner retrieval now puts rule-8-violating Numbers demos (per-cell loops, `tell application "Numbers"`, cell press/type) into every Numbers planner prompt (ml/src/brain/plan_bank.py, tools/serve_brain.sh:31, evals/planner_scenarios_v2.jsonl:193,217,239).

Open P2: finance-26 (both finance demo live cases skipped by default as 'pending'), finance-23 (advisor doc-by-path), finance-25 (4 s Numbers table poll on cold open), finance-24 (merchant prefix over-match), finance-15 (single filers / 401k-HSA-checking taxed), finance-17 (numbers written as words pass the phrasing filter).

Next moves:
- Rewrite the 3 v2-tune Numbers golds to a bulk `tell application id "com.apple.Numbers"` range read, or filter them out of the bank in `_filter_demos` plus a test. Until then, run with RETRIEVAL_K=0 for Numbers. planner-lora SFT will not fix this (1/1,194 demos are Numbers, and SFT renders prompts without retrieval while serving keeps k=1).
- Clear the stale pending keys, or run `run_live.py --id t2-finance-dupes --id t2-advisor-prep --run-pending` with Numbers not running (this also settles finance-23/25).
- Rehearse the finance demo cold once. Read finance_open_* ms from the traces and set the table-poll timeout from them.
- Receipts: limit prefix matching to known abbreviations (finance-24).
