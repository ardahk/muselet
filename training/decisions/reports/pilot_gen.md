# Generic decisions pilot report

## Status

**Stopped at `label`.** The pilot generated 150 code-gold states (25 per family, 450 questions). No code-gold candidate reached the required 95% argmax agreement, so no teacher was selected. Authoring, decontamination, splitting, datum creation, and upload were not run. No Tinker training was run.

The existing code disagreements are in the ignored artifact `runs/decisions/pilot/code_disagreements.jsonl`; generated data and API logs are not committed.

## Spend

Total recorded pilot spend is **$2.3150717** of the **$5.00** hard cap: OpenAI **$1.952329**, Anthropic **$0.362743**. Remaining budget: **$2.6849283**.

The spend includes the initial label attempt, the corrected retry, and seven diagnostics. The first Claude Haiku labeling attempt spent most of its four-token output limit on hidden thinking and yielded mostly null predictions; the retry disabled thinking. All attempts are included in the total below.

| Role/model | Calls | Code decisions covered | Spend | Spend per code decision |
|---|---:|---:|---:|---:|
| Teacher / gpt-4.1-mini | 900 | 450 | $0.294466 | $0.000654 |
| Teacher / gpt-4.1 | 900 | 450 | $1.472328 | $0.003272 |
| Teacher / claude-haiku-5-5 | 2,700 | 450 | $0.341044 | $0.000758 |
| Diagnostics / all models | 7 | — | $0.207234 | — |

No author calls or author rejections were recorded in the pipeline; the author stage was not reached. Diagnostic calls exercised the author APIs while fixing their model-specific reasoning settings.

## Code-gold agreement

Agreement denominators include only valid predictions; null predictions are reported separately as failed calls. No candidate had a permanent 4xx and the unavailable-candidate set is empty.

| Candidate | Correct / valid | Agreement | Failed calls | Selected |
|---|---:|---:|---:|---|
| gpt-4.1-mini | 364 / 445 | 81.80% | 5 | No |
| gpt-4.1 | 375 / 444 | 84.46% | 6 | No |
| claude-haiku-5-5 | 240 / 284 | 84.51% | 166 | No |

All three are below 95%; the selection gate was not relaxed.

| Family | gpt-4.1-mini | gpt-4.1 | claude-haiku-5-5 |
|---|---:|---:|---:|
| Temporal | 64/75 (85.33%; 0 failed) | 61/75 (81.33%; 0 failed) | 48/56 (85.71%; 19 failed) |
| Numeric | 58/75 (77.33%; 0 failed) | 58/75 (77.33%; 0 failed) | 45/47 (95.74%; 28 failed) |
| Counting | 59/75 (78.67%; 0 failed) | 62/75 (82.67%; 0 failed) | 10/12 (83.33%; 63 failed) |
| Multi-hop | 69/75 (92.00%; 0 failed) | 71/75 (94.67%; 0 failed) | 75/75 (100.00%; 0 failed) |
| Long-policy | 64/75 (85.33%; 0 failed) | 73/75 (97.33%; 0 failed) | 40/72 (55.56%; 3 failed) |
| Probability | 50/70 (71.43%; 5 failed) | 50/69 (72.46%; 6 failed) | 22/22 (100.00%; 53 failed) |

## Target sharpness

Mean max-probability and mean entropy (nats) use valid teacher distributions only. Claude’s values are based on 284 labeled decisions because 166 calls failed.

| Teacher | Labeled decisions | Failed calls | Mean max-probability | Mean entropy |
|---|---:|---:|---:|---:|
| gpt-4.1-mini | 445 | 5 | 0.96653 | 0.08170 |
| gpt-4.1 | 444 | 6 | 0.97632 | 0.05211 |
| claude-haiku-5-5 | 284 | 166 | 0.98944 | 0.01956 |

## Generated-data distributions

- Decision types: choice 150, noul 150, score 150.
- Choice option-count histogram: 2: 5, 3: 22, 4: 10, 5: 11, 6: 14, 7: 10, 8: 10, 9: 9, 10: 19, 11: 17, 12: 15, 15: 1, 18: 3, 19: 1, 20: 1, 21: 1, 26: 1.
- Choice gold-position histogram: 1: 30, 2: 21, 3: 28, 4: 11, 5: 11, 6: 9, 7: 3, 8: 10, 9: 4, 10: 11, 11: 4, 12: 5, 14: 1, 15: 1, 18: 1.
- Noul gold balance: true 81, false 69.
- Score gold histogram: level 0: 30, 1: 47, 2: 48, 3: 25.

## Disagreements and blocked work

Four representative disagreements were checked against the generated facts: a notice received after its due date is late; a $1,250 amount with a 15% discount and 2.5% fee on the original price has a 12.5% absolute change; four rows meet the counting criteria; and a 2% prior with 90% sensitivity and an 8% false-positive rate gives a posterior of about 18.7%. In these checked cases, the code-gold answers were consistent with the facts and the teacher disagreement was real. This does not establish that every generated gold label is correct.

The required local `evals/route_v1.jsonl`, `evals/live_t1.jsonl`, and `evals/external/utterances.jsonl` files exist. Decontamination was not run because no teacher was selected. The previously checked JevBench pinned clone and Typed Decisions revision were not used by this stopped run.

Rendered-token mean/p95, decontamination counts, the 20k-decision Tinker training-cost projection, and 20k-decision code-generation extrapolation are **not available**: no teacher was selected and no datums were built. No HF dataset was created or uploaded.
