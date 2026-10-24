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

from bench.harness.core import (
    HARNESS_POLL_INTERVAL_S,
    report_math as shared_report_math,
    run_case,
)
from bench.harness.documents import (
    DocumentInventoryError,
    document_apps_for_case,
    foreign_items,
    osascript_run_script,
    take_inventory,
)
from bench.harness.runtime import HandsRuntime
from bench.harness.session import probe_session
from bench.hobbylm.vendor import verify_provenance

DEFAULT_HOME = Path("/home/ubuntu/ext/hobbylm")
VENDORED_UPSTREAM = HERE / "upstream"


def load_tasks(home: Path, round_name: str):
    verify_provenance(VENDORED_UPSTREAM)
    filename = "hobbymac-sealed-test.tsv" if round_name == "r1" else f"hobbymac-sealed-test-{round_name}.tsv"
    rows = []
    frozen = VENDORED_UPSTREAM / "data/frozen"
    for line in (frozen / filename).read_text(encoding="utf-8").splitlines():
        if line.strip():
            ident, kind, text, expected = line.split("\t", 3)
            rows.append({"id": ident, "kind": kind, "text": text, "expected": expected.strip()})
    return rows


def plan(system: str, round_name: str, tasks: list[dict], repeats: int, port: int):
    return [
        {
            "system": system,
            "round": round_name,
            "repeat": repeat,
            **task,
            "port": port,
            "session": "session: hands probe session (skip if locked/asleep)",
            "document_apps": [
                app.name for app in document_apps_for_case({
                    "utterance": task["text"],
                    "category": task["kind"],
                })
            ],
            **({"calc_setup": "calculator_open_cleared"}
               if task["kind"] == "calc" else {}),
        }
        for repeat in range(1, repeats + 1)
        for task in tasks
    ]


