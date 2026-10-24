#!/usr/bin/env python3
"""Run Muselet on DeskMind diag fixtures and write score-compatible run folders."""

from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = Path("/home/ubuntu/ext/deskmind-ai__bench")
SUITE_VERSION = "diag-v27"
SUITE_HASH = "5eec62a0c662"
HANDS_COMMIT = "89be730acdbdd50a77bb6ac44583e190c719a14a"


def make_plan(tasks, repeats, port, runs_dir):
    return [
        {
            "task_id": task.id,
            "goal": task.goal,
            "fixture": task.fixture,
            "app": task.app,
            "reset_apps": task.reset_apps,
            "stage": task.stage,
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


class _WorkspacePageServer:
    def __init__(self, workspace: Path):
        root = workspace.resolve()
        self.workspace = root

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root), **kwargs)

            def send_head(self):
                path = Path(self.translate_path(self.path)).resolve()
                if (self.headers.get("Host", "").lower() not in server.hosts
                        or root not in path.parents
                        or any(part.startswith(".") for part in path.relative_to(root).parts)
                        or not path.is_file()):
                    self.send_error(404)
                    return None
                return super().send_head()

            def list_directory(self, path):
                self.send_error(404)
                return None

            def log_message(self, *args):
                pass

        server = self
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def url(self, path: Path) -> str:
        relative = path.absolute().relative_to(self.workspace)
        self.page_url = f"http://127.0.0.1:{self.port}/{quote(relative.as_posix())}"
        return self.page_url

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def _stage_app_names(task) -> list[str]:
    return [
        match.group(1)
        for command in task.stage
        for match in re.finditer(r"open\s+(?:-g\s+)?-a\s+\"?([\w ]+?)\"?\s", command + " ")
    ]


