# architect digest - pass 4 (2026-10-24T06:00Z)
Reviewed: main 6177cc1, wip/local cbc4879, cloud/data-pipeline 8c7c023, cloud/finance 529e9ff, cloud/fixtures-docs 4bf2291, cloud/bench 8429245, cloud/advisor 9432c30.
Resolved this pass: architect-1 (planner loop wired in wip), architect-3 (Premiere/timer executors), architect-7 (bench harnesses on cloud/bench), architect-9 (finance as brain-executor skills).

## Open P0/P1 (ranked)
1. architect-6 P1 - A script action ends the batch; expect dropped on script/skill; click 0-1000 vs points - ml/src/brain/orchestrator.py
2. architect-8 P1 - Phase-1 LoRA deadline risk (Sat 12:00 PDT); no measured fallback router - training/SPEC.md
3. architect-5 P1 - Partials dropped; ARGS decode serial after release - ml/src/brain/server.py

## Highest-leverage next moves
1. Executor fixes (architect-6): scripts continue the batch, expect forwarded on script/skill, click coordinates converted. The planner loop is now live, so these bite every multi-step demo. ~1 h.
2. Run the four demo flows end to end on the Mac with the new planner and turn each failure into a regression trace. ~2 h.
3. Speculative route+args on partials; skip args for zero-arg skills (architect-5). Route+args comes off the critical path for instant commands. ~2 h.
4. Get a baseline router score now: eval-route with the base 0.8B/4B on route_v1 and the external utterances, so tau is fitted and there is a fallback if the LoRA slips (architect-8). ~30 min.
5. First real HobbyLM-125 and DeskMind-13 runs through cloud/bench; publish latency measured at the same point HobbyLM measures it. ~3 h.
