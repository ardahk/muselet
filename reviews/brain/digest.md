# brain lane digest — pass 64 (2026-10-25T03:46:00Z)

Open: P0 0 / P1 9 / P2 11. main 4150ecb and wip/local b7b7840 are docs-only (briefs), with no lane change. New brain-48 [P2] on cloud/fix-apps-notes 1ccb123: planner `open` acts keep the raw spoken name because HandsKit reads 'name' before the resolved 'app' (repro test_brain_pass64.py). brain-47 is still open on memory-writes 88ccf06; Forget Everything now also wipes workflows and memory demos, which looks correct. Reviewed with no defect found: fix-pending dba9094 (new commands during confirm run as a task off the receive loop; cancelling sends confirm_cancel; pending ask/slot/comms are superseded only by command-verb utterances that aren't deictic), fix-email-reply 805223b (web replies still go through the confirm and a draft-signature check before cmd+return), hands-clock-verify a4d6463 (timer reply wording only), fallback 6e40c3e (default off; safe-risk skills only; timeouts, permission and cancel errors are excluded from the fallback). Note: fallback's --planner-context adds a 'Context at request'/'Screen' block to the planner's first turn that isn't in the training format (same concern as brain-22), and it's off by default. Branch suites (excluding the 18 MLX-stub failures): fallback +5 and fix-pending +1 failures, all from test fakes that weren't updated (fake_serve() without fallback_planner/planner_context; fake Orch without confirm_interrupt), not product defects. Main is 18F/2038P/108S, and review repros on main are 22F/55P.

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
-2. brain-48 (fix-apps-notes): set params['name']=resolved for act open (or drop 'name') before merging.
-1. brain-47 (memory-writes): keep _CALL_PERSON's value at >=2 words, or require 'from now on'/'remember' for 'call my X Y', before merging.
0. brain-46 (now on main): let an explicit 'down'/'up' beat 'bump' in argfix (or drop 'bump' from _UP).
1. brain-42 (now on main): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
2. brain-43 (now on main): when _verify_done returns p_yes None, return 'unverified' (or retry once) instead of accepting a bare DONE.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-27: confirm a grounded click whose target text names send/paper plane even without composer context.
5. brain-44 (now on main): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
