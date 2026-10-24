#!/usr/bin/env python3
"""Plan and report comparable HobbyLM/Muselet live replays."""

from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

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
    all_pass = sum(bool(row.get("pass")) for row in records)
    final_pass = sum(bool(row.get("final_state_only", row.get("pass"))) for row in records)
    passk = {}
    for kind, rows in sorted(by_kind.items()):
        per_id = defaultdict(list)
        for row in rows:
            per_id[row["id"]].append(bool(row.get("pass")))
        passk[kind] = sum(len(values) == repeats and all(values) for values in per_id.values()) / max(1, len(per_id))
    return {
        "n": len(records),
        "pass_rate": all_pass / max(1, len(records)),
        "final_state_only_rate": final_pass / max(1, len(records)),
        "pass_k_by_kind": passk,
        "false_done": sum(bool(row.get("false_done")) for row in records),
        "utterance_latency_s": {"p50": pct([r["utterance_latency_s"] for r in records if r.get("utterance_latency_s") is not None], .5),
                                "p95": pct([r["utterance_latency_s"] for r in records if r.get("utterance_latency_s") is not None], .95)},
        "first_action_latency_s": {"p50": pct([r["first_action_latency_s"] for r in records if r.get("first_action_latency_s") is not None], .5),
                                   "p95": pct([r["first_action_latency_s"] for r in records if r.get("first_action_latency_s") is not None], .95)},
        "completion_latency_s": {"p50": pct([r["completion_latency_s"] for r in records if r.get("completion_latency_s") is not None], .5),
                                 "p95": pct([r["completion_latency_s"] for r in records if r.get("completion_latency_s") is not None], .95)},
    }


def _final_state(helper, record, start, trace):
    kind, expected = record["kind"], record["expected"].strip()
    current = helper.snapshot()
    if kind == "calc":
        value = helper.as_num(helper.display()) if helper.running("Calculator") else None
        return value is not None and abs(value - float(expected)) < 0.006, current
    if kind == "device":
        if expected == "KEY BRIGHTNESS_DOWN":
            ok = current["bright"] < start["bright"]
        elif expected == "KEY BRIGHTNESS_UP":
            ok = current["bright"] > start["bright"] or start["bright"] >= 1
        elif expected == "KEY VOLUME_DOWN":
            ok = current["vol"][0] < start["vol"][0]
        elif expected == "KEY VOLUME_UP":
            ok = current["vol"][0] > start["vol"][0] or start["vol"][0] == 100
        else:
            ok = expected == "KEY MUTE" and current["vol"][1]
        return ok, current
    if kind == "dark":
        return current["dark"] == expected.upper().endswith("ON"), current
    if kind == "app":
        return current["front"].casefold() == expected.casefold(), current
    if kind == "folder":
        path = helper.finder_path()
        return bool(path) and path.rstrip("/").endswith(expected), current
    if kind == "timer":
        return False, current
    if kind == "screenshot":
        paths = [
            rpc.get("result", {}).get("path")
            for rpc in trace.get("rpc", [])
            if rpc.get("method") == "skill" and rpc.get("params", {}).get("name") == "take_screenshot"
        ]
        return any(path and Path(path).is_file() for path in paths), current
    if kind == "event":
        skill_calls = [
            rpc for rpc in trace.get("rpc", [])
            if rpc.get("method") == "skill" and rpc.get("params", {}).get("name") == "create_event"
        ]
        title = next((rpc.get("result", {}).get("title") for rpc in skill_calls if rpc.get("result")), "")
        readback = helper.CAL.find_event("Hobby Test", title) if title else []
        return bool(readback and helper.event_matches(record["text"], expected)), current
    if kind == "none":
        unchanged = (
            current["bright"] == start["bright"] and current["vol"] == start["vol"]
            and current["dark"] == start["dark"] and current["front"] == start["front"]
            and current["finder_windows"] == start["finder_windows"]
        )
        router = (trace.get("decisions") or [{}])[0].get("router", {})
        return unchanged and router.get("kind") == "fallback", current
    return False, current


