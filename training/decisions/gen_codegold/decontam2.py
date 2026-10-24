from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from training.decisions import decontam as base

ROOT = Path(__file__).resolve().parents[3]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _reference_texts(root: Path):
    import pyarrow.parquet as parquet

    by_ref = defaultdict(list)
    jev = base._jev_dir(root)
    for split in ("original", "easy", "hard"):
        path = jev / "datasets/public" / f"{split}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            by_ref["jevbench_public"].extend(x for x in _strings(json.loads(line)) if x.strip())
    td = parquet.read_table(root / "data/bench/typed_decisions/test-00000-of-00001.parquet")
    for raw in td.to_pylist():
        by_ref["typed_decisions_test"].extend(x for x in _strings(raw) if x.strip())
    for name, rel in (
        ("route_v1", "evals/route_v1.jsonl"),
        ("live_t1", "evals/live_t1.jsonl"),
        ("external_utterances", "evals/external/utterances.jsonl"),
        ("route_v2", "runs/decisions/codegold/refs/route_v2.jsonl"),
    ):
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            by_ref[name].extend(x for x in _strings(json.loads(line)) if x.strip())
    return by_ref


def _short_index(by_ref):
    result = {}
    for name, texts in by_ref.items():
        buckets = defaultdict(set)
        for text in texts:
            tokens = tuple(base.words(text))
            if 2 < len(tokens) < 40:
                buckets[len(tokens)].add(tokens)
        result[name] = buckets
    return result


def _within_one(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    i = j = edits = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if len(left) == len(right):
                i += 1
                j += 1
            else:
                j += 1
    edits += len(right) - j
    return edits <= 1


def _matches(text: str, buckets) -> bool:
    tokens = tuple(base.words(text))
    if not tokens or len(tokens) >= 40:
        return False
    for size in (len(tokens) - 1, len(tokens), len(tokens) + 1):
        for candidate in buckets.get(size, ()):
            if _within_one(tokens, candidate):
                return True
    return False


def _question_texts(question):
    criteria = question.get("criteria", {})
    values = criteria.values() if isinstance(criteria, dict) else criteria
    return [str(question.get("instructions", "")), *(str(value) for value in values)]


def decontam2(records: list[dict], root: Path = ROOT):
    groups = base.load_reference_sets(root)
    route_v2 = base._new_reference()
    for line in (root / "runs/decisions/codegold/refs/route_v2.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        route_v2["reference_rows"] += 1
        route_v2["text_grams"].update(base.grams(" ".join(_strings(row))))
        for question in base._dicts(row):
            route_v2["reference_questions"] += 1
            base._add_option_set(question, route_v2["option_sets"])
    groups["route_v2"] = route_v2
    short_references = _short_index(_reference_texts(root))
    reference_grams = {name: group["text_grams"] for name, group in groups.items()}
    all_grams = set().union(*reference_grams.values())
    all_options = set().union(*(group["option_sets"] for group in groups.values()))
    report = {name: {"reference_rows": groups[name].get("reference_rows", 0),
                     "reference_questions": groups[name].get("reference_questions", 0),
                     "before": {"word_13gram_rows": 0, "option_set_questions": 0,
                                "short_question_or_state": 0},
                     "after": {"word_13gram_rows": 0, "option_set_questions": 0,
                               "short_question_or_state": 0}}
              for name in groups}
    kept, rejected = [], []
    for item in records:
        body_grams = base.grams(base._record_body(item))
        matched_refs = [name for name, grams in reference_grams.items() if body_grams & grams]
        for name in matched_refs:
            report[name]["before"]["word_13gram_rows"] += 1
        short_state_hit = False
        if len(base.words(item["state"])) < 40:
            for name, buckets in short_references.items():
                if _matches(item["state"], buckets):
                    report[name]["before"]["short_question_or_state"] += 1
                    short_state_hit = True
        if matched_refs or short_state_hit:
            rejected.append({"id": item["id"], "reason": "row_overlap",
                             "references": matched_refs, "short_state": short_state_hit})
            continue
        questions = {}
        for qid, question in item["questions"].items():
            option_hit = bool(base._question_options(question) & all_options)
            short_hits = [name for name, buckets in short_references.items()
                          if any(_matches(text, buckets) for text in _question_texts(question))]
            if option_hit:
                for name, group in groups.items():
                    if base._question_options(question) & group["option_sets"]:
                        report[name]["before"]["option_set_questions"] += 1
            for name in short_hits:
                report[name]["before"]["short_question_or_state"] += 1
            if option_hit or short_hits:
                rejected.append({"id": item["id"], "qid": qid,
                                 "reason": "question_overlap", "short_references": short_hits,
                                 "option_set": option_hit})
                continue
            questions[qid] = question
        if questions:
            row = dict(item)
            row["questions"] = questions
            for field in ("gold", "gold_basis", "teacher", "teacher_samples", "target", "_meta"):
                if not isinstance(row.get(field), dict):
                    continue
                if field == "_meta":
                    meta = dict(row[field])
                    meta["surface"] = {qid: value for qid, value in meta.get("surface", {}).items()
                                       if qid in questions}
                    row[field] = meta
                else:
                    row[field] = {qid: value for qid, value in row[field].items() if qid in questions}
            kept.append(row)

    remaining = {"word_13gram_rows": 0, "option_set_questions": 0, "short_question_or_state": 0}
    for item in kept:
        body_grams = base.grams(base._record_body(item))
        for name, grams in reference_grams.items():
            if body_grams & grams:
                report[name]["after"]["word_13gram_rows"] += 1
                remaining["word_13gram_rows"] += 1
        if len(base.words(item["state"])) < 40:
            for name, buckets in short_references.items():
                if _matches(item["state"], buckets):
                    report[name]["after"]["short_question_or_state"] += 1
                    remaining["short_question_or_state"] += 1
        for qid, question in item["questions"].items():
            options = base._question_options(question)
            for name, group in groups.items():
                if options & group["option_sets"]:
                    report[name]["after"]["option_set_questions"] += 1
            if options & all_options:
                remaining["option_set_questions"] += 1
            for name, buckets in short_references.items():
                if any(_matches(text, buckets) for text in _question_texts(question)):
                    report[name]["after"]["short_question_or_state"] += 1
                    remaining["short_question_or_state"] += 1
    if any(remaining.values()):
        raise AssertionError(f"decontamination left overlaps: {remaining}")

    v1_path = Path.home() / "v1/data/records_decontam.jsonl"
    v1_rate = None
    if v1_path.is_file():
        rows = [json.loads(line) for line in v1_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        v1_grams = set().union(*(base.grams(base._record_body(row)) for row in rows))
        v1_rate = sum(bool(base.grams(base._record_body(row)) & v1_grams) for row in records) / max(1, len(records))
    stats = {
        "rows_before": len(records), "rows_after": len(kept),
        "questions_before": sum(len(x["questions"]) for x in records),
        "questions_after": sum(len(x["questions"]) for x in kept),
        "remaining_overlaps": remaining, "per_reference": report,
        "v1_13gram_overlap_rate_info_only": v1_rate,
        "rejections": rejected,
    }
    return kept, stats
