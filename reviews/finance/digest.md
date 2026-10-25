# finance digest (Pass 98, 2026-10-25; main 32c0ad4; wip 69261f5; P0 1, P1 2, P2 4)

> Pass 98: engine removal (a2004d9) is on main 32c0ad4 under a user override recorded in AGENTS.md; finance-36 accepted. NEW P0 finance-37: pitch/devpost.md:28-33,52-54, docs/REPORT.md:295-296 and pitch/claims.md:190-193,221 still claim deterministic Decimal engines / 'model never does arithmetic' and cite deleted files; README.md:16 and REPORT.md:11 already say AI-planned. Fix before 16:00Z submission. Closed as moot: 15, 17, 23, 24, 25, 28, 31, 33. Fixed: 27. Still open and now the only guard on finance results: 34 (finish criteria), 30 (verified-done context), 32 (no receipts acceptance case).

> Pass 97: no finance change (wip 73f8136 Premiere-only). Pass 96: wip aadf777 grounder one-liner. Pass 95: no finance change (main b00f679 README image; wip 35aed2d app-name resolver). Pass 94: main d09f4d8 still has the engines (finance-36 not merged); README line 16 'all math is deterministic Decimal' is true on main, false on wip. Pass 93: wip 7b8f421 adds no finance path. Pass 92: wip 9015e83 2900d4b also strips the bundle-ID/bounded-range Numbers rule and finance_review preference from planner_system.md ("no hidden app workflow tools"). main unchanged.

> Pass 91 NEW P0 finance-36 (wip only): a2004d9 deletes ml/src/brain/finance, advisor and the finance_review/advisor_prep tools; their labels now go to the AI planner. Do not merge before the deadline, or restore behind a flag; README/devpost/REPORT still claim the deterministic engines.

> Pass 85 new: finance-35 (P2) destructive-request refuse gate (orchestrator.py:161/925) refuses 'Remove all the duplicate charges from my October budget', 'Format all the amounts in my budget as currency', 'Reconcile all files in my Finance folder'. Fix: require a file/folder/disk object next to the quantifier; 'format' only with disk/drive.

> Pass 81: finance and advisor beats are no longer in pitch/demo_script.md, so finance-33 is P1 (devpost/REPORT still claim those phrases). Redirected and fallback finance tasks now run on the 35B with a 300 s budget (finance-31/33).
Open P0:
- finance-33 (main dc6f2f5): open-ended routing (OPEN_ENDED=1 default) sends demo beat 9 'Prep me for my meeting with the Hendersons.' from advisor_prep to the planner, because the calendar hint matches 'meeting'. Also finance_review whenever the user says 'file' or 'folder'. Workaround: OPEN_ENDED=0. Fix: skip executor=brain labels in open_ended_redirect (app_hints.py:104-122).
Open P1:
- finance-34 (P1 since pass 73, main e2f7e5e): the merged finish gate rejects a correct Numbers done for finance goals given a 'search' criterion (e.g. 'find duplicate charges in my statement', the full multi-clause demo request), because the subject words aren't in the window title/URL; this costs a recovery round and can end in 'Not finished'. Fix: no criterion unless the goal names a site/app.
- (finance-33 moved to P0, see above; previously cloud/open-ended fd87f69): with OPEN_ENDED=1 by default, the calendar hint's 'meeting' match sends advisor_prep's demo beat 9 ('Prep me for my meeting with the Hendersons.') to the planner. The finder_files hint does the same to finance_review when the user says 'folder' or 'file' (app_hints.py:104-122, orchestrator.py:1131-1137).

- finance-31 (now on main dc6f2f5 via ccea212; first found on cloud/fallback 6e40c3e): finance_review is risk=safe, so _with_fallback hands every recoverable failure ("Couldn't open the bank statement", including the 4 s cold-open poll from finance-25; "Couldn't read the receipts"; "Couldn't write to Numbers" after a partial write) to the planner with FALLBACK_PLANNER=1 by default. proxy.drop() removes the escalation bubble, and the 4B planner then does the categorize/duplicate/receipt math itself (ml/src/brain/orchestrator.py:98-115,1150-1190; tools/finance_review.py:322-326; tools/serve_brain.sh:53).

