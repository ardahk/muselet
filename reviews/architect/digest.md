# architect digest - pass 87 (2026-10-25T09:20Z)
Reviewed: main 2445a1d (#110-#114: sendgate also exempts 'Ask Gmail'; email_open finish criterion + evidence (Reply control + sender words); maps and shopping hint tweaks); wip/local 6e7f50b (main + one app_hints line); cloud/cool-tasks e4def97 (merges main; no new carry logic).
Tests (Linux): main agentic/fixes2/evidence/loop/same-tab/fallback/sendgate/finish 208 passed, 1 skipped; cool-tasks carry/agentic 57 passed, 1 skipped.
Open: P0 0, P1 18, P2 10. No new findings. Re-checked: 48, 51, 53, 54 (all still open).

## Open P0/P1 (ranked)
1. architect-54: search/find/Ask Gmail exemption runs before the composer check; Slack 'Message #search-team' and 'Find My follow-up' composers send on Enter with no confirm.
2. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
3. architect-51: app/timer (and, on cool-tasks, carry) tasks forced onto the 35B (5.95 s p50, .807 vs LoRA .850); AGENTS.md says they stay on the LoRA.
4. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
5. architect-49: AGENTIC_APPS default on, unmeasured (38/125 r4 tasks).
6. architect-45: .850 holdout lacks near-paraphrase caveat.
7. architect-42/44/32/37/40/28/29: r4 validity.
8. architect-26/27/35: Premiere paths unverified on macOS; stale cmd+t.

## Next moves
1. Narrow the send-gate exemption to real search fields, checked after is_composer_app; test both repros.
2. Stop on two identical soft-expect failures on blind tasks.
3. Live LoRA vs 35B on app cases; then make code and AGENTS.md agree.
4. Fix the timer-control match.
5. Caveat .850; run r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER, honest /125.
