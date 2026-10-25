# brain lane digest — pass 56 (2026-10-25T01:20:00Z)

Open: P0 0 / P1 8 / P2 9. main 9be963d merged memory-hotfix (#71) and memory-rules2 (#72; carries brain-45: undo fallback replays another window's layout), docs-demo-3 (#68) and a bench proxy fix (outside lane). Suite on main: 18 failed / 2036 passed / 108 skipped (same 18 MLX-stub). Review repros 21F/52P: the +1 is the brain-45 repro. wip/local 4d22445 is a snapshot on main@517e056 (pre-#71/#72), so its memory/* differs from main only by those merges.

## Open P0/P1 (ranked)
- brain-16 [P1] abs_level misreads times, durations, percentages and unrelated words — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-17 [P1] Compound check runs serial route passes before speculative reuse — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-35 [P1] Permission-prompt gate checks the pre-batch observation; a prompt raised mid-batch receives the next keys/type — `ml/src/brain/orchestrator.py` (main@dae4b26@?)
- brain-40 [P1] Final utterance reuses ARGS extracted from the uncased, unpunctuated partial — `ml/src/brain/orchestrator.py` (main@3772f7c)
- brain-42 [P1] Long-term person memory is a global DB shared by every Orchestrator — `ml/src/brain/orchestrator.py` (main@8fb465c via #58)
- brain-22 [P1] Planner history format conflict (runtime 'press #4 -> ok' vs examples '[ok] press #4') — `ml/src/brain/plan_bank.py` (main@27ebd13; cloud/planner-retrieval@9786fa4@dfb66a3)
- brain-41 [P1] ARGS decode cap of 24 tokens silently truncates free-text values — `ml/src/brain/decision.py` (main@2a2c2a9)
- brain-43 [P1] Unverified planner DONE accepted whenever the model verifier errors — `ml/src/brain/orchestrator.py` (main@0b83c3b via #54; cloud/planner-verify@484f5e7)

## Highest-leverage next moves
1. brain-42 (now on main): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
2. brain-43 (now on main): when _verify_done returns p_yes None, return 'unverified' (or retry once) instead of accepting a bare DONE.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-27: confirm a grounded click whose target text names send/paper plane even without composer context.
5. brain-44 (now on main): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
