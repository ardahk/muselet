"""Structural checks for the frozen memory followups evaluation set."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

QUOTAS = {
    "site_search": 30,
    "pronoun_person": 20,
    "pronoun_item": 20,
    "again": 15,
    "undo": 15,
    "correction": 15,
    "refinement": 15,
    "stale": 15,
    "unrelated": 30,
    "longterm": 25,
}
SPLITS = {"tune", "holdout"}
LONGTERM_TYPES = {"person", "place", "folder", "file", "site", "app", "preference", "contact"}
CTX_KEYS = {"app", "focused", "selection", "online", "url", "window_title", "t"}
SPECIAL_SKILLS = {"planner", "ASK", "ANSWER"}


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict]:
    path = Path(__file__).resolve().parents[1] / "skills" / "catalog.json"
    data = json.loads(path.read_text())
    return {skill["name"]: skill for skill in data["skills"]}


def lint(rows: list[dict]) -> list[str]:
    problems = []
    counts = Counter()
    splits = Counter()
    ids = set()
    catalog = _catalog()

    for row_number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            problems.append(f"line {row_number}: row must be an object")
            continue
        row_id = row.get("id")
        prefix = row_id if isinstance(row_id, str) and row_id else f"line {row_number}"

        def problem(message: str, turn_index: int | None = None) -> None:
            location = f"{prefix} turn {turn_index}" if turn_index is not None else prefix
            problems.append(f"{location}: {message}")

        expected_row_keys = {"id", "split", "category", "longterm", "turns"}
        if set(row) != expected_row_keys:
            problem(f"row keys must be exactly {sorted(expected_row_keys)}")

        if not isinstance(row_id, str) or re.fullmatch(r"mf-\d{4}", row_id) is None:
            problem("id must match mf-####")
        if isinstance(row_id, str):
            if row_id in ids:
                problem("duplicate id")
            ids.add(row_id)

        split = row.get("split")
        if not isinstance(split, str) or split not in SPLITS:
            problem("split must be tune or holdout")

        category = row.get("category")
        if not isinstance(category, str) or category not in QUOTAS:
            problem("unknown category")
        else:
            counts[category] += 1
            if isinstance(split, str) and split in SPLITS:
                splits[(category, split)] += 1

        longterm = row.get("longterm")
        if not isinstance(longterm, list):
            problem("longterm must be a list")
        else:
            for index, memory in enumerate(longterm):
                location = f"longterm[{index}]"
                if not isinstance(memory, dict):
                    problem(f"{location} must be an object")
                    continue
                keys = {"type", "key", "value"}
                if set(memory) != keys:
                    problem(f"{location} keys must be exactly {sorted(keys)}")
                for key in keys:
                    value = memory.get(key)
                    if not isinstance(value, str) or not value.strip():
                        problem(f"{location}.{key} must be a non-empty string")
                memory_type = memory.get("type")
                if not isinstance(memory_type, str) or memory_type not in LONGTERM_TYPES:
                    problem(f"{location}.type is invalid")

        turns = row.get("turns")
        if not isinstance(turns, list):
            problem("turns must be a list")
            continue
        if not 2 <= len(turns) <= 5:
            problem("turns must contain 2 to 5 items")

        previous_t = None
        for turn_index, turn in enumerate(turns):
            if not isinstance(turn, dict):
                problem("turn must be an object", turn_index)
                continue
            expected_turn_keys = {"utterance", "ctx", "outcome", "expect"}
            if set(turn) != expected_turn_keys:
                problem(f"turn keys must be exactly {sorted(expected_turn_keys)}", turn_index)

            utterance = turn.get("utterance")
            if not isinstance(utterance, str) or not utterance.strip():
                problem("utterance must be a non-empty string", turn_index)

            ctx = turn.get("ctx")
            if not isinstance(ctx, dict):
                problem("ctx must be an object", turn_index)
                ctx = {}
            if set(ctx) != CTX_KEYS:
                problem(f"ctx keys must be exactly {sorted(CTX_KEYS)}", turn_index)
            for key in ("app", "focused", "url", "window_title"):
                if not isinstance(ctx.get(key), str):
                    problem(f"ctx.{key} must be a string", turn_index)
            for key in ("selection", "online"):
                if not isinstance(ctx.get(key), bool):
                    problem(f"ctx.{key} must be a boolean", turn_index)

            current_t = ctx.get("t")
            valid_t = isinstance(current_t, (int, float)) and not isinstance(current_t, bool)
            if not valid_t:
                problem("ctx.t must be a number", turn_index)
            else:
                if turn_index == 0 and current_t != 0:
                    problem("first turn ctx.t must be 0", turn_index)
                if previous_t is not None and current_t <= previous_t:
                    problem("ctx.t must be strictly increasing", turn_index)
                previous_t = current_t

            app = ctx.get("app")
            url = ctx.get("url")
            if isinstance(app, str) and isinstance(url, str):
                browser = app in {"Zen", "Safari", "Google Chrome"}
                if browser and not url.strip():
                    problem("ctx.url must be non-empty for browser apps", turn_index)
                elif not browser and url:
                    problem("ctx.url must be empty for non-browser apps", turn_index)

            outcome = turn.get("outcome")
            if not isinstance(outcome, dict):
                problem("outcome must be an object", turn_index)
            else:
                required = {"skill", "args", "ok"}
                if not required.issubset(outcome) or set(outcome) - required - {"said"}:
                    problem("outcome keys must be skill, args, ok, and optional said", turn_index)
                skill = outcome.get("skill")
                args = outcome.get("args")
                if not isinstance(skill, str) or not skill:
                    problem("outcome.skill must be a non-empty string", turn_index)
                if not isinstance(args, dict):
                    problem("outcome.args must be an object", turn_index)
                    args = {}
                if not isinstance(outcome.get("ok"), bool):
                    problem("outcome.ok must be a boolean", turn_index)
                if "said" in outcome and not isinstance(outcome["said"], str):
                    problem("outcome.said must be a string", turn_index)

                if isinstance(skill, str) and skill:
                    if skill in catalog:
                        allowed_args = {arg["name"]: arg for arg in catalog[skill].get("args", [])}
                        for name in args.keys() - allowed_args.keys():
                            problem(f"unknown argument {name!r} for skill {skill!r}", turn_index)
                        for name, arg in allowed_args.items():
                            if arg.get("required") and name not in args:
                                problem(f"missing required argument {name!r} for skill {skill!r}", turn_index)
                            values = arg.get("enum", arg.get("values"))
                            if name in args and isinstance(values, list) and args[name] not in values:
                                problem(f"invalid value for argument {name!r} of skill {skill!r}", turn_index)
                    elif skill in SPECIAL_SKILLS:
                        expected_arg = {"planner": "goal", "ASK": "question"}.get(skill)
                        if expected_arg:
                            if set(args) != {expected_arg} or not isinstance(args.get(expected_arg), str):
                                problem(f"{skill} args must contain only a string {expected_arg!r}", turn_index)
                    else:
                        problem(f"unknown skill {skill!r}", turn_index)

            expect = turn.get("expect")
            if not isinstance(expect, dict):
                problem("expect must be an object", turn_index)
                continue
            expect_type = expect.get("type")
            if isinstance(expect_type, str) and expect_type in {"unchanged", "not_resolved"}:
                if set(expect) != {"type"}:
                    problem(f"{expect_type} expect must contain only type", turn_index)
            elif expect_type == "rewrite":
                if set(expect) != {"type", "all", "none"}:
                    problem("rewrite expect keys must be type, all, none", turn_index)
                all_values = expect.get("all")
                if (not isinstance(all_values, list) or not all_values or
                        any(not isinstance(group, list) or not group or
                            any(not isinstance(value, str) or not value.strip() for value in group)
                            for group in all_values)):
                    problem("rewrite expect all must be a non-empty list of non-empty string lists", turn_index)
                none_values = expect.get("none")
                if (not isinstance(none_values, list) or
                        any(not isinstance(value, str) or not value.strip() for value in none_values)):
                    problem("rewrite expect none must be a list of non-empty strings", turn_index)
            else:
                problem("expect.type must be unchanged, not_resolved, or rewrite", turn_index)

    for category, quota in QUOTAS.items():
        if counts[category] != quota:
            problems.append(f"dataset: category {category} has {counts[category]} rows; expected {quota}")
        tune, holdout = splits[(category, "tune")], splits[(category, "holdout")]
        if abs(tune - holdout) > 1:
            problems.append(f"dataset: category {category} split counts differ by more than 1")
    return problems


def _summary(rows: list[dict]) -> str:
    categories = {
        category: {split: sum(
            isinstance(row, dict) and row.get("category") == category and row.get("split") == split
            for row in rows
        ) for split in sorted(SPLITS)}
        for category in QUOTAS
    }
    split_counts = {split: sum(
        isinstance(row, dict) and row.get("split") == split for row in rows
    ) for split in sorted(SPLITS)}
    return f"OK: {len(rows)} rows; splits={split_counts}; categories={categories}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path,
                        default=Path(__file__).resolve().with_name("memory_followups.jsonl"))
    path = parser.parse_args().path
    rows = []
    problems = []
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        return 1
    for line_number, line in enumerate(lines, 1):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            problems.append(f"line {line_number}: invalid JSON: {exc.msg}")
    problems.extend(lint(rows))
    if problems:
        print("\n".join(problems))
        return 1
    print(_summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
