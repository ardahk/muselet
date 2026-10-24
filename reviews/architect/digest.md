# architect digest - pass 8 (self-poll, 2026-10-24T07:07Z)
Reviewed: main c2d2988, wip/local d5d2d7d, cloud/data-pipeline 8f0b9bc, cloud/finance 529e9ff, cloud/finance-2 f4ae461, cloud/fixtures-docs 4bf2291, cloud/bench 911a384, cloud/advisor 9432c30, cloud/advisor-2 ec98013, cloud/pitch 454a563, cloud/brain-2 9f41c11, cloud/grounding 42310cd.
main now has the System-2 planner (17a2755): script continues the batch, expect is verified on every action, click is refused without a screenshot. cloud/grounding converts norm1000 to global points (grounder.py:5,69). cloud/bench adds a shared live harness.

## Open P0/P1 (ranked)
1. architect-8 P1 - Phase-1 LoRA: the pilots work (val top1 0.88, $1.93 per pilot), but there is no full run, no MLX parity check and no base-model baseline yet - training/SPEC.md
2. architect-5 P1 - Partials dropped on main; fix pending on cloud/brain-2 - ml/src/brain/server.py

## Highest-leverage next moves
1. Merge cloud/brain-2 (speculative route+ARGS on partials), then measure first-action ms from the new trace against HobbyLM's 0.26 s. ~1 h.
2. Run the four demo flows end to end on the Mac with the main planner; turn each failure into a regression trace. ~2 h.
3. Wire the cloud/grounding Grounder into the orchestrator's click path (screenshot -> grounder.to_global) so pixel clicks stop failing when the AX tree is blind. ~1 h.
4. Launch the full Phase-1 run at lr4e-4 now (pilot cost suggests well under the $60 phase cap), then export and run mlx_parity.py on the Mac. Also score the base 0.8B/4B on the same validation set to show the lift. ARGS EM 0.74 is the weak spot. ~2 h wall-clock.
5. First real HobbyLM-125 and DeskMind-13 runs on the shared cloud/bench harness. ~3 h.
