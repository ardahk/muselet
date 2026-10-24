import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from bench.deskmind.run_muselet import HANDS_COMMIT, SUITE_HASH, SUITE_VERSION, write_run_files


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
        hands_commit=HANDS_COMMIT, locale="zh-Hans",
    )
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["suite_version"] == SUITE_VERSION
    assert manifest["suite_hash"] == SUITE_HASH
    assert manifest["environment"] == {
        "harness_commit": "bench-fixture",
        "hands_commit": HANDS_COMMIT,
        "locale": "zh-Hans",
    }
    assert json.loads((run_dir / "run.json").read_text()) == run
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
