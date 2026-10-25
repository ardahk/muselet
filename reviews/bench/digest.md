# bench digest — pass 58 (2026-10-25T01:55Z, main@19d57fb)

P0: 0 | open P1: 14 | open P2: 8

Ranked open P1 (new/changed first):
1. bench-39 brightness argfix (a1fd57f) tuned on HobbyLM sealed-r4 D04-D06 failures; tests quote r4 utterances verbatim. Post-fix r4 is no longer sealed for Muselet.
2. bench-38 proxy stale-client displacement never runs (lock held for the whole session); repro tests/proxy_displace_pass56.py.
3. bench-36 competitor runs not pinned to it2 though claims say "it2 only"; router not recorded.
4. bench-23 it3 chosen on route_v2 whose gold shares judge/policy with its training labels.
5. bench-34 think default = qwen sampler, one seed, +850 ms/step vs greedy.
6. bench-31 planner-LoRA trained with ~21 demos on v2-holdout screens; no holdout eval.
7. bench-16 HobbyLM --exclude-kind calc is Muselet-only (30/125).
8. bench-28 5 v2-holdout golds accept field-clobbering type. Also open: bench-11, -14, -15, -20, -21, -29.

P2 updated: bench-37 memory claims stale (rules holdout .617/.0195; LLM rows pre-gate).

Next moves:
1. HobbyLM r4: quote the pre-a1fd57f run or mark D04-D06 as fixed after observation; paraphrase the test strings; no more fixes validated on r4.
2. Fix proxy lock scope (bench-38) before the next live/HobbyLM run.
3. ROUTER=it2 on competitor runs + router id/sha/tau in result rows.
4. Symmetric HobbyLM exclusions (bench-16).
5. Memory rows -> holdout .617/.0195; THINK_SAMPLER=greedy or >=3 qwen seeds.
