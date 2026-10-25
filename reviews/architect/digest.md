# architect digest - pass 86 (2026-10-25T09:05Z)
Reviewed: main 4f94e42 (#103-#109 demo-loop: done_summary reset, YouTube play evidence needs a YouTube page, web_ui_guard hint, sendgate search/find exemption, enter_sends focused-element fallback, three builder briefs); wip/local 52eb571 (same tree as main); new cloud/cool-tasks 4c84adc (carry tasks, `note` op, relay is draft-only), cloud/native-tools 6053e4e (`--planner-mode dsl|tools`, default dsl), cloud/ui-progress a66166b (step-phrase bubble; Swift uncompiled, read only).
Tests (Linux): main 143 passed 1 skipped; cool-tasks 83 passed 1 skipped; native-tools 43 passed; ui-progress 7 passed.
Open: P0 0, P1 18, P2 10. New: architect-54. Re-checked open: 48, 51, 53.

## Open P0/P1 (ranked)
1. architect-54 (new): sendgate's search/find exemption runs before the composer check; Slack 'Message #search-team' and 'Find My follow-up' composers send on Enter with no confirm.
2. architect-53: soft expects skip the same-failure guard (30 turns / 300 s).
3. architect-51: app/timer tasks forced onto the 35B (5.95 s p50, .807 vs LoRA .850); AGENTS.md now claims they stay on the LoRA.
4. architect-48: 'set a timer for 10 minutes to stop the oven' -> cancel.
5. architect-49: AGENTIC_APPS default on, unmeasured (38/125 r4 tasks).
6. architect-45: .850 holdout lacks near-paraphrase caveat.
7. architect-42/44/32/37/40/28/29: r4 validity (screenshot start state, memory isolation, denominator, it3 overlap, post-hoc brightness, retrieval contamination, no competitor win).
8. architect-26/27/35: Premiere paths unverified on macOS; stale cmd+t.

## Next moves
1. Narrow the search/find exemption to real search fields, after is_composer_app; test both repros.
2. Stop on two identical soft-expect failures on blind tasks.
3. Live LoRA vs 35B on app cases; then make code and AGENTS.md agree.
4. Fix the timer-control match.
5. Caveat .850; run r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned AGENTIC_APPS/BLIND_PLANNER/PLANNER, honest /125.
