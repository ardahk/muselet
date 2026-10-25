# brain lane digest — pass 66 (2026-10-25T04:18:00Z)

Open: P0 0 / P1 9 / P2 12. main b340f24 merged memory-writes (#74), fix-apps-notes (#75), fix-email-reply (#76), test-strategy (#79) and planner-aux (#82; ships the LoRA planner with no few-shot, retrieval k=1, THINK=0, plus the base 4B as aux for non-DSL text and decide calls). That brings brain-47 (P1, call requests saved as memories) and brain-48 (P2, act open keeps the spoken name) onto main. Their repros test_brain_pass63.py (3F) and test_brain_pass64.py (1F) now fail on main, so main's review repros are 26F/52P. brain-22 still reaches the LoRA planner through the k=1 retrieval demo block. #76, #79 and the rest of #82 match the branch heads I reviewed with no issues. wip/local 94f6fe9 is a snapshot on main@b340f24, and its lane matches main. New branch cloud/open-ended fd87f69: I found no defect. It adds app hints (--planner-app-hints, default off) and an open-ended planner redirect (--open-ended-route, default off). When on, safe labels, including ANSWER (e.g. 'what song is playing on spotify'), are sent to the planner if an app hint matches. It also adds APP_SCHEMES (spotify:, maps:, slack: ...), which bypass fix_url and the browser choice. Spotify/Music play, pause, next and previous scripts skip the script confirm, while any other Spotify script still requires it. Note: the app-tips block, when on, adds planner input the LoRA wasn't trained on (brain-22 class). New branch cloud/planner-aux 387c3b4 = #82 pre-merge, no issues. Suites: main 18F/2182P/4xfail, open-ended 18F/2078P, planner-aux 18F/2052P (only the MLX-stub failures).

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
-2. brain-48 (now on main): set params['name']=resolved for act open (or drop 'name') before merging.
-1. brain-47 (now on main): keep _CALL_PERSON's value at >=2 words, or require 'from now on'/'remember' for 'call my X Y', before merging.
0. brain-46 (now on main): let an explicit 'down'/'up' beat 'bump' in argfix (or drop 'bump' from _UP).
1. brain-42 (now on main): default to an in-memory long-term store, or give each HobbyLM/live case a fresh MUSELET_MEMORY_DB and WorkingMemory.
2. brain-43 (now on main): when _verify_done returns p_yes None, return 'unverified' (or retry once) instead of accepting a bare DONE.
3. brain-41 + brain-40: re-run ARGS on the final transcript for free-text skills, with a larger decode budget.
4. brain-27: confirm a grounded click whose target text names send/paper plane even without composer context.
5. brain-44 (now on main): only take a browser name from an 'in/with/using <browser>' or 'open <browser>' phrase, not from the search query.
