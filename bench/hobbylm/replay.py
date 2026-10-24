#!/usr/bin/env python3
"""Plan and report comparable HobbyLM/Muselet live replays."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import shlex
import socket
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.harness.core import report_math as shared_report_math, run_case
from bench.harness.runtime import HandsRuntime

DEFAULT_HOME = Path("/home/ubuntu/ext/hobbylm")


def load_tasks(home: Path, round_name: str):
    filename = "hobbymac-sealed-test.tsv" if round_name == "r1" else f"hobbymac-sealed-test-{round_name}.tsv"
    rows = []
    for line in (home / "data/frozen" / filename).read_text().splitlines():
        if line.strip():
            ident, kind, text, expected = line.split("\t", 3)
            rows.append({"id": ident, "kind": kind, "text": text, "expected": expected.strip()})
    return rows


def plan(system: str, round_name: str, tasks: list[dict], repeats: int, port: int):
    return [
        {"system": system, "round": round_name, "repeat": repeat, **task, "port": port}
        for repeat in range(1, repeats + 1)
        for task in tasks
    ]


def report_math(records: list[dict], repeats: int) -> dict:
    by_kind = defaultdict(list)
    for record in records:
        by_kind[record["kind"]].append(record)
    def pct(values, q):
        if not values:
            return None
        ordered = sorted(values)
        index = (len(ordered) - 1) * q
        lower, upper = int(index), int(index + 0.999999999)
        return ordered[lower] if lower == upper else ordered[lower] * (upper - index) + ordered[upper] * (index - lower)
    def final_pass(row):
        return bool(row.get("pass_final_state", row.get("final_state_only", row.get("pass"))))

    def completed(row):
        return bool(row.get("completed", row.get("pass")))

    def pass_k(rows, field):
        per_id = defaultdict(list)
        for row in rows:
            per_id[row["id"]].append(field(row))
        return sum(len(values) == repeats and all(values) for values in per_id.values()) / max(1, len(per_id))

    by_kind_metrics = {}
    for kind, rows in sorted(by_kind.items()):
        by_kind_metrics[kind] = {
            "n": len(rows),
            "pass_final_state_rate": sum(final_pass(row) for row in rows) / max(1, len(rows)),
            "completed_rate": sum(completed(row) for row in rows) / max(1, len(rows)),
            "pass_final_state_k": pass_k(rows, final_pass),
            "completed_k": pass_k(rows, completed),
            "false_done": sum(bool(row.get("false_done")) for row in rows),
        }
    pass_final_state_k = pass_k(records, final_pass)
    completed_k = pass_k(records, completed)
    completed_rate = sum(completed(row) for row in records) / max(1, len(records))
    final_state_rate = sum(final_pass(row) for row in records) / max(1, len(records))
    return {
        "n": len(records),
        "pass_final_state_rate": final_state_rate,
        "completed_rate": completed_rate,
        "pass_final_state_by_kind": {kind: values["pass_final_state_rate"] for kind, values in by_kind_metrics.items()},
        "completed_by_kind": {kind: values["completed_rate"] for kind, values in by_kind_metrics.items()},
        "pass_final_state_k_by_kind": {kind: values["pass_final_state_k"] for kind, values in by_kind_metrics.items()},
        "completed_k_by_kind": {kind: values["completed_k"] for kind, values in by_kind_metrics.items()},
        "by_kind": by_kind_metrics,
        "pass_final_state_k": pass_final_state_k,
        "completed_k": completed_k,
        "false_done": sum(bool(row.get("false_done")) for row in records),
        "pass_rate": completed_rate,
        "final_state_only_rate": final_state_rate,
        "pass_k_by_kind": {kind: values["completed_k"] for kind, values in by_kind_metrics.items()},
        "utterance_latency_s": {"p50": pct([r["utterance_latency_s"] for r in records if r.get("utterance_latency_s") is not None], .5),
                                "p95": pct([r["utterance_latency_s"] for r in records if r.get("utterance_latency_s") is not None], .95)},
        "first_action_latency_s": {"p50": pct([r["first_action_latency_s"] for r in records if r.get("first_action_latency_s") is not None], .5),
                                   "p95": pct([r["first_action_latency_s"] for r in records if r.get("first_action_latency_s") is not None], .95)},
        "completion_latency_s": {"p50": pct([r["completion_latency_s"] for r in records if r.get("completion_latency_s") is not None], .5),
                                 "p95": pct([r["completion_latency_s"] for r in records if r.get("completion_latency_s") is not None], .95)},
    }


_IMAGE_SUFFIXES = {".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
_TITLE_STOPWORDS = {"with", "and", "the", "a"}


def _screenshot_location() -> Path:
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.screencapture", "location"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    location = result.stdout.strip() if result and result.returncode == 0 else ""
    return Path(location).expanduser() if location else Path.home() / "Desktop"


def _image_files(location: Path) -> list[str]:
    if not location.is_dir():
        return []
    return sorted(
        str(path.resolve())
        for path in location.iterdir()
        if path.is_file() and path.suffix.casefold() in _IMAGE_SUFFIXES
    )


def _calendar_window(helper):
    now = datetime.now(ZoneInfo(getattr(helper, "LOCAL_TZ", "UTC")))
    return now, now - timedelta(days=1), now + timedelta(days=400)


def _read_calendar_events(calendar: str, start: datetime, end: datetime) -> list[dict]:
    script = r'''
import EventKit
import Darwin
import Foundation
let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
final class AccessState: @unchecked Sendable {
    private let lock = NSLock()
    private var result = false
    func set(_ value: Bool) { lock.lock(); result = value; lock.unlock() }
    func get() -> Bool { lock.lock(); defer { lock.unlock() }; return result }
}
let access = AccessState()
store.requestFullAccessToEvents { ok, _ in access.set(ok); semaphore.signal() }
if semaphore.wait(timeout: .now() + 30) == .timedOut || !access.get() { exit(2) }
let env = ProcessInfo.processInfo.environment
let parser = ISO8601DateFormatter()
guard let start = parser.date(from: env["MUSELET_EVENT_START"] ?? ""),
      let end = parser.date(from: env["MUSELET_EVENT_END"] ?? "") else { exit(3) }
let title = env["MUSELET_EVENT_CALENDAR"] ?? ""
let calendars = store.calendars(for: .event).filter { $0.title == title }
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: calendars)
let events = store.events(matching: predicate).map { event -> [String: Any] in
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    formatter.timeZone = event.timeZone ?? TimeZone.current
    return [
        "identifier": event.eventIdentifier ?? "",
        "calendar": event.calendar?.title ?? "",
        "title": event.title ?? "",
        "notes": event.notes ?? "",
        "start": formatter.string(from: event.startDate),
        "timeZone": event.timeZone?.identifier ?? "",
        "attendees": event.attendees?.map { $0.name ?? $0.url.absoluteString } ?? []
    ]
}
let data = try JSONSerialization.data(withJSONObject: events)
print(String(data: data, encoding: .utf8)!)
'''
    result = subprocess.run(
        ["swift", "-e", script],
        env={
            **os.environ,
            "MUSELET_EVENT_CALENDAR": calendar,
            "MUSELET_EVENT_START": start.isoformat(),
            "MUSELET_EVENT_END": end.isoformat(),
        },
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"EventKit calendar snapshot failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _calendar_events(helper, start: datetime, end: datetime) -> list[dict]:
    reader = getattr(helper, "calendar_events", None)
    if callable(reader):
        return reader("Hobby Test", start, end)
    return _read_calendar_events("Hobby Test", start, end)


def _event_key(event: dict) -> tuple:
    identifier = event.get("identifier") or event.get("eventIdentifier")
    return ("id", identifier) if identifier else (
        "event", event.get("title", ""), event.get("start", "")
    )


def _new_events(before: list[dict], after: list[dict]) -> list[dict]:
    existing = {_event_key(event) for event in before}
    return [event for event in after if _event_key(event) not in existing]


def _eventkit_delete_events(identifiers: list[str]) -> None:
    if not identifiers:
        return
    script = r'''
import EventKit
import Darwin
import Foundation
let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
final class AccessState: @unchecked Sendable {
    private let lock = NSLock()
    private var result = false
    func set(_ value: Bool) { lock.lock(); result = value; lock.unlock() }
    func get() -> Bool { lock.lock(); defer { lock.unlock() }; return result }
}
let access = AccessState()
store.requestFullAccessToEvents { ok, _ in access.set(ok); semaphore.signal() }
if semaphore.wait(timeout: .now() + 30) == .timedOut || !access.get() { exit(2) }
let data = Data((ProcessInfo.processInfo.environment["MUSELET_EVENT_IDS"] ?? "[]").utf8)
let identifiers = (try JSONSerialization.jsonObject(with: data)) as? [String] ?? []
for identifier in identifiers {
    if let event = store.event(withIdentifier: identifier) {
        try? store.remove(event, span: .thisEvent, commit: false)
    }
}
try store.commit()
'''
    result = subprocess.run(
        ["swift", "-e", script],
        env={**os.environ, "MUSELET_EVENT_IDS": json.dumps(identifiers)},
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"EventKit event cleanup failed: {result.stderr.strip()}")


def _start_state(helper, record):
    start = helper.snapshot()
    if record["kind"] in ("screenshot", "none"):
        location = _screenshot_location()
        start["screenshot_location"] = str(location)
        start["screenshot_files"] = _image_files(location)
    if record["kind"] in ("event", "none"):
        now, window_start, window_end = _calendar_window(helper)
        start["calendar_now"] = now.isoformat()
        start["calendar_window"] = [window_start.isoformat(), window_end.isoformat()]
        start["calendar_events"] = _calendar_events(helper, window_start, window_end)
    return start


def _capture_final_state(helper, record, start):
    current = helper.snapshot()
    if record["kind"] == "calc":
        current["display"] = helper.display() if helper.running("Calculator") else None
    if record["kind"] in ("screenshot", "none"):
        current["screenshot_files"] = _image_files(Path(start["screenshot_location"]))
    if record["kind"] in ("event", "none"):
        window_start, window_end = (datetime.fromisoformat(value) for value in start["calendar_window"])
        current["calendar_events"] = _calendar_events(helper, window_start, window_end)
    return current


def _action_dispatched(trace: dict, first_action=None) -> bool:
    for rpc in trace.get("rpc", []):
        method = rpc.get("method") or rpc.get("params", {}).get("method")
        if method in ("act", "skill"):
            return True
    if isinstance(first_action, str):
        return first_action in ("act", "skill")
    if isinstance(first_action, dict):
        return first_action.get("method") in ("act", "skill") or bool(first_action.get("executed"))
    return False


def _event_matches_snapshot(helper, record, start, event) -> bool:
    expected = record["expected"].removeprefix("EVENT ").strip()
    parts = helper.CAL.parse_event(expected)
    if not parts:
        return False
    now = datetime.fromisoformat(start["calendar_now"])
    plan = helper.CAL.plan_event(
        expected, now, helper.LOCAL_TZ, lookup=lambda _name: []
    )
    if not plan or str(plan.problem or "").startswith("could not"):
        return False
    expected_words = {
        word for word in re.findall(r"[a-z0-9]+", plan.title.casefold())
        if word not in _TITLE_STOPWORDS
    }
    actual_words = {
        word for word in re.findall(r"[a-z0-9]+", str(event.get("title", "")).casefold())
        if word not in _TITLE_STOPWORDS
    }
    if not expected_words or len(expected_words & actual_words) / len(expected_words) < 0.5:
        return False
    try:
        actual_start = datetime.fromisoformat(event["start"])
    except (KeyError, TypeError, ValueError):
        return False
    if actual_start.tzinfo is None or plan.start.tzinfo is None or actual_start != plan.start:
        return False
    person = parts[3].strip()
    if person.casefold() not in ("none", ""):
        fields = [event.get("title", ""), event.get("notes", "")]
        attendees = event.get("attendees", [])
        fields.extend(attendees if isinstance(attendees, list) else [attendees])
        if not any(person.casefold() in str(value).casefold() for value in fields):
            return False
    return True


def _grade_final_state(helper, record, start, current, trace=None, first_action=None) -> tuple[bool, dict]:
    kind, expected = record["kind"], record["expected"].strip()
    if kind == "calc":
        display = current.get("display")
        value = helper.as_num(display) if display is not None else None
        return value is not None and abs(value - float(expected)) < 0.006, current
    if kind == "device":
        expected = expected.removeprefix("KEY ").strip()
        if expected == "BRIGHTNESS_DOWN":
            ok = current["bright"] < start["bright"]
        elif expected == "BRIGHTNESS_UP":
            ok = current["bright"] > start["bright"] or start["bright"] >= 1
        elif expected == "VOLUME_DOWN":
            ok = current["vol"][0] < start["vol"][0]
        elif expected == "VOLUME_UP":
            ok = current["vol"][0] > start["vol"][0] or start["vol"][0] == 100
        else:
            ok = expected == "MUTE" and current["vol"][1]
        return ok, current
    if kind == "dark":
        return current["dark"] == expected.upper().endswith("ON"), current
    if kind == "app":
        app = expected.removeprefix("OPEN ").strip()
        return current["front"].casefold() == app.casefold(), current
    if kind == "folder":
        folder = expected.removeprefix("FOLDER ").strip()
        path = current.get("finder_path") or getattr(helper, "finder_path", lambda: "")()
        return bool(path) and path.rstrip("/").endswith(folder), current
    if kind == "timer":
        minutes = expected.removeprefix("TIMER ").strip()
        return current.get("timers") == [int(minutes)], current
    if kind == "screenshot":
        before = set(start.get("screenshot_files", []))
        after = set(current.get("screenshot_files", current.get("screenshots", [])))
        return len(after - before) == 1, current
    if kind == "event":
        added = _new_events(start.get("calendar_events", []), current.get("calendar_events", []))
        return len(added) == 1 and _event_matches_snapshot(helper, record, start, added[0]), current
    if kind == "none":
        fields = (
            "bright", "vol", "dark", "front", "finder_windows", "running",
            "screenshot_files", "calendar_events",
        )
        unchanged = all(field in current and field in start and current[field] == start[field] for field in fields)
        return unchanged and not _action_dispatched(trace or {}, first_action), current
    return False, current


def _final_state(helper, record, start, trace, first_action=None):
    current = _capture_final_state(helper, record, start)
    return _grade_final_state(helper, record, start, current, trace, first_action)


def _restore(helper, before, trace, current=None):
    helper.sh(str(helper.WORK / "brightness"), "set", str(before["bright"]))
    helper.osa(f'set volume output volume {before["vol"][0]}')
    helper.osa(f'set volume output muted {"true" if before["vol"][1] else "false"}')
    helper.osa(
        'tell application "System Events" to tell appearance preferences to '
        f'set dark mode to {"true" if before["dark"] else "false"}'
    )
    while helper.finder_windows() > before["finder_windows"]:
        helper.osa('tell application "Finder" to close front window')
    for app, was_running in before["running"].items():
        if not was_running and app not in ("Finder", "Calculator") and helper.running(app):
            helper.osa(f'quit app "{app}"')
    if before.get("screenshot_location"):
        after_files = (current or {}).get("screenshot_files")
        if after_files is None:
            after_files = _image_files(Path(before["screenshot_location"]))
        paths = set(after_files) - set(before.get("screenshot_files", []))
        for path in paths:
            Path(path).unlink(missing_ok=True)
    if "calendar_events" in before:
        after = (current or {}).get("calendar_events")
        if after is None:
            window_start, window_end = (datetime.fromisoformat(value) for value in before["calendar_window"])
            try:
                after = _calendar_events(helper, window_start, window_end)
            except Exception:
                after = []
        ids = [
            event.get("identifier") or event.get("eventIdentifier")
            for event in _new_events(before["calendar_events"], after)
        ]
        ids = [identifier for identifier in ids if identifier]
        if callable(getattr(helper, "delete_calendar_events", None)):
            helper.delete_calendar_events(ids)
        else:
            _eventkit_delete_events(ids)


def _require_test_calendar():
    script = (
        "import EventKit; "
        "print(EKEventStore().defaultCalendarForNewEvents?.title ?? \"\")"
    )
    try:
        result = subprocess.run(
            ["swift", "-e", script], check=True, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("cannot verify Calendar's default; refusing event trial") from exc
    if result.stdout.strip() != "Hobby Test":
        raise RuntimeError("set Calendar's default calendar to 'Hobby Test' before event trials")


def _hobby_state_script(args, kind, before=None):
    encoded = base64.b64encode(json.dumps(before or {}).encode()).decode()
    python = f"""
