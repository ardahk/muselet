# architect digest - pass 13 (2026-10-24T08:08Z)
Reviewed: main 0fd5698, wip/local 64dd1cb, cloud/data-pipeline 0f3df7f, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench 6e7cd09, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/grounding 3441ee8.
New on main: AGENTS.md records the user's standing decisions (tune every option fairly, keep alternatives selectable, phase budget may exceed $60 within $150); the spend guard is now $120 phase / $140 warn. tcc_warm.py added. No new findings.

## Open P0/P1 (ranked)
1. architect-8 P1 - Phase-1 LoRA: only pilots so far; no full run or base-model baseline; about 4 h to Sat 12:00 PDT - training/
2. architect-10 P1 - Grounder merged but unused; every pixel click fails - ml/src/brain/orchestrator.py:593

## Highest-leverage next moves
1. Launch the full Phase-1 run at lr4e-4 now; export; run mlx_parity against parity_300.jsonl on the Mac; score the base 0.8B/4B on the same validation set. ~2 h wall-clock.
2. Wire the Grounder into the click path (screenshot -> locate -> to_global -> act with expect) (architect-10). ~1 h.
3. Merge cloud/brain-3 (non-DSL line skip, loop guard, web_ax_pending re-observe), then run the four demo flows on the Mac and record first-action ms. ~2 h.
4. Run HobbyLM-125 and DeskMind-13 on the finalized cloud/bench harness. ~3 h.
