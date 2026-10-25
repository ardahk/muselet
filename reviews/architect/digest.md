# architect digest - pass 90 (2026-10-25T10:05Z)
Reviewed: main b92677f (#121 MLXWorker skips cancelled futures and no longer double-sets results - correct; generic_decide temperature defaults; new README); wip/local f1e504c (same tree as main). No cloud branch moved.
Tests (Linux): main agentic/fixes2/evidence/loop/same-tab/fallback/native-planner/progress/sendgate/finish 259 passed, 1 skipped.
Open: P0 0, P1 20, P2 11. No new findings. README claims added to architect-45 and architect-51. Re-checked: 48, 53, 54, 55, 56, 57 still open.

## Open P0/P1 (ranked)
1. architect-57: destructive-refuse gate refuses 'show all files in Downloads' / 'list every file in Documents', misses 'erase everything on my disk'.
2. architect-55: failed expects return status ok on all agentic app tasks; batch continues, no failure recorded.
3. architect-54: Slack 'Message #search-team' composer sends on Enter with no confirm.
4. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
5. architect-51: app/timer tasks forced onto the 35B; README says 35B only for web/blind screens.
6. architect-45: README and pitch quote .85 without caveat and the router on route_v2 instead of route_v1_clean.
7. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
8. architect-49, 42/44/32/37/40/28/29, 26/27/35: AGENTIC_APPS unmeasured, r4 validity, Premiere on macOS.

## Next moves
1. Tighten the destructive gate; test the seven repros.
2. Soft expects: stop the batch and feed the same-failure guard.
3. Narrow the send-gate exemption to real search fields.
4. Fix README: router .922 on route_v1_clean, .85 caveat, 35B scope matching code.
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER/PLANNER_MODE=dsl, honest /125.