import base64, json, sys
sys.path.insert(0, {str(ROOT)!r})
sys.path.insert(0, {str(args.hobby_home / 'hobby')!r})
from bench.hobbylm import replay as replay
import hobbymac_run as helper
kind = {kind!r}
before = json.loads(base64.b64decode({encoded!r}).decode())
state = helper.snapshot()
if before:
    if kind == "calc":
        state["display"] = helper.display() if helper.running("Calculator") else None
    if kind in ("screenshot", "none"):
        location = Path(before["screenshot_location"])
        state["screenshot_files"] = replay._image_files(location)
    if kind == "folder" and helper.finder_windows() > before["finder_windows"]:
        state["finder_path"] = helper.finder_path()
    if kind in ("event", "none"):
        start, end = (datetime.fromisoformat(value) for value in before["calendar_window"])
        state["calendar_events"] = replay._calendar_events(helper, start, end)
else:
    if kind in ("screenshot", "none"):
        location = replay._screenshot_location()
        state["screenshot_location"] = str(location)
        state["screenshot_files"] = replay._image_files(location)
    if kind in ("event", "none"):
        now, start, end = replay._calendar_window(helper)
        state["calendar_now"] = now.isoformat()
        state["calendar_window"] = [start.isoformat(), end.isoformat()]
        state["calendar_events"] = replay._calendar_events(helper, start, end)
