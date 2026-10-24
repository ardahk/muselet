# architect digest - pass 10 (2026-10-24T07:35Z)
Reviewed: main d8ad966, wip/local 85ec0df, cloud/data-pipeline b8c0604, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/fixtures-docs 4bf2291, cloud/bench 911a384, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/grounding 3441ee8.
New on main: confirm_cancel frame, latency chip, row-formula recipe, and the HobbyLM/DeskMind external utterances for dedup. Speculative route on partials is now live on main. The grounder (cloud/grounding 3441ee8) is still not called from the orchestrator.

## Open P0/P1 (ranked)
1. architect-8 P1 - Phase-1 LoRA: only pilots so far (val top1 0.88); no full run, no MLX parity result, no base-model baseline; about 4.5 h to Sat 12:00 PDT - training/
2. architect-5 P1 - ARGS still serial after the final utterance on main; speculative ARGS waits on the cloud/brain-2 merge - ml/src/brain/orchestrator.py

## Highest-leverage next moves
1. Launch the full Phase-1 run at lr4e-4 now (about $2 per pilot); export; run the sharded mlx_parity on the Mac; score the base 0.8B/4B on the same validation set. ARGS EM 0.74 is the weak spot. ~2 h wall-clock.
2. Merge cloud/brain-2 (speculative ARGS, verified done, planner fallback, one-shot confirm) and measure first-action ms with the latency chip. ~1 h.
3. Run the four demo flows end to end on the Mac with the main planner; turn each failure into a regression trace. ~2 h.
4. Wire the Grounder into the click path (screenshot -> grounder -> global points) so blind-AX demos (Premiere panels) can click. ~1 h.
5. First real HobbyLM-125 and DeskMind-13 runs on the shared cloud/bench harness. ~3 h.
