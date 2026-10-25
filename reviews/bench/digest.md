# bench digest — pass 55 (2026-10-25T01:05Z, main@e4594d9)

P0: 0 | open P1: 12 | open P2: 8

Ranked open P1 (new/changed first):
1. bench-36 it3 now default router; competitor-bench claims (main and docs-demo-3) say "it2 only" and replay/DeskMind runs neither pin nor record the router.
2. bench-23 (P2->P1) it3 chosen on route_v2 +10.7, but route_v2 gold and it3 relabels share judge/policy; route_v1_clean (independent) is -2.0.
3. bench-34 planner think default = qwen sampler on one seed (101 vs 100/156) at +850 ms/step vs greedy.
4. bench-31 planner-LoRA trained with ~21 demos on v2-holdout screens; no holdout eval.
5. bench-16 HobbyLM --exclude-kind calc is Muselet-only (30/125 r4 tasks).
6. bench-28 5 v2-holdout golds accept field-clobbering type.
7. bench-11, bench-14, bench-15, bench-20, bench-21, bench-29 unchanged (see findings.jsonl).

Next moves:
1. Pin ROUTER for HobbyLM/DeskMind runs (it2, or relabel claims to it3 citing the data_route sec-4 gate) and write router+sha+tau into every result row.
2. Quote it3 with route_v1_clean next to route_v2; label route_v2 as same-policy gold.
3. THINK_SAMPLER=greedy default, or >=3 qwen seeds.
4. Symmetric HobbyLM exclusions / intersection denominator.
5. Fix the 5 v2-holdout golds before LoRA-vs-base on the 105 screen-clean rows.

Note: bench-35 (stale router claim) is fixed on cloud/docs-demo-3 c615c37; resolves on merge.

Watch (pass 55, not a finding yet): cloud/memory-rules2 03c3cd1 rewrites ml/src/brain/memory/rules.py (+421) from live regressions; the claims' memory row (.574 / .0195 on the frozen holdout) is from the pre-rules2 code, so re-run evals/memory_eval.py holdout after merge before quoting. Its new tests contain 2 phrases that are also holdout utterances ('a bit more', 'make it thursday instead'), both generic; no tune-only leakage beyond that.
Reviewed fine: main e4594d9 proxy wait_disconnected polls _slot_released (fixes event re-clear race), run_live keeps the case skip_reason; mem-wiki-search check now also reads Zen. Nit: the new test_live_record_merge_keeps_case_skip_reason re-implements the merge expression instead of calling run_live code, so it would not catch a regression.
