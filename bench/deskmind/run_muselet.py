#!/usr/bin/env python3
"""Run Muselet on DeskMind diag fixtures and write score-compatible run folders."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = Path("/home/ubuntu/ext/deskmind-ai__bench")


def make_plan(tasks, repeats, port, runs_dir):
    return [
        {
            "task_id": task.id,
            "goal": task.goal,
            "fixture": task.fixture,
            "repeat": repeat,
            "workspace": str(runs_dir / task.id / f"repeat-{repeat}" / "ws"),
            "hands": ["hands", "serve", "--url", f"ws://127.0.0.1:{port}", "--utterance", task.goal],
        }
        for task in tasks
        for repeat in range(1, repeats + 1)
    ]


def _trace_snapshot(trace_path: Path, offset: int) -> list[str]:
    if not trace_path.is_file():
        return []
    with trace_path.open("r", encoding="utf-8") as stream:
        stream.seek(offset)
        return [line for line in stream if line.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-dir", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--task-set", default="diag")
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--hands-command", default="hands")
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs/bench/deskmind/muselet")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.bench_dir))
    from deskmind_bench.graders.primitives import GradeContext
    from deskmind_bench.graders.score import grade
    from deskmind_bench.scoring import pristine_sentinels
    from deskmind_bench.suite import suite_hash
    from deskmind_bench.task import load_set
    from deskmind_bench.verify import NULL_METRICS, _unpack

    tasks = load_set(args.bench_dir / "tasks", args.task_set)
    if args.task:
        selected = set(args.task)
        tasks = [task for task in tasks if task.id in selected]
        missing = selected - {task.id for task in tasks}
        if missing:
            parser.error(f"unknown task IDs: {', '.join(sorted(missing))}")
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    plans = make_plan(tasks, args.repeats, args.port, args.runs_dir)
    if args.dry_run:
        print(json.dumps({"suite_hash": suite_hash(args.task_set), "planned": plans,
                          "score": f"deskmind-bench score {args.runs_dir} --suite-version diag-v25 --out {args.runs_dir}/score.json",
                          "table": f"deskmind-bench table {args.runs_dir}/score.json"}, ensure_ascii=False, indent=2))
        return 0
    if sys.platform != "darwin":
        parser.error("live DeskMind Bench replay requires macOS, Accessibility permissions, and a running brain server")
    binary = shutil.which(args.hands_command) or args.hands_command
    fixtures = args.bench_dir / "fixtures"
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        for repeat in range(1, args.repeats + 1):
            run_id = f"muselet-{task.id}-{repeat}-{uuid.uuid4().hex[:8]}"
            run_dir = args.runs_dir / run_id
            run_dir.mkdir(parents=True)
            ws = _unpack(task, fixtures, run_dir)
            manifest = {
                "run_id": run_id, "task_id": task.id, "fixture": task.fixture,
                "suite_hash": suite_hash(args.task_set), "repeat": repeat,
                "harness_commit": subprocess.run(
                    ["git", "-C", str(args.bench_dir), "rev-parse", "HEAD"],
                    check=True, capture_output=True, text=True,
                ).stdout.strip(),
            }
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            trace_path = ROOT / "runs/traces" / f"{datetime.now().date().isoformat()}.jsonl"
            trace_offset = trace_path.stat().st_size if trace_path.is_file() else 0
            command = [binary, "serve", "--url", f"ws://127.0.0.1:{args.port}", "--utterance", task.goal]
            started = time.monotonic()
            log_path = run_dir / "hands.log"
            trace_records = []
            try:
                with log_path.open("w", encoding="utf-8") as log:
                    process = subprocess.Popen(
                        command, cwd=ws, stdout=log, stderr=subprocess.STDOUT,
                        env={**os.environ, "NO_COLOR": "1"},
                    )
                    deadline = started + task.budget.wall_clock_s
                    while time.monotonic() < deadline:
                        trace_lines = _trace_snapshot(trace_path, trace_offset)
                        for line in trace_lines:
                            item = json.loads(line)
                            if item.get("utterance") == task.goal:
                                trace_records.append(line)
                        if trace_records:
                            break
                        if process.poll() is not None:
                            break
                        time.sleep(0.2)
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
                detail = log_path.read_text(encoding="utf-8")
                state = "completed" if trace_records and json.loads(trace_records[-1]).get("outcome") == "ok" else (
                    "failed" if trace_records else "timeout"
                )
            except OSError as exc:
                state, detail = "failed", str(exc)
                log_path.write_text(detail, encoding="utf-8")
            trace_lines = trace_records
            (run_dir / "trace.jsonl").write_text("".join(trace_lines), encoding="utf-8")
            run = {
                "run_id": run_id, "task_id": task.id, "state": state,
                "metrics": dict(NULL_METRICS), "driver_state": {},
                "elapsed_s": time.monotonic() - started,
                "grade": None, "failure": {"class": "none", "detail": "", "auto": False},
            }
            context = GradeContext(
                workspace=ws, vars=task.vars, driver_state=run["driver_state"],
                run={"state": state, "metrics": run["metrics"], "dir": str(run_dir),
                     "fixture_dir": str(fixtures / task.fixture) if task.fixture else None},
            )
            grade_result = grade(task, context, sentinel_digests=pristine_sentinels(task, fixtures))
            run["grade"] = grade_result.to_json()
            (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({"run_id": run_id, "task_id": task.id, "state": state,
                              "strict": grade_result.strict, "run_dir": str(run_dir)})
                  )
    print(f"deskmind-bench score {args.runs_dir} --suite-version diag-v25 --out {args.runs_dir}/score.json")
    print(f"deskmind-bench table {args.runs_dir}/score.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
