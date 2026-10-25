# architect digest - pass 91 (2026-10-25T10:40Z)
Reviewed: main 430e59e (#122 fix-lane: draft_email own-words, premiere_edit via agentic route, PLANNER=35b retrieval 0 / think 1024; #123 style vs literal replies; #124 Observe pins focused element + text inputs past the node cap; #125 Act types into Adobe hot-text buttons); wip/local 9f6aa0d (same tree as main); cloud/cool-tasks 2fafa9e (merges main). Swift read only, not compiled.
Tests (Linux): main agentic/fixes2/evidence/loop/same-tab/fallback/native-planner/progress/sendgate/finish 318 passed, 1 skipped.
Open: P0 0, P1 21, P2 12. New: architect-58 (P1), architect-59 (P2). Updated: 49, 51. Re-checked: 48, 53, 54, 55, 57 still open.

## Open P0/P1 (ranked)
1. architect-57: destructive-refuse gate refuses 'show all files in Downloads', misses 'erase everything on my disk'.
2. architect-55: failed expects return status ok on all agentic app tasks; batch continues, no failure recorded.
3. architect-58 (new): 'nice work on the demo' / 'I am running short today' are treated as a style, so the model writes its own reply instead of the user's words.
4. architect-54: Slack 'Message #search-team' composer sends on Enter with no confirm.
5. architect-51: c104e8b's own diagnosis (retrieval distracts the 35B, think 512 truncates) is fixed only for PLANNER=35b; the default app-task 35B still has both.
6. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
7. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
8. architect-49/45 and r4 validity (42/44/32/37/40/28/29), Premiere on macOS (26/27/35); premiere_edit now planner-operated with {} args.

## Next moves
1. Tighten the destructive gate; fix soft-expect batch continuation (55) and the loop guard (53).
2. Style only for bare style phrases; test both repros stay literal.
3. Apply retrieval_k 0 / think 1024 to the blind 35B too (cli.py:181-183), or measure; fix the THINK no-op.
4. Narrow the send-gate exemption to real search fields.
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER/PLANNER_MODE=dsl, honest /125; fix README claims.
