#!/usr/bin/env python3
"""Collect planner demonstrations from the OpenAI and Anthropic teachers."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import anthropic
import openai

import render


MODELS = {
    "openai": "gpt-5.6-sol",
    "anthropic": "claude-opus-5-5",
}
MAX_ATTEMPTS = 6
RETRY_DELAYS = (1, 2, 4, 8, 16)
REQUIRED_FIELDS = ("id", "goal", "observation", "last_batch", "script_output")
_file_lock = threading.Lock()
_stop_launching = threading.Event()


def _read_states(path: Path, only_ids: set[str] | None, limit: int | None) -> list[dict[str, Any]]:
    states = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                state = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            missing = [field for field in REQUIRED_FIELDS if field not in state]
            if missing:
                raise ValueError(f"{path}:{line_number}: missing required fields: {', '.join(missing)}")
            if only_ids is not None and state["id"] not in only_ids:
                continue
            states.append(state)
            if limit is not None and len(states) >= limit:
                break
    return states


def _read_rows(replies_path: Path) -> list[dict[str, Any]]:
    if not replies_path.exists():
        return []
    rows = []
    with replies_path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{replies_path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def _row_cost(row: dict[str, Any]) -> float:
    usage = row.get("usage") or {}
    input_tokens = int(usage.get("input") or 0)
    cached = int(usage.get("cached_input") or 0)
    cache_write = int(usage.get("cache_write") or 0)
    output_tokens = int(usage.get("output") or 0)
    if row.get("teacher") == "openai":
        input_cost = (max(0, input_tokens - cached) * 4.0) + (cached * 1.0)
    else:
        input_cost = (input_tokens * 4.0) + (cached * 0.4) + (cache_write * 5.0)
    return (input_cost + output_tokens * 20.0) / 1_000_000


def spend(directory: str | Path) -> dict[str, Any]:
    """Summarize recorded API usage and estimated cost for a run directory."""
    replies_path = Path(directory).expanduser() / "replies.jsonl"
    summary: dict[str, Any] = {"models": {}, "total_calls": 0, "total_tokens": 0, "total_usd": 0.0}
    for row in _read_rows(replies_path):
        model = row.get("model") or MODELS.get(row.get("teacher"), "unknown")
        usage = row.get("usage") or {}
        model_summary = summary["models"].setdefault(
            model,
            {
                "calls": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "cache_write_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0,
                "usd": 0.0,
            },
        )
        input_tokens = int(usage.get("input") or 0)
        cached = int(usage.get("cached_input") or 0)
        cache_write = int(usage.get("cache_write") or 0)
        output_tokens = int(usage.get("output") or 0)
        reasoning = int(usage.get("reasoning") or 0)
        token_total = input_tokens + output_tokens
        if row.get("teacher") == "anthropic":
            token_total += cached + cache_write
        model_summary["calls"] += 1
        model_summary["input_tokens"] += input_tokens
        model_summary["cached_input_tokens"] += cached
        model_summary["cache_write_tokens"] += cache_write
        model_summary["output_tokens"] += output_tokens
        model_summary["reasoning_tokens"] += reasoning
        model_summary["total_tokens"] += token_total
        model_summary["usd"] += _row_cost(row)
        summary["total_calls"] += 1
        summary["total_tokens"] += token_total
        summary["total_usd"] += _row_cost(row)
    for model_summary in summary["models"].values():
        model_summary["usd"] = round(model_summary["usd"], 8)
    summary["total_usd"] = round(summary["total_usd"], 8)
    return summary


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429 or (isinstance(status, int) and 500 <= status <= 599):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    name = type(exc).__name__.lower()
    return any(part in name for part in ("ratelimit", "connection", "timeout", "internalserver"))


def _safe_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    for secret_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN"):
        secret = os.environ.get(secret_name)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9]{12,})\b", "[REDACTED]", message)


def _record(replies_path: Path, row: dict[str, Any]) -> None:
    with _file_lock:
        with replies_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()


def _budget_reached(replies_path: Path, budget: float) -> bool:
    with _file_lock:
        return spend(replies_path.parent)["total_usd"] >= budget


def _call_openai(state: dict[str, Any], effort: str) -> tuple[str, str | None, dict[str, int]]:
    client = openai.OpenAI(timeout=300)
    messages = render.messages(state)
    response = client.chat.completions.create(
        model=MODELS["openai"],
        messages=messages,
        max_completion_tokens=6000,
        reasoning_effort=effort,
    )
    choice = response.choices[0]
    usage = response.usage
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    counts = {
        "input": int(getattr(usage, "prompt_tokens", 0) or 0),
        "cached_input": int(getattr(prompt_details, "cached_tokens", 0) or 0),
        "cache_write": 0,
        "output": int(getattr(usage, "completion_tokens", 0) or 0),
        "reasoning": int(getattr(completion_details, "reasoning_tokens", 0) or 0),
    }
    return choice.message.content or "", choice.finish_reason, counts


def _call_anthropic(state: dict[str, Any]) -> tuple[str, str | None, dict[str, int]]:
    client = anthropic.Anthropic(timeout=300)
    messages = render.messages(state)
    response = client.messages.create(
        model=MODELS["anthropic"],
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": messages[0]["content"],
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": messages[1]["content"]}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    usage = response.usage
    counts = {
        "input": int(getattr(usage, "input_tokens", 0) or 0),
        "cached_input": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        "cache_write": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        "output": int(getattr(usage, "output_tokens", 0) or 0),
        "reasoning": 0,
    }
    return text, response.stop_reason, counts


def _run_call(
    state: dict[str, Any],
    teacher: str,
    effort: str,
    replies_path: Path,
    budget: float,
) -> dict[str, Any] | None:
    finish_key = "finish_reason" if teacher == "openai" else "stop_reason"
    model = MODELS[teacher]
    if _stop_launching.is_set() or _budget_reached(replies_path, budget):
        _stop_launching.set()
        return None

    started = time.monotonic()
    text = None
    reason = None
    error = None
    usage = {"input": 0, "cached_input": 0, "cache_write": 0, "output": 0, "reasoning": 0}
    for attempt in range(MAX_ATTEMPTS):
        try:
            if teacher == "openai":
                text, reason, usage = _call_openai(state, effort)
            else:
                text, reason, usage = _call_anthropic(state)
            break
        except Exception as exc:
            error = _safe_error(exc)
            if not _retryable(exc) or attempt + 1 >= MAX_ATTEMPTS:
                break
            time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])

    row = {
        "id": state["id"],
        "teacher": teacher,
        "model": model,
        "text": text,
        finish_key: reason,
        "usage": usage,
        "ms": round((time.monotonic() - started) * 1000, 1),
        "error": error,
    }
    _record(replies_path, row)
    return row


def _print_summary(summary: dict[str, Any]) -> None:
    for model, values in sorted(summary["models"].items()):
        print(
            f"{model}: calls={values['calls']} tokens={values['total_tokens']} "
            f"(input={values['input_tokens']}, cached={values['cached_input_tokens']}, "
            f"cache_write={values['cache_write_tokens']}, output={values['output_tokens']}) "
            f"USD=${values['usd']:.6f}"
        )
    print(f"Total: calls={summary['total_calls']} tokens={summary['total_tokens']} USD=${summary['total_usd']:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("~/data/planner_demos"))
    parser.add_argument("--only-ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--openai-effort", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--conc", type=int, default=8)
    parser.add_argument("--budget-stop", type=float, default=85)
    args = parser.parse_args()
    if args.conc < 1:
        parser.error("--conc must be at least 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.budget_stop < 0:
        parser.error("--budget-stop must not be negative")

    out_dir = args.out.expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    replies_path = out_dir / "replies.jsonl"
    states = _read_states(args.states, set(args.only_ids.split(",")) if args.only_ids else None, args.limit)
    existing = _read_rows(replies_path)
    completed = {(row.get("id"), row.get("teacher")) for row in existing if not row.get("error")}
    calls = [
        (state, teacher)
        for state in states
        for teacher in ("openai", "anthropic")
        if (state["id"], teacher) not in completed
    ]
    _stop_launching.clear()
    if spend(out_dir)["total_usd"] >= args.budget_stop:
        print(f"Budget stop: existing spend is at or above ${args.budget_stop:.2f}; no calls launched.")
        summary = spend(out_dir)
    elif not calls:
        print("No teacher calls needed; all selected state/teacher pairs already have successful replies.")
        summary = spend(out_dir)
    else:
        iterator = iter(calls)
        active = set()
        stopped = False
        with ThreadPoolExecutor(max_workers=args.conc) as pool:
            def submit_one() -> bool:
                nonlocal stopped
                if _stop_launching.is_set() or _budget_reached(replies_path, args.budget_stop):
                    _stop_launching.set()
                    stopped = True
                    return False
                try:
                    state, teacher = next(iterator)
                except StopIteration:
                    return False
                active.add(pool.submit(_run_call, state, teacher, args.openai_effort, replies_path, args.budget_stop))
                return True

            while len(active) < args.conc and submit_one():
                pass
            while active:
                done, active = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    result = future.result()
                    if result is None:
                        stopped = True
                if stopped:
                    _stop_launching.set()
                while not stopped and len(active) < args.conc and submit_one():
                    pass
        if stopped:
            print(f"Budget stop reached at ${spend(out_dir)['total_usd']:.6f}; remaining calls were not launched.")
        summary = spend(out_dir)

    _print_summary(summary)
    (out_dir / "spend.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
