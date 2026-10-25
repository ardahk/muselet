# brain lane digest — pass 65 (2026-10-25T04:02:00Z)

Open: P0 0 / P1 9 / P2 12. main 4150ecb and wip/local b7b7840 haven't moved. New brain-49 [P2] on cloud/fix-same-tab 065e65f: with a browser page focused, _page_task_for runs before the messaging redirect and the router, and its unanchored 'on this page' alternative sends 'text mom what's on this page' and 'remind me to check the price on this page tomorrow' to the planner as page tasks (repro test_brain_pass65.py: 3F on fix-same-tab, skipped on main). The rest of fix-same-tab looks right: same_tab is a code-only arg, it's skipped when 'new tab/window' is said or a different browser is named, web_search only reuses a search-engine tab, and HandsKit reports same_tab_used. Note: any open_url with a browser in front now replaces the current tab by design. cloud/fallback 2ef5805 only narrows the messaging exclusion to compose_email/draft_email (send_message is still excluded by label, and fallback is still safe-risk only and off by default). Its 5 stale test fakes are still unfixed. cloud/test-strategy 96c96d2 adds the offline brain.replay (recorded hands; unrecorded RPCs raise replay_unrecorded) and records ctx, routed text and the args skill in traces, and I found no issues. Suites (excluding the 18 MLX-stub failures): fix-same-tab +0 (2047P), test-strategy +0 (2042P, 8 xfail = the strict-xfail user-test regressions), fallback +5 (stale fakes). Review repros are 22F/55P on all three. brain-47 (memory-writes) and brain-48 (fix-apps-notes) are unchanged.

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
-3. brain-49 (fix-same-tab): check comms.parse_message before _page_task_for, or anchor 'on this page' to page-action verbs, before merging.
-2. brain-48 (fix-apps-notes): set params['name']=resolved for act open (or drop 'name') before merging.
-1. brain-47 (memory-writes): keep _CALL_PERSON's value at >=2 words, or require 'from now on'/'remember' for 'call my X Y', before merging.
0. brain-46 (now on main): let an explicit 'down'/'up' beat 'bump' in argfix (or drop 'bump' from _UP).
1. brain-42 (now on main): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
2. brain-43 (now on main): when _verify_done returns p_yes None, return 'unverified' (or retry once) instead of accepting a bare DONE.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-27: confirm a grounded click whose target text names send/paper plane even without composer context.
5. brain-44 (now on main): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
