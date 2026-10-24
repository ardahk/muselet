from __future__ import annotations

import csv
import io
import math
import random
import re
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

from ..common import finish_record, key_for_value, round_bands, score_level_for


def _csv(rows, columns):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().rstrip()


def _percent(value: Fraction) -> Decimal:
    return (Decimal(value.numerator) * 100 / Decimal(value.denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _money(value) -> Decimal:
    number = Decimal(value.numerator) / Decimal(value.denominator) if isinstance(value, Fraction) else Decimal(value)
    return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _band(rng, quantity, instruction, value, metric, unit="%"):
    criteria, level = round_bands(
        value, unit, [Decimal("1"), Decimal("2"), Decimal("5"), Decimal("10"), Decimal("25")],
        rng, metric=metric,
    )
    return {"quantity": quantity, "spec": ("score", instruction, str(level), criteria)}


def _percent_band(rng, quantity, instruction, probability, metric):
    return _band(rng, quantity, instruction, Decimal(probability.numerator) * 100 / Decimal(probability.denominator), metric)


def _threshold(rng, probability):
    target_true = bool(rng.randrange(2))
    point = probability + (Fraction(-1, 20) if target_true else Fraction(1, 20))
    point = max(Fraction(1, 100), min(Fraction(99, 100), point))
    return point


def _new_case(rng):
    kind = rng.choice(("bayes", "hypergeometric", "independent", "expected_value", "contingency"))
    if kind == "bayes":
        denominator = rng.choice((8_000, 10_000, 12_000, 16_000))
        count = rng.randint(500, 1_700)
        prior = Fraction(count, denominator)
        sensitivity = Fraction(rng.randint(86, 98), 100)
        specificity = Fraction(rng.randint(86, 98), 100)
        archived = prior + Fraction(8, 100) if prior < Fraction(12, 100) else prior - Fraction(8, 100)
        archived = Fraction(_percent(archived) / 100)
        posterior = prior * sensitivity / (prior * sensitivity + (1-prior) * (1-specificity))
        positive = prior * sensitivity + (1-prior) * (1-specificity)
        old_posterior = archived * sensitivity / (archived * sensitivity + (1-archived) * (1-specificity))
        case = {"kind": kind, "count": count, "denominator": denominator, "prior": prior,
                "sensitivity": sensitivity, "specificity": specificity,
                "archived": archived, "posterior": posterior, "positive": positive,
                "old_posterior": old_posterior}
        case["point"] = _threshold(rng, posterior)
        return case
    if kind == "hypergeometric":
        population = rng.randint(150, 260)
        sample = rng.randint(11, 18)
        old_sample = sample - rng.randint(2, 5)
        flagged = rng.randint(8, 16)
        while flagged in (sample, old_sample):
            flagged = 8 + (flagged - 7) % 9
        current = 1 - Fraction(math.comb(population-flagged, sample), math.comb(population, sample))
        previous = 1 - Fraction(math.comb(population-flagged, old_sample), math.comb(population, old_sample))
        case = {"kind": kind, "population": population, "sample": sample,
                "old_sample": old_sample, "flagged": flagged, "current": current,
                "old": previous, "expected": Fraction(sample*flagged, population)}
        case["point"] = _threshold(rng, current)
        return case
    if kind == "independent":
        labels = ("late delivery", "temperature excursion", "label mismatch", "seal variance")
        rates = rng.sample((8, 10, 12, 14, 16, 18, 20, 22, 24), 4)
        events = list(zip(labels, (Fraction(rate, 100) for rate in rates)))
        none = math.prod((1-p for _, p in events), start=Fraction(1))
        any_event = 1-none
        exactly_one = sum(
            (p * math.prod((1-q for j, (_, q) in enumerate(events) if j != i), start=Fraction(1))
             for i, (_, p) in enumerate(events)),
            Fraction(0),
        )
        case = {"kind": kind, "events": events, "none": none, "any": any_event,
                "exactly_one": exactly_one, "expected": sum((p for _, p in events), Fraction(0))}
        case["point"] = _threshold(rng, any_event)
        return case
    if kind == "expected_value":
        labels = ("Cold-chain audit", "Route analytics", "Supplier onboarding", "Invoice triage")
        options = []
        costs = set()
        for label in rng.sample(labels, rng.randint(3, 4)):
            cost = rng.randint(160, 420)
            while cost in costs:
                cost += 1
            costs.add(cost)
            probability = Fraction(rng.randint(38, 82), 100)
            benefit = rng.randint(850, 1_700)
            options.append({"name": label, "probability": probability, "benefit": benefit,
                            "cost": cost, "gross": probability*benefit,
                            "net": probability*benefit-cost})
        options.sort(key=lambda item: item["net"], reverse=True)
        best = options[0]["net"]
        point = best + (50 if rng.randrange(2) else -50)
        return {"kind": kind, "options": options, "point": point}
    counts = {
        "reviewed_closed": rng.randint(42, 95), "reviewed_open": rng.randint(24, 55),
        "unreviewed_closed": rng.randint(25, 60), "unreviewed_open": rng.randint(42, 100),
    }
    total = sum(counts.values())
    conditional = Fraction(counts["reviewed_closed"], counts["reviewed_closed"]+counts["reviewed_open"])
    reverse = Fraction(counts["reviewed_closed"], counts["reviewed_closed"]+counts["unreviewed_closed"])
    marginal_closed = Fraction(counts["reviewed_closed"]+counts["unreviewed_closed"], total)
    marginal_flagged = Fraction(counts["reviewed_closed"]+counts["reviewed_open"], total)
    union = Fraction(total-counts["unreviewed_open"], total)
    case = {"kind": kind, "counts": counts, "conditional": conditional, "reverse": reverse,
            "marginal_closed": marginal_closed, "marginal_flagged": marginal_flagged,
            "union": union, "joint": Fraction(counts["reviewed_closed"], total)}
    case["point"] = _threshold(rng, conditional)
    return case


def _render(case):
    kind = case["kind"]
    if kind == "bayes":
        return (
            "SCREENING REVIEW — Regional Respiratory Clinic\n"
            "The surveillance team is estimating the chance that a patient with a positive screen has the condition. "
            "The active cohort provides the prior rate, while the laboratory validation panel describes the test. "
            "A positive result alone is not a diagnosis, and the prior quarter's dashboard uses a different population.\n\n"
            "CURRENT COHORT\n"
            f"Condition found in {case['count']:,} of {case['denominator']:,} screened patients.\n"
            f"Archived quarter estimate: {_percent(case['archived']):.2f}% for a different clinic population.\n"
            f"Review point: at least {_percent(case['point']):.2f}%\n\n"
            "LABORATORY VALIDATION\n"
            f"Positive results among affected patients: {int(case['sensitivity']*100):,} of 100.\n"
            f"Negative results among unaffected patients: {int(case['specificity']*100):,} of 100.\n"
            "The validation panel was reviewed by the clinical methods group and uses the same assay version "
            "as the current clinic cohort. One patient's new result is positive. The review team requests a "
            "population-adjusted interpretation rather than repeating sensitivity as the individual probability.\n\n"
            "This extract is prepared for the Monday case conference. The cohort count is a base rate, while the "
            "validation panel describes how often the assay returns each result within affected and unaffected "
            "groups. Use both sources together when estimating the positive predictive value."
        )
    if kind == "hypergeometric":
        return (
            "LOT QUALITY REPORT — North Warehouse\n"
            "The supplier lot is under review after a small number of units were flagged during intake. Quality "
            "staff draw units from the sealed lot without replacement; a selected unit is not returned before "
            "the next draw. The release question concerns whether the current sample contains at least one flagged unit.\n\n"
            "LOT REGISTER\n"
            f"Lot size: {case['population']:,} units.\n"
            f"Flagged units recorded at intake: {case['flagged']:,}.\n"
            f"Current inspection plan: select {case['sample']:,} units without replacement.\n"
            f"Archived inspection plan: select {case['old_sample']:,} units; replaced for this shipment.\n"
            f"Review point: at least {_percent(case['point']):.2f}%\n\n"
            "The current plan took effect before the lot arrived. The archived plan remains in the quality binder "
            "because earlier shipments used a smaller sample, but it does not govern this release review. For this "
            "report, the intake count is fixed and every possible subset of the stated size is equally likely. "
            "No unit-level sequence or replacement draw is assumed.\n\n"
            "The receiving manager needs the risk of one or more flagged units in the current draw, not the fraction "
            "of flagged units in the full lot. The previous plan is included for comparison only."
        )
    if kind == "independent":
        table = _csv(
            [{"Operational event": name, "Observed probability": f"{_percent(probability):.2f}%"}
             for name, probability in case["events"]],
            ("Operational event", "Observed probability"),
        )
        return (
            "OPERATIONS RISK BULLETIN — Evening Dispatch\n"
            "The safety desk is estimating whether any monitored disruption will occur during the next dispatch "
            "shift. The four event estimates refer to separate routes and equipment checks. The current protocol "
            "treats these events as independent; adding their rates would count overlapping outcomes more than once.\n\n"
            "EVENT ESTIMATES\n" + table + "\n\n"
            f"Review point: at least {_percent(case['point']):.2f}%\n\n"
            "The rates come from the latest reviewed quarter and are applied to a single upcoming shift. A status "
            "dashboard also shows 31 alerts across the entire month, but that count is not the denominator for an "
            "individual shift. The dispatch lead needs the chance of at least one event and related quantities for "
            "comparing staffing plans.\n\n"
            "This bulletin is a planning estimate, not a forecast of which route will be affected. The event rows "
            "remain separate in the source register; the stated independence assumption is the permitted joint model."
        )
    if kind == "expected_value":
        table = _csv(
            [{
                "Initiative": item["name"],
                "Chance of success": f"{_percent(item['probability']):.2f}%",
                "Value if successful (USD)": f"{item['benefit']:.2f}",
                "Fixed implementation cost (USD)": f"{item['cost']:.2f}",
            } for item in case["options"]],
            ("Initiative", "Chance of success", "Value if successful (USD)", "Fixed implementation cost (USD)"),
        )
        return (
            "PORTFOLIO REVIEW — Service Improvement Proposals\n"
            "The planning group is comparing initiatives for a one-year service improvement budget. Each proposal "
            "has a stated probability of success, a value realized only on success, and a fixed implementation cost "
            "paid regardless of outcome. The recommendation should maximize expected net value after that cost.\n\n"
            "PROPOSAL REGISTER\n" + table + "\n\n"
            f"Review point: at least ${case['point']:.2f}\n\n"
            "The finance committee uses the review point as a minimum expected-net hurdle. Values are estimates in "
            "US dollars and are not guaranteed proceeds. An executive summary from an earlier meeting ranks gross "
            "benefit before implementation costs were entered.\n\n"
            "The proposals were prepared by separate operating teams, but the finance desk applied the same forecast "
            "horizon and costing convention to each. Use the listed probabilities, benefits, and costs on a common basis."
        )
    counts = case["counts"]
    table = _csv(
        [
            {"Service outcome": "Completed", "Flagged for review": counts["reviewed_closed"],
             "Not flagged": counts["unreviewed_closed"]},
            {"Service outcome": "Open", "Flagged for review": counts["reviewed_open"],
             "Not flagged": counts["unreviewed_open"]},
        ],
        ("Service outcome", "Flagged for review", "Not flagged"),
    )
    return (
        "SERVICE QUALITY REPORT — Follow-up Outcomes\n"
        "The audit team is checking whether cases flagged for expedited review have a different completion rate. "
        "The table counts distinct cases in the same reporting period. Completion among flagged cases, the reverse "
        "conditional, and the marginal completion rate have different denominators.\n\n"
        "FOLLOW-UP CROSS-TABULATION\n" + table + "\n\n"
        f"Review point: at least {_percent(case['point']):.2f}%\n\n"
        "The completed and open categories are mutually exclusive and cover all cases in this extract. A dashboard "
        "headline quotes the overall completion total, but that total alone does not answer a question conditioned "
        "on review status. Preserve the row and column labels when forming the requested rate."
    )


def _read_state(state):
    if "SCREENING REVIEW — Regional Respiratory Clinic" in state:
        count, denominator = (
            int(value.replace(",", ""))
            for value in re.search(r"Condition found in ([\d,]+) of ([\d,]+) screened", state).groups()
        )
        sensitivity = Fraction(int(re.search(r"Positive results among affected patients: (\d+) of 100", state).group(1)), 100)
        specificity = Fraction(int(re.search(r"Negative results among unaffected patients: (\d+) of 100", state).group(1)), 100)
        archived = Fraction(Decimal(re.search(r"Archived quarter estimate: ([\d.]+)%", state).group(1)) / 100)
        prior = Fraction(count, denominator)
        posterior = prior*sensitivity/(prior*sensitivity+(1-prior)*(1-specificity))
        old = archived*sensitivity/(archived*sensitivity+(1-archived)*(1-specificity))
        positive = prior*sensitivity+(1-prior)*(1-specificity)
        point = Fraction(Decimal(re.search(r"Review point: at least ([\d.]+)%", state).group(1))/100)
        return {"kind": "bayes", "prior": prior, "posterior": posterior, "old": old,
                "positive": positive, "point": point}
    if "LOT QUALITY REPORT — North Warehouse" in state:
        vals = {key: int(re.search(pattern, state).group(1).replace(",", "")) for key, pattern in {
            "population": r"Lot size: ([\d,]+)",
            "flagged": r"Flagged units recorded at intake: ([\d,]+)",
            "sample": r"Current inspection plan: select ([\d,]+)",
            "old_sample": r"Archived inspection plan: select ([\d,]+)",
        }.items()}
        n, k, size, old_size = vals["population"], vals["flagged"], vals["sample"], vals["old_sample"]
        point = Fraction(Decimal(re.search(r"Review point: at least ([\d.]+)%", state).group(1))/100)
        return {"kind": "hypergeometric", **vals,
                "current": 1-Fraction(math.comb(n-k, size), math.comb(n, size)),
                "old": 1-Fraction(math.comb(n-k, old_size), math.comb(n, old_size)),
                "expected": Fraction(size*k, n), "point": point}
    if "OPERATIONS RISK BULLETIN — Evening Dispatch" in state:
        table = state.split("EVENT ESTIMATES\n", 1)[1].split("\n\n", 1)[0]
        events = [(row["Operational event"], Fraction(Decimal(row["Observed probability"][:-1])/100))
                  for row in csv.DictReader(io.StringIO(table))]
        none = math.prod((1-p for _, p in events), start=Fraction(1))
        exactly_one = sum((p*math.prod((1-q for j, (_, q) in enumerate(events) if j != i), start=Fraction(1))
                           for i, (_, p) in enumerate(events)), Fraction(0))
        point = Fraction(Decimal(re.search(r"Review point: at least ([\d.]+)%", state).group(1))/100)
        return {"kind": "independent", "events": events, "any": 1-none, "none": none,
                "exactly_one": exactly_one, "expected": sum((p for _, p in events), Fraction(0)),
                "point": point}
    if "PORTFOLIO REVIEW — Service Improvement Proposals" in state:
        table = state.split("PROPOSAL REGISTER\n", 1)[1].split("\n\n", 1)[0]
        options = []
        for row in csv.DictReader(io.StringIO(table)):
            probability = Fraction(Decimal(row["Chance of success"][:-1])/100)
            benefit, cost = Decimal(row["Value if successful (USD)"]), Decimal(row["Fixed implementation cost (USD)"])
            options.append({"name": row["Initiative"], "probability": probability, "benefit": benefit,
                            "cost": cost, "gross": _money(probability*Fraction(benefit)),
                            "net": _money(probability*Fraction(benefit)-Fraction(cost))})
        options.sort(key=lambda item: item["net"], reverse=True)
        point = Decimal(re.search(r"Review point: at least \$([\d.]+)", state).group(1))
        return {"kind": "expected_value", "options": options, "point": point}
    if "SERVICE QUALITY REPORT — Follow-up Outcomes" in state:
        table = state.split("FOLLOW-UP CROSS-TABULATION\n", 1)[1].split("\n\n", 1)[0]
        rows = {row["Service outcome"]: row for row in csv.DictReader(io.StringIO(table))}
        rc, ro = int(rows["Completed"]["Flagged for review"]), int(rows["Open"]["Flagged for review"])
        uc, uo = int(rows["Completed"]["Not flagged"]), int(rows["Open"]["Not flagged"])
        total = rc+ro+uc+uo
        point = Fraction(Decimal(re.search(r"Review point: at least ([\d.]+)%", state).group(1))/100)
        return {"kind": "contingency", "rc": rc, "ro": ro, "uc": uc, "uo": uo,
                "conditional": Fraction(rc, rc+ro), "reverse": Fraction(rc, rc+uc),
                "marginal_closed": Fraction(rc+uc, total), "marginal_flagged": Fraction(rc+ro, total),
                "union": Fraction(total-uo, total), "joint": Fraction(rc, total), "point": point}
    raise ValueError("unrecognized probability report")


def _question_pool(rng, case):
    kind = case["kind"]
    if kind == "bayes":
        p = case["posterior"]
        count = round(100*p)
        prior_count = round(100*case["prior"])
        old_count = round(100*case["old_posterior"])
        return [
            _band(rng, "positive_predictive_value", "Which band contains the chance of condition after a positive screen?",
                  Decimal(p.numerator)*100/Decimal(p.denominator), "The positive predictive probability"),
            _band(rng, "unaffected_after_positive", "Which band contains the chance of no condition after a positive screen?",
                  Decimal((1-p).numerator)*100/Decimal((1-p).denominator), "The probability of no condition after a positive screen"),
            _band(rng, "positive_test_rate", "Which band contains the chance that a cohort member tests positive?",
                  Decimal(case["positive"].numerator)*100/Decimal(case["positive"].denominator), "The probability of a positive screen"),
            {"quantity": "expected_affected_count", "spec": ("choice", "Among 100 positive screens, how many affected cases are expected?",
                key_for_value("affected_cases", count), {
                    key_for_value("affected_cases", count): f"The expected count is {count} affected cases.",
                    key_for_value("affected_cases", prior_count): f"The expected count is {prior_count} affected cases.",
                    key_for_value("affected_cases", old_count): f"The expected count is {old_count} affected cases.",
                })},
            {"quantity": "review_point", "spec": ("noul", "Is the posterior probability at least the review point?",
                "true" if p >= case["point"] else "false", {
                    "false": "The posterior probability meets the review point: No.",
                    "true": "The posterior probability meets the review point: Yes.",
                })},
            _band(rng, "archived_posterior", "Which band contains the archived-model estimate after a positive screen?",
                  Decimal(case["old_posterior"].numerator)*100/Decimal(case["old_posterior"].denominator),
                  "The archived-model probability"),
        ]
    if kind == "hypergeometric":
        p = case["current"]
        return [
            _percent_band(rng, "at_least_one_flag", "Which band contains the chance of at least one flagged unit in the current draw?", p, "The probability of at least one flagged unit"),
            _percent_band(rng, "no_flagged_units", "Which band contains the chance that the current draw has no flagged unit?", 1-p, "The probability of no flagged units"),
            _band(rng, "expected_flagged_units", "Which band contains the expected flagged-unit count in the current draw?",
                  Decimal(case["expected"].numerator)/Decimal(case["expected"].denominator), "The expected flagged-unit count", "units"),
            _percent_band(rng, "archived_plan_risk", "Which band contains the chance of at least one flagged unit under the archived plan?", case["old"], "The archived-plan probability"),
            {"quantity": "review_point", "spec": ("noul", "Is the current-plan risk at least the review point?",
                "true" if p >= case["point"] else "false", {
                    "false": "The current-plan risk meets the review point: No.",
                    "true": "The current-plan risk meets the review point: Yes.",
                })},
            {"quantity": "sample_size", "spec": ("choice", "How many units are selected under the current inspection plan?",
                key_for_value("sample_units", case["sample"]), {
                    key_for_value("sample_units", case["sample"]): f"The selected sample contains {case['sample']} units.",
                    key_for_value("sample_units", case["old_sample"]): f"The selected sample contains {case['old_sample']} units.",
                    key_for_value("sample_units", case["flagged"]): f"The selected sample contains {case['flagged']} units.",
                })},
        ]
    if kind == "independent":
        events = case["events"]
        best = max(events, key=lambda item: item[1])
        return [
            _percent_band(rng, "any_event", "Which band contains the chance of at least one disruption?", case["any"], "The probability of at least one disruption"),
            _percent_band(rng, "no_events", "Which band contains the chance of no disruption?", case["none"], "The probability of no disruption"),
            _percent_band(rng, "exactly_one", "Which band contains the chance of exactly one disruption?", case["exactly_one"], "The probability of exactly one disruption"),
            _band(rng, "expected_disruptions", "Which band contains the expected number of disruptions?",
                  Decimal(case["expected"].numerator)/Decimal(case["expected"].denominator), "The expected disruption count", "events"),
            {"quantity": "review_point", "spec": ("noul", "Is the probability of at least one disruption at least the review point?",
                "true" if case["any"] >= case["point"] else "false", {
                    "false": "The disruption probability meets the review point: No.",
                    "true": "The disruption probability meets the review point: Yes.",
                })},
            {"quantity": "highest_event_rate", "spec": ("choice", "Which event has the highest individual probability?",
                key_for_value("event_rate", _percent(best[1])), {
                    key_for_value("event_rate", _percent(rate)): f"The highest individual event probability is {_percent(rate):.2f}%."
                    for _, rate in events
                })},
        ]
    if kind == "expected_value":
        options = case["options"]
        best, second = options[0], options[1]
        return [
            {"quantity": "best_initiative", "spec": ("choice", "Which initiative has the highest expected net value after fixed costs?",
                key_for_value("initiative", best["name"]), {
                    key_for_value("initiative", item["name"]): f"{item['name']} has the highest expected net value."
                    for item in options
                })},
            _band(rng, "best_net_value", "Which band contains the highest expected net value?",
                  Decimal(best["net"].numerator)/Decimal(best["net"].denominator), "The highest expected net value", "$"),
            _percent_band(rng, "winning_success_probability", "Which band contains the winning initiative's success probability?",
                best["probability"], "The winning initiative probability"),
            _band(rng, "net_value_margin", "Which band contains the gap between the best and next-best expected net values?",
                  Decimal((best["net"]-second["net"]).numerator)/Decimal((best["net"]-second["net"]).denominator),
                  "The expected net-value margin", "$"),
            {"quantity": "review_point", "spec": ("noul", "Does the best expected net value meet the review point?",
                "true" if best["net"] >= case["point"] else "false", {
                    "false": "The best expected net value meets the review point: No.",
                    "true": "The best expected net value meets the review point: Yes.",
                })},
            {"quantity": "winning_fixed_cost", "spec": ("choice", "What fixed cost is listed for the leading initiative?",
                key_for_value("fixed_cost", best["cost"]), {
                    key_for_value("fixed_cost", item["cost"]): f"The listed fixed cost is ${item['cost']:,.2f}."
                    for item in options
                })},
        ]
    return [
        _percent_band(rng, "completion_given_flagged", "Which band contains completion among cases flagged for review?", case["conditional"], "The conditional completion probability"),
        _percent_band(rng, "flagged_given_completed", "Which band contains the chance of a review flag among completed cases?", case["reverse"], "The reverse conditional probability"),
        _percent_band(rng, "marginal_completion", "Which band contains the overall case-completion rate?", case["marginal_closed"], "The overall completion probability"),
        _percent_band(rng, "marginal_flagged", "Which band contains the overall review-flag rate?", case["marginal_flagged"], "The overall review probability"),
        _percent_band(rng, "union_probability", "Which band contains the chance a case was flagged or completed?", case["union"], "The probability of a flagged or completed case"),
        {"quantity": "review_point", "spec": ("noul", "Is completion among flagged cases at least the review point?",
            "true" if case["conditional"] >= case["point"] else "false", {
                "false": "Completion among flagged cases meets the review point: No.",
                "true": "Completion among flagged cases meets the review point: Yes.",
            })},
    ]


def _primary(case):
    kind = case["kind"]
    if kind == "bayes":
        return case["posterior"], case.get("old_posterior", case.get("old"))
    if kind == "hypergeometric":
        return case["current"], case.get("previous", case.get("old"))
    if kind == "independent":
        return case["any"], sum((p for _, p in case["events"]), Fraction(0))
    if kind == "expected_value":
        return case["options"][0]["net"], case["options"][0]["gross"]
    return case["conditional"], case["joint"]


def _expected(record_state, instruction, criteria):
    case = _read_state(record_state)
    kind = case["kind"]
    if kind == "bayes":
        values = {
            "Which band contains the chance of condition after a positive screen?": ("score", case["posterior"]),
            "Which band contains the chance of no condition after a positive screen?": ("score", 1-case["posterior"]),
            "Which band contains the chance that a cohort member tests positive?": ("score", case["positive"]),
            "Which band contains the archived-model estimate after a positive screen?": ("score", case["old"]),
            "Among 100 positive screens, how many affected cases are expected?": ("choice", key_for_value("affected_cases", round(100*case["posterior"]))),
            "Is the posterior probability at least the review point?": ("noul", "true" if case["posterior"] >= case["point"] else "false"),
        }
    elif kind == "hypergeometric":
        values = {
            "Which band contains the chance of at least one flagged unit in the current draw?": ("score", case["current"]),
            "Which band contains the chance that the current draw has no flagged unit?": ("score", 1-case["current"]),
            "Which band contains the expected flagged-unit count in the current draw?": ("score", Decimal(case["expected"].numerator)/Decimal(case["expected"].denominator)),
            "Which band contains the chance of at least one flagged unit under the archived plan?": ("score", case["old"]),
            "Is the current-plan risk at least the review point?": ("noul", "true" if case["current"] >= case["point"] else "false"),
            "How many units are selected under the current inspection plan?": ("choice", key_for_value("sample_units", case["sample"])),
        }
    elif kind == "independent":
        best = max(case["events"], key=lambda item: item[1])
        values = {
            "Which band contains the chance of at least one disruption?": ("score", case["any"]),
            "Which band contains the chance of no disruption?": ("score", case["none"]),
            "Which band contains the chance of exactly one disruption?": ("score", case["exactly_one"]),
            "Which band contains the expected number of disruptions?": ("score", case["expected"]),
            "Is the probability of at least one disruption at least the review point?": ("noul", "true" if case["any"] >= case["point"] else "false"),
            "Which event has the highest individual probability?": ("choice", key_for_value("event_rate", _percent(best[1]))),
        }
    elif kind == "expected_value":
        best, second = case["options"][:2]
        values = {
            "Which initiative has the highest expected net value after fixed costs?": ("choice", key_for_value("initiative", best["name"])),
            "Which band contains the highest expected net value?": ("score", best["net"]),
            "Which band contains the winning initiative's success probability?": ("score", case["options"][0]["probability"]),
            "Which band contains the gap between the best and next-best expected net values?": ("score", best["net"]-second["net"]),
            "Does the best expected net value meet the review point?": ("noul", "true" if best["net"] >= case["point"] else "false"),
            "What fixed cost is listed for the leading initiative?": ("choice", key_for_value("fixed_cost", best["cost"])),
        }
    else:
        values = {
            "Which band contains completion among cases flagged for review?": ("score", case["conditional"]),
            "Which band contains the chance of a review flag among completed cases?": ("score", case["reverse"]),
            "Which band contains the overall case-completion rate?": ("score", case["marginal_closed"]),
            "Which band contains the overall review-flag rate?": ("score", case["marginal_flagged"]),
            "Which band contains the chance a case was flagged or completed?": ("score", case["union"]),
            "Is completion among flagged cases at least the review point?": ("noul", "true" if case["conditional"] >= case["point"] else "false"),
        }
    if instruction not in values:
        raise ValueError("unknown probability question")
    kind, value = values[instruction]
    if kind == "score":
        if isinstance(value, Fraction):
            value = Decimal(value.numerator)*100/Decimal(value.denominator) if "%" in " ".join(criteria) else Decimal(value.numerator)/Decimal(value.denominator)
        return score_level_for(value, criteria)
    return value


def _note_value(case, stated):
    actual, mistaken = _primary(case)
    if case["kind"] == "expected_value":
        expected = _money(actual)
        wrong = _money(mistaken)
        parsed = Decimal(stated)
    else:
        expected, wrong = _percent(actual), _percent(mistaken)
        parsed = Decimal(stated)
    return parsed == expected, parsed == wrong


def verify_rendered(record: dict) -> bool:
    try:
        for qid, question in record["questions"].items():
            instruction = question["instructions"]
            answer = _expected(record["state"], instruction, question["criteria"])
            if answer != record["gold"][qid]:
                return False
            if question["type"] == "choice" and answer not in question["criteria"]:
                return False
        note = re.search(
            r"Mira \((?:clinical|planning)\): I get \$?([\d,]+(?:\.\d+)?)(%)? as the review estimate\.",
            record["state"],
        )
        meta = record["_meta"]["staff_note"]
        if meta["included"] != bool(note):
            return False
        if note:
            case = _read_state(record["state"])
            correct, mistaken = _note_value(case, note.group(1).replace(",", ""))
            if meta["correct"] is not correct or (not correct and not mistaken):
                return False
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, ZeroDivisionError):
        return False
    return True


def _score_input(state, instruction):
    case = _read_state(state)
    kind = case["kind"]
    value = _expected(state, instruction, [])
    if kind == "bayes":
        vals = {
            "Which band contains the chance of condition after a positive screen?": case["posterior"],
            "Which band contains the chance of no condition after a positive screen?": 1-case["posterior"],
            "Which band contains the chance that a cohort member tests positive?": case["positive"],
            "Which band contains the archived-model estimate after a positive screen?": case["old"],
        }
    elif kind == "hypergeometric":
        vals = {
            "Which band contains the chance of at least one flagged unit in the current draw?": case["current"],
            "Which band contains the chance that the current draw has no flagged unit?": 1-case["current"],
            "Which band contains the expected flagged-unit count in the current draw?": case["expected"],
            "Which band contains the chance of at least one flagged unit under the archived plan?": case["old"],
        }
    elif kind == "independent":
        vals = {
            "Which band contains the chance of at least one disruption?": case["any"],
            "Which band contains the chance of no disruption?": case["none"],
            "Which band contains the chance of exactly one disruption?": case["exactly_one"],
            "Which band contains the expected number of disruptions?": case["expected"],
        }
    elif kind == "expected_value":
        vals = {
            "Which band contains the highest expected net value?": case["options"][0]["net"],
            "Which band contains the winning initiative's success probability?": case["options"][0]["probability"],
            "Which band contains the gap between the best and next-best expected net values?": case["options"][0]["net"]-case["options"][1]["net"],
        }
    else:
        vals = {
            "Which band contains completion among cases flagged for review?": case["conditional"],
            "Which band contains the chance of a review flag among completed cases?": case["reverse"],
            "Which band contains the overall case-completion rate?": case["marginal_closed"],
            "Which band contains the overall review-flag rate?": case["marginal_flagged"],
            "Which band contains the chance a case was flagged or completed?": case["union"],
        }
    value = vals[instruction]
    if isinstance(value, Fraction):
        if "%" in instruction or kind in ("bayes", "hypergeometric", "independent", "contingency") and "count" not in instruction and "number of disruptions" not in instruction:
            return Decimal(value.numerator)*100/Decimal(value.denominator)
        return Decimal(value.numerator)/Decimal(value.denominator)
    return value


def generate(rng: random.Random, n_questions: int) -> dict:
    if not 2 <= n_questions <= 5:
        raise ValueError("n_questions must be between 2 and 5")
    case = _new_case(rng)
    state = _render(case)
    pool = _question_pool(rng, case)
    selected = rng.sample(pool, n_questions)
    note = None
    if rng.random() < 0.65:
        correct = rng.random() < 0.30
        actual, mistaken = _primary(case)
        estimate = actual if correct else mistaken
        if case["kind"] == "expected_value":
            note = (f"Mira (planning): I get ${_money(estimate):,.2f} as the review estimate.", correct)
        else:
            note = (f"Mira (clinical): I get {_percent(estimate):.2f}% as the review estimate.", correct)
    record = finish_record(
        rng, "cg_probability", "probability_model_review", state,
        [item["spec"] for item in selected],
        facts={"case": case}, traps=[
            "base_rate", "without_replacement", "independent_events",
            "expected_cost", "conditional_denominator", "archived_data",
        ],
        note=note,
    )
    record["_meta"]["quantity_kinds"] = {
        f"q{index}": item["quantity"] for index, item in enumerate(selected, start=1)
    }
    return record
