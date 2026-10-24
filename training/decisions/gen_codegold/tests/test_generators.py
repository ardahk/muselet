from __future__ import annotations

import random
import re
from collections import Counter, defaultdict

import pytest

from bench.systemone.schema import parse_request
from training.decisions.build import _chi_square_position, _leak_errors
from training.decisions.gen_codegold import FAMILIES
from training.decisions.gen_codegold.families import GENERATORS
from training.decisions.gen_codegold.families import (
    cg_counting, cg_long_policy, cg_multi_hop, cg_numeric,
    cg_probability, cg_temporal, cg_trap,
)

MODULES = {
    "cg_counting": cg_counting, "cg_multi_hop": cg_multi_hop,
    "cg_long_policy": cg_long_policy, "cg_temporal": cg_temporal,
    "cg_numeric": cg_numeric, "cg_probability": cg_probability, "cg_trap": cg_trap,
}


def _record(family, seed):
    rng = random.Random(seed)
    return GENERATORS[family](rng, rng.randint(2, 5))


@pytest.mark.parametrize("family", FAMILIES)
def test_generators_validate_schema_and_independent_gold(family):
    verifier = MODULES[family].verify_rendered
    for seed in range(200):
        record = _record(family, seed)
        assert 2 <= len(record["questions"]) <= 5
        parse_request({"state": record["state"], "questions": record["questions"]})
        assert set(record["gold"]) == set(record["questions"])
        assert set(record["gold_basis"].values()) == {"code"}
        assert record["_meta"]["traps"]
        assert set(record["_meta"]["surface"]) == set(record["questions"])
        assert not _leak_errors(record)
        for qid, question in record["questions"].items():
            kind, criteria = question["type"], question["criteria"]
            if kind == "choice":
                assert 2 <= len(criteria) <= 26
                assert len(criteria) == len(set(criteria))
                assert record["gold"][qid] in criteria
            elif kind == "score":
                assert 3 <= len(criteria) <= 6
                assert record["gold"][qid] in {str(i) for i in range(len(criteria))}
                if family in {
                    "cg_counting", "cg_multi_hop", "cg_numeric",
                    "cg_temporal", "cg_probability", "cg_trap", "cg_long_policy",
                }:
                    assert all("less than" in band.lower() for band in criteria[:-1])
                    assert "at least" in criteria[-1].lower()
                else:
                    assert all(">=" in band and "<" in band for band in criteria[:-1])
                    assert ">=" in criteria[-1] and "<" not in criteria[-1]
            else:
                assert set(criteria) == {"false", "true"}
                assert record["gold"][qid] in criteria
    assert all(verifier(_record(family, seed)) for seed in range(200))


@pytest.mark.parametrize("family", FAMILIES)
def test_generator_distributions(family):
    rng = random.Random(880_123 + FAMILIES.index(family))
    records, noul, score, option_counts = [], Counter(), defaultdict(Counter), Counter()
    tokens = []
    for _ in range(2000):
        record = GENERATORS[family](rng, rng.randint(2, 5))
        records.append(record)
        tokens.append(record["_meta"]["approx_tokens"])
        for qid, question in record["questions"].items():
            if question["type"] == "noul":
                noul[record["gold"][qid]] += 1
            elif question["type"] == "score":
                count = len(question["criteria"])
                score[count][record["gold"][qid]] += 1
            else:
                option_counts[len(question["criteria"])] += 1

    true_share = noul["true"] / sum(noul.values())
    assert 0.45 <= true_share <= 0.55
    assert _chi_square_position(records)[-1] > 0.05
    assert option_counts
    assert all(2 <= option_count <= 26 for option_count in option_counts)
    for count, levels in score.items():
        total = sum(levels.values())
        expected = total / count
        assert set(levels) == {str(i) for i in range(count)}
        assert all(0.5 * expected <= levels[str(i)] <= 1.5 * expected for i in range(count))
    if family == "cg_long_policy":
        assert min(tokens) >= 2000
        assert max(tokens) <= 6000
        assert max(tokens) - min(tokens) >= 1000


