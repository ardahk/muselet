from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


TOKEN = re.compile(r"[a-z0-9]+(?:['.][a-z0-9]+)*")
JEV_PIN = "609a664e81f46e03731600bd7bd9f1b7a61257c5"
TD_REVISION = "80cb93ae477fdfc91e3b6114f7a281c444dda843"


def words(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def grams(text: str, size: int = 13) -> set[tuple[str, ...]]:
    tokens = words(text)
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from strings(item)


def _jev_dir(root: Path) -> Path:
    for base in (root / "runs/bench/_src/jevbench", Path.home() / "research/jevbench"):
        if (base / ".git").exists():
            commit = subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"], text=True).strip()
            if commit == JEV_PIN:
                return base
    raise FileNotFoundError(f"pinned JevBench clone at {JEV_PIN} was not found")


def _new_reference() -> dict:
    return {
        "text_grams": set(),
        "option_sets": set(),
        "reference_rows": 0,
        "reference_questions": 0,
    }


def _add_reference_questions(reference: dict, questions):
    for question in questions:
        if question.get("type") not in ("choice", "noul", "score"):
            continue
        reference["reference_questions"] += 1
        _add_option_set(question, reference["option_sets"])


def load_reference_sets(root: Path) -> dict[str, dict]:
    import pyarrow.parquet as parquet

    references = {}
    jev_reference = _new_reference()
    jev = _jev_dir(root)
    for split in ("original", "easy", "hard"):
        path = jev / "datasets/public" / f"{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            question = row.get("question", {})
            jev_reference["reference_rows"] += 1
            jev_reference["reference_questions"] += 1
            jev_reference["text_grams"].update(
                grams(" ".join([str(row.get("state", "")), *strings(question)]))
            )
            for obj in _dicts(question):
                _add_option_set(obj, jev_reference["option_sets"])
    references["jevbench_public"] = jev_reference

    td_path = root / "data/bench/typed_decisions/test-00000-of-00001.parquet"
    if not td_path.is_file():
        raise FileNotFoundError(f"Typed Decisions test parquet missing at pinned revision {TD_REVISION}: {td_path}")
    table = parquet.read_table(td_path)
    td_reference = _new_reference()
    for raw in table.to_pylist():
        question_map = json.loads(raw["questions"])
        state = json.loads(raw["state"])
        td_reference["reference_rows"] += 1
        td_reference["reference_questions"] += len(question_map)
        td_reference["text_grams"].update(grams(" ".join(strings(state))))
        for question in question_map.values():
            td_reference["text_grams"].update(grams(" ".join(strings(question))))
            _add_option_set(question, td_reference["option_sets"])
    references["typed_decisions_test"] = td_reference

    for name, rel in (
        ("route_v1", "evals/route_v1.jsonl"),
        ("live_t1", "evals/live_t1.jsonl"),
        ("external_utterances", "evals/external/utterances.jsonl"),
    ):
        reference = _new_reference()
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"required contamination reference missing: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            reference["reference_rows"] += 1
            reference["text_grams"].update(grams(" ".join(strings(row))))
            _add_reference_questions(reference, (item for item in _dicts(row)))
        references[name] = reference
    return references


def load_references(root: Path) -> tuple[set[tuple[str, ...]], set[frozenset[str]]]:
    groups = load_reference_sets(root)
    text_grams = set().union(*(group["text_grams"] for group in groups.values()))
    option_sets = set().union(*(group["option_sets"] for group in groups.values()))
    return text_grams, option_sets


def _add_option_set(question: dict, option_sets: set[frozenset[str]]):
    kind, criteria = question.get("type"), question.get("criteria", {})
    if kind == "noul":
        return
    if kind == "choice":
        keys = criteria.keys() if isinstance(criteria, dict) else (item.get("key") for item in criteria)
        option_sets.add(frozenset(str(key).lower() for key in keys))
    elif kind == "score" and isinstance(criteria, list):
        option_sets.add(frozenset(str(level).lower() for level in criteria))


def _record_body(item: dict) -> str:
    return " ".join([
        item["state"],
        *(text for question in item["questions"].values()
          for text in [str(question.get("instructions", "")), *strings(question.get("criteria", {}))]),
    ])


def _question_options(question: dict) -> set[frozenset[str]]:
    options = set()
    _add_option_set(question, options)
    return options


def decontam(records: list[dict], root: Path) -> tuple[list[dict], dict]:
    reference_groups = load_reference_sets(root)
    reference_grams = set().union(*(group["text_grams"] for group in reference_groups.values()))
    option_sets = set().union(*(group["option_sets"] for group in reference_groups.values()))
    before_questions = sum(len(item["questions"]) for item in records)
    per_reference = {
        name: {
            "reference_rows": group["reference_rows"],
            "reference_questions": group["reference_questions"],
            "before": {"word_13gram_rows": 0, "option_set_questions": 0},
            "after": {"word_13gram_rows": 0, "option_set_questions": 0},
            "examples": {"word_13gram": [], "option_sets": []},
        }
        for name, group in reference_groups.items()
    }
    for item in records:
        item_grams = grams(_record_body(item))
        question_options = {
            qid: _question_options(question)
            for qid, question in item["questions"].items()
        }
        for name, group in reference_groups.items():
            text_matches = item_grams & group["text_grams"]
            if text_matches:
                per_reference[name]["before"]["word_13gram_rows"] += 1
                if len(per_reference[name]["examples"]["word_13gram"]) < 5:
                    per_reference[name]["examples"]["word_13gram"].append({
                        "record_id": item["id"],
                        "family": item["family"],
                        "match": " ".join(sorted(text_matches)[0]),
                    })
            for qid, candidates in question_options.items():
                matches = candidates & group["option_sets"]
                if matches:
                    per_reference[name]["before"]["option_set_questions"] += 1
                    if len(per_reference[name]["examples"]["option_sets"]) < 5:
                        matched_set = min(matches, key=lambda values: (len(values), tuple(sorted(values))))
                        per_reference[name]["examples"]["option_sets"].append({
                            "record_id": item["id"],
                            "family": item["family"],
                            "qid": qid,
                            "match": sorted(matched_set),
                        })
    kept, text_dropped, option_dropped = [], 0, 0
    for item in records:
        if grams(_record_body(item)) & reference_grams:
            text_dropped += 1
            continue
        questions = {}
        for qid, question in item["questions"].items():
            if _question_options(question) & option_sets:
                option_dropped += 1
                continue
            questions[qid] = question
        if questions:
            row = dict(item)
            row["questions"] = questions
            for key in ("gold", "gold_basis", "teacher", "target", "authored_answer", "rationale"):
                if isinstance(row.get(key), dict):
                    row[key] = {qid: value for qid, value in row[key].items() if qid in questions}
            kept.append(row)
    after_questions = sum(len(item["questions"]) for item in kept)
    remaining_text = sum(
        bool(grams(_record_body(item)) & reference_grams)
        for item in kept
    )
    remaining_options = 0
    for item in kept:
        item_grams = grams(_record_body(item))
        question_options = {
            qid: _question_options(question)
            for qid, question in item["questions"].items()
        }
        for name, group in reference_groups.items():
            if item_grams & group["text_grams"]:
                per_reference[name]["after"]["word_13gram_rows"] += 1
            for candidates in question_options.values():
                if candidates & group["option_sets"]:
                    per_reference[name]["after"]["option_set_questions"] += 1
    for item in kept:
        for question in item["questions"].values():
            remaining_options += int(bool(_question_options(question) & option_sets))
    report = {
        "rows_before": len(records), "rows_after": len(kept),
        "questions_before": before_questions, "questions_after": after_questions,
        "dropped_text_13gram_rows": text_dropped, "dropped_option_questions": option_dropped,
        "remaining_overlaps": {"word_13gram": remaining_text, "option_sets": remaining_options},
        "per_reference": per_reference,
    }
    if remaining_text or remaining_options:
        raise AssertionError("decontamination left reference overlaps")
    return kept, report


def _dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _dicts(item)
