# architect digest - pass 102 (2026-10-26T03:55Z)
Reviewed: main 32c0ad4 (unchanged); wip/local 0b155b2 (on main@32c0ad4): Phase-2 long-horizon benchmark LH-v1 (18 live cases: fixture mart/forms/webmail/wiki/bank sites, TextEdit/Finder/Numbers native cases, 2 online), seed data, graders, grader tests, pre-registered hypotheses H1-H8 in docs/phase2/LAB_NOTEBOOK.md. No ml/ or app/ changes. Graders are final-state, preconditions/setup check a clean Safari/TextEdit/Numbers/Finder, and hypotheses are written before results — good protocol. bench/tests/test_lh_graders.py 33 passed; evals/lh_v1_build.py regenerates lh_v1.jsonl byte-identically.
New P1 architect-66: two native-case teardowns rm -f files in ~/Documents, ~/Desktop, ~/Downloads (and iCloud TextEdit) chosen by common file name + mtime newer than case start; reproduced deletion of a user todo.txt and a pre-existing invoice-0423.pdf with a temp HOME.
Note: H5 (frontier claude planner) is diagnostic-only per the notebook; it must not be reported as an on-device result.
Tests: ml/ unchanged since pass 101 (main 32c0ad4: 88 failed, 2199 passed).
Open: P0 0, P1 24, P2 14. Re-checks from pass 101 stand (code unchanged).

## Open P0/P1 (ranked)
1. architect-63: wip suite red (88) and hangs; Premiere confirm-timeout safety tests among them.
2. architect-55: failed expects never block on app tasks; finance/advisor and Premiere have no finish criterion.
3. architect-62: finance/advisor have no verification; AGENTIC_APPS=0 doc is false.
4. architect-61: planner retrieval/few-shot/system prompt changed without a re-run; .850/.770 stale.
5. architect-57: destructive gate refuses 'show all files in Downloads', misses 'erase everything on my disk'.
6. architect-58: 'nice work on the demo' treated as a style.
7. architect-54: Slack 'Message #search-team' sends on Enter without confirm.
8. architect-53/51/48, r4 validity (42/44/32/37/40/28/29), Premiere on macOS (26/27/35).

## Next moves
1. Main: use LOAD_POLL_S in _repoll_loading so main is green again (64).
2. Port the old safety tests to the planner path, bound the planner worker; get wip green before pushing main (63).
3. Hard expects + finish criteria for finance_review/advisor_prep/premiere_edit (55/62); make the Numbers hint agree with rule 16 (65).
4. Re-run planner holdouts at k=0 + new system prompt, or keep k=1 (61); tighten 57/58/54.
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned PLANNER/BLIND_PLANNER/PLANNER_MODE=dsl/MUSELET_NO_ESCALATE=1, honest /125.
