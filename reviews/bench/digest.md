# bench digest — pass 63 (2026-10-25T03:25Z, main@fa0f040)

P0: 0 | open P1: 13 | open P2: 11

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

Pass 60: new P2 bench-40 (unverified, needs Mac) HobbyLM EventKit date parse in 55e38f9 likely still exits 3 on aware+microsecond isoformat; event tasks would skip for Muselet only. Check: on the Mac, look for 'EventKit calendar snapshot failed' in the r4 event-kind records. Reviewed fine: wip/local fd357b3 moves the end-state calendar read into the runner process (EventKit access), reusing the start-state window.

Pass 61 (no new findings): main 13d0486 = the wip fd357b3 change reviewed in pass 60 (end-state calendar read in the runner process, start window reused); fine. bench-40 still open: the Swift parseDate in _read_calendar_events is unchanged and the runner still passes aware+microsecond isoformat strings.

Pass 62: NEW P1 bench-41: 6a37d0c patched vendored calc_checker.swift without updating PROVENANCE.md; verify_provenance raises, so replay.py won't start. Fix: add a harness-patch row with both hashes, rebuild calc_checker, then grade calc for both systems and drop --exclude-kind calc (closes bench-16's calc part).

Pass 63 (no new findings): bench-41 still blocks replay at fa0f040 (provenance hash re-checked). 7235a34 is a good isolation change: bench brains (PORT != 8765) get a fresh MUSELET_MEMORY_DB per start, so user memory isn't touched. Watch (unverified): the store is per brain start, not per case, so long-term memories written in one HobbyLM/live case can carry into later cases in the same run. HobbyLM has no memory, so reset the store per case or report memory hits. fa0f040 design (Clock-only timers) touches no bench/eval code; re-check bench-20 timer gradability on the next r4 run. memory-writes and design-polish don't touch my lane.