def report_math(records: list[dict], repeats: int) -> dict:
    eligible = [
        record for record in records
        if record.get("status") != "skipped" and not record.get("ungradable")
    ]
    by_kind = defaultdict(list)
    for record in eligible:
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
            if row.get("status") != "skipped" and not row.get("ungradable"):
                per_id[row["id"]].append(field(row))
        eligible = [
            values for values in per_id.values()
            if len(values) == repeats
        ]
        return sum(all(values) for values in eligible) / max(1, len(eligible))

    def latency_kinds(field):
        return sorted({
            row["kind"] for row in records
            if row.get(field) is not None and row.get("status") != "skipped"
            and not row.get("ungradable")
        })

    verified = [
        row["verified_latency_s"] for row in records
        if row.get("kind") != "none" and row.get("verified_latency_s") is not None
        and not row.get("ungradable")
    ]
    latency_by_kind = {}
    for kind in sorted({
        row["kind"] for row in records
        if row.get("status") != "skipped" and not row.get("ungradable")
    }):
        rows = [
            row for row in records
            if row.get("kind") == kind and row.get("status") != "skipped"
            and not row.get("ungradable")
        ]
        first_values = [row["first_action_latency_s"] for row in rows
                        if row.get("first_action_latency_s") is not None]
        verified_values = [row["verified_latency_s"] for row in rows
                           if kind != "none" and row.get("verified_latency_s") is not None]
        latency_by_kind[kind] = {
            "first_action_p50": pct(first_values, .5),
            "first_action_p95": pct(first_values, .95),
            "verified_p50": pct(verified_values, .5),
            "verified_p95": pct(verified_values, .95),
            "first_action_n": len(first_values),
            "verified_n": len(verified_values),
        }
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
    pass_final_state_k = pass_k(eligible, final_pass)
    completed_k = pass_k(eligible, completed)
    completed_rate = sum(completed(row) for row in eligible) / max(1, len(eligible))
    final_state_rate = sum(final_pass(row) for row in eligible) / max(1, len(eligible))
    return {
        "n": len(eligible),
        "skipped": sum(row.get("status") == "skipped" for row in records),
        "ungradable": sum(bool(row.get("ungradable")) for row in records),
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
        "utterance_latency_s": {"p50": pct([r["utterance_latency_s"] for r in records if r.get("utterance_latency_s") is not None and not r.get("ungradable")], .5),
                                "p95": pct([r["utterance_latency_s"] for r in records if r.get("utterance_latency_s") is not None and not r.get("ungradable")], .95)},
        "first_action_latency_s": {"p50": pct([r["first_action_latency_s"] for r in records if r.get("first_action_latency_s") is not None and not r.get("ungradable")], .5),
                                   "p95": pct([r["first_action_latency_s"] for r in records if r.get("first_action_latency_s") is not None and not r.get("ungradable")], .95)},
        "completion_latency_s": {"p50": pct([r["completion_latency_s"] for r in records if r.get("completion_latency_s") is not None and r.get("kind") != "none" and not r.get("ungradable")], .5),
                                 "p95": pct([r["completion_latency_s"] for r in records if r.get("completion_latency_s") is not None and r.get("kind") != "none" and not r.get("ungradable")], .95)},
        "verified_latency_s": {"p50": pct(verified, .5), "p95": pct(verified, .95)},
        "latency_kinds": {
            "utterance": latency_kinds("utterance_latency_s"),
            "first_action": latency_kinds("first_action_latency_s"),
            "verified": sorted({
                row["kind"] for row in records
                if row.get("kind") != "none" and row.get("verified_latency_s") is not None
            }),
        },
        "latency_by_kind": latency_by_kind,
        "ungradable": sum(bool(row.get("ungradable")) for row in records),
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
let calendars = store.calendars(for: .event).filter {
    $0.title == title && $0.source.sourceType == .local
}
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
    from bench.hobbylm.calendar_safety import BENCH_CALENDAR

    reader = getattr(helper, "calendar_events", None)
    if callable(reader):
        return reader(BENCH_CALENDAR, start, end)
    return _read_calendar_events(BENCH_CALENDAR, start, end)


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
    if let event = store.event(withIdentifier: identifier),
       event.calendar.title == "Muselet Bench",
       event.calendar.source.sourceType == .local {
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
    try:
        start["finder_window_ids"] = _finder_window_ids(helper)
    except Exception:
        start["finder_window_ids"] = None
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


def _finder_window_ids(helper):
    if callable(getattr(helper, "finder_window_ids", None)):
        values = helper.finder_window_ids()
    else:
        values = helper.osa(
            'tell application "Finder" to get id of every Finder window'
        )
    if values is None or values == "":
        return []
    if isinstance(values, (list, tuple, set)):
        candidates = values
    else:
        candidates = re.findall(r"\d+", str(values))
    ids = []
    for value in candidates:
        try:
            identifier = int(value)
        except (TypeError, ValueError):
            continue
        if identifier not in ids:
            ids.append(identifier)
    return ids


def _capture_final_state(helper, record, start):
    current = helper.snapshot()
    try:
        current["finder_window_ids"] = _finder_window_ids(helper)
    except Exception:
        current["finder_window_ids"] = None
    if record["kind"] == "calc":
        current["display"] = helper.display() if helper.running("Calculator") else None
    if (
        record["kind"] == "folder"
        and current.get("finder_window_ids") is not None
        and start.get("finder_window_ids") is not None
        and set(current["finder_window_ids"]) - set(start["finder_window_ids"])
    ):
        current["finder_path"] = helper.finder_path()
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


def _worker_snapshot_grade(helper, record, start, current, *, first_action=False, safety_blocked=False):
    kind = record["kind"]
    required_start, required_current = {
        "calc": ((), ("display",)),
        "device": (("bright", "vol"), ("bright", "vol")),
        "dark": ((), ("dark",)),
        "app": ((), ("front",)),
        "folder": (("finder_windows",), ("finder_path",)),
        "timer": ((), ("timers",)),
        "screenshot": (("screenshot_files",), ("screenshot_files",)),
        "event": (("calendar_events",), ("calendar_events",)),
        "none": (
            ("bright", "vol", "dark", "front", "finder_windows", "running",
             "screenshot_files", "calendar_events"),
            ("bright", "vol", "dark", "front", "finder_windows", "running",
             "screenshot_files", "calendar_events"),
        ),
    }.get(kind, ((), ()))
    missing = sorted(
        {field for field in required_start if field not in start}
        | {field for field in required_current if field not in current}
    )
    if missing:
        return {
            "passed": False,
            "ungradable": True,
            "missing_snapshots": missing,
            "observed": current,
        }
    passed, observed = _grade_final_state(
        helper, record, start, current, trace={"rpc": []},
        first_action={"executed": first_action},
    )
    return {
        "passed": bool(passed and not safety_blocked),
        "ungradable": False,
        "safety_blocked": safety_blocked,
        "observed": observed,
    }


def _restore(helper, before, trace, current=None):
    helper.sh(str(helper.WORK / "brightness"), "set", str(before["bright"]))
    helper.osa(f'set volume output volume {before["vol"][0]}')
    helper.osa(f'set volume output muted {"true" if before["vol"][1] else "false"}')
    helper.osa(
        'tell application "System Events" to tell appearance preferences to '
        f'set dark mode to {"true" if before["dark"] else "false"}'
    )
    baseline_finder_ids = before.get("finder_window_ids")
    if baseline_finder_ids is not None:
        for identifier in _finder_window_ids(helper):
            if identifier not in set(baseline_finder_ids):
                helper.osa(
                    'tell application "Finder" to close '
                    f'(every Finder window whose id is {int(identifier)})'
                )
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
        _eventkit_delete_events(ids)


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
try:
    state["finder_window_ids"] = replay._finder_window_ids(helper)
except Exception:
    state["finder_window_ids"] = None
if before:
    if kind == "calc":
        state["display"] = helper.display() if helper.running("Calculator") else None
    if kind in ("screenshot", "none"):
        location = Path(before["screenshot_location"])
        state["screenshot_files"] = replay._image_files(location)
    if (
        kind == "folder"
        and state.get("finder_window_ids") is not None
        and before.get("finder_window_ids") is not None
        and set(state["finder_window_ids"]) - set(before["finder_window_ids"])
    ):
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
        self.timer_calls = []
        self.timer_start_calls = []
        self.timer_grading = None
        self.timer_teardown = None
        self.timer_preexisting_ids = set()
        self.timer_rpc_available = None
        self.timer_after_snapshot = False
        self.timer_rpc_error = None
        self.started_timer_ids = []

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
        if self.task["kind"] == "timer" and self.timer_after_snapshot:
            self.final_state["timers"] = [
                item["minutes"] for item in self.timer_calls
            ]
        return self.final_state

    async def capture_timer_baseline(self):
        self.timer_start_calls = _timer_start_results(self.proxy.capture.frames)
        try:
            response = await self.run_rpc("timers", {})
        except Exception as exc:
            if not _rpc_method_absent(exc):
                self.timer_rpc_error = str(exc)
                raise
            self.timer_rpc_available = False
            self.timer_grading = "proxied_start_timer_ok_results"
            return
        self.timer_rpc_available = True
        self.timer_grading = "hands_timers_rpc"
        self.timer_preexisting_ids = {
            item["id"] for item in _timer_rpc_items(response)
            if item.get("id") is not None
        }

    async def capture_timer_after_case(self):
        self.timer_start_calls = _timer_start_results(self.proxy.capture.frames)
        if self.timer_rpc_available:
            response = await self.run_rpc("timers", {})
            self.timer_calls = [
                item for item in _timer_rpc_items(response)
                if item.get("id") not in self.timer_preexisting_ids
            ]
            self.timer_calls.sort(key=lambda item: str(item.get("fires_at", "")))
        else:
            self.timer_calls = self.timer_start_calls
        self.started_timer_ids = list(dict.fromkeys(
            [
                item.get("id", item.get("timer_id"))
                for item in self.timer_calls
                if item.get("id", item.get("timer_id")) is not None
            ] + [
                item.get("timer_id") for item in self.timer_start_calls
                if item.get("timer_id") is not None
            ]
        ))
        self.timer_after_snapshot = True


def _rpc_method_absent(error):
    return bool(re.search(
        r"(?:unknown[\s_-]+(?:rpc|method)|(?:rpc|method)[\s_-]+not[\s_-]+found|no such method)",
        str(error),
        re.IGNORECASE,
    ))


def _timer_rpc_items(reply):
    value = reply.get("result", reply) if isinstance(reply, dict) else reply
    if isinstance(value, dict):
        timers = value.get("timers", [])
    else:
        timers = value
    if not isinstance(timers, list):
        return []
    items = []
    for timer in timers:
        if not isinstance(timer, dict) or not isinstance(timer.get("minutes"), (int, float)):
            continue
        items.append({
            "id": timer.get("id"),
            "timer_id": timer.get("id"),
            "minutes": round(timer["minutes"]),
            "seconds": timer.get("total_s"),
            "fires_at": timer.get("fires_at"),
            "label": timer.get("label"),
        })
    return items


def _rpc_result_value(frame):
    value = frame.get("result")
    if isinstance(value, list):
        return {"timers": value}
    if not isinstance(value, dict):
        return {}
    nested = value.get("result")
    return {**value, **nested} if isinstance(nested, dict) else value


def _timer_start_results(frames):
    results = []
    requests = [
        frame["frame"] for frame in frames
        if frame.get("direction") == "brain_to_hands"
        and isinstance(frame.get("frame"), dict)
        and frame["frame"].get("t") == "rpc"
        and frame["frame"].get("method") == "skill"
        and (frame["frame"].get("params") or {}).get("name") == "start_timer"
    ]
    for request in requests:
        request_id = request.get("id")
        response = next((
            item["frame"] for item in frames
            if item.get("direction") == "hands_to_brain"
            and isinstance(item.get("frame"), dict)
            and item["frame"].get("t") == "rpc_result"
            and item["frame"].get("id") == request_id
        ), None)
        if not response or response.get("ok") is not True:
            continue
        value = _rpc_result_value(response)
        args = (request.get("params") or {}).get("args") or {}
        seconds = value.get("seconds")
        if not isinstance(seconds, (int, float)):
            from brain.decision import parse_duration
            seconds = parse_duration(str(args.get("duration", "")))
        if not isinstance(seconds, (int, float)):
            continue
        results.append({
            "minutes": round(seconds / 60),
            "seconds": seconds,
            "timer_id": value.get("timer_id"),
        })
    return results


async def _calculator_setup(runtime, helper, timeout_s=5.0):
    try:
        await runtime.run_script(
            "applescript", 'tell application "Calculator" to activate')
        await runtime.run_script(
            "applescript", 'tell application "System Events" to key code 53')
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            remaining = deadline - asyncio.get_running_loop().time()
            frontmost = await asyncio.wait_for(asyncio.to_thread(
                helper.sh, "osascript", "-e",
                'tell application "System Events" to get name of first process whose frontmost is true',
            ), remaining)
            if frontmost == "Calculator":
                remaining = deadline - asyncio.get_running_loop().time()
                display = await asyncio.wait_for(
                    asyncio.to_thread(helper.display), max(0.001, remaining))
            else:
                display = None
            if frontmost == "Calculator" and display == "0":
                return True
            await asyncio.sleep(min(0.1, max(0, deadline - asyncio.get_running_loop().time())))
    except Exception:
        return False
    return False


async def _prepare_calculator(runtime, helper, timeout_s=5.0):
    await runtime.start_scripts()
    return await _calculator_setup(runtime, helper, timeout_s=timeout_s)


async def _calculator_case_setup(runtime, helper, timeout_s=5.0):
    if await _prepare_calculator(runtime, helper, timeout_s=timeout_s):
        return None
    return {
        "status": "skipped",
        "strict_pass": False,
        "skip_reason": "calc_setup_failed",
        "calc_setup": "calculator_open_cleared",
    }


def _run_metadata(tasks):
    metadata = {}
    if any(task["kind"] == "calc" for task in tasks):
        metadata["calc_setup"] = "calculator_open_cleared"
    if any(task["kind"] == "timer" for task in tasks):
        metadata["timer_grading"] = "hands_timers_rpc"
    return metadata


async def _timer_teardown(runtime, result):
    timer_ids = list(runtime.started_timer_ids)
    if not timer_ids:
        runtime.timer_teardown = {
            "timer_teardown": "no_case_timers_to_cancel",
            "timer_ids": [],
            "cancelled_ids": [],
        }
        return runtime.timer_teardown
    cancelled_ids = []
    errors = []
    for timer_id in timer_ids:
        try:
            await runtime.run_rpc("timers_cancel", {"id": timer_id})
            cancelled_ids.append(timer_id)
        except Exception as exc:
            message = str(exc)
            if _rpc_method_absent(exc):
                runtime.timer_rpc_available = False
                runtime.timer_teardown = {
                    "timer_teardown": "not_cancelled_no_timers_cancel_rpc",
                    "timer_ids": timer_ids,
                    "cancelled_ids": cancelled_ids,
                    "errors": errors + [{"id": timer_id, "error": message}],
                }
                return runtime.timer_teardown
            errors.append({"id": timer_id, "error": message})
    runtime.timer_teardown = {
        "timer_teardown": "timers_cancel",
        "timer_ids": timer_ids,
        "cancelled_ids": cancelled_ids,
        "errors": errors,
    }
    return {
        **runtime.timer_teardown,
        **({"ok": False} if any(
            not re.search(r"unknown_timer", item["error"], re.IGNORECASE)
            for item in errors
        ) else {}),
    }


def _hobby_predicates(helper, args, task):
    grader_record = {
        "id": task["id"], "kind": task["kind"],
        "expected": task["expected"], "text": task["text"],
    }

    async def grade(runtime, context):
        current = await runtime.capture_state()
        if task["kind"] == "timer" and not runtime.timer_after_snapshot:
            return {"passed": False, "actual": {"timers": "awaiting post-case snapshot"}}
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


async def _run_muselet_cases(args, tasks, run_root, helper, *, event_allowed=None):
    from bench.harness.proxy import BenchProxy

    run_root.mkdir(parents=True, exist_ok=True)
    records = []
    trace_path = ROOT / "runs/traces" / f"{datetime.now().date().isoformat()}.jsonl"
    async with BenchProxy(f"ws://127.0.0.1:{args.port}", port=args.proxy_port) as proxy:
        for repeat in range(1, args.repeats + 1):
            for task in tasks:
                run_id = f"{task['id']}-r{repeat}"
                session = probe_session(args.hands_bin)
                if session["skip_reason"]:
                    rec = {
                        "id": task["id"], "kind": task["kind"], "repeat": repeat,
                        "status": "skipped", "strict_pass": False,
                        **session,
                        **({"timer_grading": "not_run_skipped"} if task["kind"] == "timer" else {}),
                    }
                    records.append(rec)
                    print(json.dumps(rec, ensure_ascii=False), flush=True)
                    continue
                if task["kind"] == "event" and event_allowed is None:
                    try:
                        from bench.hobbylm.calendar_safety import (
                            is_local_default, probe_bench_calendar,
                            setup_bench_calendar,
                        )
                        if args.setup_bench_calendar:
                            setup_bench_calendar()
                        event_allowed = is_local_default(probe_bench_calendar())
                    except Exception:
                        event_allowed = False
                if task["kind"] == "event" and not event_allowed:
                    rec = {
                        "id": task["id"], "kind": task["kind"], "repeat": repeat,
                        "status": "skipped", "strict_pass": False,
                        "skip_reason": "bench calendar not local default",
                        **session,
                    }
                    records.append(rec)
                    print(json.dumps(rec, ensure_ascii=False), flush=True)
                    continue
                await proxy.wait_disconnected()
                await proxy.begin_case(run_id, False)
                runtime = _HobbyRuntime(
                    proxy, args.hands_bin, run_root / "hands-logs", run_id,
                    helper=helper, task=task, replay_args=args, cwd=ROOT,
                )
                if task["kind"] == "calc":
                    setup_skip = await _calculator_case_setup(runtime, helper)
                    if setup_skip is not None:
                        await runtime.stop()
                        rec = {
                            "id": task["id"], "kind": task["kind"],
                            "repeat": repeat, "status": "skipped",
                            **setup_skip,
                            **session,
                        }
                        records.append(rec)
                        print(json.dumps(rec, ensure_ascii=False), flush=True)
                        continue
                grade, restore = _hobby_predicates(helper, args, task)
                case = {
                    "id": task["id"], "kind": task["kind"], "category": task["kind"],
                    "utterance": task["text"], "timeout_s": args.timeout,
                    "check": [grade],
                    **({
                        "before_utterance": lambda runtime, _result: runtime.capture_timer_baseline(),
                        "after_utterance": lambda runtime, _result: runtime.capture_timer_after_case(),
                    } if task["kind"] == "timer" else {}),
                    "teardown": (
                        [_timer_teardown, restore]
                        if task["kind"] == "timer" else [restore]
                    ),
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
                    **session,
                    **({"calc_setup": "calculator_open_cleared"}
                       if task["kind"] == "calc" else {}),
                    **({
                        "timer_grading": runtime.timer_grading or "not_run",
                        "timer_calls": runtime.timer_calls,
                        "timer_start_calls": runtime.timer_start_calls,
                        "timer_state": runtime.timer_calls,
                        "timer_seconds": [
                            item.get("seconds") for item in runtime.timer_calls
                        ],
                        "timer_ids": runtime.started_timer_ids,
                        **({
                            "timer_teardown": "not_run_skipped",
                            "timer_ids": [],
                            "cancelled_ids": [],
                        } if result.get("status") == "skipped" else
                            runtime.timer_teardown or {
                                "timer_teardown": "not_run",
                                "cancelled_ids": [],
                            }),
                    } if task["kind"] == "timer" else {}),
                }
                records.append(rec)
                print(json.dumps(rec, ensure_ascii=False, default=str), flush=True)
    summary = report_math(records, args.repeats)
    summary["shared_harness"] = shared_report_math(records, args.repeats)
    metadata = _run_metadata(tasks)
    timer_records = [
        record for record in records if record.get("kind") == "timer"
    ]
    if timer_records:
        metadata["timer_grading_by_case"] = {
            f"{record['id']}-r{record['repeat']}": record.get("timer_grading")
            for record in timer_records
        }
    summary.update(metadata)
    payload = {
        "system": "muselet", "round": args.round, "port": args.port,
        "proxy_port": args.proxy_port,
        "metadata": metadata,
        "first_action_method": "proxy wire timestamp from utterance frame to first act/skill RPC",
        "results": records, "summary": summary,
    }
    (run_root / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (run_root / "manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(run_root)
    return 0


def _muselet_run(args, tasks, run_root):
    if sys.platform != "darwin":
        raise RuntimeError("Muselet replay requires macOS desktop access and Accessibility permission")
    from bench.hobbylm.calendar_safety import BENCH_CALENDAR
    sys.path.insert(0, str(args.hobby_home / "hobby"))
    import hobbymac_run as helper
    helper.TEST_CAL = BENCH_CALENDAR

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
        return asyncio.run(
            _run_muselet_cases(args, tasks, run_root, helper)
        )
    finally:
        if brain is not None and brain.poll() is None:
            brain.terminate()
            try:
                brain.wait(timeout=5)
            except subprocess.TimeoutExpired:
                brain.kill()
                brain.wait(timeout=5)
        brain_log.close()


def _load_parent_hobby_helper(home: Path):
    import importlib

    from bench.hobbylm.calendar_safety import BENCH_CALENDAR

    os.environ["HOBBY_HOME"] = str(home)
    sys.path.insert(0, str(home / "hobby"))
    sys.path.insert(0, str(HERE / "upstream" / "hobby"))
    helper = importlib.import_module("hobbymac_run")
    helper.ROOT = home
    helper.WORK = home / "data"
    helper.TEST_CAL = BENCH_CALENDAR
    return helper


async def _worker_event(stdout):
    while True:
        line = await stdout.readline()
        if not line:
            return None
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(event, dict) and "ev" in event:
            return event


async def _hobby_worker_document_guard(task, run_script=None):
    case = {"utterance": task["text"], "category": task["kind"]}
    apps = document_apps_for_case(case)
    app_names = [app.name for app in apps]
    if not apps:
        return {"document_apps": [], "document_baseline": {}}
    try:
        baseline = await take_inventory(run_script or osascript_run_script, apps)
    except DocumentInventoryError as exc:
        return {
            "status": "skipped",
            "strict_pass": False,
            "ungradable": False,
            "skip_reason": "user_documents_unverifiable",
            "document_apps": app_names,
            "document_inventory_error": str(exc),
        }
    user_documents = foreign_items(baseline)
    result = {"document_apps": app_names, "document_baseline": baseline}
    if user_documents:
        result.update({
            "status": "skipped",
            "strict_pass": False,
            "ungradable": False,
            "skip_reason": "user_documents_open",
            "user_documents": user_documents,
        })
    return result


def _probe_hobby_event_calendar(setup_bench_calendar):
    try:
        from bench.hobbylm.calendar_safety import (
            is_local_default, probe_bench_calendar,
            setup_bench_calendar as setup_calendar,
        )
        if setup_bench_calendar:
            setup_calendar()
        return is_local_default(probe_bench_calendar())
    except Exception:
        return False


async def _run_hobby_worker_case(
    proc, helper, task, repeat, *, hands_bin="hands", event_allowed=None,
    setup_bench_calendar=False, run_script=None, event_probe_cache=None,
):
    record = {
        "id": task["id"], "kind": task["kind"], "expected": task["expected"],
        "text": task["text"],
    }
    session = probe_session(hands_bin)
    if session["skip_reason"]:
        return {
            **record, "repeat": repeat, "status": "skipped",
            "strict_pass": False, "ungradable": False, **session,
        }
    record.update(session)
    if task["kind"] == "event":
        if event_probe_cache is not None:
            if not event_probe_cache["checked"]:
                event_probe_cache["allowed"] = _probe_hobby_event_calendar(
                    setup_bench_calendar
                )
                event_probe_cache["checked"] = True
            event_allowed = event_probe_cache["allowed"]
        elif event_allowed is None:
            event_allowed = _probe_hobby_event_calendar(setup_bench_calendar)
    if task["kind"] == "event" and not event_allowed:
        return {
            **record, "repeat": repeat, "status": "skipped",
            "strict_pass": False, "ungradable": False,
            "skip_reason": "bench calendar not local default",
        }
    document_guard = await _hobby_worker_document_guard(task, run_script)
    if document_guard.get("status") == "skipped":
        return {**record, "repeat": repeat, **document_guard}
    record.update(document_guard)
    proc.stdin.write((json.dumps(task, ensure_ascii=False) + "\n").encode())
    await proc.stdin.drain()
    events = []
    start_state = None
    final_state = None
    t0_receipt = None
    action_receipt = None
    verified_latency = None
    safety_blocked = False
    stop_poll = asyncio.Event()

    async def poll_state():
        nonlocal verified_latency
        while not stop_poll.is_set():
            try:
                await asyncio.wait_for(stop_poll.wait(), HARNESS_POLL_INTERVAL_S)
                continue
            except asyncio.TimeoutError:
                pass
            if t0_receipt is None or start_state is None:
                continue
            try:
                current = await asyncio.to_thread(
                    _capture_final_state, helper, record, start_state
                )
                grade = _worker_snapshot_grade(
                    helper, record, start_state, current,
                    first_action=action_receipt is not None,
                    safety_blocked=safety_blocked,
                )
                if (
                    verified_latency is None and task["kind"] != "none"
                    and grade["passed"] and not grade["ungradable"]
                ):
                    verified_latency = max(0.0, time.monotonic() - t0_receipt)
            except Exception:
                continue

    poll_task = asyncio.create_task(poll_state())
    upstream_row = None
    final_grade = None
    while True:
        event = await _worker_event(proc.stdout)
        if event is None:
            stop_poll.set()
            await poll_task
            raise RuntimeError("HobbyLM worker exited before completing the case")
        events.append(event)
        now = time.monotonic()
        if event["ev"] == "setup_done":
            start_state = await asyncio.to_thread(_start_state, helper, record)
            proc.stdin.write(b'{"ack":true}\n')
            await proc.stdin.drain()
        elif event["ev"] == "t0" and t0_receipt is None:
            t0_receipt = now
        elif event["ev"] == "first_action" and action_receipt is None:
            action_receipt = now
        elif event["ev"] == "safety_blocked":
            safety_blocked = True
        elif event["ev"] == "pre_teardown":
            stop_poll.set()
            await poll_task
            if start_state is not None:
                try:
                    final_state = await asyncio.to_thread(
                        _capture_final_state, helper, record, start_state
                    )
                    final_grade = _worker_snapshot_grade(
                        helper, record, start_state, final_state,
                        first_action=action_receipt is not None,
                        safety_blocked=safety_blocked,
                    )
                except Exception as exc:
                    final_grade = {
                        "passed": False, "ungradable": True,
                        "missing_snapshots": [f"snapshot failure: {exc}"],
                    }
            else:
                final_grade = {
                    "passed": False, "ungradable": True,
                    "missing_snapshots": ["parent setup snapshot"],
                }
            proc.stdin.write(b'{"ack":true}\n')
            await proc.stdin.drain()
        elif event["ev"] == "done":
            upstream_row = event.get("row")
            break

    if not stop_poll.is_set():
        stop_poll.set()
        await poll_task
    if final_grade is None:
        final_grade = {
            "passed": False, "ungradable": True,
            "missing_snapshots": ["worker omitted pre-teardown snapshot"],
        }
    if upstream_row and upstream_row.get("safety_blocked"):
        safety_blocked = True
        final_grade["passed"] = False
        final_grade["safety_blocked"] = True
    strict_pass = bool(final_grade["passed"] and not final_grade["ungradable"])
    finished = time.monotonic()
    return {
        "id": task["id"], "kind": task["kind"], "repeat": repeat,
        "document_apps": document_guard.get("document_apps", []),
        "document_baseline": document_guard.get("document_baseline", {}),
        "status": "ungradable" if final_grade["ungradable"] else "completed",
        "strict_pass": strict_pass, "pass": strict_pass,
        "pass_final_state": strict_pass, "final_state_only": strict_pass,
        "completed": strict_pass, "false_done": bool(
            upstream_row and upstream_row.get("said_done") and not strict_pass
        ),
        "upstream_completed": bool(upstream_row and upstream_row.get("completed")),
        "upstream_correct_outcome": bool(upstream_row and upstream_row.get("correct_outcome")),
        "reported_success": bool(upstream_row and upstream_row.get("said_done")),
        "safety_blocked": safety_blocked,
        "safety_blocks": [item for item in events if item["ev"] == "safety_blocked"],
        "confirm_reply": False, "confirm_asked": sum(item["ev"] == "confirm_asked" for item in events),
        "t0_parent_monotonic": t0_receipt,
        "first_action_parent_monotonic": action_receipt,
        "utterance_latency_s": max(0.0, finished - t0_receipt) if t0_receipt is not None else None,
        "first_action_latency_s": (
            max(0.0, action_receipt - t0_receipt)
            if action_receipt is not None and t0_receipt is not None else None
        ),
        "verified_latency_s": None if task["kind"] == "none" else verified_latency,
        "completion_latency_s": None if task["kind"] == "none" else verified_latency,
        "ungradable": bool(final_grade["ungradable"]),
        "missing_snapshots": final_grade.get("missing_snapshots", []),
        "strict_observations": final_grade.get("observed"),
        "start_state": start_state, "final_state": final_state,
        "worker_events": events, "upstream_row": upstream_row,
        "agent_reported_utterance_latency_s": (
            upstream_row.get("seconds_total") if upstream_row else None
        ),
    }


async def _run_hobby_worker(args, tasks, run_root, helper, *, event_allowed=None):
    run_root.mkdir(parents=True, exist_ok=True)
    runner = args.hobby_home / ".venv/bin/python"
    worker = HERE / "hobby_worker.py"
    env = {**os.environ, "HOBBY_HOME": str(args.hobby_home)}
    proc = await asyncio.create_subprocess_exec(
        str(runner), str(worker), "--hobby-home", str(args.hobby_home),
        "--model", args.model, "--round", args.round, "--runtime", "mlx",
        cwd=args.hobby_home, env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stderr_task = asyncio.create_task(proc.stderr.read())
    records = []
    event_probe_cache = {
        "checked": event_allowed is not None,
        "allowed": event_allowed,
    }
    try:
        for repeat in range(1, args.repeats + 1):
            for task in tasks:
                record = await _run_hobby_worker_case(
                    proc, helper, task, repeat, hands_bin=args.hands_bin,
                    event_allowed=event_allowed,
                    setup_bench_calendar=args.setup_bench_calendar,
                    event_probe_cache=event_probe_cache,
                )
                records.append(record)
                print(json.dumps(record, ensure_ascii=False, default=str), flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            proc.terminate()
            await proc.wait()
    stderr = await stderr_task
    (run_root / "worker.stderr.log").write_bytes(stderr)
    payload = {
        "system": "hobbylm", "round": args.round, "model": args.model,
        "worker": str(worker), "results": records,
        "summary": report_math(records, args.repeats),
    }
    (run_root / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(run_root)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--system", choices=("muselet", "hobbylm", "hobbylm-published"), required=True
    )
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
    parser.add_argument("--setup-bench-calendar", action="store_true",
                        help="Create Muselet Bench only in an existing local Calendar source.")
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

    if args.system == "hobbylm-published":
        parser.error(
            "hobbylm-published is reference-only; run the pinned upstream runner "
            "outside this guarded replay harness"
        )
    if sys.platform != "darwin":
        parser.error("HobbyLM replay requires macOS desktop access")
    helper = _load_parent_hobby_helper(args.hobby_home)
    run_root = Path("runs/bench/hobbylm/hobbylm") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        return asyncio.run(
            _run_hobby_worker(args, tasks, run_root, helper)
        )
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
