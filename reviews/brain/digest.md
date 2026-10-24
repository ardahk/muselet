# brain lane digest — pass 50 (2026-10-24T23:47:00Z)

Open: P0 0 / P1 8 / P2 8. main 18c139f merged safety-brain12/18/38/27, planner-think (default off), planner-lora, live-cases; brain-12/18/38 resolved. Suite on main: 17 failed / 1840 passed / 108 skipped (all failures need real MLX: 8 historical + 8 planner_think + 1 brain18 plan test). wip/local 719907a unchanged.

## Open P0/P1 (ranked)
- brain-16 [P1] abs_level misreads times, durations, percentages and unrelated words — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-17 [P1] Compound check runs serial route passes before speculative reuse — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-35 [P1] Permission-prompt gate checks the pre-batch observation; a prompt raised mid-batch receives the next keys/type — `ml/src/brain/orchestrator.py` (main@dae4b26@?)
- brain-40 [P1] Final utterance reuses ARGS extracted from the uncased, unpunctuated partial — `ml/src/brain/orchestrator.py` (main@3772f7c)
- brain-42 [P1] Long-term person memory is a global DB shared by every Orchestrator — `ml/src/brain/orchestrator.py` (cloud/memory-lt@cc056af)
- brain-22 [P1] Planner history format conflict (runtime 'press #4 -> ok' vs examples '[ok] press #4') — `ml/src/brain/plan_bank.py` (main@27ebd13; cloud/planner-retrieval@9786fa4@dfb66a3)
- brain-41 [P1] ARGS decode cap of 24 tokens silently truncates free-text values — `ml/src/brain/decision.py` (main@2a2c2a9)
- brain-43 [P1] Unverified planner DONE accepted whenever the model verifier errors — `ml/src/brain/orchestrator.py` (cloud/planner-verify@d22b9a9)

## Highest-leverage next moves
1. memory-lt (brain-42): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
2. planner-verify (brain-43): a verifier exception must give 'unverified', not accept a bare DONE.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-27: confirm a grounded click whose target text names send/paper plane even without composer context.
5. brain-9 (brain-44): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
