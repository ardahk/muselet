"""Shared lifecycle, predicate, template, and reporting code for benchmarks."""

from __future__ import annotations

import asyncio
import inspect
import json
import math
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable


_TEMPLATE = re.compile(r"\{\{([a-z_]+)\}\}")
_SCRIPT_LANGS = ("applescript", "shell", "jxa")


def template_values(
    *, sandbox: Path | None = None, today: date | None = None
) -> dict[str, str]:
    today = today or date.today()
    friday_delta = (4 - today.weekday()) % 7 or 7
    next_friday = date.fromordinal(today.toordinal() + friday_delta)
    return {
        "sandbox": str(sandbox or Path.home() / "MuseletSandbox"),
        "tomorrow_ymd": _ymd(date.fromordinal(today.toordinal() + 1)),
        "next_friday_ymd": _ymd(next_friday),
    }


def _ymd(value: date) -> str:
    return f"{value.year}-{value.month}-{value.day}"


def resolve_templates(value: Any, values: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _TEMPLATE.sub(
            lambda match: values.get(match.group(1), match.group(0)), value
        )
    if isinstance(value, list):
        return [resolve_templates(item, values) for item in value]
    if isinstance(value, dict):
        return {key: resolve_templates(item, values) for key, item in value.items()}
    return value


def _output_text(result: dict[str, Any]) -> str:
    value = result.get("output", result.get("stdout", ""))
    if value is None:
        return ""
    return str(value).strip()


def _trace_rpcs(trace: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not trace:
        return []
    calls = trace.get("rpc", [])
    return [call for call in calls if isinstance(call, dict)] if isinstance(calls, list) else []


def _rpc_name(call: dict[str, Any]) -> str | None:
    params = call.get("params", {})
    if not isinstance(params, dict):
        return None
    return params.get("name") if call.get("method") == "skill" else (
        params.get("op") or params.get("name")
    )


def _trace_says(context: dict[str, Any]) -> list[str]:
    capture = context.get("capture") or {}
    frames = capture.get("frames", []) if isinstance(capture, dict) else []
    return [
        str(item.get("frame", {}).get("text", ""))
        for item in frames
        if isinstance(item, dict)
        and item.get("direction") == "brain_to_hands"
        and isinstance(item.get("frame"), dict)
        and item["frame"].get("t") == "say"
    ]


def _skill_matches(trace: dict[str, Any] | None, expected: dict[str, Any]) -> bool:
    expected_args = expected.get("args", {})
    for call in _trace_rpcs(trace):
        params = call.get("params", {})
        if call.get("method") != "skill" or not isinstance(params, dict):
            continue
        if params.get("name") != expected.get("name"):
            continue
        args = params.get("args", {})
        if isinstance(args, dict) and all(args.get(key) == value for key, value in expected_args.items()):
            return True
    return False


def _rpc_matches(trace: dict[str, Any] | None, expected: dict[str, Any]) -> bool:
    for call in _trace_rpcs(trace):
        if call.get("method") != expected.get("method"):
            continue
        if "name" not in expected or _rpc_name(call) == expected["name"]:
            return True
    return False


def _compare(actual: str, predicate: dict[str, Any]) -> tuple[bool, Any]:
    for operator in ("equals", "contains", "int_between", "not_contains"):
        if operator not in predicate:
            continue
        expected = predicate[operator]
        if operator == "equals":
            normalized = str(expected).strip()
            return actual == normalized, actual
        if operator == "contains":
            return str(expected) in actual, actual
        if operator == "not_contains":
            return str(expected) not in actual, actual
        try:
            number = float(actual)
            lower, upper = expected
            return float(lower) <= number <= float(upper), number
        except (TypeError, ValueError):
            return False, actual
    raise ValueError(f"predicate has no supported comparator: {predicate!r}")


async def evaluate_predicate(
    predicate: Any,
    executor: Any,
    context: dict[str, Any],
    *,
    allow_inflight: bool = False,
) -> dict[str, Any]:
    """Evaluate one declarative predicate or a grader callback."""
    if callable(predicate):
        value = predicate(executor, context)
        if inspect.isawaitable(value):
            value = await value
        if isinstance(value, dict) and "passed" in value:
            return {
                "predicate": getattr(predicate, "__name__", "callable"),
                **value,
            }
        return {"predicate": getattr(predicate, "__name__", "callable"), "passed": bool(value), "actual": value}
    if not isinstance(predicate, dict):
        return {"predicate": predicate, "passed": False, "error": "predicate must be an object"}
    if "trace_skill" in predicate:
        expected = predicate["trace_skill"]
        passed = _skill_matches(context.get("trace"), expected)
        return {"predicate": predicate, "passed": passed, "actual": context.get("trace", {}).get("rpc", [])}
    if "trace_rpc" in predicate:
        expected = predicate["trace_rpc"]
        passed = _rpc_matches(context.get("trace"), expected)
        return {"predicate": predicate, "passed": passed, "actual": context.get("trace", {}).get("rpc", [])}
    if "trace_say" in predicate:
        expected = str(predicate["trace_say"].get("contains", ""))
        says = _trace_says(context)
        passed = any(expected in text for text in says)
        return {"predicate": predicate, "passed": passed, "actual": says}
    lang = next((name for name in _SCRIPT_LANGS if name in predicate), None)
    if lang is None:
        return {"predicate": predicate, "passed": False, "error": "unknown predicate type"}
    try:
        result = await executor.run_script(
            lang, str(predicate[lang]), allow_inflight=allow_inflight
        )
        actual = _output_text(result)
        passed, observed = _compare(actual, predicate)
        return {"predicate": predicate, "passed": passed, "actual": observed, "script_result": result}
    except Exception as exc:
        return {"predicate": predicate, "passed": False, "error": str(exc)}


async def evaluate_predicates(
    predicates: list[Any],
    executor: Any,
    context: dict[str, Any],
    *,
    allow_inflight: bool = False,
) -> list[dict[str, Any]]:
    return [
        await evaluate_predicate(
            predicate, executor, context, allow_inflight=allow_inflight
        )
        for predicate in predicates
    ]


def find_trace_record(
    path: Path, utterance: str, started_wall: str | None
) -> dict[str, Any] | None:
    """Return the newest matching trace whose wall timestamp is not pre-case."""
    if not path.is_file():
        return None
    start = _wall_datetime(started_wall)
    latest = None
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("utterance") != utterance:
                continue
            if start is not None:
                timestamp = _wall_datetime(record.get("ts"))
                if timestamp is None or timestamp < start:
                    continue
            latest = record
    return latest


def _wall_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


def _decision_refused(value: Any) -> bool:
    if isinstance(value, dict):
        if str(value.get("op", "")).casefold() == "refuse":
            return True
        if str(value.get("kind", "")).casefold() == "refuse":
            return True
        route_probs = value.get("route_probs")
        if isinstance(route_probs, list) and route_probs:
            first = route_probs[0]
            if isinstance(first, (list, tuple)) and first and str(first[0]).upper() == "REFUSE":
                return True
        return any(_decision_refused(item) for item in value.values())
    if isinstance(value, list):
        return any(_decision_refused(item) for item in value)
    return False


def outcome_matches(expected: str | None, trace: dict[str, Any] | None) -> bool:
    if expected is None:
        return True
    if expected == "refused":
        return bool(trace) and _decision_refused(trace.get("decisions", []))
    return bool(trace) and trace.get("outcome") == expected


def _said_success(trace: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    if trace and trace.get("outcome") == "ok":
        return True
    capture = context.get("capture") or {}
    if isinstance(capture, dict):
        for item in capture.get("frames", []):
            frame = item.get("frame", {}) if isinstance(item, dict) else {}
            if isinstance(frame, dict) and frame.get("t") == "ui" and frame.get("mascot") == "success":
                return True
    return any(re.search(r"\b(done|success(?:ful)?)\b", text, re.IGNORECASE) for text in _trace_says(context))


async def run_case(
    case: dict[str, Any],
    runtime: Any,
    *,
    values: dict[str, str],
    trace_path: Path,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """Run one live-style task, keeping all safety and grading logic shared."""
    case = resolve_templates(case, values)
    utterance = str(case.get("utterance", case.get("text", "")))
    result: dict[str, Any] = {
        "id": case.get("id"),
        "tier": case.get("tier"),
        "category": case.get("category"),
        "kind": case.get("kind", case.get("category")),
        "utterance": utterance,
        "status": "failed",
        "strict_pass": False,
        "check_observations": [],
        "forbid_observations": [],
        "setup_observations": [],
        "teardown_observations": [],
        "restore_observations": [],
    }
    await runtime.start_scripts()
    preconditions = await evaluate_predicates(
        case.get("precondition", []), runtime, {"capture": runtime.snapshot(), "trace": None}
    )
    result["precondition_observations"] = preconditions
    if any(not item["passed"] for item in preconditions):
        result["status"] = "skipped"
        result["skip_reason"] = "precondition failed"
        await runtime.stop()
        return result

    restore_values: list[tuple[dict[str, Any], str]] = []
    setup_error = None
    for item in case.get("restore", []):
        try:
            observed = await runtime.run_script("applescript", str(item["get"]))
            value = _output_text(observed)
            restore_values.append((item, value))
            result["restore_observations"].append({"get": item["get"], "value": value})
        except Exception as exc:
            result["restore_observations"].append({"get": item.get("get"), "error": str(exc)})
            setup_error = setup_error or f"restore-get failed: {exc}"
    for step in case.get("setup", []):
        lang = next((key for key in _SCRIPT_LANGS if key in step), None)
        if lang is None:
            setup_error = setup_error or f"unsupported setup step: {step!r}"
            continue
        try:
            script_result = await runtime.run_script(lang, str(step[lang]))
            result["setup_observations"].append({"step": step, "result": script_result})
        except Exception as exc:
            result["setup_observations"].append({"step": step, "error": str(exc)})
            setup_error = setup_error or f"setup failed: {exc}"

    trace: dict[str, Any] | None = None
    check_context: dict[str, Any] = {"capture": runtime.snapshot(), "trace": None, "utterance": utterance}
    try:
        if setup_error is None:
            await runtime.start_utterance(utterance)
            capture = runtime.snapshot()
            t0 = getattr(runtime, "utterance_monotonic", None)
            started_wall = capture.get("utterance_wall")
            timeout_s = float(case.get("timeout_s", 30))
            deadline = (t0 if t0 is not None else time.monotonic()) + timeout_s
            first_action_latency = None
            verified_latency = None
            while time.monotonic() < deadline:
                capture = runtime.snapshot()
                trace = find_trace_record(trace_path, utterance, started_wall)
                if trace is not None and runtime.terminal_monotonic is None:
                    runtime.mark_utterance_finished()
                first = runtime.first_action_monotonic
                if first is not None and t0 is not None:
                    first_action_latency = max(0.0, first - t0)
                    check_context = {
                        "capture": capture, "trace": trace, "utterance": utterance,
                        "started_wall": started_wall,
                    }
                    observations = await evaluate_predicates(
                        case.get("check", []), runtime, check_context, allow_inflight=True
                    )
                    result["check_observations"].append({
                        "at_s": max(0.0, time.monotonic() - t0),
                        "phase": "poll",
                        "observations": observations,
                    })
                    checks_pass = all(item["passed"] for item in observations)
                    expected_pass = outcome_matches(case.get("expect_outcome"), trace)
                    if checks_pass and expected_pass and verified_latency is None:
                        verified_latency = max(0.0, time.monotonic() - t0)
                if runtime.terminal_monotonic is not None:
                    break
                await asyncio.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
            if runtime.terminal_monotonic is None:
                result["timed_out"] = True
                await runtime.prepare_for_cleanup()
            else:
                result["timed_out"] = False
            trace = find_trace_record(trace_path, utterance, started_wall)
            if trace is None and not result.get("timed_out", False):
                trace_deadline = time.monotonic() + 2
                while trace is None and time.monotonic() < trace_deadline:
                    await asyncio.sleep(0.1)
                    trace = find_trace_record(trace_path, utterance, started_wall)
            capture = runtime.snapshot()
            check_context = {
                "capture": capture, "trace": trace, "utterance": utterance,
                "started_wall": started_wall,
            }
            checks = await evaluate_predicates(case.get("check", []), runtime, check_context)
            result["check_observations"].append({
                "at_s": max(0.0, time.monotonic() - t0) if t0 is not None else None,
                "phase": "final",
                "observations": checks,
            })
            forbids = await evaluate_predicates(case.get("forbid", []), runtime, check_context)
            result["forbid_observations"] = forbids
            outcome_ok = outcome_matches(case.get("expect_outcome"), trace)
            if (
                verified_latency is None
                and t0 is not None
                and outcome_ok
                and all(item["passed"] for item in checks)
                and not any(item["passed"] for item in forbids)
                and not capture.get("confirm_asked_unexpectedly", False)
            ):
                verified_latency = max(0.0, time.monotonic() - t0)
            strict_pass = (
                not result.get("timed_out", False)
                and outcome_ok
                and all(item["passed"] for item in checks)
                and not any(item["passed"] for item in forbids)
                and not capture.get("confirm_asked_unexpectedly", False)
            )
            result.update({
                "status": "passed" if strict_pass else "failed",
                "strict_pass": strict_pass,
                "expect_outcome": case.get("expect_outcome"),
                "observed_outcome": trace.get("outcome") if trace else None,
                "outcome_pass": outcome_ok,
                "trace": trace,
                "frames": capture.get("frames", []),
                "first_action_latency_s": first_action_latency,
                "verified_latency_s": verified_latency,
                "confirm_count": capture.get("confirm_count", 0),
                "confirm_asked_unexpectedly": capture.get("confirm_asked_unexpectedly", False),
                "false_done": _said_success(trace, check_context) and not strict_pass,
            })
        else:
            result["setup_error"] = setup_error
            result["status"] = "failed"
            result["strict_pass"] = False
            await runtime.prepare_for_cleanup()
    except Exception as exc:
        result["error"] = str(exc)
        result["status"] = "failed"
        result["strict_pass"] = False
        await runtime.prepare_for_cleanup()
    finally:
        # The precondition passed, so cleanup is permitted even after setup or utterance failure.
        for step in case.get("teardown", []):
            if callable(step):
                try:
                    cleanup_result = step(runtime, result)
                    if inspect.isawaitable(cleanup_result):
                        cleanup_result = await cleanup_result
                    result["teardown_observations"].append({"step": "callable", "result": cleanup_result})
                    if isinstance(cleanup_result, dict) and cleanup_result.get("ok") is False:
                        result["strict_pass"] = False
                        result["status"] = "failed"
                except Exception as exc:
                    result["teardown_observations"].append({"step": "callable", "error": str(exc)})
                    result["strict_pass"] = False
                    result["status"] = "failed"
                continue
            lang = next((key for key in _SCRIPT_LANGS if key in step), None)
            if lang is None:
                result["teardown_observations"].append({"step": step, "error": "unsupported teardown step"})
                continue
            try:
                script_result = await runtime.run_script(lang, str(step[lang]))
                result["teardown_observations"].append({"step": step, "result": script_result})
            except Exception as exc:
                result["teardown_observations"].append({"step": step, "error": str(exc)})
                result["strict_pass"] = False
                result["status"] = "failed"
        for item, value in reversed(restore_values):
            script = str(item["set"]).replace("{value}", value)
            try:
                script_result = await runtime.run_script("applescript", script)
                result["restore_observations"].append({"set": script, "result": script_result})
            except Exception as exc:
                result["restore_observations"].append({"set": script, "error": str(exc)})
                result["strict_pass"] = False
                result["status"] = "failed"
        result["frames"] = runtime.snapshot().get("frames", result.get("frames", []))
        await runtime.stop()
    return result


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def report_math(records: list[dict[str, Any]], repeats: int = 1) -> dict[str, Any]:
    executed = [row for row in records if row.get("status") != "skipped"]
    passed = [row for row in executed if row.get("strict_pass", row.get("pass", False))]

    def grouped(field: str) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in records:
            key = str(row.get(field) or row.get("kind") or "unknown")
            groups.setdefault(key, []).append(row)
        return {
            key: _pass_stats(rows)
            for key, rows in sorted(groups.items())
        }

    by_id: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        by_id.setdefault(str(row.get("id", "unknown")), []).append(row)
    pass_k = [
        all(item.get("status") != "skipped" and item.get("strict_pass", item.get("pass", False))
            for item in rows)
        for rows in by_id.values()
        if len(rows) == repeats and all(item.get("status") != "skipped" for item in rows)
    ]
    first = [
        float(value) for row in executed
        if (value := row.get("first_action_latency_s")) is not None
    ]
    verified = [
        float(value) for row in executed
        if (value := row.get("verified_latency_s", row.get("completion_latency_s"))) is not None
    ]
    pending = [row for row in records if row.get("pending")]
    return {
        "cases": len(records),
        "executed": len(executed),
        "skipped": sum(row.get("status") == "skipped" for row in records),
        "strict_passes": len(passed),
        "strict_pass_rate": len(passed) / len(executed) if executed else None,
        "by_tier": grouped("tier"),
        "by_category": grouped("category"),
        "by_kind": grouped("kind"),
        "pass^k": {
            "k": repeats,
            "eligible": len(pass_k),
            "passed": sum(pass_k),
            "rate": sum(pass_k) / len(pass_k) if pass_k else None,
        },
        "false_done": sum(bool(row.get("false_done")) for row in records),
        "confirms_asked": sum(int(row.get("confirm_count", 0)) for row in records),
        "latency_s": {
            "first_action_p50": _percentile(first, 0.5),
            "first_action_p95": _percentile(first, 0.95),
            "verified_p50": _percentile(verified, 0.5),
            "verified_p95": _percentile(verified, 0.95),
        },
        "pending_cases": pending,
    }


def _pass_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row.get("status") != "skipped"]
    passes = sum(bool(row.get("strict_pass", row.get("pass", False))) for row in eligible)
    return {
        "cases": len(rows),
        "executed": len(eligible),
        "skipped": len(rows) - len(eligible),
        "passed": passes,
        "strict_pass_rate": passes / len(eligible) if eligible else None,
    }
