# architect digest - pass 93 (2026-10-25T11:10Z)
Reviewed: main 2de65a9 (#129 blocks cmd+L/cmd+T in browser tasks unless the user mentions the address bar or a new tab, and widens cart_count to Walmart/Target labels; #131 soft expects for every agentic app task plus a one-batch Premiere hint); wip/local 5b70519 (same tree as main). No cloud branch moved.
#129 looks right: the guard fails without a strike and points to url + the page's own search box; cart_count('Cart, 0 items') -> 0, 'Shopping cart 3 items' -> 3.
Tests (Linux): main ml/tests 2433 passed, 113 skipped, 2 xfailed (test_planner_think.py ignored: needs libmlx).
Open: P0 0, P1 21, P2 12. No new findings. Updated: 55, 53 (scope widened by #131). Re-checked: 48, 54, 57, 58 still open.

## Open P0/P1 (ranked)
1. architect-55: failed expects now return status ok on every agentic app task, including premiere_edit, which has no finish criterion (progress_kind -> None).
2. architect-57: destructive-refuse gate refuses 'show all files in Downloads', misses 'erase everything on my disk'.
3. architect-58: 'nice work on the demo' is treated as a style, so the model writes its own reply instead of the user's words.
4. architect-54: Slack 'Message #search-team' composer sends on Enter with no confirm.
5. architect-53: soft expects skip the same-failure guard (30 turns / 300 s), now on all app tasks.
6. architect-51: app-task 35B keeps retrieval k=1 / think 512; NO_ESCALATE not pinned for benchmarks.
7. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
8. architect-49/45 and r4 validity (42/44/32/37/40/28/29), Premiere on macOS (26/27/35).

## Next moves
1. Hard expects when progress_kind is None; soft failures stop the batch and feed the loop guard (55/53).
2. Tighten the destructive gate.
3. Style only for bare style phrases; narrow the send-gate exemption.
4. Fair LoRA-vs-35B live app comparison with MUSELET_NO_ESCALATE=1; align the 35B settings.
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER/PLANNER_MODE=dsl/MUSELET_NO_ESCALATE, honest /125; fix README claims.
