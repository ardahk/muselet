from __future__ import annotations

import random

from .core import NAMES, choose_domain, question_specs, record


def posterior_positive(base_rate: float, sensitivity: float, false_positive: float) -> float:
    numerator = base_rate * sensitivity
    return numerator / (numerator + (1 - base_rate) * false_positive)


def expected_value(probability: float, reward: float, cost: float) -> float:
    return round(probability * reward - cost, 2)


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    name = rng.choice(NAMES)
    base = rng.choice((0.005, 0.02, 0.05, 0.10, 0.25))
    sensitivity, false_positive = 0.9, 0.08
    posterior = posterior_positive(base, sensitivity, false_positive)
    p_a, p_b = rng.choice(((0.25, 0.40), (0.55, 0.35), (0.30, 0.20)))
    ev_a, ev_b = expected_value(p_a, 100, 20), expected_value(p_b, 80, 12)
    better = "option_a" if ev_a > ev_b else "option_b"
    if rng.randrange(2):
        state = (
            f"{name} evaluates a {domain} screening signal. The base rate is {base:.1%}; sensitivity is 90%; "
            f"false-positive rate is 8%. Separately, option A succeeds with probability {p_a:.0%}, pays $100 "
            f"on success, and costs $20. Option B succeeds with probability {p_b:.0%}, pays $80 on success, "
            "and costs $12. Compare expected net value when asked, not probability alone."
        )
    else:
        state = (
            f"Decision memo — {domain}, prepared by {name}. Screening prevalence={base:.1%}, true-positive "
            "rate=0.90, false-positive rate=0.08. Intervention A: probability of success "
            f"{p_a:.0%}, reward $100, cost $20. Intervention B: probability of success {p_b:.0%}, "
            "reward $80, cost $12. Expected net value equals probability × reward minus cost."
        )
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            if rng.choice(("value", "probability")) == "value":
                specs.append((kind, "Which intervention has the higher expected net value?", better,
                              {"option_a": f"Expected net value ${ev_a:.2f}.",
                               "option_b": f"Expected net value ${ev_b:.2f}."}, None))
            else:
                most_likely = "option_a" if p_a > p_b else "option_b"
                specs.append((kind, "Which intervention has the higher probability of success?", most_likely,
                              {"option_a": f"Success probability {p_a:.0%}.",
                               "option_b": f"Success probability {p_b:.0%}."}, None))
        elif kind == "noul":
            specs.append((kind, "Is the posterior probability after a positive signal above 50%?",
                          "true" if posterior > 0.5 else "false", None, None))
        else:
            band = "0" if posterior < 0.10 else "1" if posterior < 0.30 else "2"
            specs.append((kind, "Which band contains the posterior probability after a positive signal?",
                          band, None, ["Below 10%", "10-29.9%", "30% or higher"]))
    return record(rng, "probability", domain, state, specs)
