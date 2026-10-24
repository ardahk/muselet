# decisions — digest (pass 39)

Heads: cloud/decisions ae36620 (rebased on 18c139f, import move only), main 0b83c3b (planner-verify #54 merged -> decisions-37 now lands on merge of PR #39), wip e4f4331. Budget: about $142.06 MTD estimated, $5.9 under the $148 stop.
Contamination re-check this pass: 2400 freshly generated code-family items vs JevBench public (231, pinned 609a664) + TD test (pinned 80cb93a): 0 word-13-gram hits. Authored rows / HF v1 data not re-checkable (private, HTTP 401).

## Open P0/P1 (ranked)
1. decisions-37 P1 inline() decider has no temperature attrs; merge with cloud/decisions -> AttributeError in planner verify — ml/src/brain/generic_decide.py:177-190@main 0b83c3b
2. decisions-32 P1 Full run fails its gate; TD +.0065 vs DeskMind is within noise, test-selected — training/decisions/HANDOFF.md:7-8,82-89
3. decisions-5 P1 4-bit MLX export has no logit parity check vs Tinker; Tinker numbers can't be carried over — training/decisions/export.py
4. decisions-33 P1 near_miss_values makes gold the medoid (~2x chance) — training/decisions/families/core.py:29-49
5. decisions-17 P1 per-family noul priors (counting 7.5% true, numeric 73%) — families/*
6. decisions-14 P1 live_t1 T1 quoted while live_t1 was the tuning set — pitch/claims.md
7. decisions-13 P1 route_acc 'top-1' is tau-gated — pitch/claims.md:13
8. decisions-25 / -4 / -3 P1 data brief stale; noul order flip; route regression unmeasured

## Highest-leverage next moves
- Before merging PR #39 (cloud/decisions) into main, set temperature_probs/conf in GenericMLXDecider.inline() (decisions-37).
- Bench the mlx4 export on the Mac with the same runners before quoting any number (decisions-5).
- results.md: full run is below DeskMind on JevBench and tied on TD on a different backend; label rows test-selected (decisions-32). Keep claims.md:85-86.
- Any data-decisions v2 merge: gate gold-rank uniformity and noul balance per family in build.py (decisions-33, -17).
- Budget: MTD ~= $136.22 (console 21:30Z) + planner-lora $5.84 est. = ~$142.1, so ~$5.9 left to the $148 stop. Only the decisions calibrated cross-check (~$0.27 est.) fits; no decisions retrain. Re-read the console before any sampling (planner-lora brief stops sampling at $146).
