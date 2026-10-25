"""Shared clocks, lifecycle, predicates, templates, and reporting for benchmarks.

Setup finishes before t0. Muselet t0 is the forwarded final utterance; HobbyLM
t0 is its first model call. First action excludes observation and harness RPCs;
verified is the first shared poll whose strict final-state grade passes.
"""

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

from bench.harness.documents import (
    DOCUMENT_APPS,
    DocumentApp,
    DocumentInventoryError,
    close_created_script,
    created_items,
    document_apps_for_case,
    foreign_items,
    is_broad_close,
    is_document_close,
    quit_target,
    take_inventory,
    unclosable_items,
)


_TEMPLATE = re.compile(r"\{\{([a-z_]+)\}\}")
_SCRIPT_LANGS = ("applescript", "shell", "jxa")
HARNESS_POLL_INTERVAL_S = 0.5
FINAL_SETTLE_S = 3.0    # final checks retry this long for state the agent already caused (page loads, UI settle)
VERIFIED_LATENCY_KINDS = ("stateful", "answer", "none")


class HarnessTimeout(RuntimeError):
    def __init__(self, stage: str, slot_released: bool):
        super().__init__(f"harness timed out during {stage}")
        self.stage = stage
        self.slot_released = bool(slot_released)


def _mark_harness_timeout(result: dict[str, Any], exc: HarnessTimeout) -> bool:
    result.update({
        "status": "harness_timeout",
        "strict_pass": False,
        "harness_timeout": {
            "stage": exc.stage,
            "slot_released": exc.slot_released,
        },
    })
    return not exc.slot_released


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
    if "int_at_least_saved" in predicate:
        name, delta = predicate["int_at_least_saved"]
        saved = context.get("saved", {})
        try:
            bound = float(saved[name]) + float(delta)
        except (KeyError, TypeError, ValueError):
            return {"predicate": predicate, "passed": False, "error": f"no saved value {name!r}"}
        predicate = {
            key: value for key, value in predicate.items() if key != "int_at_least_saved"
        } | {"int_between": [bound, float("inf")]}
    if "rpc" in predicate:
        try:
            response = await executor.run_rpc(
                str(predicate["rpc"]), dict(predicate.get("params", {})),
                allow_inflight=allow_inflight,
            )
            actual = _rpc_actual(response, predicate)
            passed, observed = _compare(actual, predicate)
            return {"predicate": predicate, "passed": passed, "actual": observed, "rpc_result": response}
        except HarnessTimeout:
            raise
        except Exception as exc:
            return {"predicate": predicate, "passed": False, "error": str(exc)}
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
    except HarnessTimeout:
        raise
    except Exception as exc:
        return {"predicate": predicate, "passed": False, "error": str(exc)}