def _app_running(process_name: str) -> bool:
    try:
        return subprocess.run(
            ["/usr/bin/pgrep", "-x", process_name],
            capture_output=True, timeout=5,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _close_app_windows(bundle: str, runs_dir: Path):
    app_name = {
        "com.apple.finder": "Finder",
        "com.apple.textedit": "TextEdit",
        "com.apple.safari": "Safari",
    }.get(bundle.lower(), bundle.rsplit(".", 1)[-1])
    if not _app_running(app_name):
        return
    if bundle.lower() == "com.apple.textedit":
        script = (
            f'tell application "TextEdit" to close (every document whose path starts with '
            f'{json.dumps(str(runs_dir.resolve()) + "/")}) saving no'
        )
        subprocess.run(["osascript", "-e", script], check=True, timeout=30, capture_output=True)
        return
    script = (
        f'tell application id {json.dumps(bundle)}\n'
        "  repeat with i from (count of windows) to 1 by -1\n"
        "    try\n"
        "      close window i\n"
        "    end try\n"
        "  end repeat\n"
        "end tell"
    )
    subprocess.run(["osascript", "-e", script], check=True, timeout=30, capture_output=True)


def _stage_task(task, workspace: Path, runs_dir: Path, page_servers: list[_WorkspacePageServer]):
    for bundle in task.reset_apps:
        _close_app_windows(bundle, runs_dir)

    stage_apps = _stage_app_names(task)
    if task.app.lower() == "com.apple.finder" or any(name.lower() == "finder" for name in stage_apps):
        script = (
            'tell application "Finder"\n'
            "  repeat with i from (count of Finder windows) to 1 by -1\n"
            "    try\n"
            "      set p to POSIX path of ((target of Finder window i) as alias)\n"
            f"      if p starts with {json.dumps(str(runs_dir.resolve()) + '/')} then close Finder window i\n"
            "    end try\n"
            "  end repeat\n"
            "end tell"
        )
        subprocess.run(["osascript", "-e", script], check=True, timeout=30, capture_output=True)

    commands = list(task.stage)
    for command in commands:
        browser = re.search(r"open\s+(?:-g\s+)?-a\s+['\"]?Safari['\"]?\s+(.+)$", command)
        if browser:
            argument = browser.group(1).strip().strip("'\"")
            path = Path(argument.replace("$WS", str(workspace)))
            if not path.is_absolute():
                path = workspace / path
            if path.is_file():
                page_server = _WorkspacePageServer(workspace)
                page_servers.append(page_server)
                command = command[:browser.start(1)] + shlex.quote(page_server.url(path))

        app_match = re.search(r"open\s+(?:-g\s+)?-a\s+['\"]?([\w ]+?)['\"]?\s", command + " ")
        app_names = {
            "com.apple.finder": "finder",
            "com.apple.textedit": "textedit",
            "com.apple.safari": "safari",
        }
        primary = app_match and app_match.group(1).strip().lower() == app_names.get(task.app.lower())
        command = re.sub(r"(^|[;&|]\s*)open\s+(?!-g)", r"\1open -g ", command) if not primary else command
        if primary:
            command = re.sub(r"(^|[;&|]\s*)open\s+(?:-g\s+)?", r"\1open ", command)
        if re.search(r"open (?:-g )?-a \"?TextEdit\"?\s", command + " ") and "--args" not in command:
            command += " --args -ApplePersistenceIgnoreState YES"
        subprocess.run(
            ["/bin/sh", "-c", command], cwd=workspace,
            env={**os.environ, "WS": str(workspace)},
            check=True, timeout=30, capture_output=True, text=True,
        )
        time.sleep(1.2)

    if not task.stage and task.app.lower() == "com.apple.finder":
        subprocess.run(["open", str(workspace)], check=True, timeout=30, capture_output=True)
    elif not task.stage:
        subprocess.run(["open", "-b", task.app], check=True, timeout=30, capture_output=True)


def _close_staged_pages(page_servers: list[_WorkspacePageServer]):
    if not page_servers:
        return
    script = "\n".join(
        f'tell application "Safari" to close (every document whose URL is {json.dumps(server.page_url)})'
        for server in page_servers if hasattr(server, "page_url")
    )
    if script and _app_running("Safari"):
        try:
            subprocess.run(["osascript", "-e", script], timeout=15, capture_output=True)
        except (OSError, subprocess.SubprocessError):
            pass


def _require_zh_hans():
    result = subprocess.run(
        ["defaults", "read", "-g", "AppleLanguages"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    if "zh-Hans" not in result.stdout:
        raise RuntimeError(f"DeskMind {SUITE_VERSION} requires macOS AppleLanguages to include zh-Hans")


def _installed_hands_commit(python: str) -> str:
    code = (
        "import importlib.metadata as m,json; "
        "d=m.distribution('deskmind-hands'); "
        "u=json.loads(d.read_text('direct_url.json') or '{}'); "
        "print(u.get('vcs_info',{}).get('commit_id',''))"
    )
    try:
        result = subprocess.run(
            [python, "-c", code], capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Cannot inspect installed deskmind-hands package: {exc}") from exc
    if result.returncode:
        raise RuntimeError(f"Cannot inspect installed deskmind-hands package: {result.stderr.strip()}")
    commit = result.stdout.strip()
    if not commit:
        raise RuntimeError("Installed deskmind-hands has no VCS commit metadata")
    return commit


def _check_hands_commit(python: str) -> str:
    commit = _installed_hands_commit(python)
    if commit != HANDS_COMMIT:
        raise RuntimeError(
            f"DeskMind Bench {SUITE_VERSION} requires deskmind-hands {HANDS_COMMIT}; "
            f"found {commit}"
        )
    return commit


def write_run_files(
    run_dir: Path, task, run: dict, trace_lines: list[str], *,
    suite_hash: str, repeat: int, harness_commit: str, hands_commit: str,
    deskmind_python: str, locale: str,
) -> None:
    environment = {
        "harness_commit": harness_commit,
        "hands_commit": hands_commit,
        "deskmind_python": deskmind_python,
        "locale": locale,
    }
    run["environment"] = environment
    manifest = {
        "run_id": run["run_id"], "task_id": task.id, "fixture": task.fixture,
        "suite": "diag", "suite_version": SUITE_VERSION, "suite_hash": suite_hash,
        "repeat": repeat,
        "environment": environment,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "trace.jsonl").write_text("".join(trace_lines), encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-dir", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--task-set", default="diag")
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--hands-command", default="hands")
    parser.add_argument(
        "--deskmind-python",
        help="Python from the venv containing the pinned DeskMind Hands/Bench packages",
    )
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
    installed_suite_hash = suite_hash(args.task_set)
    if args.task_set != "diag" or installed_suite_hash != SUITE_HASH:
        parser.error(
            f"expected diag-v27 suite hash {SUITE_HASH}, found "
            f"{args.task_set} {installed_suite_hash}"
        )
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
                          "suite_version": SUITE_VERSION,
                          "hands_commit": HANDS_COMMIT,
                          "score": f"deskmind-bench score {args.runs_dir} --suite-version {SUITE_VERSION} --out {args.runs_dir}/score.json",
                          "table": f"deskmind-bench table {args.runs_dir}/score.json"}, ensure_ascii=False, indent=2))
        return 0
    if not args.deskmind_python:
        parser.error("--deskmind-python is required for live runs")
    if sys.platform != "darwin":
        parser.error("live DeskMind Bench replay requires macOS, Accessibility permissions, and a running brain server")
    _require_zh_hans()
    binary = shutil.which(args.hands_command) or args.hands_command
    deskmind_python = shutil.which(args.deskmind_python)
    if not deskmind_python:
        parser.error(f"DeskMind Python not found: {args.deskmind_python}")
    deskmind_python = os.path.abspath(deskmind_python)
    try:
        installed_commit = _check_hands_commit(deskmind_python)
    except RuntimeError as exc:
        parser.error(str(exc))
    fixtures = args.bench_dir / "fixtures"
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        for repeat in range(1, args.repeats + 1):
            run_id = f"muselet-{task.id}-{repeat}-{uuid.uuid4().hex[:8]}"
            run_dir = args.runs_dir / run_id
            run_dir.mkdir(parents=True)
            ws = _unpack(task, fixtures, run_dir)
            harness_commit = subprocess.run(
                ["git", "-C", str(args.bench_dir), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            trace_path = ROOT / "runs/traces" / f"{datetime.now().date().isoformat()}.jsonl"
            trace_offset = trace_path.stat().st_size if trace_path.is_file() else 0
            command = [binary, "serve", "--url", f"ws://127.0.0.1:{args.port}", "--utterance", task.goal]
            started = time.monotonic()
            log_path = run_dir / "hands.log"
            trace_records = []
            page_servers = []
            try:
                _stage_task(task, ws, args.runs_dir, page_servers)
                trace_offset = trace_path.stat().st_size if trace_path.is_file() else 0
                started = time.monotonic()
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
            except (OSError, subprocess.SubprocessError) as exc:
                state, detail = "failed", str(exc)
                log_path.write_text(detail, encoding="utf-8")
            finally:
                _close_staged_pages(page_servers)
                for page_server in page_servers:
                    page_server.close()
            trace_lines = trace_records
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
            write_run_files(
                run_dir, task, run, trace_lines,
                suite_hash=suite_hash(args.task_set), repeat=repeat,
                harness_commit=harness_commit, hands_commit=installed_commit,
                deskmind_python=deskmind_python, locale="zh-Hans",
            )
            print(json.dumps({"run_id": run_id, "task_id": task.id, "state": state,
                              "strict": grade_result.strict, "run_dir": str(run_dir)})
                  )
    print(f"deskmind-bench score {args.runs_dir} --suite-version {SUITE_VERSION} --out {args.runs_dir}/score.json")
    print(f"deskmind-bench table {args.runs_dir}/score.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
