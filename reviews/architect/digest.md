# architect digest - pass 88 (2026-10-25T09:35Z)
Reviewed: main 85958b0 (#115 a524768 soft expects whenever a finish criterion/progress kind exists; #116 shopping few-shot + stock-skip hint; #117 shopping goals never create_reminder); wip/local 3d21638 (same tree as main); cloud/cool-tasks a77104e (merges main).
Tests (Linux): main agentic/fixes2/evidence/loop/same-tab/fallback/sendgate/finish 208 passed, 1 skipped; cool-tasks carry/agentic 57 passed, 1 skipped.
Open: P0 0, P1 19, P2 11. New: architect-55 (P1), architect-56 (P2). Re-checked: 48, 51, 53, 54 still open.

## Open P0/P1 (ranked)
1. architect-55 (new): on every agentic app task (reminder, message, timer, play, cart) a failed expect returns status ok, so the batch keeps going and no failure is recorded.
2. architect-54: Slack 'Message #search-team' / 'Find My follow-up' composers send on Enter with no confirm.
3. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
4. architect-51: app/timer tasks forced onto the 35B (5.95 s p50, .807 vs LoRA .850).
5. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
6. architect-49: AGENTIC_APPS default on, unmeasured.
7. architect-45: .850 holdout lacks near-paraphrase caveat.
8. architect-42/44/32/37/40/28/29: r4 validity. architect-26/27/35: Premiere unverified on macOS.
P2 new: architect-56 shopping override catches 'remind me to buy milk tomorrow'.

## Next moves
1. Soft expects: keep the result but stop the batch and feed the same-failure guard; test it.
2. Narrow the send-gate exemption to real search fields, after is_composer_app.
3. Gate the shopping override on the absence of a reminder cue.
4. Live LoRA vs 35B on app cases; fix the timer-control match.
5. Caveat .850; run r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER, honest /125.
