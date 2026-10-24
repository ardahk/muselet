# architect digest - pass 5 (2026-10-24T06:15Z)
Reviewed: main e78f143, wip/local e0bdc65, cloud/data-pipeline 153a01c, cloud/finance 529e9ff, cloud/finance-2 f4ae461, cloud/fixtures-docs 4bf2291, cloud/bench 14c7eb1, cloud/advisor 9432c30, cloud/advisor-2 ec98013, cloud/pitch 454a563.
Resolved this pass: architect-1 (planner loop wired in wip), architect-3 (Premiere/timer executors), architect-7 (bench harnesses on cloud/bench), architect-9 (finance as brain-executor skills).

## Open P0/P1 (ranked)
1. architect-6 P1 - Planner's 0-1000 click coordinates are never converted to screen points (script/expect parts fixed) - ml/src/brain/orchestrator.py
2. architect-8 P1 - Phase-1 LoRA deadline risk (Sat 12:00 PDT); no measured fallback router - training/SPEC.md
3. architect-5 P1 - Partials dropped; ARGS decode serial after release - ml/src/brain/server.py

## Highest-leverage next moves
1. Convert the planner's click x,y (0-1000 of the screenshot) to global points using the screenshot {origin,width,height,scale} before act (architect-6). ~30 min.
2. Run the four demo flows end to end on the Mac with the new planner and turn each failure into a regression trace. ~2 h.
3. Speculative route+args on partials; skip args for zero-arg skills (architect-5). Route+args comes off the critical path for instant commands. ~2 h.
4. Get a baseline router score now: eval-route with the base 0.8B/4B on route_v1 and the external utterances, so tau is fitted and there is a fallback if the LoRA slips (architect-8). ~30 min.
5. First real HobbyLM-125 and DeskMind-13 runs through cloud/bench; publish latency measured at the same point HobbyLM measures it. ~3 h.