def test_word_level_distance_is_bounded():
    from training.decisions.gen_codegold.decontam2 import _within_one

    assert _within_one(("alpha", "beta"), ("alpha", "gamma"))
    assert _within_one(("alpha", "beta"), ("alpha", "beta", "gamma"))
    assert not _within_one(("alpha", "beta"), ("gamma", "delta"))


@pytest.mark.parametrize("family", ["cg_temporal", "cg_probability", "cg_trap", "cg_long_policy"])
def test_rebuilt_family_notes_are_mistake_derived(family):
    rng = random.Random(12_345 + FAMILIES.index(family))
    included = correct = 0
    for _ in range(2_000):
        record = GENERATORS[family](rng, rng.randint(2, 5))
        note = record["_meta"]["staff_note"]
        included += note["included"]
        correct += bool(note["included"] and note["correct"])
        assert MODULES[family].verify_rendered(record)
    assert 0.60 <= included / 2_000 <= 0.70
    assert 0.25 <= correct / included <= 0.35


def test_long_policy_has_balanced_schema_outcomes_and_nonrepetitive_filler():
    rng = random.Random(84_219)
    outcomes = defaultdict(Counter)
    schemas = set()
    for _ in range(2_000):
        record = cg_long_policy.generate(rng, rng.randint(2, 5))
        schema = record["_meta"]["schema"]
        schemas.add(schema)
        outcomes[schema][record["_meta"]["outcome"]] += 1
        filler = record["state"].split("ADMINISTRATIVE REFERENCE NOTES\n", 1)[1]
        sentences = re.split(r"(?<=[.!?])\s+", filler.strip())
        assert max(Counter(sentences).values()) <= 2
        assert cg_long_policy.verify_rendered(record)
    assert len(schemas) >= 5
    for counts in outcomes.values():
        assert set(counts) == {
            "not_covered", "late", "not_eligible", "exception_authorized", "full", "partial"
        }
        assert max(counts.values()) / sum(counts.values()) <= 0.40


def test_long_policy_dispositions_are_natural_and_letter_presence_is_not_asked():
    for seed in range(300):
        record = _record("cg_long_policy", seed + 3_000)
        assert all(
            question["instructions"] != "Is a signed case letter present in the file?"
            for question in record["questions"].values()
        )
        for question in record["questions"].values():
            if question["instructions"] != "Which disposition follows from the schedule?":
                continue
            assert all(
                text.startswith("The request is ")
                and " because " in text
                and text.endswith(".")
                for text in question["criteria"].values()
            )
        assert cg_long_policy.verify_rendered(record)


def test_prose_sections_are_substrings_and_verifier_independent():
    for family in FAMILIES:
        verifier = MODULES[family].verify_rendered
        for seed in range(8):
            record = _record(family, 120_000 + seed)
            sections = record["_meta"]["prose_sections"]
            assert sections
            for section in sections:
                assert section in record["state"]
                words = section.split()
                random.Random(seed + len(section)).shuffle(words)
                trial = dict(record)
                trial["state"] = record["state"].replace(section, " ".join(words), 1)
                assert verifier(trial), (family, section)


def test_each_trap_type_is_decisive_in_generated_records():
    rng = random.Random(31_415)
    deciding = Counter()
    totals = Counter()
    for _ in range(3_000):
        record = GENERATORS["cg_trap"](rng, rng.randint(2, 5))
        trap_type = record["_meta"]["trap_type"]
        totals[trap_type] += 1
        deciding[trap_type] += bool(record["_meta"]["facts"]["case"]["decisive"])
    assert set(totals) == {"negation", "source_precedence", "irrelevant_number"}
    assert all(deciding[kind] / totals[kind] >= 0.20 for kind in totals)


def _state_without_note(record):
    note = record["_meta"].get("narrative_section", "")
    return record["state"].replace(note, "", 1) if note else record["state"]


