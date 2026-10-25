# architect digest - pass 89 (2026-10-25T09:50Z)
Reviewed: main ca73c12 (#108 native-tools merged, --planner-mode default dsl; #105 ui-progress step bubbles; #118/#119 deterministic destructive-request refuse gate before routing; #120 Premiere speed/duration hint); wip/local 47f809a (same tree as main); cloud/cool-tasks 3937e6b (merges main 85958b0). ui-progress Swift read only, not compiled.
Tests (Linux): main agentic/fixes2/evidence/loop/same-tab/fallback/native-planner/progress/sendgate/finish 259 passed, 1 skipped; cool-tasks carry/agentic 57 passed, 1 skipped.
Open: P0 0, P1 20, P2 11. New: architect-57. Re-checked: 48, 51, 53, 54, 55, 56 still open.

## Open P0/P1 (ranked)
1. architect-57 (new): the destructive-refuse gate runs before routing and refuses 'show all files in Downloads', 'list every file in Documents', 'remove all items from my cart', but lets 'erase everything on my disk' through.
2. architect-55: failed expects return status ok on all agentic app tasks; batch continues, no failure recorded.
3. architect-54: Slack 'Message #search-team' composer sends on Enter with no confirm.
4. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
5. architect-51: app/timer tasks forced onto the 35B; PLANNER_MODE=tools now selectable and unmeasured.
6. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
7. architect-49/45: AGENTIC_APPS unmeasured; .850 caveat.
8. architect-42/44/32/37/40/28/29: r4 validity. architect-26/27/35: Premiere unverified on macOS.

## Next moves
1. Tighten the destructive gate to verb + files/disk/everything objects; test the seven repros.
2. Soft expects: stop the batch and feed the same-failure guard.
3. Narrow the send-gate exemption to real search fields.
4. Live LoRA vs 35B on app cases; fix the timer-control match.
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER/PLANNER_MODE=dsl, honest /125; caveat .850.
