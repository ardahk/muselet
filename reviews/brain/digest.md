# brain lane digest — pass 48 (2026-10-24T23:24:00Z)

Open: P0 0 / P1 9 / P2 10. main 46b97f5 and wip/local 719907a: no lane changes since a97fcba.

## Open P0/P1 (ranked)
- brain-38 [P1] Deterministic message parser hijacks non-messaging commands and other-channel requests — `ml/src/brain/comms.py` (cloud/comms-2@c65ee70; fix verified on cloud/safety-brain38@54ca8f6)
- brain-16 [P1] abs_level misreads times, durations, percentages and unrelated words — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-17 [P1] Compound check runs serial route passes before speculative reuse — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-35 [P1] Permission-prompt gate checks the pre-batch observation; a prompt raised mid-batch receives the next keys/type — `ml/src/brain/orchestrator.py` (main@dae4b26@?)
- brain-40 [P1] Final utterance reuses ARGS extracted from the uncased, unpunctuated partial — `ml/src/brain/orchestrator.py` (main@3772f7c)
- brain-42 [P1] Long-term person memory is a global DB shared by every Orchestrator — `ml/src/brain/orchestrator.py` (cloud/memory-lt@cc056af)
- brain-22 [P1] Planner history format conflict (runtime 'press #4 -> ok' vs examples '[ok] press #4') — `ml/src/brain/plan_bank.py` (main@27ebd13; cloud/planner-retrieval@9786fa4@dfb66a3)
- brain-41 [P1] ARGS decode cap of 24 tokens silently truncates free-text values — `ml/src/brain/decision.py` (main@2a2c2a9)
- brain-43 [P1] Unverified planner DONE accepted whenever the model verifier errors — `ml/src/brain/orchestrator.py` (cloud/planner-verify@d22b9a9)

## Highest-leverage next moves
1. Merge cloud/safety-brain38 (brain-38 P1), safety-brain12 (brain-12) and safety-brain18 (brain-18): each branch's repros pass; the only extra failures are MLX stand-in tests.
2. memory-lt (brain-42): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
3. planner-verify (brain-43): a verifier exception must give 'unverified', not accept a bare DONE.
4. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
5. brain-9 (brain-44): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
