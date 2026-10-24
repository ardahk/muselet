# brain lane digest — pass 46 (2026-10-24T22:42:51Z)

Open: P0 1 / P1 13 / P2 10. Reviewed main 806b0d4, wip/local 6b1006e, w9-safety 6aa332a, memory-lt f0ea345, planner-verify c9de7aa, planner-think 6d14a7a, hands-clock 26d4427, decisions 08dae49.

## Open P0/P1 (ranked)
- brain-39 [P0] Restart/shut down/log out/empty scripts run without CONFIRM — `ml/src/brain/orchestrator.py` (cloud/w9-safety@50a3b25)
- brain-38 [P1] Deterministic message parser hijacks non-messaging commands and other-channel requests — `ml/src/brain/comms.py` (cloud/comms-2@c65ee70)
- brain-16 [P1] abs_level misreads times, durations, percentages and unrelated words — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-17 [P1] Compound check runs serial route passes before speculative reuse — `ml/src/brain/orchestrator.py` (main@fb2cfd0@003d1bb)
- brain-24 [P1] Fuzzy destructive path lookup picks a different existing file — `ml/src/brain/pathfind.py` (cloud/w9-safety@2a7d0df)
- brain-25 [P1] Calculator delivery can type into the wrong frontmost app — `ml/src/brain/orchestrator.py` (cloud/w9-safety@2a7d0df)
- brain-29 [P1] open_app/open site rewrite opens the website for installed Zoom/Teams/Outlook; failed apps RPC caches [] for 60 s — `ml/src/brain/orchestrator.py` (cloud/w9-safety@0a7f383)
- brain-30 [P1] 35B escalation load races: overlapping enables load two copies, and 'off' during a load leaves it resident — `ml/src/brain/orchestrator.py` (cloud/w9-safety@47e0754)
- brain-35 [P1] Permission-prompt gate checks the pre-batch observation; a prompt raised mid-batch receives the next keys/type — `ml/src/brain/orchestrator.py` (main@dae4b26@?)
- brain-40 [P1] Final utterance reuses ARGS extracted from the uncased, unpunctuated partial — `ml/src/brain/orchestrator.py` (main@3772f7c)
- brain-42 [P1] Long-term person memory is a global DB shared by every Orchestrator — `ml/src/brain/orchestrator.py` (cloud/memory-lt@f0ea345)
- brain-22 [P1] Planner history format conflict (runtime 'press #4 -> ok' vs examples '[ok] press #4') — `ml/src/brain/plan_bank.py` (main@27ebd13; cloud/planner-retrieval@9786fa4@dfb66a3)
- brain-41 [P1] ARGS decode cap of 24 tokens silently truncates free-text values — `ml/src/brain/decision.py` (main@2a2c2a9)
- brain-43 [P1] Unverified planner DONE accepted whenever the model verifier errors — `ml/src/brain/orchestrator.py` (cloud/planner-verify@c9de7aa)

## Highest-leverage next moves
1. Merge cloud/w9-safety. It closes the brain-39 P0 and brain-14/24/25/29/30. At 6aa332a: 1621 passed, 8 failures that need real MLX. Its new origins=[None] blocks browser-origin WS hijack; check once on the Mac that the URLSession client still connects.
2. Before merging memory-lt (brain-42): use an in-memory long-term store by default, give tests an autouse tmp MUSELET_MEMORY_DB, and reset memory per bench case.
3. In planner-verify (brain-43), a verifier exception must give 'unverified', not success.
4. Fix brain-41 (24-token ARGS cap) and brain-40 (stale partial ARGS) together: re-run ARGS on the final transcript for free-text skills, with a larger budget there.
5. planner-think is off by default (think_budget=0). Its 8 test_planner_think failures here come from the MLX stub; confirm they pass on the Mac.
