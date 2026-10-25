# bench digest — pass 56 (2026-10-25T01:25Z, main@9be963d)

P0: 0 | open P1: 13 | open P2: 8

Ranked open P1 (new/changed first):
1. bench-38 proxy stale-client displacement (517e056) never runs: session holds _connection_lock, new client hangs until stale one closes (repro: tests/proxy_displace_pass56.py).
2. bench-36 competitor runs not pinned to it2 though claims say "it2 only"; router not recorded in results.
3. bench-23 it3 chosen on route_v2 whose gold shares judge/policy with its training labels.
4. bench-34 think default = qwen sampler on one seed, +850 ms/step vs greedy.
5. bench-31 planner-LoRA trained with ~21 demos on v2-holdout screens; no holdout eval.
6. bench-16 HobbyLM --exclude-kind calc is Muselet-only (30/125).
7. bench-28 5 v2-holdout golds accept field-clobbering type.
8. bench-11, -14, -15, -20, -21, -29 unchanged.

New P2: bench-37 memory claims stale; holdout now .617 / .0195 (tune .97). Resolved: bench-35.

Next moves:
1. Fix proxy lock scope (bench-38) before the next HobbyLM/live run; add a held-open-client test.
2. ROUTER=it2 on competitor runs + router id/sha/tau in result rows.
3. Memory row -> holdout .617 / .0195 @ 9be963d.
4. THINK_SAMPLER=greedy or >=3 qwen seeds.
5. Symmetric HobbyLM exclusions; fix 5 v2-holdout golds.