def _restore(helper, before, trace):
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
    for rpc in trace.get("rpc", []):
        if rpc.get("method") == "skill" and rpc.get("params", {}).get("name") == "take_screenshot":
            path = rpc.get("result", {}).get("path")
            if path:
                Path(path).unlink(missing_ok=True)
        if rpc.get("method") == "skill" and rpc.get("params", {}).get("name") == "create_event":
            title = rpc.get("result", {}).get("title", "")
            if title:
                helper.CAL.osa(
                    'tell application "Calendar" to tell calendar "Hobby Test" '
                    f'to delete (every event whose summary is "{title.replace(chr(34), chr(39))}")'
                )


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
                before = helper.snapshot()
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
                        try:
                            correct, _ = _final_state(helper, task, before, {})
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
                try:
                    correct, final = _final_state(helper, task, before, trace)
                except Exception as exc:
                    correct, final = False, {}
                    final_error = str(exc)
                else:
                    final_error = None
                first_events = []
                if first_action_file.is_file():
                    with first_action_file.open(encoding="utf-8") as source:
                        source.seek(first_offset)
                        first_events = [json.loads(line) for line in source if line.strip()]
                first = next((item for item in first_events if item.get("utterance") == task["text"]), None)
                reported = trace.get("outcome") == "ok"
                rec = {
                    "id": task["id"], "kind": task["kind"], "repeat": repeat,
                    "pass": bool(correct), "final_state_only": bool(correct),
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
                _restore(helper, before, trace)
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
        if kind == "calc":
            value = helper.as_num(final.get("display"))
            final_only = value is not None and abs(value - float(expected)) < 0.006
        elif kind == "none":
            unchanged = (
                final.get("bright") == start.get("bright") and final.get("vol") == start.get("vol")
                and final.get("dark") == start.get("dark") and final.get("front") == start.get("front")
                and not row.get("executed")
            )
            final_only = unchanged and bool(row.get("steps")) and row["steps"][0]["parsed"].get("kind") == "UNKNOWN"
        elif kind == "event":
            final_only = (
                bool(final.get("calendar_readback") and final["calendar_readback"][0])
                and len(final.get("events", [])) == 1
                and helper.event_matches(row["request"], expected)
            )
        elif kind == "device":
            if expected == "KEY BRIGHTNESS_DOWN":
                final_only = final["bright"] < start["bright"]
            elif expected == "KEY BRIGHTNESS_UP":
                final_only = final["bright"] > start["bright"] or start["bright"] >= 1
            elif expected == "KEY VOLUME_DOWN":
                final_only = final["vol"][0] < start["vol"][0]
            elif expected == "KEY VOLUME_UP":
                final_only = final["vol"][0] > start["vol"][0] or start["vol"][0] == 100
            else:
                final_only = expected == "KEY MUTE" and final["vol"][1]
        elif kind == "dark":
            final_only = final["dark"] == expected.upper().endswith("ON")
        elif kind == "app":
            final_only = final["front"].casefold() == expected.casefold()
        elif kind == "folder":
            final_only = bool(final.get("finder_path")) and final["finder_path"].rstrip("/").endswith(expected)
        elif kind == "timer":
            final_only = final.get("timers") == [int(expected.removeprefix("TIMER ").strip())]
        elif kind == "screenshot":
            final_only = len(final.get("screenshots", [])) == 1
        else:
            final_only = False
        records.append({
            "id": row["id"], "kind": row["kind"], "repeat": repeat, "pass": bool(row["completed"]),
            "strict_completed": bool(row["completed"]), "final_state_only": bool(final_only),
            "false_done": bool(row["said_done"] and not row["correct_outcome"]),
            "utterance_latency_s": row["seconds_total"],
            "first_action_latency_s": row["steps"][0]["seconds"] if row["steps"] else None,
            "completion_latency_s": row["seconds_total"] if row["correct_outcome"] else None,
            "final_state_regrade": bool(final_only),
        })
    payload = {
        "system": "hobbylm", "round": args.round, "upstream_results": [str(path) for path in result_paths],
        "strict_vs_final_state": records, "summary": report_math(records, args.repeats),
        "published_score_output": score_outputs,
        "upstream_stdout": run_outputs,
    }
    (run_root / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["summary"], indent=2))
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
