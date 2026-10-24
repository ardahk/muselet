# decisions — digest (pass 32)

Heads: cloud/decisions f6fb133 (unchanged since pass 31; full run done, uncalibrated JevBench .801 / TD .6645, cal + route evals not run), cloud/data-decisions 91de461, main 2a2c2a9 / wip/local 4f963a7 (only new briefs: planner-lora, ui-polish; budget edit), cloud/memory-eval c05944e adds evals/memory_followups.jsonl.
Contamination re-check this pass: 2400 freshly generated code-family items vs JevBench public (231, pinned 609a664) + TD test (pinned 80cb93a): 0 word-13-gram hits. Authored rows / HF v1 data not re-checkable (private, HTTP 401).

## Open P0/P1 (ranked)
1. decisions-32 P1 Full run fails its gate; TD +.0065 vs DeskMind is within noise, test-selected — training/decisions/HANDOFF.md:7-8,82-89
2. decisions-30 P1 MLX backend ignores calibration temperatures — bench/systemone/cli.py:34-36, generic_decide.py:226
3. decisions-31 P1 Calibration fit on template-inflated dev sharpens (T .905/.741) — training/decisions/calibrate.py:43-67
4. decisions-33 P1 near_miss_values makes gold the medoid (~2x chance) — training/decisions/families/core.py:29-49
5. decisions-17 P1 per-family noul priors (counting 7.5% true, numeric 73%) — families/*
6. decisions-14 P1 live_t1 T1 quoted while live_t1 was the tuning set — pitch/claims.md
7. decisions-13 P1 route_acc 'top-1' is tau-gated — pitch/claims.md:13
8. decisions-25 / -5 / -4 / -3 P1 data brief stale; bf16 vs Mac mixing; noul order flip; route regression unmeasured

## Highest-leverage next moves
- Before any 'calibrated' number: wire temperatures into GenericMLXDecider (decisions-30) and refit on non-template dev or ship T=1 (decisions-31).
- results.md: full run is below DeskMind on JevBench and tied on TD on a different backend; label rows test-selected (decisions-32). Keep claims.md:85-86.
- Any data-decisions v2 merge: gate gold-rank uniformity and noul balance per family in build.py (decisions-33, -17).
- Budget: user allows full $150, hard stop $148 MTD; only planner-lora (<= $7, abort >= $142) is approved to train. Console read $136.22 at 21:30Z; 136.22 + 7 + decisions cal cross-check (~$0.27 est.) = ~$143.5, which leaves ~$4.5 margin, so no other lane may train. Any decisions retrain needs lead approval plus a written estimate.
- Route stays it2; this adapter is System One only (decisions-3).
