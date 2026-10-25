# architect digest - pass 92 (2026-10-25T10:55Z)
Reviewed: main 298526d (#126 Observe always adds a focused text input the walk missed; #127 sample_row: GPU top-k then temp/top-p on the k survivors, plus prefill_ms/prompt_tokens in planner stats; #128 MUSELET_NO_ESCALATE ignores the app's 35B toggle); wip/local d409a32 (same tree as main); cloud/cool-tasks cfbec49 (merges main). Swift read only, not compiled.
sample_row (planner.py:155-166@298526d): same distribution as sample_logits except ties at the k-th logit (argpartition keeps exactly k); negligible. Not executed: MLX is unavailable on Linux.
Tests (Linux): main ml/tests 2432 passed, 113 skipped, 2 xfailed (test_planner_think.py ignored: needs libmlx).
Open: P0 0, P1 21, P2 12. No new findings. Updated: 51. Re-checked: 48, 54, 57, 58 still open; orchestrator.py, sendgate.py and agentic.py are unchanged since 430e59e.

## Open P0/P1 (ranked)
1. architect-57: destructive-refuse gate refuses 'show all files in Downloads', misses 'erase everything on my disk'.
2. architect-55: failed expects return status ok on all agentic app tasks; batch continues, no failure recorded.
3. architect-58: 'nice work on the demo' is treated as a style, so the model writes its own reply instead of the user's words.
4. architect-54: Slack 'Message #search-team' composer sends on Enter with no confirm.
5. architect-51: the app-task 35B keeps retrieval k=1 / think 512 (cli.py:181-183); NO_ESCALATE is not pinned for benchmark runs.
6. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
7. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
8. architect-49/45 and r4 validity (42/44/32/37/40/28/29), Premiere on macOS (26/27/35).

## Next moves
1. Tighten the destructive gate; fix soft-expect batch continuation (55) and the loop guard (53).
2. Style only for bare style phrases; test that literal text stays literal.
3. Narrow the send-gate exemption to real search fields.
4. Use MUSELET_NO_ESCALATE for a fair LoRA-vs-35B live app comparison; align the 35B settings.
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER/PLANNER_MODE=dsl/MUSELET_NO_ESCALATE, honest /125; fix README claims.
