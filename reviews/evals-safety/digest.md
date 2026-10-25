# evals-safety digest (pass 74, 2026-10-25T05:22:19Z)

New: -54 (P1) planner few-shot contains open-ended eval case oe-spotify-jazz verbatim with its solution (wip/local).


-52 resolved on main by #86. -53 (P2) now on main.


New: -53 (P2) wip/local rejects any first-turn ASK on vague goals, incl. recipient asks.
-52: fenced on wip/local c156d18; not yet on main/fallback.


1. **P0 -50** sealed HobbyLM D04-D06 utterances tuned on (a1fd57f); exclude/separate them in any later HobbyLM number.


Open: P0 0, P1 9, P2 11.

## Open P0/P1 (ranked)
0. **-46 (P1):** new live_t2 cases are missing from every decontam gate; the gates hard-code live_t1. (on main e9fb42d, still unfixed)
1. **-39 (P1):** the finance rules miss BERKELEY BOWL, so Groceries comes out 203.61 vs the key's 298.70 without the model. (`ml/src/brain/finance/categorize.py`)
2. **-43 (P1):** the decisions trainers have no month-to-date gate. Month-to-date is ~$142 against the $148 stop. (`training/decisions/*.py`)
3. **-36 (P1):** v2 clobbering accept rules can be retrieved at k=1, and the offline eval runs at k=0. (`evals/planner_scenarios_v2.jsonl`)
4. **-42 (P1):** route_v1 case 87 is mislabeled (should be draft_email); 73 and 89 are ambiguous. (`evals/route_v1.jsonl`)
5. **-40 (P1):** the finance fixtures contradict cloud/session_b.md. (`evals/fixtures/finance/generate.py`)
6. **-25 (P1):** skips and --exclude-kind drop out of the live/HobbyLM denominator. (`bench/`)
7. **-11 (P1):** done is model-claimed; planner-verify is a self-judge. (`ml/src/brain/orchestrator.py`)

## Next moves
0. Planner think: prefer t512 greedy, or seed-repeat qwen; don't select on holdout (-47).
1. Add BERKELEY BOWL to the Groceries rules, plus a no-model fixture==truth test (-39).
2. Port the planner-lora month-to-date guard to the decisions trainers before any approval (-43).
3. Relabel route_v1 case 87 and re-quote it2 on clean (-42).
4. Run the planner offline eval at the serving k (-36/-45).
5. Glob evals/live_t*.jsonl in gate.py, plan_bank.py and build.py before live_t2 is quoted (-46).
