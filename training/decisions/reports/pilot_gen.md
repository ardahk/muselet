# Generation pilot: `pilot`

- Cumulative API spend: OpenAI $4.543336; Anthropic $1.297583; total $5.840919.
- Amendment-2 API spend: OpenAI $2.591008; Anthropic $0.934840; total $3.525848.
- Code-gold teacher selected: `gpt-5.4-nano`.
- Retained decisions: 470 across 166 states.

## Cost by role

| Role | USD per decision | Calls/decisions logged | USD total / decision* |
|---|---:|---:|---:|
| author | $0.086036 | 60 | $2.150907 |
| diagnostic | $0.029605 | 7 | $0.207234 |
| gate:gpt-5.4-mini | $0.002630 | 150 | $0.394566 |
| gate:gpt-5.4-nano | $0.000759 | 150 | $0.113868 |
| paraphrase | $0.002009 | 110 | $0.220974 |
| teacher:claude-haiku-5-5 | $0.000758 | 450 | $0.341044 |
| teacher:claude-sonnet-5-5 | $0.011148 | 31 | $0.345578 |
| teacher:gpt-4.1 | $0.003208 | 481 | $1.543176 |
| teacher:gpt-4.1-mini | $0.000654 | 450 | $0.294466 |
| teacher:gpt-5.4-nano | $0.000764 | 300 | $0.229107 |

*Role totals include all logged pilot rounds; totals are divided by the corresponding decision count, and Claude sampling calls share a decision ID.

## Code-gold agreement by family and teacher

