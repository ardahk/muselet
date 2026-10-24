# Lane: decisions (generalist System One training + benchmark claims)

Watch branch `cloud/decisions` (and cloud A's `cloud/data-pipeline` where it feeds the multi-task run).
Priorities, highest first:
1. Contamination: any training item overlapping JevBench public (231), the typed-decisions test, `evals/route_v1.jsonl`,
   `evals/live_t1.jsonl` or `evals/external/utterances.jsonl` (word 13-gram or identical option sets). Re-run the
   check yourself on a sample; P0 if anything leaks.
2. Render parity: training tokens must equal what `bench/systemone` + `ml/src/brain/generic_decide.py` produce at
   inference. P0 on any mismatch.
3. Claims hygiene: zero-shot vs fitted-on-train labelling, same runner/scorer as the published benchmarks, calibration
   fitted only on our own dev data, route regression reported.
4. Label quality: sample 30 synthetic items per competency; verifiable items must have code-computed gold; flag
   teacher errors and label shortcuts (the answer leaking from option wording or order).
5. Budget discipline: every Tinker run has a written hypothesis and estimate first; over $25 needs the lead's OK.
