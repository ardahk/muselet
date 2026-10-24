# brain lane digest — pass 47 (2026-10-24T22:59:53Z)

Open: P0 1 / P1 9 / P2 10. main a97fcba (w9-safety merged), wip/local ac41cd2 (still on main@806b0d4).

## Open P0/P1 (ranked)
- brain-39 [P0] Restart/shut down/log out/empty scripts run without CONFIRM — `ml/src/brain/orchestrator.py` (cloud/w9-safety@50a3b25)
- brain-38 [P1] Deterministic message parser hijacks non-messaging commands and other-channel requests — `ml/src/brain/comms.py` (cloud/comms-2@c65ee70)
- brain-16 [P1] abs_level misreads times, durations, percentages and unrelated words — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-17 [P1] Compound check runs serial route passes before speculative reuse — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-35 [P1] Permission-prompt gate checks the pre-batch observation; a prompt raised mid-batch receives the next keys/type — `ml/src/brain/orchestrator.py` (main@dae4b26@?)
- brain-40 [P1] Final utterance reuses ARGS extracted from the uncased, unpunctuated partial — `ml/src/brain/orchestrator.py` (main@3772f7c)
- brain-42 [P1] Long-term person memory is a global DB shared by every Orchestrator — `ml/src/brain/orchestrator.py` (cloud/memory-lt@cc056af)
- brain-22 [P1] Planner history format conflict (runtime 'press #4 -> ok' vs examples '[ok] press #4') — `ml/src/brain/plan_bank.py` (main@27ebd13; cloud/planner-retrieval@9786fa4@dfb66a3)
- brain-41 [P1] ARGS decode cap of 24 tokens silently truncates free-text values — `ml/src/brain/decision.py` (main@2a2c2a9)
- brain-43 [P1] Unverified planner DONE accepted whenever the model verifier errors — `ml/src/brain/orchestrator.py` (cloud/planner-verify@d22b9a9)

## Highest-leverage next moves
1. memory-lt (brain-42): default to an in-memory long-term store, or have the HobbyLM replay and live harness set a per-case MUSELET_MEMORY_DB and reset WorkingMemory between cases.
2. planner-verify (brain-43): a verifier exception must give 'unverified'. Merging it also fixes main's test_plan_bank default-bank failure.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-38: gate the deterministic message parser on a messaging intent and channel.
5. brain-9 (brain-44): guard named_browser so browsers named in the query don't count; fix the branch's own failing web_search test.