```json
{
  "gpt-5.4-nano": {
    "overall": {
      "correct": 148,
      "total": 150,
      "agreement": 0.9866666666666667,
      "failed_calls": 1,
      "failed_questions": 0,
      "no_majority": 0,
      "mean_max_probability": 0.9935762793225111,
      "mean_entropy_nats": 0.03196995612572725
    },
    "by_family": {
      "temporal": {
        "correct": 23,
        "total": 25,
        "agreement": 0.92,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9863698361105274,
        "mean_entropy_nats": 0.05147940845006059
      },
      "numeric": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9961169618141127,
        "mean_entropy_nats": 0.030726452262472503
      },
      "counting": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9973746130091613,
        "mean_entropy_nats": 0.020769516416670547
      },
      "multi_hop": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9975343666394505,
        "mean_entropy_nats": 0.01950601975742988
      },
      "long_policy": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9964668719259553,
        "mean_entropy_nats": 0.02795426852162623
      },
      "probability": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 1,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9875950264358593,
        "mean_entropy_nats": 0.04138407134610376
      }
    },
    "by_type": {
      "choice": {
        "correct": 48,
        "total": 50,
        "agreement": 0.96,
        "failed_calls": 1,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9838997852809792,
        "mean_entropy_nats": 0.07082868778199689
      },
      "noul": {
        "correct": 50,
        "total": 50,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9990019960079841,
        "mean_entropy_nats": 0.007893467179205428
      },
      "score": {
        "correct": 50,
        "total": 50,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9978270566785699,
        "mean_entropy_nats": 0.01718771341597944
      }
    },
    "cost_usd": 0.11386775,
    "cost_per_decision": 0.0007591183333333334,
    "unavailable": null
  },
  "gpt-5.4-mini": {
    "overall": {
      "correct": 146,
      "total": 147,
      "agreement": 0.9931972789115646,
      "failed_calls": 42,
      "failed_questions": 3,
      "no_majority": 0,
      "mean_max_probability": 0.9952094733372134,
      "mean_entropy_nats": 0.02846656110078426
    },
    "by_family": {
      "temporal": {
        "correct": 23,
        "total": 24,
        "agreement": 0.9583333333333334,
        "failed_calls": 9,
        "failed_questions": 1,
        "no_majority": 0,
        "mean_max_probability": 0.9860461479608574,
        "mean_entropy_nats": 0.052608744874291756
      },
      "numeric": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 4,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9961169618141127,
        "mean_entropy_nats": 0.030726452262472503
      },
      "counting": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9973746130091613,
        "mean_entropy_nats": 0.020769516416670547
      },
      "multi_hop": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 15,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9975343666394505,
        "mean_entropy_nats": 0.01950601975742988
      },
      "long_policy": {
        "correct": 25,
        "total": 25,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9964668719259553,
        "mean_entropy_nats": 0.02795426852162623
      },
      "probability": {
        "correct": 23,
        "total": 23,
        "agreement": 1.0,
        "failed_calls": 14,
        "failed_questions": 2,
        "no_majority": 0,
        "mean_max_probability": 0.9975375954257738,
        "mean_entropy_nats": 0.01948122525553501
      }
    },
    "by_type": {
      "choice": {
        "correct": 49,
        "total": 50,
        "agreement": 0.98,
        "failed_calls": 8,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9889671578480836,
        "mean_entropy_nats": 0.05955684042085878
      },
      "noul": {
        "correct": 50,
        "total": 50,
        "agreement": 1.0,
        "failed_calls": 0,
        "failed_questions": 0,
        "no_majority": 0,
        "mean_max_probability": 0.9990019960079841,
        "mean_entropy_nats": 0.007893467179205428
      },
      "score": {
        "correct": 47,
        "total": 47,
        "agreement": 1.0,
        "failed_calls": 34,
        "failed_questions": 3,
        "no_majority": 0,
        "mean_max_probability": 0.9978156359099357,
        "mean_entropy_nats": 0.01727806599600162
      }
    },
    "cost_usd": 0.394566,
    "cost_per_decision": 0.00263044,
    "unavailable": null
  },
  "claude-haiku-5-5": {
    "overall": {
      "correct": 0,
      "total": 0,
      "agreement": null,
      "failed_calls": 174,
      "failed_questions": 150,
      "no_majority": 0,
      "mean_max_probability": null,
      "mean_entropy_nats": null
    },
    "by_family": {
      "temporal": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 49,
        "failed_questions": 25,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "numeric": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 25,
        "failed_questions": 25,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "counting": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 25,
        "failed_questions": 25,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "multi_hop": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 25,
        "failed_questions": 25,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "long_policy": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 25,
        "failed_questions": 25,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "probability": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 25,
        "failed_questions": 25,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      }
    },
    "by_type": {
      "choice": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 62,
        "failed_questions": 50,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "noul": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 56,
        "failed_questions": 50,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      },
      "score": {
        "correct": 0,
        "total": 0,
        "agreement": null,
        "failed_calls": 56,
        "failed_questions": 50,
        "no_majority": 0,
        "mean_max_probability": null,
        "mean_entropy_nats": null
      }
    },
    "cost_usd": 0,
    "cost_per_decision": 0.0,
    "unavailable": {
      "status_code": 400
    }
  }
}
```

## Failed calls and unavailable candidates

- Failed/null teacher predictions: 24 (excluded from agreement denominators).
```json
{
  "gpt-5.4-nano": 18,
  "claude-sonnet-5-5": 6
}
```
Unavailable model statuses:
```json
{
  "claude-haiku-5-5": {
    "status_code": 400
  }
}
```

## Teacher target sharpness

Mean maximum probability and Shannon entropy (nats) are computed over non-null raw teacher distributions.
```json
{
  "code_gate": {
    "gpt-5.4-nano": {
      "correct": 148,
      "total": 150,
      "agreement": 0.9866666666666667,
      "failed_calls": 1,
      "failed_questions": 0,
      "no_majority": 0,
      "mean_max_probability": 0.9935762793225111,
      "mean_entropy_nats": 0.03196995612572725
    },
    "gpt-5.4-mini": {
      "correct": 146,
      "total": 147,
      "agreement": 0.9931972789115646,
      "failed_calls": 42,
      "failed_questions": 3,
      "no_majority": 0,
      "mean_max_probability": 0.9952094733372134,
      "mean_entropy_nats": 0.02846656110078426
    },
    "claude-haiku-5-5": {
      "correct": 0,
      "total": 0,
      "agreement": null,
      "failed_calls": 174,
      "failed_questions": 150,
      "no_majority": 0,
      "mean_max_probability": null,
      "mean_entropy_nats": null
    }
  },
  "authored": {
    "gpt-4.1": {
      "labeled_decisions": 31,
      "failed_calls": 0,
      "mean_max_probability": 0.9988313580802283,
      "mean_entropy_nats": 0.005027156802996667
    },
    "claude-sonnet-5-5": {
      "labeled_decisions": 25,
      "failed_calls": 6,
      "mean_max_probability": 1.0,
      "mean_entropy_nats": 0.0
    }
  }
}
```