- finance-27: by default, planner retrieval now puts rule-8-violating Numbers demos (per-cell loops, `tell application "Numbers"`, cell press/type) into every Numbers planner prompt (ml/src/brain/plan_bank.py, tools/serve_brain.sh:31, evals/planner_scenarios_v2.jsonl:193,217,239).

- finance-30: verified-done never sees Numbers script results, so answer goals are likely rejected (ml/src/brain/orchestrator.py:1633-1690, 2655-2700).

Open P2: finance-32 (the new acceptance gate on cloud/test-strategy has no 'Reconcile my receipts.' case, so the OCR/receipt beat is ungated), finance-29 (W9 script gate confirms the prompt's SUMIF recipe, 'Duplicate' cell text and `set n to row count`), finance-28 (the 'all' summary drops the unmatched receipt and need-review count at the 12-word cap), finance-26 (both finance demo live cases skipped by default as 'pending'), finance-23 (advisor doc-by-path), finance-25 (4 s Numbers table poll on cold open), finance-24 (merchant prefix over-match), finance-15 (single filers / 401k-HSA-checking taxed), finance-17 (numbers written as words pass the phrasing filter).

Next moves:
- finance-33 cheapest fix: the per-hint "redirect" flag is on main since pass 77; set "redirect": false on the calendar and finder_files rows in prompts/app_hints.jsonl.
- Pass 72 note (wip 422399a): the new timer_control pre-route catches 'cancel that …' / 'stop that …' for 600 s after start_timer; demo beat 2 sets a timer ~78 s before the finance beat. Demo phrases don't match; keep finance follow-ups free of cancel/stop + it/that during rehearsal, or require 'timer' unless Clock is frontmost.
- Before recording on main dc6f2f5: OPEN_ENDED=0 (finance-33) and FALLBACK_PLANNER=0 (finance-31), or exempt executor=brain skills from both paths, then run acc-demo-advisor-prep and acc-demo-finance-dupes.
- finance-33: before merging cloud/open-ended, exempt executor=brain skills from open_ended_redirect and add the demo phrases as tests.
- finance-27 now matters more: the LoRA planner ships without few-shot, so the retrieved v2-numbers-* example is the only Numbers example in the prompt.
- finance-32: add acc-demo-finance-receipts (checks for 6 matched, 1 mismatch, PHILZ unmatched) to build_acceptance.py.
- finance-31: before merging cloud/fallback, exempt finance_review/advisor_prep from _with_fallback and keep the fail_say bubble. Add a test where a finance_review ToolError with fallback on makes no planner call.
- Rewrite the 3 v2-tune Numbers golds to a bulk `tell application id "com.apple.Numbers"` range read, or filter them out of the bank in `_filter_demos` plus a test. Until then, run with RETRIEVAL_K=0 for Numbers. planner-lora SFT will not fix this (1/1,194 demos are Numbers, and SFT renders prompts without retrieval while serving keeps k=1).
- The demo script (builder_docs_demo.md:9) includes finance review and advisor prep: clear the stale pending keys, or run `run_live.py --id t2-finance-dupes --id t2-advisor-prep --run-pending` with Numbers not running (this also settles finance-23/25).
- Rehearse the finance demo cold once. Read finance_open_* ms from the traces and set the table-poll timeout from them.
- finance-27 + finance-29 together: safety-bench28 already has the plan_bank denylist hook (UNSAFE_APPEND_IDS); adding the 3 v2 Numbers ids there is a one-line fix. Strip string literals before the Numbers branch of script_needs_confirm.
- finance-30: put the script result and the done summary into the _verify_done state, and measure p_yes on one 'average of column C' run on the Mac.
- it3 default: before recording, on the Mac run evals/router_check.py --router it3 filtered to the 43 finance_review/advisor_prep rows of route_v2, plus the 3 demo phrases (pitch/demo_script.md beats 8-9). Check label and task arg; no per-skill it3 number exists in the repo.
- Receipts: limit prefix matching to known abbreviations (finance-24).
