# architect digest - pass 97 (2026-10-25T12:58Z)
Reviewed: main d09f4d8 (#130 page-loaded signal: AXLoaded web_loaded/web_busy, waits after navigation; README rebrand + kitten.png); wip/local 01a929c (snapshot of local main@264cc82, not on origin/main): click-AX test fixed, Numbers cheat sheet adds Sort-picker and SORT/SORTBY facts, docs. No cloud branch moved. Swift (Observe.swift/RPC.swift) read only, not compiled.
Tests (Linux, --timeout=30, test_planner_think.py ignored): main 1 failed, 2436 passed, 113 skipped (new: architect-64); wip 88 failed, 2137 passed, 111 skipped, 2 xfailed, planner worker still times out.
Open: P0 0, P1 23, P2 15. New: 64, 65 (P2). Re-checked (ran): 63, 62, 57, 58, 54, 48 open; 55, 53, 51, 61 untouched.

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
