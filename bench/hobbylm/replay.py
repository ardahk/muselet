#!/usr/bin/env python3
"""Plan and report comparable HobbyLM/Muselet live replays."""

from __future__ import annotations

import argparse
import json
import os
import re
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
    timing_file = run_root / "sent.json"
    first_action_file = run_root / "first-actions.jsonl"
    brain_log = (run_root / "brain.log").open("w", encoding="utf-8")
    brain = None
    if not args.external_brain:
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "ml/src"), os.environ.get("PYTHONPATH", ""))),
        }
        brain = subprocess.Popen(
            [sys.executable, "-m", "bench.hobbylm.muselet_brain", "--port", str(args.port),
             "--timing-file", str(timing_file), "--first-action-file", str(first_action_file)],
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

    records = []
    trace_path = ROOT / "runs/traces" / f"{datetime.now().date().isoformat()}.jsonl"
    try:
        for repeat in range(1, args.repeats + 1):
            for task in tasks:
                if helper.running("Calculator"):
                    helper.osa('quit app "Calculator"')
                before = _start_state(helper, task)
                run_id = f"{task['id']}-r{repeat}"
                local_trace_offset = trace_path.stat().st_size if trace_path.is_file() else 0
                first_offset = first_action_file.stat().st_size if first_action_file.is_file() else 0
                sent = time.monotonic()
                timing_file.write_text(
                    json.dumps({"sent_monotonic": sent, "utterance": task["text"]}),
                    encoding="utf-8",
                )
                log_path = run_root / f"{run_id}.hands.log"
                with log_path.open("w", encoding="utf-8") as log:
                    proc = subprocess.Popen(
                        ["hands", "serve", "--url", f"ws://127.0.0.1:{args.port}",
                         "--utterance", task["text"]],
                        stdout=log, stderr=subprocess.STDOUT,
                    )
                    deadline = sent + args.timeout
                    trace = {}
                    first_completion = None
                    while time.monotonic() < deadline:
                        now = time.monotonic()
                        if task["kind"] in ("calc", "device", "dark", "app", "folder"):
                            try:
                                correct, _ = _grade_final_state(
                                    helper, task, before, _capture_final_state(helper, task, before)
                                )
                                if correct and first_completion is None:
                                    first_completion = now - sent
                            except Exception:
                                pass
                        if trace_path.is_file():
                            with trace_path.open(encoding="utf-8") as source:
                                source.seek(local_trace_offset)
                                lines = [line for line in source if line.strip()]
                            for line in lines:
                                candidate = json.loads(line)
                                if candidate.get("utterance") == task["text"]:
                                    trace = candidate
                            if trace:
                                break
                        if proc.poll() is not None:
                            break
                        time.sleep(0.2)
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=3)
                first_events = []
                if first_action_file.is_file():
                    with first_action_file.open(encoding="utf-8") as source:
                        source.seek(first_offset)
                        first_events = [json.loads(line) for line in source if line.strip()]
                first = next((item for item in first_events if item.get("utterance") == task["text"]), None)
                try:
                    correct, final = _final_state(helper, task, before, trace, first)
                except Exception as exc:
                    correct, final = False, {}
                    final_error = str(exc)
                else:
                    final_error = None
                reported = trace.get("outcome") == "ok"
                completed = bool(correct and reported)
                rec = {
                    "id": task["id"], "kind": task["kind"], "repeat": repeat,
                    "pass": completed, "pass_final_state": bool(correct),
                    "final_state_only": bool(correct), "completed": completed,
                    "false_done": reported and not correct, "reported_success": reported,
                    "utterance_latency_s": time.monotonic() - sent,
                    "first_action_latency_s": first.get("latency_s") if first else None,
                    "completion_latency_s": first_completion,
                    "final_state": final, "trace": trace, "final_error": final_error,
                    "first_action_method": first.get("method") if first else None,
                    "grader_note": "start_timer is currently not implemented and has no independently observable state"
                    if task["kind"] == "timer" else None,
                }
                records.append(rec)
                _restore(helper, before, trace, final)
                print(json.dumps(rec, ensure_ascii=False))
    finally:
        if brain is not None and brain.poll() is None:
            brain.terminate()
            try:
                brain.wait(timeout=5)
            except subprocess.TimeoutExpired:
                brain.kill()
                brain.wait(timeout=5)
        brain_log.close()
    payload = {
        "system": "muselet", "round": args.round, "port": args.port,
        "first_action_method": "benchmark BrainServer.rpc hook, time.monotonic from utterance start to first act/skill dispatch",
        "results": records, "summary": report_math(records, args.repeats),
    }
    (run_root / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(run_root)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=("muselet", "hobbylm"), required=True)
    parser.add_argument("--round", choices=("r1", "r2", "r3", "r4"), default="r4")
    parser.add_argument("--ids", default="")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hobby-home", type=Path, default=Path(__import__("os").environ.get("HOBBY_HOME", DEFAULT_HOME)))
    parser.add_argument("--model", choices=("trained", "untrained"), default="trained")
    parser.add_argument("--external-brain", action="store_true",
                        help="Use an already-running Brain server (first-action timing is unavailable).")
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
