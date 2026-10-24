# architect digest - pass 11 (2026-10-24T07:45Z)
Reviewed: main 4a74659, wip/local 85c73ed, cloud/data-pipeline 9c526b1, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/fixtures-docs 4bf2291, cloud/bench c3ca0b3, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/grounding 3441ee8.
main merged cloud/pitch (#6), cloud/grounding (#9) and cloud/advisor-2 (#5). Speculative route+ARGS is live, resolving architect-5. cloud/bench has a complete live-harness runbook.

## Open P0/P1 (ranked)
1. architect-8 P1 - Phase-1 LoRA: only pilots so far (val top1 0.88); no full run, MLX parity result or base-model baseline; about 4 h to Sat 12:00 PDT - training/
2. architect-10 P1 - Grounder merged but unused; every pixel click fails - ml/src/brain/orchestrator.py:590-594

## Highest-leverage next moves
1. Launch the full Phase-1 run at lr4e-4 now; export; run the sharded mlx_parity on the Mac; score the base 0.8B/4B on the same validation set. ~2 h wall-clock.
2. Wire the Grounder into the click path (screenshot -> locate -> to_global -> act with expect) (architect-10). ~1 h.
3. Run the four demo flows end to end on the Mac and record first-action ms from the latency chip against HobbyLM's 0.26 s. ~2 h.
4. Run HobbyLM-125 and DeskMind-13 on the cloud/bench live harness following its runbook. ~3 h.
