# architect digest - pass 94 (2026-10-25T11:40Z)
Reviewed: main 2de65a9 (unchanged since pass 93); wip/local 4db92e8 (snapshot on local main@313fc46, not yet on origin/main): page-load signal (AXLoaded/AXElementBusy in observe, wait-for-load after navigation, `wait` returns early once loaded), fused expects stripped for agentic tasks, Numbers sort guard against cell rewrites, Premiere clipSpeed hot-text, panel without the model picker, 'Opening browser' progress text. No cloud branch moved. Swift read only, not compiled.
Watch, not filed: every `press` in a browser now triggers one extra observe in _await_page_load (orchestrator.py:3764-3777@4db92e8); cost per step = one observe's ax_ms, unmeasured.
Tests (Linux): wip ml/tests 2464 passed, 113 skipped, 2 xfailed (test_planner_think.py ignored: needs libmlx).
Open: P0 0, P1 21, P2 13. New: architect-60 (P2). Updated: 55. Re-checked: 48, 53, 54, 57, 58 still open.

## Open P0/P1 (ranked)
1. architect-55: failed expects never block on agentic app tasks (fused expect stripped on wip; soft verify returns ok), including premiere_edit with no finish criterion.
2. architect-57: destructive-refuse gate refuses 'show all files in Downloads', misses 'erase everything on my disk'.
3. architect-58: 'nice work on the demo' is treated as a style, so the model writes its own reply.
4. architect-54: Slack 'Message #search-team' composer sends on Enter with no confirm.
5. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
6. architect-51: app-task 35B keeps retrieval k=1 / think 512; escalation state not pinned for benchmarks (see 60).
7. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
8. architect-49/45 and r4 validity (42/44/32/37/40/28/29), Premiere on macOS (26/27/35).

## Next moves
1. Hard expects when progress_kind is None; soft failures stop the batch and feed the loop guard (55/53).
2. Tighten the destructive gate.
3. Style only for bare style phrases; narrow the send-gate exemption.
4. Before merging 696a9cf: keep the 35B toggle visible or stop sending the stored value (60).
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER/PLANNER_MODE=dsl/MUSELET_NO_ESCALATE=1, honest /125; fix README claims.
