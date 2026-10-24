# Pilot review samples

**Blocked:** the label stage stopped because none of the three code-gold candidates reached the required 95% overall agreement. There is no selected teacher target, and the authoring stage did not run, so the requested set of 12 final training samples (including six authored examples) is not available. No targets were fabricated or selected below the threshold.

The 194 code-gold disagreements from the latest labeling attempt, including full generated states, questions, code gold, teacher predictions, and valid target distributions, are available in the ignored file `runs/decisions/pilot/code_disagreements.jsonl` for review. They are not committed.

Four disagreements were manually checked against their source facts: the late-notice temporal case, the discount-plus-fee numeric case, the four-row counting case, and the Bayesian base-rate case. Those individual code-gold answers matched the facts; they do not validate all generated examples.
