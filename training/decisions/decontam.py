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


def _pilot_references(root: Path) -> tuple[set[tuple[str, ...]], set[frozenset[str]], int, int]:
    path = root / "runs/decisions/pilot/records_decontam.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"pilot decontamination reference missing: {path}")
    text_grams, option_sets = set(), set()
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = 0
    for row in records:
        text_grams.update(grams(" ".join([row.get("state", ""), *strings(row.get("questions", {}))])))
        for question in row.get("questions", {}).values():
            questions += 1
            _add_option_set(question, option_sets)
    return text_grams, option_sets, len(records), questions


def load_references(root: Path, include_pilot: bool = False) -> tuple[set[tuple[str, ...]], set[frozenset[str]]]:
    import pyarrow.parquet as parquet

    text_grams, option_sets = set(), set()
    jev = _jev_dir(root)
    for split in ("original", "easy", "hard"):
        path = jev / "datasets/public" / f"{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            text_grams.update(grams(" ".join([str(row.get("state", "")), *strings(row.get("question", {}))])))
            for obj in _dicts(row.get("question", {})):
                _add_option_set(obj, option_sets)
    td_path = root / "data/bench/typed_decisions/test-00000-of-00001.parquet"
    if not td_path.is_file():
        raise FileNotFoundError(f"Typed Decisions test parquet missing at pinned revision {TD_REVISION}: {td_path}")
    table = parquet.read_table(td_path)
    for raw in table.to_pylist():
        question_map = json.loads(raw["questions"])
        state = json.loads(raw["state"])
        text_grams.update(grams(" ".join(strings(state))))
        for question in question_map.values():
            text_grams.update(grams(" ".join(strings(question))))
            _add_option_set(question, option_sets)
    for rel in ("evals/route_v1.jsonl", "evals/live_t1.jsonl", "evals/external/utterances.jsonl"):
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"required contamination reference missing: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            text_grams.update(grams(" ".join(strings(json.loads(line)))))
    if include_pilot:
        pilot_grams, pilot_options, _, _ = _pilot_references(root)
        text_grams.update(pilot_grams)
        option_sets.update(pilot_options)
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


def decontam(records: list[dict], root: Path, include_pilot: bool = False) -> tuple[list[dict], dict]:
    reference_grams, option_sets = load_references(root, include_pilot=include_pilot)
    pilot_grams, pilot_options, pilot_rows, pilot_questions = (
        _pilot_references(root) if include_pilot else (set(), set(), 0, 0)
    )
    before_questions = sum(len(item["questions"]) for item in records)
    pilot_text_before = pilot_option_before = 0
    if include_pilot:
        for item in records:
            body = " ".join([
                item["state"],
                *(text for question in item["questions"].values()
                  for text in [str(question.get("instructions", "")), *strings(question.get("criteria", {}))]),
            ])
            pilot_text_before += int(bool(grams(body) & pilot_grams))
            for question in item["questions"].values():
                candidate = set()
                _add_option_set(question, candidate)
                pilot_option_before += int(bool(candidate & pilot_options))
    kept, text_dropped, option_dropped = [], 0, 0
    for item in records:
        body = " ".join([item["state"], *(
            text for question in item["questions"].values()
            for text in [str(question.get("instructions", "")), *strings(question.get("criteria", {}))]
        )])
        if grams(body) & reference_grams:
            text_dropped += 1
            continue
        questions = {}
        for qid, question in item["questions"].items():
            candidate = set()
            _add_option_set(question, candidate)
            if candidate and candidate & option_sets:
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
        bool(grams(" ".join([item["state"], *(
            text for question in item["questions"].values()
            for text in [str(question.get("instructions", "")), *strings(question.get("criteria", {}))]
        )])) & reference_grams)
        for item in kept
    )
    remaining_options = 0
    for item in kept:
        for question in item["questions"].values():
            candidate = set()
            _add_option_set(question, candidate)
            remaining_options += int(bool(candidate & option_sets))
    report = {
        "rows_before": len(records), "rows_after": len(kept),
        "questions_before": before_questions, "questions_after": after_questions,
        "dropped_text_13gram_rows": text_dropped, "dropped_option_questions": option_dropped,
        "pilot_reference_rows": pilot_rows, "pilot_reference_questions": pilot_questions,
        "pilot_overlaps_before": {
            "word_13gram_rows": pilot_text_before, "option_set_questions": pilot_option_before,
        },
        "remaining_overlaps": {"word_13gram": remaining_text, "option_sets": remaining_options},
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
