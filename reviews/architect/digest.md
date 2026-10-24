# architect digest - pass 14 (2026-10-24T08:22Z)
Reviewed: main 280715d, wip/local 38768f3, cloud/data-pipeline 1d65818, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench 6e7cd09, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/grounding 3441ee8.
New on main: the live-test safety rule (runner-enforced preconditions; never touch user documents), observe window fallback, no typing into nothing, compiled skill scripts, and new HandsKit result fields. cloud/data-pipeline adds a route_v1 eval through a Tinker sampler.

## Open P0/P1 (ranked)
1. architect-8 P1 - Phase-1 LoRA: no full run or base-model score yet; about 3.5 h to Sat 12:00 PDT - training/
2. architect-11 P1 - Brain ignores web_ax_pending/no_text_target/exit_code from HandsKit - ml/src/brain/orchestrator.py
3. architect-10 P1 - Grounder merged but unused; every pixel click fails - ml/src/brain/orchestrator.py:593

## Highest-leverage next moves
1. Launch the full Phase-1 run at lr4e-4; run eval_route on the base 0.8B/4B and the LoRA on route_v1/val (tuned vs tuned per AGENTS.md); MLX parity on the Mac. ~2 h wall-clock.
2. Merge cloud/brain-3 so the browser demo waits out web_ax_pending and script failures reach the planner (architect-11). ~30 min.
3. Wire the Grounder into the click path (architect-10). ~1 h.
4. Run the four demo flows through the precondition-enforcing live runner (live_t1) and record first-action ms. ~2 h.
5. HobbyLM-125 and DeskMind-13 on the cloud/bench harness. ~3 h.