print(json.dumps(state, ensure_ascii=False, default=str))
"""
    python = python.replace(
        "import base64, json, sys",
        "import base64, json, sys\nfrom datetime import datetime\nfrom pathlib import Path",
    )
    helper_dir = args.hobby_home / "hobby"
    command = (
        f"HOBBY_HOME={shlex.quote(str(args.hobby_home))} "
        f"PYTHONPATH={shlex.quote(os.pathsep.join((str(ROOT), str(helper_dir))))} "
        f"{shlex.quote(sys.executable)} -c {shlex.quote(python)}"
    )
    return command


def _hobby_restore_script(args, start, current, trace):
    encoded = base64.b64encode(json.dumps({
        "start": start, "current": current, "trace": trace or {},
    }, ensure_ascii=False, default=str).encode()).decode()
    python = f"""
import base64, json, sys
sys.path.insert(0, {str(ROOT)!r})
sys.path.insert(0, {str(args.hobby_home / 'hobby')!r})
from bench.hobbylm import replay
import hobbymac_run as helper
payload = json.loads(base64.b64decode({encoded!r}).decode())
replay._restore(helper, payload["start"], payload["trace"], payload["current"])
print(json.dumps({{"ok": True}}))
"""
    helper_dir = args.hobby_home / "hobby"
    return (
        f"HOBBY_HOME={shlex.quote(str(args.hobby_home))} "
        f"PYTHONPATH={shlex.quote(os.pathsep.join((str(ROOT), str(helper_dir))))} "
        f"{shlex.quote(sys.executable)} -c {shlex.quote(python)}"
    )


class _HobbyRuntime(HandsRuntime):
    def __init__(self, *args, helper, task, replay_args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = helper
        self.task = task
        self.replay_args = replay_args
        self.start_state = None
        self.final_state = None
        self.last_trace = None

    async def start_scripts(self):
        await super().start_scripts()
        if self.start_state is None:
            self.start_state = await self.capture_state()

    async def capture_state(self):
        result = await self.run_script(
            "shell",
            _hobby_state_script(self.replay_args, self.task["kind"], self.start_state),
            allow_inflight=self.proxy.capture.active,
        )
        self.final_state = json.loads(result["output"])
        return self.final_state


def _hobby_predicates(helper, args, task):
    grader_record = {
        "id": task["id"], "kind": task["kind"],
        "expected": task["expected"], "text": task["text"],
    }

    async def grade(runtime, context):
        current = await runtime.capture_state()
        runtime.last_trace = context.get("trace")
        first_action = (
            {"method": "act"}
            if runtime.first_action_monotonic is not None else None
        )
        passed, observed = _grade_final_state(
            helper, grader_record, runtime.start_state, current,
            context.get("trace"), first_action,
        )
        return {"passed": bool(passed), "actual": observed}

    async def restore(runtime, result):
        current = runtime.final_state
        if current is None:
            current = await runtime.capture_state()
        trace = runtime.last_trace or result.get("trace")
        code = _hobby_restore_script(
            args, runtime.start_state, current, trace
        )
        return await runtime.run_script("shell", code)

    return grade, restore


async def _run_muselet_cases(args, tasks, run_root, helper):
    from bench.harness.proxy import BenchProxy

    run_root.mkdir(parents=True, exist_ok=True)
    records = []
    trace_path = ROOT / "runs/traces" / f"{datetime.now().date().isoformat()}.jsonl"
    async with BenchProxy(f"ws://127.0.0.1:{args.port}", port=args.proxy_port) as proxy:
        for repeat in range(1, args.repeats + 1):
            for task in tasks:
                run_id = f"{task['id']}-r{repeat}"
                await proxy.wait_disconnected()
                await proxy.begin_case(run_id, None)
                runtime = _HobbyRuntime(
                    proxy, args.hands_bin, run_root / "hands-logs", run_id,
                    helper=helper, task=task, replay_args=args, cwd=ROOT,
                )
                grade, restore = _hobby_predicates(helper, args, task)
                case = {
                    "id": task["id"], "kind": task["kind"], "category": task["kind"],
                    "utterance": task["text"], "timeout_s": args.timeout,
                    "expect_outcome": "ok", "check": [grade], "teardown": [restore],
                }
                try:
                    result = await run_case(
                        case, runtime, values={}, trace_path=trace_path,
                    )
                except Exception as exc:
                    await runtime.stop()
                    result = {"status": "failed", "strict_pass": False, "error": str(exc)}
                final_observations = (
                    result.get("check_observations", [])[-1].get("observations", [])
                    if result.get("check_observations") else []
                )
                final_state_only = bool(
                    final_observations and final_observations[0].get("passed")
                )
                capture = proxy.snapshot()
                elapsed = None
                if runtime.utterance_monotonic is not None and capture.get("frames"):
                    terminal = proxy.capture.terminal_monotonic
                    if terminal is not None:
                        elapsed = max(0.0, terminal - runtime.utterance_monotonic)
                trace = result.get("trace") or {}
                first_action = next((
                    item.get("frame", {}) for item in result.get("frames", [])
                    if item.get("direction") == "brain_to_hands"
                    and isinstance(item.get("frame"), dict)
                    and item["frame"].get("t") == "rpc"
                    and item["frame"].get("method") in ("act", "skill")
                ), {})
                rec = {
                    "id": task["id"], "kind": task["kind"], "repeat": repeat,
                    "pass": bool(result.get("strict_pass")),
                    "pass_final_state": final_state_only,
                    "final_state_only": final_state_only,
                    "completed": bool(result.get("strict_pass")),
                    "strict_completed": bool(result.get("strict_pass")),
                    "false_done": bool(result.get("false_done")),
                    "reported_success": trace.get("outcome") == "ok",
                    "utterance_latency_s": elapsed,
                    "first_action_latency_s": result.get("first_action_latency_s"),
                    "completion_latency_s": result.get("verified_latency_s"),
                    "verified_latency_s": result.get("verified_latency_s"),
                    "final_state": runtime.final_state,
                    "start_state": runtime.start_state,
                    "trace": trace,
                    "frames": result.get("frames", []),
                    "first_action_method": first_action.get("method"),
                    "grader_note": (
                        "start_timer is currently not implemented and has no independently observable state"
                        if task["kind"] == "timer" else None
                    ),
                }
                records.append(rec)
                print(json.dumps(rec, ensure_ascii=False, default=str), flush=True)
    summary = report_math(records, args.repeats)
    summary["shared_harness"] = shared_report_math(records, args.repeats)
    payload = {
        "system": "muselet", "round": args.round, "port": args.port,
        "proxy_port": args.proxy_port,
        "first_action_method": "proxy wire timestamp from utterance frame to first act/skill RPC",
        "results": records, "summary": summary,
    }
    (run_root / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(run_root)
    return 0


def _muselet_run(args, tasks, run_root):
    if sys.platform != "darwin":
        raise RuntimeError("Muselet replay requires macOS desktop access and Accessibility permission")
    if any(task["kind"] == "event" for task in tasks) and not args.allow_calendar:
        raise RuntimeError("event trials require --allow-calendar and Calendar's default calendar set to 'Hobby Test'")
    sys.path.insert(0, str(args.hobby_home / "hobby"))
    import hobbymac_run as helper
    if any(task["kind"] == "event" for task in tasks):
        _require_test_calendar()

    run_root.mkdir(parents=True, exist_ok=True)
    brain_log = (run_root / "brain.log").open("w", encoding="utf-8")
    brain = None
    if not args.external_brain:
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "ml/src"), os.environ.get("PYTHONPATH", ""))),
        }
        brain = subprocess.Popen(
            [sys.executable, "-m", "bench.hobbylm.muselet_brain", "--port", str(args.port)],
            cwd=ROOT, env=env, stdout=brain_log, stderr=subprocess.STDOUT,
        )
        for _ in range(100):
            if brain.poll() is not None:
                brain_log.close()
                raise RuntimeError(f"benchmark brain exited; see {run_root / 'brain.log'}")
            try:
                with socket.create_connection(("127.0.0.1", args.port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            if brain.poll() is None:
                brain.terminate()
                try:
                    brain.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    brain.kill()
                    brain.wait(timeout=5)
            brain_log.close()
            raise RuntimeError(f"benchmark brain did not listen on port {args.port}")
    try:
        return asyncio.run(_run_muselet_cases(args, tasks, run_root, helper))
    finally:
        if brain is not None and brain.poll() is None:
            brain.terminate()
            try:
                brain.wait(timeout=5)
            except subprocess.TimeoutExpired:
                brain.kill()
                brain.wait(timeout=5)
        brain_log.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=("muselet", "hobbylm"), required=True)
    parser.add_argument("--round", choices=("r1", "r2", "r3", "r4"), default="r4")
    parser.add_argument("--ids", default="")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--proxy-port", type=int, default=8790)
    parser.add_argument("--hands-bin", default="hands")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hobby-home", type=Path, default=Path(__import__("os").environ.get("HOBBY_HOME", DEFAULT_HOME)))
    parser.add_argument("--model", choices=("trained", "untrained"), default="trained")
    parser.add_argument("--external-brain", action="store_true",
                        help="Use an already-running Brain server; wire timing remains available through the proxy.")
    parser.add_argument("--allow-calendar", action="store_true",
                        help="Permit event trials only when Calendar's default calendar is the test calendar.")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    tasks = load_tasks(args.hobby_home, args.round)
    if args.ids:
        allowed = set(args.ids.split(","))
        tasks = [task for task in tasks if task["id"] in allowed]
        missing = allowed - {task["id"] for task in tasks}
        if missing:
            parser.error(f"unknown task IDs: {', '.join(sorted(missing))}")
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    planned = plan(args.system, args.round, tasks, args.repeats, args.port)
    if args.dry_run:
        print(json.dumps({"system": args.system, "round": args.round, "planned": len(planned),
                          "tasks": planned}, ensure_ascii=False, indent=2))
        return 0

    if args.system == "muselet":
        try:
            return _muselet_run(
                args, tasks,
                Path("runs/bench/hobbylm/muselet") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            )
        except RuntimeError as exc:
            parser.error(str(exc))

    run_root = Path("runs/bench/hobbylm/hobbylm") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root.mkdir(parents=True)
    runner = args.hobby_home / ".venv/bin/python"
    command = [str(runner), "hobby/hobbymac_run.py", "--model", args.model,
               "--round", args.round, "--adapter", args.round, "--runtime", "mlx"]
    if args.ids:
        command.extend(["--ids", args.ids])
    upstream_runs, result_paths, score_outputs, run_outputs = [], [], [], []
    for _ in range(args.repeats):
        started_at = time.time()
        completed = subprocess.run(command, cwd=args.hobby_home, check=True, text=True, capture_output=True)
        run_candidates = sorted(
            (args.hobby_home / "data/runs").glob("hobbymac-*/results.json"),
            key=lambda path: path.stat().st_mtime,
        )
        result_path = next((path for path in reversed(run_candidates) if path.stat().st_mtime >= started_at), None)
        if result_path is None:
            raise RuntimeError(f"hobbymac_run.py did not produce results.json; stdout: {completed.stdout}")
        score_run = subprocess.run(
            [str(runner), "hobby/hobbymac_score.py", str(result_path)],
            cwd=args.hobby_home, check=True, text=True, capture_output=True,
        )
        result_paths.append(result_path)
        upstream_runs.append(json.loads(result_path.read_text(encoding="utf-8")))
        score_outputs.append(score_run.stdout)
        run_outputs.append(completed.stdout)
    sys.path.insert(0, str(args.hobby_home / "hobby"))
    import hobbymac_run as helper
    records = []
    upstream_rows = [
        (repeat, row)
        for repeat, upstream in enumerate(upstream_runs, 1)
        for row in upstream["results"]
    ]
    for repeat, row in upstream_rows:
        kind, expected, final, start = row["kind"], row["expected"], row["final"], row["start"]
        start_state, current = dict(start), dict(final)
        start_state.setdefault("screenshot_files", [])
        current["screenshot_files"] = current.get("screenshot_files", current.get("screenshots", []))
        grader_record = {
            "id": row["id"], "kind": kind, "expected": expected, "text": row.get("request", "")
        }
        final_only, _ = _grade_final_state(
            helper, grader_record, start_state, current,
            first_action={"executed": bool(row.get("executed"))},
        )
        missing_state = []
        if kind == "event" and not ("calendar_events" in start_state and "calendar_events" in current):
            missing_state.append("before/after Calendar snapshots")
        if kind == "none":
            missing_state.extend(
                key for key in ("finder_windows", "running", "screenshot_files", "calendar_events")
                if key not in start_state or key not in current
            )
        records.append({
            "id": row["id"], "kind": kind, "repeat": repeat,
            "pass": bool(row["completed"]), "completed": bool(row["completed"]),
            "strict_completed": bool(row["completed"]),
            "pass_final_state": bool(final_only), "final_state_only": bool(final_only),
            "reported_success": bool(row.get("said_done")),
            "false_done": bool(row.get("said_done") and not final_only),
            "utterance_latency_s": row["seconds_total"],
            "first_action_latency_s": row["steps"][0]["seconds"] if row["steps"] else None,
            "completion_latency_s": row["seconds_total"] if row["correct_outcome"] else None,
            "final_state_regrade": bool(final_only),
            "grader_note": (
                "upstream results omit " + ", ".join(sorted(set(missing_state)))
                if missing_state else None
            ),
        })
    payload = {
        "system": "hobbylm", "round": args.round, "upstream_results": [str(path) for path in result_paths],
        "results": records, "strict_vs_final_state": records,
        "summary": report_math(records, args.repeats),
        "published_score_output": score_outputs,
        "upstream_stdout": run_outputs,
    }
    (run_root / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["summary"], indent=2))
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
