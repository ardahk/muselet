# brain lane digest — pass 63 (2026-10-25T03:28:00Z)

Open: P0 0 / P1 9 / P2 10. main fa0f040 merged design (#70: Clock hint and Shortcuts timer backend removed, as reviewed on cloud/design) and 7235a34. 7235a34 only partly fixes brain-42: serve_brain.sh gives non-8765 brains a fresh DB per start, but the HobbyLM replay spawns muselet_brain directly on default :8765 with no MUSELET_MEMORY_DB. New brain-47 [P1] on cloud/memory-writes d04e26c: 'call my dad back' / 'call me back later' become remember commands, so no call is placed and a bogus person row is stored (repro test_brain_pass63.py). cloud/design-polish bf4ae64 is Swift-only and outside the lane. Suite on main: 18 failed / 2038 passed / 108 skipped (same 18 MLX-stub; −8 passed = removed Shortcuts timer tests). Review repros on main 22F/52P, unchanged. wip/local 973a9b0 is on main@7235a34 (pre-#70) and differs only by #70.

## Open P0/P1 (ranked)
- brain-47 [P1] memory-writes: call requests swallowed as person memory writes — `ml/src/brain/memory/policy.py` (cloud/memory-writes@d04e26c)
- brain-16 [P1] abs_level misreads times, durations, percentages and unrelated words — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-17 [P1] Compound check runs serial route passes before speculative reuse — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-35 [P1] Permission-prompt gate checks the pre-batch observation; a prompt raised mid-batch receives the next keys/type — `ml/src/brain/orchestrator.py` (main@dae4b26@?)
- brain-40 [P1] Final utterance reuses ARGS extracted from the uncased, unpunctuated partial — `ml/src/brain/orchestrator.py` (main@3772f7c)
- brain-42 [P1] Long-term person memory is a global DB shared by every Orchestrator — `ml/src/brain/orchestrator.py` (main@8fb465c via #58)
- brain-22 [P1] Planner history format conflict (runtime 'press #4 -> ok' vs examples '[ok] press #4') — `ml/src/brain/plan_bank.py` (main@27ebd13; cloud/planner-retrieval@9786fa4@dfb66a3)
- brain-41 [P1] ARGS decode cap of 24 tokens silently truncates free-text values — `ml/src/brain/decision.py` (main@2a2c2a9)
- brain-43 [P1] Unverified planner DONE accepted whenever the model verifier errors — `ml/src/brain/orchestrator.py` (main@0b83c3b via #54; cloud/planner-verify@484f5e7)

## Highest-leverage next moves
-1. brain-47 (memory-writes): keep _CALL_PERSON's value at >=2 words, or require 'from now on'/'remember' for 'call my X Y', before merging.
0. brain-46 (now on main): let an explicit 'down'/'up' beat 'bump' in argfix (or drop 'bump' from _UP).
1. brain-42 (now on main): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
2. brain-43 (now on main): when _verify_done returns p_yes None, return 'unverified' (or retry once) instead of accepting a bare DONE.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-27: confirm a grounded click whose target text names send/paper plane even without composer context.
5. brain-44 (now on main): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
