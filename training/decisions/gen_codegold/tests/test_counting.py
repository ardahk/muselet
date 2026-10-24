import random
import re
from collections import Counter, defaultdict
from decimal import Decimal

from training.decisions.gen_codegold.common import round_bands, score_level_for
from training.decisions.gen_codegold.families import cg_counting


def _generate(seed):
    rng = random.Random(seed)
    return cg_counting.generate(rng, rng.randint(2, 5))


def test_counting_independent_text_verifier_recomputes_500_seeds():
    for seed in range(500):
        record = _generate(seed)
        assert cg_counting.verify_rendered(record), f"independent verifier rejected seed {seed}"
        assert 2 <= len(record["questions"]) <= 5
        assert len({question["instructions"] for question in record["questions"].values()}) == len(
            record["questions"]
        )


def test_counting_d9_distributions_and_surface_constraints():
    records = [_generate(seed + 10_000) for seed in range(2_000)]
    included_notes = []
    note_positions = Counter()
    choice_positions = defaultdict(Counter)
    score_levels = defaultdict(Counter)
    noul_answers = []

    for record in records:
        state = record["state"]
        tokens = len(state) // 4
        assert 600 <= tokens <= 2_500
        assert "schema" not in state.lower()
        assert not re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", state)
        rows, *_ = cg_counting._read_export(state)
        assert 50 <= len(rows) <= 60
        instructions = [question["instructions"] for question in record["questions"].values()]
        assert len(instructions) == len(set(instructions))
        quantities = list(record["_meta"]["quantity_kinds"].values())
        assert len(quantities) == len(set(quantities))

        staff_note = record["_meta"]["staff_note"]
        if staff_note["included"]:
            included_notes.append(staff_note["correct"])
            note_positions[staff_note["position"]] += 1
        else:
            assert staff_note["correct"] is None
            assert staff_note["position"] is None

        for qid, question in record["questions"].items():
            criteria = question["criteria"]
            assert not any(re.match(rf"^{re.escape(qid)}_", key) for key in criteria) if isinstance(
                criteria, dict
            ) else True
            assert not any("candidate" in str(key).lower() for key in criteria)
            assert not any("candidate" in str(value).lower() for value in criteria.values()) if isinstance(
                criteria, dict
            ) else True
            if question["type"] == "choice":
                assert 2 <= len(criteria) <= 26
                assert record["gold"][qid] in criteria
                choice_positions[len(criteria)][list(criteria).index(record["gold"][qid])] += 1
            elif question["type"] == "score":
                assert record["gold"][qid].isdigit()
                assert int(record["gold"][qid]) < len(criteria)
                score_levels[len(criteria)][record["gold"][qid]] += 1
                for level in criteria:
                    for number in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level):
                        if "." in number:
                            assert len(number.rsplit(".", 1)[1]) <= 2
            else:
                noul_answers.append(record["gold"][qid])

    note_rate = sum(note is True for note in included_notes) / len(included_notes)
    assert 0.60 <= len(included_notes) / len(records) <= 0.70
    assert 0.25 <= note_rate <= 0.35
    assert len(note_positions) >= 3
    assert 0.45 <= noul_answers.count("true") / len(noul_answers) <= 0.55

    for positions in choice_positions.values():
        if sum(positions.values()) >= 30:
            assert len(positions) > 1
            assert max(positions.values()) / min(positions.values()) < 2.25
    for count, distribution in score_levels.items():
        observed = [distribution[str(index)] for index in range(count)]
        assert min(observed) > 0
        assert max(observed) / min(observed) < 1.8