def _choice_value_literals(text):
    timestamps = re.findall(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?:Z| [A-Z]{2,4})?\b", text)
    remainder = re.sub(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?:Z| [A-Z]{2,4})?\b", "", text)
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", remainder)
    amounts = re.findall(r"\$\s?\d[\d,]*(?:\.\d{1,2})?", text)
    quantities = re.findall(
        r"\b\d+\s+(?:eligible\s+)?(?:transactions?|units?|cases?|proposals?|events?|records?)\b",
        text,
        flags=re.IGNORECASE,
    )
    identifiers = re.findall(r"\b(?:VN|AG|FX|PC|AUD)-\d{3,}\b", text)
    return [*timestamps, *dates, *amounts, *quantities, *identifiers]


@pytest.mark.parametrize("family", FAMILIES)
def test_choice_answers_and_audited_intermediates_are_not_repeated(family):
    for seed in range(100):
        record = _record(family, 90_000 + seed)
        visible_state = _state_without_note(record)
        for qid, question in record["questions"].items():
            if question["type"] != "choice":
                continue
            gold_text = question["criteria"][record["gold"][qid]]
            assert gold_text not in visible_state
            for literal in _choice_value_literals(gold_text):
                assert literal not in visible_state, (family, seed, qid, literal)
        for value in record["_leak_audit"]["intermediate_values"]:
            assert value not in visible_state, (family, seed, value)


def test_temporal_intake_clock_is_coherent_and_dst_aware():
    rng = random.Random(77_031)
    hidden_offsets = near_dst = 0
    for _ in range(2_000):
        record = cg_temporal.generate(rng, rng.randint(2, 5))
        data = cg_temporal._read_state(record["state"])
        cutoff_line = re.search(
            r"^Daily cutoff timestamp: (.+) \[([A-Za-z_]+/[A-Za-z_]+)\]$",
            record["state"],
            re.MULTILINE,
        )
        receipt_line = re.search(
            r"^Receipt timestamp: (.+) \[([A-Za-z_]+/[A-Za-z_]+)\]$",
            record["state"],
            re.MULTILINE,
        )
        assert cutoff_line and receipt_line
        cutoff_local = data["cutoff"].astimezone(
            cg_temporal.ZoneInfo(cutoff_line.group(2))
        )
        receipt_local = data["receipt"].astimezone(
            cg_temporal.ZoneInfo(receipt_line.group(2))
        )
        assert cutoff_local.date() == data["deadline"]
        assert abs((receipt_local.date() - data["deadline"]).days) <= 1
        if not record["_meta"]["clock_offset_visible"]:
            hidden_offsets += 1
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", cutoff_line.group(1))
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", receipt_line.group(1))
        near_dst += record["_meta"]["deadline_near_dst"]
        assert cg_temporal.verify_rendered(record)
        assert "computed anniversary is" not in record["state"].lower()
        assert "window ending on" not in record["state"].lower()
    assert hidden_offsets / 2_000 >= 0.50
    assert near_dst / 2_000 >= 0.30


def test_probability_independent_pool_omits_event_rate_read_off():
    for seed in range(500):
        record = _record("cg_probability", seed + 1_200)
        assert all(
            question["instructions"] != "Which event has the highest individual probability?"
            for question in record["questions"].values()
        )


def test_trap_pools_only_offer_sources_present_in_each_schema():
    for seed in range(1_000):
        record = _record("cg_trap", seed + 12_000)
        case = record["_meta"]["facts"]["case"]
        assert not (
            case["kind"] == "irrelevant_number"
            and any(
                question["instructions"] == "Is a signed exception on file?"
                for question in record["questions"].values()
            )
        )
        for question in record["questions"].values():
            if question["instructions"] != "Which record controls this claim review?":
                continue
            sources = [
                re.search(r"controlling record is the (.+)\.", option).group(1)
                for option in question["criteria"].values()
            ]
            assert len(sources) == len(set(sources))
            assert all(source.lower() in record["state"].lower() for source in sources)
