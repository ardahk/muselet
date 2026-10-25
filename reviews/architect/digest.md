# architect digest - pass 101 (2026-10-25T15:50Z)
Reviewed: main 32c0ad4 — local main pushed (de6319c..32c0ad4: finance/advisor engine deletion, planner prompt/defaults, AX-ref clicks, Numbers/Premiere fixes, recursive app discovery, docs reconcile). wip/local 69261f5 has the same tree as main. Docs now separate script defaults from a deployed override (base 4B native-tools planner, THINK=1024, RETRIEVAL_K=0, FEWSHOT=none, escalation off) and caveat historical numbers. No cloud branch moved.
Tests (Linux, main 32c0ad4, --timeout=30, test_planner_think.py ignored): 88 failed, 2199 passed, 111 skipped, 2 xfailed — the red wip suite is now on main.
Open: P0 0, P1 23, P2 14. No new findings. Resolved: 64 (LOAD_POLL_S used; AGENTS.md still says .25 s, code is 0.1). Updated: 63 (now on main), 61 (deployed config unmeasured), 45 (README route_v2 .945). Re-checked (ran): 62, 57, 58, 54.

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