## Rejections

- Rejected questions/items: 49; generated records: 166.
- Rejection rate by generated record: 29.5%.
```json
{
  "selected teacher's sampled distribution disagreed with code gold": 5,
  "JSONDecodeError: Unterminated string starting at: line 13 column 37 (char 9052)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 5027 (char 5026)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 4434 (char 4433)": 1,
  "JSONDecodeError: Extra data: line 3 column 1 (char 4831)": 1,
  "ValueError: q1: authored answer True is not an option": 3,
  "JSONDecodeError: Unterminated string starting at: line 31 column 28 (char 8952)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 4328 (char 4327)": 1,
  "ProtocolError: score criteria must be a list of 2..10 levels": 3,
  "JSONDecodeError: Expecting ',' delimiter: line 1 column 5566 (char 5565)": 1,
  "ValueError: q1: authored answer False is not an option": 6,
  "ValueError: q1: choice criteria are not a map": 3,
  "JSONDecodeError: Unterminated string starting at: line 21 column 9 (char 8686)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 5328 (char 5327)": 1,
  "JSONDecodeError: Unterminated string starting at: line 2 column 12 (char 13)": 1,
  "JSONDecodeError: Unterminated string starting at: line 36 column 9 (char 9852)": 1,
  "JSONDecodeError: Unterminated string starting at: line 25 column 20 (char 7880)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 5018 (char 5017)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 8478 (char 8477)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 4555 (char 4554)": 1,
  "JSONDecodeError: Unterminated string starting at: line 18 column 42 (char 9084)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 4603 (char 4602)": 1,
  "JSONDecodeError: Unterminated string starting at: line 38 column 20 (char 8322)": 1,
  "ValueError: q2: authored answer False is not an option": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 5087 (char 5086)": 1,
  "JSONDecodeError: Unterminated string starting at: line 12 column 20 (char 9097)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 4902 (char 4901)": 1,
  "JSONDecodeError: Unterminated string starting at: line 1 column 4872 (char 4871)": 1,
  "GPT-4.1 argmax disagreed with Claude majority or was unlabeled": 6
}
```

## Histograms

- Question types: `{"choice": 158, "noul": 158, "score": 154}`
- Option counts: `{"10": 13, "11": 10, "12": 12, "15": 1, "18": 1, "19": 1, "2": 185, "26": 1, "3": 125, "4": 45, "5": 24, "6": 12, "7": 14, "8": 13, "9": 13}`
- Gold positions (0-based): `{"0": 161, "1": 164, "10": 1, "11": 2, "16": 1, "2": 67, "3": 25, "4": 18, "5": 12, "6": 9, "7": 4, "8": 4, "9": 2}`
- Gold-position chi-square, conditional on each question's option count: 4.9907 (df=3, p=0.17248).
- Noul balance: `{"false": 77, "true": 81}`
- Score levels: `{"0": 50, "1": 49, "2": 44, "3": 11}`

## Decontamination

```json
{
  "rows_before": 166,
  "rows_after": 166,
  "questions_before": 470,
  "questions_after": 470,
  "dropped_text_13gram_rows": 0,
  "dropped_option_questions": 0,
  "remaining_overlaps": {
    "word_13gram": 0,
    "option_sets": 0
  }
}
```

## Render and cost projections

- Mean rendered input tokens/Datum: 659.5.
- p95 rendered input tokens/Datum: 2167.
- 20k decision Tinker projection at $0.73/M train tokens: $9.6427 (using mean input tokens + one target token).
- 20k code-teacher generation projection using `gpt-5.4-nano`: $15.2433; computed from actual selected-teacher API usage per labeled code decision.

## Teacher disagreements

See `runs/decisions/pilot/code_disagreements.jsonl`; the pilot stores the complete state, question, gold label, and each candidate distribution for manual inspection.
