from __future__ import annotations

import random

from .core import NAMES, article, choose_domain, question_specs, record


def posterior_positive(base_rate: float, sensitivity: float, false_positive: float) -> float:
    numerator = base_rate * sensitivity
    return numerator / (numerator + (1 - base_rate) * false_positive)


def expected_value(probability: float, reward: float, cost: float) -> float:
    return round(probability * reward - cost, 2)


def _money_options(answer: float) -> dict[str, str]:
    options = {}
    for offset in range(-12, 14):
        value = round(answer + offset * 1.0, 2)
        key = f"usd_{value:.2f}".replace(".", "_")
        options[key] = f"The expected net value is ${value:.2f} under the stated success rate and cost."
    return options


def generate(rng: random.Random, domain: str, n_questions: int, types: list[str]) -> dict:
    domain = choose_domain(rng, domain)
    analyst = rng.choice(NAMES)
    if rng.choice(("screening", "proposal")) == "screening":
        base = rng.choice((0.005, 0.02, 0.05, 0.10, 0.25))
        sensitivity, false_positive = 0.9, 0.08
        posterior = posterior_positive(base, sensitivity, false_positive)
        threshold = rng.choice((0.10, 0.30, 0.50))
        state = rng.choice((
            f"SCREENING REVIEW — {domain}\nPrepared by: {analyst}\n"
            f"Prevalence in the screened population: {base:.1%}\n"
            f"Test sensitivity: {sensitivity:.0%}\nFalse-positive rate: {false_positive:.0%}\n"
            f"Route a positive result for specialist review only when its posterior probability exceeds {threshold:.0%}.",
            f"{analyst} is reviewing {article(domain)} {domain} screening protocol. The condition's base rate is {base:.1%}; "
            f"the test detects true cases with {sensitivity:.0%} sensitivity and has a {false_positive:.0%} "
            f"false-positive rate. The referral threshold is strictly above {threshold:.0%} posterior probability.",
        ))
        options = {}
        for offset in range(-12, 14):
            value = max(0.0, min(1.0, posterior + offset * 0.005))
            key = f"posterior_{value:.4f}".replace(".", "_")
            options[key] = f"The posterior probability of a true case is {value:.2%}."
        specs = []
        for kind in question_specs(types, n_questions):
            if kind == "choice":
                specs.append((kind, "What is the posterior probability of a true case after a positive result?",
                              f"posterior_{posterior:.4f}".replace(".", "_"), options, None))
            elif kind == "noul":
                specs.append((kind, f"Does the positive result exceed the strict {threshold:.0%} referral threshold?",
                              "true" if posterior > threshold else "false",
                              {"false": f"The posterior probability {posterior:.2%} is not above {threshold:.0%}.",
                               "true": f"The posterior probability {posterior:.2%} is above {threshold:.0%}."}, None))
            else:
                score = "0" if posterior < 0.10 else "1" if posterior < 0.30 else "2"
                specs.append((kind, "Which evidence-risk tier contains the posterior probability?",
                              score, None,
                              ["Posterior probability is below 10%.",
                               "Posterior probability is 10% to under 30%.",
                               "Posterior probability is at least 30%."]))
        return record(rng, "probability", domain, state, specs)

    success_a, success_b = rng.choice(((0.25, 0.40), (0.55, 0.35), (0.30, 0.20), (0.62, 0.48)))
    value_a = expected_value(success_a, 100, 20)
    value_b = expected_value(success_b, 80, 12)
    winner = "proposal_a" if success_a > success_b else "proposal_b"
    best_value = value_a if winner == "proposal_a" else value_b
    probability = max(success_a, success_b)
    state = rng.choice((
        f"PROJECT REVIEW — {domain}\nOwner: {analyst}\n"
        f"Proposal A: success probability {success_a:.0%}; value on success $100; fixed cost $20.\n"
        f"Proposal B: success probability {success_b:.0%}; value on success $80; fixed cost $12.\n"
        "Expected net value is success probability multiplied by value, less fixed cost.",
        f"{analyst} is comparing two {domain} initiatives. Proposal A succeeds with probability {success_a:.0%}, "
        f"returns $100 if successful, and costs $20. B succeeds with probability {success_b:.0%}, "
        "returns $80 if successful, and costs $12. Compare success likelihood separately from expected net value.",
    ))
    specs = []
    for kind in question_specs(types, n_questions):
        if kind == "choice":
            specs.append((kind, "Which proposal is more likely to succeed?",
                          winner,
                          {"proposal_a": f"Proposal A has {success_a:.0%} success probability and expected net value ${value_a:.2f}.",
                           "proposal_b": f"Proposal B has {success_b:.0%} success probability and expected net value ${value_b:.2f}."},
                          None))
        elif kind == "noul":
            specs.append((kind, "Does the more likely proposal also have positive expected net value?",
                          "true" if best_value > 0 else "false",
                          {"false": f"The higher-probability proposal's expected net value is ${best_value:.2f}, not positive.",
                           "true": f"The higher-probability proposal's expected net value is ${best_value:.2f}, above zero."},
                          None))
        else:
            specs.append((kind, "Which band contains the higher proposal's success probability?",
                          "0" if probability < 0.30 else "1" if probability < 0.60 else "2",
                          None, ["The higher success probability is below 30%.",
                                 "The higher success probability is 30% to under 60%.",
                                 "The higher success probability is at least 60%."]))
    return record(rng, "probability", domain, state, specs)
