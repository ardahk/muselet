# architect digest - pass 103 (2026-10-26T04:05Z)
Reviewed: main 32c0ad4 (unchanged); wip/local d714345 (local main 2f96add, not on origin/main): LH-v1 fixture server (stdlib, binds 127.0.0.1:8777), runner fields (named milestones, require_confirm, evidence screenshot before teardown, setup_failed skips), 32 training tasks (mart/mail/wiki only; different products, threads and quiz pages; forms, bank and native families held out), and checks that no longer launch an app (`if application is running then tell` launched TextEdit on macOS 27). Looks right. No cloud branch moved.
Tests (Linux): bench/tests 1 failed, 329 passed — the failure (declined confirm-no-send ends 'ok') is pre-existing at 0b155b2 and comes from main's brain; filed under 63. Build scripts regenerate lh_v1.jsonl/lh_train.jsonl byte-identically. ml/ unchanged (88 failed at pass 101).
Open: P0 0, P1 24, P2 14. No new findings. 66 re-run: still deletes user files. 63 updated.

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
