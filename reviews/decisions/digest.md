# decisions — digest (pass 40)

Heads: cloud/decisions ae36620 (unchanged), main 8fb465c (serving it2 tau .35, planner think 512; memory 1/2 merged), wip fe6c209 (== main). Budget: about $142.06 MTD estimated, $5.9 under the $148 stop.
Contamination re-check this pass: 2400 freshly generated code-family items vs JevBench public (231, pinned 609a664) + TD test (pinned 80cb93a): 0 word-13-gram hits. Authored rows / HF v1 data not re-checkable (private, HTTP 401).

## Open P0/P1 (ranked)
1. decisions-37 P1 inline() decider has no temperature attrs; merge with cloud/decisions -> AttributeError in planner verify — ml/src/brain/generic_decide.py:177-190@main 0b83c3b
2. decisions-38 P1 serving tau .65->.35 but claims.md:13 (.913), :163 (tau .55), REPORT.md:12 (tau .65) not updated — pitch/claims.md
3. decisions-32 P1 Full run fails its gate; TD +.0065 vs DeskMind is within noise, test-selected — training/decisions/HANDOFF.md:7-8,82-89
4. decisions-5 P1 4-bit MLX export has no logit parity check vs Tinker; Tinker numbers can't be carried over — training/decisions/export.py
5. decisions-33 P1 near_miss_values makes gold the medoid (~2x chance) — training/decisions/families/core.py:29-49
6. decisions-17 P1 per-family noul priors (counting 7.5% true, numeric 73%) — families/*
7. decisions-14 P1 live_t1 T1 quoted while live_t1 was the tuning set — pitch/claims.md
8. decisions-13 P1 route_acc 'top-1' is tau-gated — pitch/claims.md:13
9. decisions-25 / -4 / -3 P1 data brief stale; noul order flip; route regression unmeasured

## Highest-leverage next moves
- Before merging PR #39 (cloud/decisions) into main, set temperature_probs/conf in GenericMLXDecider.inline() (decisions-37).
- Re-derive {{route_acc}} at serving tau .35 (same metric) and fix claims.md:13,163 / REPORT.md:12 (decisions-38).
- Bench the mlx4 export on the Mac with the same runners before quoting any number (decisions-5).
- results.md: full run is below DeskMind on JevBench and tied on TD on a different backend; label rows test-selected (decisions-32). Keep claims.md:85-86.
- Any data-decisions v2 merge: gate gold-rank uniformity and noul balance per family in build.py (decisions-33, -17).