def test_common_round_bands_have_rounded_edges_and_uniform_gold():
    rng = random.Random(40_401)
    gold_counts = Counter()
    boundary_count = 0
    round_values = (Decimal("75"), Decimal("125"), Decimal("175"))
    for value in round_values:
        local_boundaries = 0
        for _ in range(2_000):
            criteria, gold_index = round_bands(
                value, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50")],
                rng, levels=(5, 5), boundary_rate=0.15, metric="The eligible amount",
            )
            assert len(criteria) == 5
            assert score_level_for(value, criteria) == str(gold_index)
            edges = {
                Decimal(token.replace(",", ""))
                for level in criteria
                for token in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level)
            }
            if value in edges:
                local_boundaries += 1
            for level in criteria:
                for number in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level):
                    if "." in number:
                        assert len(number.rsplit(".", 1)[1]) <= 2
            gold_counts[gold_index] += 1
        boundary_count += local_boundaries

    assert 0.12 <= boundary_count / 6_000 <= 0.18
    assert max(gold_counts.values()) / min(gold_counts.values()) < 1.2
    widths = []
    for _ in range(500):
        value = Decimal("877.37")
        criteria, _ = round_bands(
            value, "$", [Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50")],
            rng, levels=(5, 5), boundary_rate=0, metric="The eligible amount",
        )
        edges = sorted({
            Decimal(token.replace(",", ""))
            for level in criteria
            for token in re.findall(r"-?\d[\d,]*(?:\.\d+)?", level)
        })
        assert len(edges) == 4
        assert value not in edges
        assert min(abs(value - edge) for edge in edges) >= max(
            value * Decimal("0.02"), (edges[1] - edges[0]) * Decimal("0.10")
        )
        widths.append([right - left for left, right in zip(edges, edges[1:])])
        assert all("The eligible amount" in level for level in criteria)
        assert all(" but less than " in level for level in criteria[1:-1])
    assert all(len(set(width)) == 1 for width in widths)


def test_counting_generates_exact_review_cap_boundaries():
    exact_boundaries = 0
    cap_questions = 0
    for seed in range(1_000):
        record = _generate(seed + 70_000)
        rows, start, end, minimum, included, cap = cg_counting._read_export(record["state"])
        total = sum(
            (Decimal(row["amount"]) for row in
             cg_counting._eligible_rows(rows, start, end, minimum, included)),
            Decimal("0"),
        )
        exact_boundaries += total == cap
        for question in record["questions"].values():
            if question["type"] == "noul" and "review cap" in question["instructions"]:
                cap_questions += 1
                if total == cap:
                    assert (
                        "at least" in question["instructions"]
                        or "meet or exceed" in question["instructions"]
                        or "strictly exceed" in question["instructions"]
                    )
    assert 0.12 <= exact_boundaries / 1_000 <= 0.18
    assert cap_questions > 300


def _neutralized_counting_option(text):
    normalized = re.sub(r"\$[\d,]+(?:\.\d{1,2})?", "<value>", text)
    normalized = re.sub(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", "<value>", normalized)
    for group in sorted(cg_counting.GROUPS, key=len, reverse=True):
        normalized = re.sub(
            re.escape(cg_counting._display(group)), "<entity>", normalized, flags=re.IGNORECASE
        )
    return normalized


def test_counting_neutral_options_plurality_and_note_wording():
    for seed in range(500):
        record = _generate(seed + 30_000)
        for qid, question in record["questions"].items():
            if question["type"] != "choice":
                continue
            provenance = record["_meta"]["option_provenance"][qid]
            assert set(question["criteria"]) <= set(provenance)
            normalized = {
                _neutralized_counting_option(text)
                for text in question["criteria"].values()
            }
            assert len(normalized) == 1, (seed, qid, question["criteria"])
            assert not any(
                phrase in text.lower()
                for text in question["criteria"].values()
                for phrase in ("omits the", "if the review", "after applying", "dropping the")
            )
            assert not any(
                re.search(r"\b1 eligible transactions\b", text, flags=re.IGNORECASE)
                for text in question["criteria"].values()
            )
        note = record["_meta"]["narrative_section"]
        if note:
            assert note.startswith("Mira (finance): I get $")
            assert not re.search(
                r"applying|posted.status|duplicate|reporting.window|minimum.amount|approved.group",
                note,
                flags=re.IGNORECASE,
            )


def test_counting_traps_are_shuffled_and_ledger_is_broad():
    trap_positions = []
    identical_duplicates = 0
    varied_duplicates = 0
    for seed in range(1_000):
        record = _generate(seed + 50_000)
        rows, start, end, minimum, included, _ = cg_counting._read_export(record["state"])
        assert 5 <= len({row["group"] for row in rows}) <= 9
        assert 3 <= len(included) <= 6
        eligible_group_rows = sum(row["group"] in included for row in rows)
        assert 0.40 <= eligible_group_rows / len(rows) <= 0.70
        assert 3 <= len(cg_counting._eligible_rows(rows, start, end, minimum, included)) <= 30
        assert max(Counter(row["amount"] for row in rows).values()) <= 3

        trap_ids = set(record["_meta"]["trap_rows"])
        trap_positions.extend(
            index / (len(rows) - 1)
            for index, row in enumerate(rows)
            if row["record"] in trap_ids
        )
        source_rows = record["_meta"]["facts"]["rows"]
        for duplicate in (row for row in source_rows if row["trap_kind"] == "duplicate upload"):
            original = next(
                row for row in source_rows
                if row["transaction"] == duplicate["transaction"]
                and row["record"] != duplicate["record"]
            )
            if duplicate["amount"] == original["amount"]:
                identical_duplicates += 1
            else:
                varied_duplicates += 1

    mean_position = sum(trap_positions) / len(trap_positions)
    assert 0.40 <= mean_position <= 0.60
    assert identical_duplicates > 100
    assert varied_duplicates > 100


def test_counting_allows_one_question_per_quantity_kind():
    for seed in range(1_000):
        record = _generate(seed + 70_000)
        quantities = list(record["_meta"]["quantity_kinds"].values())
        assert len(quantities) == len(set(quantities))
        assert quantities.count("eligible_total") <= 1


def test_counting_questions_name_exact_below_minimum_and_reversal_totals():
    for seed in range(500):
        record = _generate(seed + 80_000)
        for qid, quantity in record["_meta"]["quantity_kinds"].items():
            question = record["questions"][qid]
            if quantity == "reversed_amount":
                phrase = "The total of otherwise-eligible entries cancelled by reversal notices"
                assert question["instructions"] == (
                    "What is the total of otherwise-eligible entries cancelled by reversal notices?"
                )
            elif quantity == "below_minimum_charges":
                phrase = (
                    "The total of entries that pass every other rule but fall below the minimum amount"
                )
                assert question["instructions"] == (
                    "What is the total of entries that pass every other rule but fall below the minimum amount?"
                )
            else:
                continue
            assert all(phrase in level for level in question["criteria"])
