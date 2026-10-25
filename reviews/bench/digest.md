# bench digest — pass 59 (2026-10-25T02:25Z, main@f5b4606)

P0: 0 | open P1: 12 | open P2: 10

Ranked open P1:
1. bench-36 competitor runs not pinned to it2 though claims say "it2 only"; router not recorded in results.
2. bench-23 it3 chosen on route_v2 whose gold shares judge/policy with its training labels.
3. bench-34 think default = qwen sampler, one seed, +850 ms/step vs greedy.
4. bench-31 planner-LoRA trained with ~21 demos on v2-holdout screens; no holdout eval.
5. bench-16 HobbyLM --exclude-kind calc is Muselet-only (30/125).
6. bench-28 5 v2-holdout golds accept field-clobbering type.
7. bench-11, -14, -15, -20, -21, -29 unchanged.

Downgraded this pass: bench-38 (proxy wedge mitigated by force_release; forced releases not recorded, displacement branch dead) and bench-39 (r4 strings paraphrased out of tests; r4 disclosure still needed). Also P2: bench-37 memory claims stale (holdout .617/.0195).

Next moves:
1. Record forced_releases / slot_forced per case and in the run summary (bench-38).
2. ROUTER=it2 on competitor runs + router id/sha/tau in result rows (bench-36).
3. Disclose r4 D04-D06 fixed-after-observation; report r4 with and without them (bench-39).
4. Symmetric HobbyLM exclusions (bench-16).
5. THINK_SAMPLER=greedy or >=3 qwen seeds (bench-34).
