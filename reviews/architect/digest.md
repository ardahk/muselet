# architect digest - pass 99 (2026-10-25T13:55Z)
Reviewed: main b00f679 (unchanged); wip/local aadf777 (local main@264cc82 plus uncommitted work): CANVAS_APPS prefix widened from "Adobe Premiere Pro" to "Adobe Premiere", so an unversioned "Adobe Premiere" process name also gets the blind planner/grounder hint (it also now covers Premiere Rush/Elements, which are canvas apps too). Looks right. No cloud branch moved.
Carried from pass 98 (watch, not filed): the recursive app search runs on every `apps` RPC and open-by-name; its cost on a full /Applications is unmeasured.
Tests (Linux, wip aadf777, --timeout=30, test_planner_think.py ignored): 88 failed, 2182 passed, 111 skipped, 2 xfailed; same failure set as 35aed2d. main still red on test_loading_title_repolls_until_expect_passes (64).
Open: P0 0, P1 23, P2 15. No new findings. Re-checked (ran): 63, 62, 57, 58, 54; 64, 65, 55, 53, 51, 61, 48 untouched by this diff.

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
