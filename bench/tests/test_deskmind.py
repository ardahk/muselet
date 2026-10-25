import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from bench.deskmind.run_muselet import (
    HANDS_COMMIT,
    SUITE_HASH,
    SUITE_VERSION,
    _WorkspacePageServer,
    _check_hands_commit,
    _document_apps_for_task,
    make_plan,
    write_run_files,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "bench/tests/fixtures/deskmind-v27/G07-finder-newfolder"
DESKMIND_BENCH = Path(os.environ.get(
    "DESKMIND_BENCH", "/home/ubuntu/ext/deskmind-ai__bench"
))


def test_writer_records_external_scorer_metadata(tmp_path):
    class Task:
        id = "G07-finder-newfolder"
        fixture = "diag_finder2"

    run_dir = tmp_path / Task.id
    run_dir.mkdir()
    (run_dir / "ws").mkdir()
    run = {
        "run_id": Task.id, "task_id": Task.id, "state": "completed",
        "metrics": {}, "driver_state": {}, "elapsed_s": 0.1,
        "grade": {"strict": True}, "failure": {"class": "none"},
    }
    write_run_files(
        run_dir, Task, run, ['{"t":"step","n":1,"kind":"done"}\n'],
        suite_hash=SUITE_HASH, repeat=1, harness_commit="bench-fixture",
        hands_commit=HANDS_COMMIT, deskmind_python="/venv/bin/python",
        locale="zh-Hans",
    )
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["suite_version"] == SUITE_VERSION
    assert manifest["suite_hash"] == SUITE_HASH
    assert manifest["environment"] == {
        "harness_commit": "bench-fixture",
        "hands_commit": HANDS_COMMIT,
        "deskmind_python": "/venv/bin/python",
        "locale": "zh-Hans",
    }
    run_record = json.loads((run_dir / "run.json").read_text())
    assert run_record == run
    assert run_record["environment"] == manifest["environment"]
    assert (run_dir / "trace.jsonl").read_text() == '{"t":"step","n":1,"kind":"done"}\n'


def test_committed_fixture_is_regradable_by_pinned_scorer():
    if not (DESKMIND_BENCH / "deskmind_bench/scoring.py").is_file():
        pytest.skip("external DeskMind Bench checkout is unavailable")
    sys.path.insert(0, str(DESKMIND_BENCH))
    try:
        from deskmind_bench.scoring import score
        summary = score(
            [FIXTURE], "diag", root=DESKMIND_BENCH,
            suite_version=SUITE_VERSION, label="muselet-fixture",
        )
    finally:
        sys.path.remove(str(DESKMIND_BENCH))
    assert summary["regrade"]["runs"] == 1
    assert summary["regrade"]["regraded"] == 1
    assert summary["harness_commits"] == ["bench-fixture"]


@pytest.mark.parametrize(
    ("reported_commit", "matches_pin"),
    [(HANDS_COMMIT, True), ("deadbeef", False)],
)
def test_hands_commit_check_uses_explicit_deskmind_python(
    tmp_path, reported_commit, matches_pin,
):
    interpreter = tmp_path / "python"
    interpreter.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{reported_commit}'\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)

    if matches_pin:
        assert _check_hands_commit(str(interpreter)) == HANDS_COMMIT
    else:
        with pytest.raises(RuntimeError, match=f"found {reported_commit}"):
            _check_hands_commit(str(interpreter))


def test_plan_preserves_loaded_goal_and_setup():
    task = SimpleNamespace(
        id="G03-safari-extract", goal="Safari goal, already loaded",
        fixture="diag_web", app="com.apple.Safari",
        reset_apps=["com.apple.Safari", "com.apple.TextEdit"],
        stage=['open -a TextEdit "$WS/inventory.csv"', 'open -a Safari "$WS/page.html"'],
    )
    row = make_plan([task], 1, 8765, Path("/runs/bench"))
    assert row[0]["goal"] == task.goal
    assert row[0]["hands"][-1] == task.goal
    assert row[0]["app"] == task.app
    assert row[0]["reset_apps"] == task.reset_apps
    assert row[0]["stage"] == task.stage
    assert {app.name for app in _document_apps_for_task(task)} == {"TextEdit", "Safari"}


def test_workspace_page_server_serves_only_workspace_files(tmp_path, subtests):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    page = workspace / "page.html"
    page.write_text("fixture")
    outside = tmp_path / "outside.html"
    outside.write_text("outside")
    (workspace / "leak.html").symlink_to(outside)
    server = _WorkspacePageServer(workspace)
    try:
        with urllib.request.urlopen(server.url(page), timeout=5) as response:
            assert response.read() == b"fixture"
        for path in (workspace / "leak.html", workspace / ".hidden"):
            with subtests.test(path=path.name):
                with pytest.raises(urllib.error.HTTPError):
                    urllib.request.urlopen(server.url(path), timeout=5)
    finally:
        server.close()