def _item_matches(item: Any, where: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    for key, expected in where.items():
        value = item.get(key)
        options = expected if isinstance(expected, list) else [expected]
        if not any(
            abs(float(value) - float(option)) <= 1.5
            if isinstance(option, (int, float)) and isinstance(value, (int, float))
            else str(value).casefold() == str(option).casefold()
            for option in options
        ):
            return False
    return True


def _rpc_actual(response: dict[str, Any], predicate: dict[str, Any]) -> str:
    """`count: {path, where}` counts matching list items; `path` alone reads a value."""
    count = predicate.get("count")
    path = count.get("path") if isinstance(count, dict) else predicate.get("path")
    value: Any = response
    for key in str(path or "").split("."):
        if key:
            value = value.get(key) if isinstance(value, dict) else None
    if isinstance(count, dict):
        items = value if isinstance(value, list) else []
        return str(sum(_item_matches(item, count.get("where", {})) for item in items))
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


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
    if isinstance(value, str):
        return bool(re.match(r"^\s*refuse(?:\s|$)", value, re.IGNORECASE))
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


def outcome_matches(
    expected: str | None,
    trace: dict[str, Any] | None,
    capture: dict[str, Any] | None = None,
) -> bool:
    if expected is None:
        return True
    if expected == "refused":
        return bool(trace) and _decision_refused(trace.get("decisions", []))
    if expected == "cancelled" and capture and capture.get("confirm_cancelled"):
        return True
    return bool(trace) and trace.get("outcome") == expected


def _agent_reported_ms(trace: dict[str, Any] | None, capture: dict[str, Any]) -> dict[str, Any]:
    reported = {}
    if trace:
        if isinstance(trace.get("stages"), dict):
            reported["brain_stages"] = trace["stages"]
        if trace.get("release_to_first_action_ms") is not None:
            reported["release_to_first_action_ms"] = trace["release_to_first_action_ms"]
    ui_values = [
        frame["frame"]["latency_ms"]
        for frame in capture.get("frames", [])
        if isinstance(frame, dict)
        and isinstance(frame.get("frame"), dict)
        and frame["frame"].get("t") == "ui"
        and isinstance(frame["frame"].get("latency_ms"), (int, float))
    ]
    if ui_values:
        reported["ui_latency_chip_ms"] = ui_values
    return reported


def _planner_actions(trace: dict[str, Any] | None) -> list[dict[str, Any]]:
    actions = []
    for decision in (trace or {}).get("decisions", []):
        if not isinstance(decision, dict):
            continue
        for line in decision.get("lines", []):
            match = re.match(r"\s*(refuse|ask|confirm)\b", str(line), re.IGNORECASE)
            if match:
                actions.append({
                    "planner_turn": decision.get("planner_turn"),
                    "action": match.group(1).casefold(),
                    "line": line,
                })
    return actions


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


def _turn_reply(frames: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """(last final mascot mood, brain reply text) from one turn's frames."""
    mood = reply = None
    for item in frames:
        frame = item.get("frame") if item.get("direction") == "brain_to_hands" else None
        if not isinstance(frame, dict):
            continue
        if frame.get("t") == "say" and frame.get("text"):
            reply = str(frame["text"])
        elif frame.get("t") == "ui" and frame.get("mascot") in ("success", "confused", "sleeping"):
            mood = str(frame["mascot"])
            if frame.get("bubble") and reply is None:
                reply = str(frame["bubble"])
    return mood, reply


async def _run_turns(
    case: dict[str, Any],
    runtime: Any,
    result: dict[str, Any],
    trace_path: Path,
    poll_interval: float,
    timeout_s: float,
) -> tuple[float | None, str | None, float | None, float | None, str]:
    """Send `case["turns"]` in order on one HandsKit client (one brain session).

    Each turn waits for its final outcome, then `wait_s`, then its own `check`s
    (a check with `save` stores its observed value for later `int_at_least_saved`).
    Returns (t0, started_wall, first_action_latency, verified_latency, utterance)
    of the last turn sent; the caller grades the case's top-level checks.
    """
    turns = case["turns"]
    texts = [str(turn["utterance"]) for turn in turns]
    saved: dict[str, Any] = result.setdefault("saved_values", {})
    records: list[dict[str, Any]] = result.setdefault("turns", [])
    total_s = sum(float(turn.get("timeout_s", timeout_s)) + float(turn.get("wait_s", 1.0)) + 15 for turn in turns)
    t0 = started_wall = first_action_latency = verified_latency = None
    utterance = texts[0]
    turns_ok = True
    for index, turn in enumerate(turns):
        utterance = texts[index]
        turn_timeout = float(turn.get("timeout_s", timeout_s))
        record: dict[str, Any] = {
            "index": index + 1,
            "utterance": utterance,
            "confirm_reply": turn.get("confirm_reply", case.get("confirm_reply")),
        }
        records.append(record)
        if index and not await runtime.wait_next_turn(turn_timeout + 15):
            record.update({"status": "not_sent", "passed": False})
            turns_ok = False
            break
        frame_start = len(runtime.snapshot().get("frames", []))
        runtime.begin_turn(record["confirm_reply"])
        if index:
            await runtime.send_next_turn()
        else:
            await runtime.start_turns(texts, timeout_s=total_s)
        capture = runtime.snapshot()
        t0 = getattr(runtime, "utterance_monotonic", None)
        started_wall = capture.get("utterance_wall")
        deadline = (t0 if t0 is not None else time.monotonic()) + turn_timeout
        first_action_latency = verified_latency = None
        last = index == len(turns) - 1
        trace = None
        while time.monotonic() < deadline:
            capture = runtime.snapshot()
            trace = find_trace_record(trace_path, utterance, started_wall)
            if trace is not None and runtime.terminal_monotonic is None:
                runtime.mark_utterance_finished()
            first = runtime.first_action_monotonic
            if first is not None and t0 is not None:
                first_action_latency = max(0.0, first - t0)
                if last:
                    context = {
                        "capture": capture, "trace": trace, "utterance": utterance,
                        "started_wall": started_wall, "saved": saved,
                    }
                    observations = await evaluate_predicates(
                        case.get("check", []), runtime, context, allow_inflight=True
                    )
                    result["check_observations"].append({
                        "at_s": max(0.0, time.monotonic() - t0),
                        "phase": "poll", "turn": index + 1, "observations": observations,
                    })
                    if (
                        verified_latency is None
                        and all(item["passed"] for item in observations)
                        and outcome_matches(case.get("expect_outcome"), trace, capture)
                    ):
                        verified_latency = max(0.0, time.monotonic() - t0)
            if runtime.terminal_monotonic is not None:
                break
            await asyncio.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
        timed_out = runtime.terminal_monotonic is None
        terminal = runtime.terminal_monotonic
        if not timed_out:
            await asyncio.sleep(float(turn.get("wait_s", 1.0)))
            trace = trace or find_trace_record(trace_path, utterance, started_wall)
        capture = runtime.snapshot()
        mood, reply = _turn_reply(capture.get("frames", [])[frame_start:])
        record.update({
            "status": "timed_out" if timed_out else "done",
            "observed_outcome": trace.get("outcome") if trace else None,
            "mood": mood,
            "reply": reply,
            "latency_s": max(0.0, terminal - t0) if terminal is not None and t0 is not None else None,
            "first_action_latency_s": first_action_latency,
            "started_wall": started_wall,
        })
        if timed_out:
            turns_ok = False
            break
        passed = True
        if "expect_outcome" in turn:
            record["outcome_pass"] = outcome_matches(turn["expect_outcome"], trace, capture)
            passed = record["outcome_pass"]
        if turn.get("check"):
            context = {
                "capture": capture, "trace": trace, "utterance": utterance,
                "started_wall": started_wall, "saved": saved,
            }
            checks = await evaluate_predicates(turn["check"], runtime, context)
            for predicate, item in zip(turn["check"], checks):
                if isinstance(predicate, dict) and predicate.get("save") and "actual" in item:
                    saved[str(predicate["save"])] = item["actual"]
            record["check_observations"] = checks
            passed = passed and all(item["passed"] for item in checks)
        record["passed"] = passed
        turns_ok = turns_ok and passed
    result["turns_ok"] = turns_ok
    result["timed_out"] = any(item.get("status") == "timed_out" for item in records)
    if result["timed_out"]:
        await runtime.prepare_for_cleanup()
    return t0, started_wall, first_action_latency, verified_latency, utterance


async def _cancel_timers(runtime: Any, step: dict[str, Any], result: dict[str, Any]) -> None:
    """Teardown `{"cancel_timers": {"where": {...}}}`: cancel each matching `timers` entry by id.

    Only safe when a precondition proved no matching timer existed before the case.
    """
    where = dict(step["cancel_timers"].get("where", {}))
    try:
        listing = await runtime.run_rpc("timers", {})
        targets = [
            item for item in listing.get("timers", []) if _item_matches(item, where)
        ]
        outcomes = []
        for item in targets:
            try:
                outcomes.append(await runtime.run_rpc("timers_cancel", {"id": item.get("id")}))
            except HarnessTimeout:
                raise
            except Exception as exc:
                outcomes.append({"ok": False, "id": item.get("id"), "error": str(exc)})
        result["teardown_observations"].append({"step": step, "targets": targets, "result": outcomes})
        if any(
            not outcome.get("ok", True) or outcome.get("unsupported") or outcome.get("failed")
            for outcome in outcomes
        ):
            result["teardown_incomplete"] = True
    except HarnessTimeout:
        raise
    except Exception as exc:
        result["teardown_observations"].append({"step": step, "error": str(exc)})
        result["teardown_incomplete"] = True


_FINDER_WINDOW_IDS = 'tell application "Finder" to get id of every Finder window'


def _running_names(listing: Any) -> set[str]:
    names: set[str] = set()
    for app in listing.get("running", []) if isinstance(listing, dict) else []:
        # bundle ids only when present: helpers such as com.apple.messages.AssistantExtension are named "Messages"
        bundle = (app.get("bundle_id") or app.get("bundleId")) if isinstance(app, dict) else None
        value = bundle or (app.get("name") if isinstance(app, dict) else app)
        if value:
            names.add(str(value).casefold())
    return names


def _is_running(app: DocumentApp, names: set[str]) -> bool:
    return any(key.casefold() in names for key in (app.name, *app.bundle_ids))


async def _launch_snapshot(runtime: Any) -> dict[str, Any] | None:
    """Running apps + Finder window ids before setup (None for runtimes without RPCs, e.g. fakes)."""
    if not hasattr(runtime, "run_rpc") or not hasattr(runtime, "run_skill"):
        return None
    try:
        listing = await runtime.run_rpc("apps", {})
        finder = await runtime.run_script("applescript", _FINDER_WINDOW_IDS)
    except HarnessTimeout:
        raise
    except Exception as exc:
        return {"error": str(exc)}
    return {"running": sorted(_running_names(listing)),
            "finder_windows": re.findall(r"\d+", str((finder or {}).get("output") or ""))}


async def _close_case_launched(runtime: Any, baseline: dict[str, Any] | None, result: dict[str, Any]) -> None:
    """Quit the document apps this case launched and close the Finder windows it opened, so later cases
    don't skip on our own leftovers. Apps running and windows open before the case are never touched."""
    if not baseline or baseline.get("error"):
        return
    after = await _launch_snapshot(runtime)
    if not after or after.get("error"):
        result["teardown_observations"].append(
            {"step": "close_case_launched", "error": (after or {}).get("error", "no snapshot")})
        return
    before, now = set(baseline["running"]), set(after["running"])
    for app in DOCUMENT_APPS:
        if not _is_running(app, now) or _is_running(app, before):
            continue
        try:
            outcome = await runtime.run_skill("quit_app", {"app": app.name})
        except HarnessTimeout:
            raise
        except Exception as exc:
            outcome = {"ok": False, "error": str(exc)}
        result["teardown_observations"].append({"step": "quit_case_launched_app", "app": app.name, "result": outcome})
        if isinstance(outcome, dict) and outcome.get("ok") is False:
            result["teardown_incomplete"] = True
    old_ids = set(baseline["finder_windows"])
    new_ids = [i for i in after["finder_windows"] if i not in old_ids]
    if new_ids:
        script = ('tell application "Finder"\nrepeat with i in {' + ", ".join(new_ids) + "}\n"
                  "close (every Finder window whose id is i)\nend repeat\nend tell")
        try:
            outcome = await runtime.run_script("applescript", script)
        except HarnessTimeout:
            raise
        except Exception as exc:
            outcome = {"ok": False, "error": str(exc)}
            result["teardown_incomplete"] = True
        result["teardown_observations"].append({"step": "close_case_finder_windows", "ids": new_ids, "result": outcome})


def _precondition_steps(case: dict[str, Any]) -> list[Any]:
    predicates = case.get("precondition", [])
    if predicates is None:
        return []
    return predicates if isinstance(predicates, list) else [predicates]


def _has_nonmechanical_precondition(predicates: list[Any]) -> bool:
    return any(
        callable(predicate)
        or (
            isinstance(predicate, dict)
            and any(str(key).startswith("trace_") for key in predicate)
        )
        for predicate in predicates
    )


def _app_running_in_baseline(app: DocumentApp, baseline: dict) -> bool:
    return any(
        bool(baseline.get(bundle_id, {}).get("running"))
        for bundle_id in app.bundle_ids
        if isinstance(baseline.get(bundle_id), dict)
    )


async def run_case(
    case: dict[str, Any],
    runtime: Any,
    *,
    values: dict[str, str],
    trace_path: Path,
    poll_interval: float = HARNESS_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Run one live-style task, keeping all safety and grading logic shared."""
    case = resolve_templates(case, values)
    utterance = str(case.get("utterance", case.get("text", "")))
    if case.get("turns"):
        utterance = " → ".join(str(turn.get("utterance", "")) for turn in case["turns"])
    precondition_steps = _precondition_steps(case)
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
    timeout_slot_held = False
    if _has_nonmechanical_precondition(precondition_steps):
        result["status"] = "skipped"
        result["skip_reason"] = "precondition not mechanical"
        result["precondition_observations"] = [
            {"predicate": predicate, "passed": False, "error": "precondition not mechanical"}
            for predicate in precondition_steps
            if callable(predicate)
            or (
                isinstance(predicate, dict)
                and any(str(key).startswith("trace_") for key in predicate)
            )
        ]
        await runtime.stop()
        return result
    try:
        await runtime.start_scripts()
        preconditions = await evaluate_predicates(
            precondition_steps,
            runtime,
            {"capture": runtime.snapshot(), "trace": None},
        )
    except HarnessTimeout as exc:
        timeout_slot_held = _mark_harness_timeout(result, exc)
        if timeout_slot_held:
            result["teardown_incomplete"] = True
            result["teardown_observations"].extend(
                {"step": step, "skipped": "harness_timeout_slot_held"}
                for step in case.get("teardown", [])
            )
        await runtime.stop()
        return result
    except Exception as exc:
        result["status"] = "skipped"
        result["skip_reason"] = "precondition error"
        result["precondition_error"] = str(exc)
        result["precondition_observations"] = []
        await runtime.stop()
        return result
    result["precondition_observations"] = preconditions
    evaluation_errors = [item["error"] for item in preconditions if item.get("error")]
    if evaluation_errors:
        result["status"] = "skipped"
        result["skip_reason"] = "precondition error"
        result["precondition_error"] = "; ".join(str(error) for error in evaluation_errors)
        await runtime.stop()
        return result
    if any(not item["passed"] for item in preconditions):
        result["status"] = "skipped"
        result["skip_reason"] = "precondition failed"
        await runtime.stop()
        return result

    document_apps = document_apps_for_case(case)
    document_baseline: dict[str, dict] = {}
    document_after_setup: dict[str, dict] | None = None
    result["document_apps"] = [app.name for app in document_apps]
    result["document_baseline"] = document_baseline
    if document_apps:
        try:
            document_baseline = await take_inventory(runtime.run_script, document_apps)
        except DocumentInventoryError as exc:
            result["status"] = "skipped"
            result["skip_reason"] = "user_documents_unverifiable"
            result["document_inventory_error"] = str(exc)
            await runtime.stop()
            return result
        except HarnessTimeout as exc:
            timeout_slot_held = _mark_harness_timeout(result, exc)
            if not exc.slot_released:
                result["teardown_incomplete"] = True
                result["teardown_observations"].extend(
                    {"step": step, "skipped": "harness_timeout_slot_held"}
                    for step in case.get("teardown", [])
                )
            await runtime.stop()
            return result
        result["document_baseline"] = document_baseline
        user_documents = foreign_items(document_baseline)
        if user_documents:
            result["status"] = "skipped"
            result["skip_reason"] = "user_documents_open"
            result["user_documents"] = user_documents
            await runtime.stop()
            return result

    launch_baseline = await _launch_snapshot(runtime)
    result["launch_baseline"] = launch_baseline

    guard = case.get("pre_setup_guard")
    if callable(guard):
        try:
            guard_result = guard(runtime, result)
            if inspect.isawaitable(guard_result):
                guard_result = await guard_result
        except HarnessTimeout as exc:
            timeout_slot_held = _mark_harness_timeout(result, exc)
            if not exc.slot_released:
                result["teardown_incomplete"] = True
                result["teardown_observations"].extend(
                    {"step": step, "skipped": "harness_timeout_slot_held"}
                    for step in case.get("teardown", [])
                )
            await runtime.stop()
            return result
        except Exception as exc:
            guard_result = {
                "status": "skipped",
                "skip_reason": "fixture_plan_unverifiable",
                "fixture_plan_error": str(exc),
            }
        if isinstance(guard_result, dict):
            result.update(guard_result)
            if guard_result.get("status") == "skipped":
                await runtime.stop()
                return result

    restore_values: list[tuple[dict[str, Any], str]] = []

    async def abort_held_slot(
        *,
        teardown_steps: list[Any] | None = None,
        restore_items: list[tuple[dict[str, Any], str]] | None = None,
    ) -> dict[str, Any]:
        teardown_steps = (
            case.get("teardown", []) if teardown_steps is None else teardown_steps
        )
        restore_items = restore_values if restore_items is None else restore_items
        result["teardown_incomplete"] = True
        result["teardown_observations"].extend(
            {"step": step, "skipped": "harness_timeout_slot_held"}
            for step in teardown_steps
        )
        result["restore_observations"].extend(
            {"set": item.get("set"), "skipped": "harness_timeout_slot_held"}
            for item, _value in restore_items
        )
        try:
            result["frames"] = runtime.snapshot().get(
                "frames", result.get("frames", [])
            )
        finally:
            await runtime.stop()
        if hasattr(runtime, "hands_serve_summary"):
            result["hands_serve_summary"] = runtime.hands_serve_summary
        return result

    setup_error = None
    setup_timeout: HarnessTimeout | None = None
    for item in case.get("restore", []):
        try:
            observed = await runtime.run_script("applescript", str(item["get"]))
            value = _output_text(observed)
            restore_values.append((item, value))
            result["restore_observations"].append({"get": item["get"], "value": value})
        except HarnessTimeout as exc:
            setup_timeout = exc
            break
        except Exception as exc:
            result["restore_observations"].append({"get": item.get("get"), "error": str(exc)})
            setup_error = setup_error or f"restore-get failed: {exc}"
    for step in case.get("setup", []):
        if setup_timeout:
            break
        lang = next((key for key in _SCRIPT_LANGS if key in step), None)
        if lang is None:
            setup_error = setup_error or f"unsupported setup step: {step!r}"
            continue
        try:
            script_result = await runtime.run_script(lang, str(step[lang]))
            result["setup_observations"].append({"step": step, "result": script_result})
        except HarnessTimeout as exc:
            setup_timeout = exc
            break
        except Exception as exc:
            result["setup_observations"].append({"step": step, "error": str(exc)})
            setup_error = setup_error or f"setup failed: {exc}"

    if document_apps:
        try:
            document_after_setup = await take_inventory(runtime.run_script, document_apps)
            result["document_after_setup"] = document_after_setup
        except HarnessTimeout as exc:
            setup_timeout = exc
        except Exception as exc:
            result["document_after_setup_error"] = str(exc)

    before_utterance = case.get("before_utterance")
    if callable(before_utterance) and setup_error is None and setup_timeout is None:
        try:
            hook_result = before_utterance(runtime, result)
            if inspect.isawaitable(hook_result):
                hook_result = await hook_result
            result["before_utterance_observation"] = hook_result
        except Exception as exc:
            if isinstance(exc, HarnessTimeout):
                setup_timeout = exc
            else:
                setup_error = f"before-utterance setup failed: {exc}"

    trace: dict[str, Any] | None = None
    try:
        if setup_timeout is not None:
            raise setup_timeout
        check_context: dict[str, Any] = {
            "capture": runtime.snapshot(), "trace": None, "utterance": utterance
        }
        if setup_error is None:
            timeout_s = float(case.get("timeout_s", 30))
            if case.get("turns"):
                (
                    t0, started_wall, first_action_latency, verified_latency, utterance,
                ) = await _run_turns(case, runtime, result, trace_path, poll_interval, timeout_s)
            else:
                if "timeout_s" in inspect.signature(runtime.start_utterance).parameters:
                    await runtime.start_utterance(utterance, timeout_s=timeout_s)
                else:
                    await runtime.start_utterance(utterance)
                capture = runtime.snapshot()
                t0 = getattr(runtime, "utterance_monotonic", None)
                started_wall = capture.get("utterance_wall")
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
                        expected_pass = outcome_matches(case.get("expect_outcome"), trace, capture)
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
            after_utterance = case.get("after_utterance")
            if callable(after_utterance):
                try:
                    hook_result = after_utterance(runtime, result)
                    if inspect.isawaitable(hook_result):
                        hook_result = await hook_result
                    result["after_utterance_observation"] = hook_result
                except Exception as exc:
                    if isinstance(exc, HarnessTimeout):
                        raise
                    result["after_utterance_error"] = str(exc)
                    result["status"] = "failed"
                    result["strict_pass"] = False
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
            if "saved_values" in result:
                check_context["saved"] = result["saved_values"]
            checks = await evaluate_predicates(case.get("check", []), runtime, check_context)
            settle_deadline = time.monotonic() + float(case.get("settle_s", FINAL_SETTLE_S))
            while not all(item["passed"] for item in checks) and time.monotonic() < settle_deadline:
                result["check_observations"].append({
                    "at_s": max(0.0, time.monotonic() - t0) if t0 is not None else None,
                    "phase": "settle",
                    "observations": checks,
                })
                await asyncio.sleep(poll_interval)
                checks = await evaluate_predicates(case.get("check", []), runtime, check_context)
            result["check_observations"].append({
                "at_s": max(0.0, time.monotonic() - t0) if t0 is not None else None,
                "phase": "final",
                "observations": checks,
            })
            forbids = await evaluate_predicates(case.get("forbid", []), runtime, check_context)
            result["forbid_observations"] = forbids
            outcome_ok = outcome_matches(case.get("expect_outcome"), trace, capture)
            if (
                verified_latency is None
                and t0 is not None
                and case.get("kind") != "none"
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
                and not capture.get("safety_blocked", False)
                and result.get("turns_ok", True)
            )
            result.update({
                "status": "passed" if strict_pass else "failed",
                "strict_pass": strict_pass,
                "expect_outcome": case.get("expect_outcome"),
                "observed_outcome": trace.get("outcome") if trace else None,
                "outcome_pass": outcome_ok,
                "trace": trace,
                "planner_actions": _planner_actions(trace),
                "agent_reported_ms": _agent_reported_ms(trace, capture),
                "frames": capture.get("frames", []),
                "utterance_latency_s": (
                    max(0.0, runtime.terminal_monotonic - t0)
                    if runtime.terminal_monotonic is not None and t0 is not None
                    else None
                ),
                "first_action_latency_s": first_action_latency,
                "verified_latency_s": verified_latency,
                "confirm_count": capture.get("confirm_count", 0),
                "confirm_cancelled": capture.get("confirm_cancelled", False),
                "confirm_asked_unexpectedly": capture.get("confirm_asked_unexpectedly", False),
                "safety_blocked": capture.get("safety_blocked", False),
                "safety_blocks": capture.get("safety_blocks", []),
                "false_done": _said_success(trace, check_context) and not strict_pass,
            })
        else:
            result["setup_error"] = setup_error
            result["status"] = "failed"
            result["strict_pass"] = False
            await runtime.prepare_for_cleanup()
    except HarnessTimeout as exc:
        timeout_slot_held = _mark_harness_timeout(result, exc)
        if exc.slot_released:
            try:
                await runtime.prepare_for_cleanup()
            except HarnessTimeout as cleanup_exc:
                timeout_slot_held = _mark_harness_timeout(result, cleanup_exc)
    except Exception as exc:
        result["error"] = str(exc)
        result["status"] = "failed"
        result["strict_pass"] = False
        await runtime.prepare_for_cleanup()
    finally:
        if timeout_slot_held:
            return await abort_held_slot()

        def note_timeout(exc: HarnessTimeout) -> None:
            nonlocal timeout_slot_held
            timeout_slot_held = _mark_harness_timeout(result, exc)

        document_pre_teardown: dict[str, dict] | None = None
        if document_apps:
            try:
                document_pre_teardown = await take_inventory(runtime.run_script, document_apps)
                result["document_pre_teardown"] = document_pre_teardown
            except HarnessTimeout as exc:
                note_timeout(exc)
                if timeout_slot_held:
                    return await abort_held_slot()
            except Exception as exc:
                result["document_pre_teardown_error"] = str(exc)
            created = created_items(
                document_baseline,
                *(
                    snapshot
                    for snapshot in (document_after_setup, document_pre_teardown)
                    if snapshot is not None
                ),
            )
            result["document_created"] = created
            incomplete = unclosable_items(created)
            if incomplete:
                result["teardown_incomplete"] = True
                result["teardown_incomplete_items"] = incomplete
            cleanup_script = close_created_script(created)
            if cleanup_script is not None and not timeout_slot_held:
                try:
                    cleanup_result = await runtime.run_script("jxa", cleanup_script)
                    result["teardown_observations"].append({
                        "step": "close_created_documents",
                        "result": cleanup_result,
                    })
                except HarnessTimeout as exc:
                    note_timeout(exc)
                    if timeout_slot_held:
                        return await abort_held_slot()
                except Exception as exc:
                    result["teardown_observations"].append({
                        "step": "close_created_documents",
                        "error": str(exc),
                    })
                    result["strict_pass"] = False
                    result["status"] = "failed"

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
                    if isinstance(exc, HarnessTimeout):
                        note_timeout(exc)
                        if timeout_slot_held:
                            remaining_teardown = [
                                pending for pending in case.get("teardown", [])
                                if pending is not step
                            ]
                            return await abort_held_slot(
                                teardown_steps=remaining_teardown,
                            )
                        result["teardown_observations"].append({
                            "step": "callable", "error": str(exc),
                        })
                        continue
                    result["teardown_observations"].append({"step": "callable", "error": str(exc)})
                    result["strict_pass"] = False
                    result["status"] = "failed"
                continue
            if isinstance(step, dict) and "cancel_timers" in step:
                try:
                    await _cancel_timers(runtime, step, result)
                except HarnessTimeout as exc:
                    note_timeout(exc)
                    if timeout_slot_held:
                        return await abort_held_slot(teardown_steps=[
                            pending for pending in case.get("teardown", []) if pending is not step
                        ])
                continue
            lang = next((key for key in _SCRIPT_LANGS if key in step), None)
            if lang is None:
                result["teardown_observations"].append({"step": step, "error": "unsupported teardown step"})
                continue
            script = str(step[lang])
            if is_broad_close(script):
                result["teardown_observations"].append({
                    "step": step,
                    "skipped": "broad close forbidden",
                })
                continue
            if is_document_close(script):
                result["teardown_observations"].append({
                    "step": step,
                    "skipped": "case close delegated to tracked cleanup",
                })
                continue
            target = quit_target(script)
            if target is not None:
                if re.search(r"\bsaving\s+no\b", script, re.IGNORECASE):
                    result["teardown_observations"].append({
                        "step": step,
                        "skipped": "quit with saving no forbidden",
                    })
                    continue
                if _app_running_in_baseline(target, document_baseline):
                    result["teardown_observations"].append({
                        "step": step,
                        "skipped": "document app was running at baseline",
                    })
                    continue
            try:
                script_result = await runtime.run_script(lang, script)
                result["teardown_observations"].append({"step": step, "result": script_result})
            except Exception as exc:
                if isinstance(exc, HarnessTimeout):
                    note_timeout(exc)
                    if timeout_slot_held:
                        remaining_teardown = [
                            pending for pending in case.get("teardown", [])
                            if pending is not step
                        ]
                        return await abort_held_slot(
                            teardown_steps=remaining_teardown,
                        )
                    result["teardown_observations"].append({
                        "step": step, "error": str(exc),
                    })
                    continue
                result["teardown_observations"].append({"step": step, "error": str(exc)})
                result["strict_pass"] = False
                result["status"] = "failed"
        if not timeout_slot_held:
            try:
                await _close_case_launched(runtime, launch_baseline, result)
            except HarnessTimeout as exc:
                note_timeout(exc)
                if timeout_slot_held:
                    return await abort_held_slot(teardown_steps=[])
        for item, value in reversed(restore_values):
            script = str(item["set"]).replace("{value}", value)
            try:
                script_result = await runtime.run_script("applescript", script)
                result["restore_observations"].append({"set": script, "result": script_result})
            except Exception as exc:
                if isinstance(exc, HarnessTimeout):
                    note_timeout(exc)
                    if timeout_slot_held:
                        remaining_restores = [
                            pair for pair in restore_values
                            if pair[0] is not step
                        ]
                        return await abort_held_slot(
                            teardown_steps=[],
                            restore_items=remaining_restores,
                        )
                    result["restore_observations"].append({
                        "set": script, "error": str(exc),
                    })
                    continue
                result["restore_observations"].append({"set": script, "error": str(exc)})
                result["strict_pass"] = False
                result["status"] = "failed"
        try:
            result["frames"] = runtime.snapshot().get("frames", result.get("frames", []))
        finally:
            await runtime.stop()
    if hasattr(runtime, "hands_serve_summary"):
        result["hands_serve_summary"] = runtime.hands_serve_summary
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


def _report_math_section(records: list[dict[str, Any]], repeats: int = 1) -> dict[str, Any]:
    executed = [
        row for row in records
        if row.get("status") not in ("skipped", "harness_timeout")
        and not row.get("ungradable")
    ]
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
        all(item.get("status") not in ("skipped", "harness_timeout")
            and not item.get("ungradable")
            and item.get("strict_pass", item.get("pass", False))
            for item in rows)
        for rows in by_id.values()
        if len(rows) == repeats and all(
            item.get("status") not in ("skipped", "harness_timeout")
            and not item.get("ungradable")
            for item in rows
        )
    ]
    first = [
        float(value) for row in executed
        if (value := row.get("first_action_latency_s")) is not None
    ]
    verified = [
        float(value) for row in executed
        if row.get("kind") != "none"
        if (value := row.get("verified_latency_s", row.get("completion_latency_s"))) is not None
    ]
    latency_by_kind = {}
    for kind in sorted({
        str(row.get("kind") or "unknown")
        for row in executed
    }):
        group = [row for row in executed if str(row.get("kind") or "unknown") == kind]
        first_values = [
            float(row["first_action_latency_s"]) for row in group
            if row.get("first_action_latency_s") is not None
        ]
        verified_values = [
            float(row.get("verified_latency_s", row.get("completion_latency_s")))
            for row in group
            if kind != "none"
            and row.get("verified_latency_s", row.get("completion_latency_s")) is not None
        ]
        latency_by_kind[kind] = {
            "first_action_p50": _percentile(first_values, 0.5),
            "first_action_p95": _percentile(first_values, 0.95),
            "verified_p50": _percentile(verified_values, 0.5),
            "verified_p95": _percentile(verified_values, 0.95),
            "first_action_n": len(first_values),
            "verified_n": len(verified_values),
        }
    return {
        "cases": len(records),
        "executed": len(executed),
        "skipped": sum(row.get("status") == "skipped" for row in records),
        "ungradable": sum(bool(row.get("ungradable")) for row in records),
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
        "latency_kinds": {
            "first_action": sorted({
                str(row.get("kind") or "unknown") for row in executed
                if row.get("first_action_latency_s") is not None
            }),
            "verified": sorted({
                str(row.get("kind") or "unknown") for row in executed
                if row.get("kind") != "none"
                and row.get("verified_latency_s", row.get("completion_latency_s")) is not None
            }),
        },
        "latency_by_kind": latency_by_kind,
    }


def report_math(records: list[dict[str, Any]], repeats: int = 1) -> dict[str, Any]:
    pending = [row for row in records if row.get("pending")]
    main = [row for row in records if not row.get("pending")]
    summary = _report_math_section(main, repeats)
    summary["pending_cases"] = pending
    pending_summary = _report_math_section(pending, repeats)
    pending_by_tier = {}
    for tier in sorted({str(row.get("tier") or "unknown") for row in pending}):
        group = [row for row in pending if str(row.get("tier") or "unknown") == tier]
        tier_summary = _report_math_section(group, repeats)
        pending_by_tier[tier] = {
            **tier_summary["by_tier"].get(tier, _pass_stats(group)),
            "pass^k": tier_summary["pass^k"],
            "latency_s": tier_summary["latency_s"],
        }
    pending_summary["by_tier"] = pending_by_tier
    summary["pending"] = pending_summary
    timeouts = [row for row in records if row.get("status") == "harness_timeout"]
    summary["harness_timeouts"] = {
        "count": len(timeouts),
        "ids": [row.get("id") for row in timeouts],
    }
    return summary


def _pass_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        row for row in rows
        if row.get("status") not in ("skipped", "harness_timeout")
        and not row.get("ungradable")
    ]
    passes = sum(bool(row.get("strict_pass", row.get("pass", False))) for row in eligible)
    return {
        "cases": len(rows),
        "executed": len(eligible),
        "skipped": sum(row.get("status") == "skipped" for row in rows),
        "ungradable": sum(bool(row.get("ungradable")) for row in rows),
        "passed": passes,
        "strict_pass_rate": passes / len(eligible) if eligible else None,
    }
