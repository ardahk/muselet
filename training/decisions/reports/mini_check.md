# Decisions quality mini-check: `pilot`

- Mini-check spend: $0.648333 / $3.00; cumulative spend $6.489253 / $10.00.
- Round spend includes a prior partial mini attempt and schema/parameter diagnostics; diagnostic probes are excluded from author unit rates.
- Code: 30 states, 96 questions, 5 per family.
- Authored: 18 schema-valid states requested from 16 mini / 4 Sonnet; 18 states retained after teacher agreement.
- Questions/state: overall 3.56, code 3.20, authored 4.17; expected code draw range 1–6.
- Nano agreement across all code questions: 94/95 (98.95%); failed calls 5.
- Nano code agreement on the 60-question gate: 59/59 valid majorities (100.00%); failed calls 3; majority coverage 59/60 (98.33%); 95% gate PASS when unavailable questions count as misses.
- Nano vs GPT-4.1-mini authored argmax agreement: 75/86 (87.21%).

## Author retention and unit costs

| Author model | Requested states | Schema-valid / requested | Retained / schema-valid | Retained decisions / labeled decisions | $ / retained decision |
|---|---:|---:|---:|---:|---:|
| gpt-5.4-mini | 16 | 15/16 (93.8%) | 15/15 (100.0%) | 62/75 (82.7%) | $0.004196 |
| claude-sonnet-5-5 | 4 | 3/4 (75.0%) | 3/3 (100.0%) | 13/15 (86.7%) | $0.015714 |

## Agreement by code question type

`{"choice:correct": 24, "noul:correct": 18, "score:correct": 17}`; valid majority counts `{"choice": 24, "noul": 18, "score": 17}`.
- Gate agreement by family: `{"counting:correct": 10, "long_policy:correct": 10, "multi_hop:correct": 10, "numeric:correct": 10, "probability:correct": 9, "temporal:correct": 10}`.

## Position and leakage

- Gold-position quartiles: observed `[12, 4, 14, 12]`, expected `[15.77, 6.13, 13.97, 6.13]`; χ²=7.2536, df=3, p=0.06424.
- Leak test: PASS; 30 states checked, 0 failures.
- Leak details: `[]`.

## Cost projection

- Measured code teacher spend: $0.080121 / 96 generated code decisions ($0.000834/decision); 9,000 decisions: $7.51.
- Authored authoring+label spend projected at retained-decision rates for 7,000 decisions: $45.50.
- Combined projection for 9,000 code-gold plus 7,000 authored decisions: $53.01.

## Decontamination

```json
{
  "rows_before": 48,
  "rows_after": 48,
  "questions_before": 171,
  "questions_after": 171,
  "dropped_text_13gram_rows": 0,
  "dropped_option_questions": 0,
  "remaining_overlaps": {
    "word_13gram": 0,
    "option_sets": 0
  }
}
```

## Artifacts

- Records: `runs/decisions/pilot/records_decontam.jsonl`
- Samples: `training/decisions/reports/pilot_samples.md`
- Author question agreement: 75/86 valid pairs.
