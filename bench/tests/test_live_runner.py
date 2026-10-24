import argparse
import asyncio
import json
import shlex
from pathlib import Path

import bench.live.run_live as live
from bench.live.run_live import (
    ROOT as REPO_ROOT,
    _dry_run,
    _filter_reasons,
    _fixture_plan_guard,
    _load_suite,
    _shell_rooted_case,
)


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "evals/live_t1.jsonl"


def _args(**overrides):
    values = {
        "suite": SUITE,
        "tier": set(),
        "category": set(),
        "id": set(),
        "include_manual": False,
        "include_pending": False,
        "run_pending": False,
        "allow_user_ok": False,
        "offline": False,
        "repeat": 2,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_dry_run_includes_all_live_cases_and_tier_counts(capsys):
    cases = _load_suite(SUITE)
    assert len(cases) == 43
    assert _dry_run(cases, _args()) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["tier_counts"] == {"T1": 33, "T2": 10}
    assert plan["cases_by_repeat"] == 86
    assert len(plan["case_plan"]) == 43
    assert all("{{" not in json.dumps(row["resolved"]) for row in plan["case_plan"])
    assert all("document_apps" in row for row in plan["case_plan"])
    assert any(row["document_apps"] for row in plan["case_plan"])
    assert all(
        row["step_order"][0] == "session: hands probe session (skip if locked/asleep)"
        for row in plan["case_plan"]
    )


def test_filters_report_manual_pending_online_and_user_consent_skips():
    cases = _load_suite(SUITE)
    args = _args()
    manual = next(case for case in cases if case.get("manual"))
    pending = next(case for case in cases if case.get("pending"))
    online = next(case for case in cases if case.get("online"))
    requires_ok = next(case for case in cases if case.get("requires_user_ok"))
    assert "manual" in _filter_reasons(manual, args)[0]
    assert "pending" in _filter_reasons(pending, args)[0]
    assert "--include-pending" in _filter_reasons(pending, args)[0]
    assert "--run-pending" in _filter_reasons(pending, args)[0]
    assert any("consent" in reason for reason in _filter_reasons(requires_ok, args))
    assert "manual" not in _filter_reasons(manual, _args(include_manual=True))
    assert "pending" not in _filter_reasons(pending, _args(include_pending=True))
    assert "pending" not in _filter_reasons(pending, _args(run_pending=True))
    assert "consent" not in " ".join(
        _filter_reasons(requires_ok, _args(include_pending=True))
    )
    assert "online" in _filter_reasons(online, _args(offline=True))[0]
    assert not _filter_reasons(
        requires_ok, _args(include_pending=True, allow_user_ok=True)
    )


def test_pending_demo_cases_are_runnable_only_with_the_opt_ins(capsys):
    cases = _load_suite(SUITE)
    assert _dry_run(cases, _args(tier={"T2"}, run_pending=True, allow_user_ok=True)) == 0
    plan = json.loads(capsys.readouterr().out)
    rows = {row["id"]: row for row in plan["case_plan"]}
    assert rows["t2-finance-dupes"]["filter"] == "run"
    assert rows["t2-advisor-prep"]["filter"] == "run"
    assert _dry_run(cases, _args(tier={"T2"}, run_pending=True)) == 0
    plan = json.loads(capsys.readouterr().out)
    rows = {row["id"]: row for row in plan["case_plan"]}
    assert rows["t2-finance-dupes"]["filter"] == "run"
    assert "consent" in rows["t2-advisor-prep"]["skip_reason"]
    assert _dry_run(cases, _args(tier={"T2"}, include_pending=True)) == 0
    plan = json.loads(capsys.readouterr().out)
    rows = {row["id"]: row for row in plan["case_plan"]}
    for case_id in ("t2-finance-dupes", "t2-advisor-prep"):
        assert rows[case_id]["filter"] == "report"
        assert rows[case_id]["skip_reason"] == (
            "pending (use --run-pending to execute)"
        )
        assert rows[case_id]["step_order"] == [
            "report only: no session probe, setup, or utterance",
        ]


def test_tier_category_and_id_filters_are_combined():
    case = {"id": "a", "tier": "T1", "category": "system"}
    assert not _filter_reasons(case, _args(tier={"T1"}, category={"system"}, id={"a"}))
    assert "tier filter" in _filter_reasons(case, _args(tier={"T2"}))
    assert "category filter" in _filter_reasons(case, _args(category={"apps"}))
    assert "id filter" in _filter_reasons(case, _args(id={"b"}))


def test_fixture_shell_commands_are_rooted_and_overwrite_plans_skip():
    case = {
        "setup": [{"shell": "bash evals/fixtures/finance/setup_mac.sh --apply"}],
        "teardown": [{"shell": "bash evals/fixtures/finance/setup_mac.sh teardown"}],
    }
    rooted = _shell_rooted_case(case)
    assert rooted["setup"][0]["shell"].startswith(f"cd {REPO_ROOT} && ")
    assert rooted["teardown"][0]["shell"].startswith(f"cd {REPO_ROOT} && ")
    assert case["setup"][0]["shell"].startswith("bash ")

    class Runtime:
        async def run_script(self, lang, code):
            assert lang == "shell"
            assert "--dry-run" in code
            assert "--apply" not in code
            return {"ok": True, "output": "budget (differs: overwrite)"}

    guard = _fixture_plan_guard(rooted)
    result = asyncio.run(guard(Runtime(), {}))
    assert result["skip_reason"] == "fixture_would_overwrite"


def test_run_live_roots_shell_steps_once_for_normal_and_event_cases(
    tmp_path, monkeypatch
):
    from bench.hobbylm import calendar_safety

    class Proxy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def begin_case(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(live, "BenchProxy", lambda *_args, **_kwargs: Proxy())
    monkeypatch.setattr(live, "serve_timeout_supported", lambda _hands_bin: False)
    monkeypatch.setattr(live, "probe_session", lambda _hands_bin: {
        "skip_reason": None, "session_probe": {"screen_locked": False},
    })
    monkeypatch.setattr(live, "HandsRuntime", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    async def released(_proxy):
        return True

    monkeypatch.setattr(live, "release_slot_for_case", released)
    monkeypatch.setattr(calendar_safety, "is_local_default", lambda _probe: True)
    monkeypatch.setattr(calendar_safety, "probe_bench_calendar", lambda: {})
    monkeypatch.setattr(calendar_safety, "snapshot_bench_events", lambda: [])
    monkeypatch.setattr(calendar_safety, "delete_bench_events", lambda _ids: None)
    captured = {}

    async def record_run_case(case, _runtime, **_kwargs):
        captured[case["id"]] = case
        return {"id": case["id"], "status": "passed", "strict_pass": True}

    monkeypatch.setattr(live, "run_case", record_run_case)
    args = argparse.Namespace(
        out=tmp_path / "rooted-run",
        suite=SUITE,
        tier=set(),
        category=set(),
        id=set(),
        repeat=1,
        brain_url="ws://127.0.0.1:8765",
        proxy_port=8790,
        hands_bin="hands",
        no_safety_guard=False,
        setup_bench_calendar=False,
        include_manual=False,
        include_pending=False,
        run_pending=False,
        allow_user_ok=False,
        offline=False,
    )
    cases = [
        {
            "id": "normal-rooting", "category": "apps", "utterance": "normal",
            "setup": [{"shell": "bash normal-setup.sh"}],
            "teardown": [{"shell": "bash normal-teardown.sh"}],
        },
        {
            "id": "event-rooting", "category": "event", "utterance": "event",
            "setup": [{"shell": "bash event-setup.sh"}],
            "teardown": [{"shell": "bash event-teardown.sh"}],
        },
    ]

    assert asyncio.run(live._run_live(cases, args)) == 0
    prefix = f"cd {shlex.quote(str(REPO_ROOT))} && "
    normal = captured["normal-rooting"]
    event = captured["event-rooting"]
    for key in ("setup", "teardown"):
        for step in normal[key]:
            assert step["shell"].startswith(prefix)
            assert step["shell"].count(prefix) == 1
    for step in event["setup"]:
        assert step["shell"].startswith(prefix)
        assert step["shell"].count(prefix) == 1
    assert event["teardown"] == []


def test_include_pending_reports_without_session_probe_or_actions(
    tmp_path, monkeypatch
):
    class Proxy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr(live, "BenchProxy", lambda *_args, **_kwargs: Proxy())
    monkeypatch.setattr(live, "serve_timeout_supported", lambda _hands_bin: False)
    monkeypatch.setattr(
        live, "probe_session",
        lambda _hands_bin: (_ for _ in ()).throw(AssertionError("session probe called")),
    )

    async def unexpected_release(_proxy):
        raise AssertionError("slot release attempted")

    monkeypatch.setattr(live, "release_slot_for_case", unexpected_release)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    output_dir = tmp_path / "pending-report"
    args = argparse.Namespace(
        out=output_dir,
        suite=SUITE,
        tier=set(),
        category=set(),
        id=set(),
        repeat=1,
        brain_url="ws://127.0.0.1:8765",
        proxy_port=8790,
        hands_bin="hands",
        no_safety_guard=False,
        setup_bench_calendar=False,
        include_manual=False,
        include_pending=True,
        run_pending=False,
        allow_user_ok=False,
        offline=False,
    )
    cases = [
        case for case in _load_suite(SUITE)
        if case["id"] in {"t2-finance-dupes", "t2-advisor-prep"}
    ]

    assert asyncio.run(live._run_live(cases, args)) == 0
    records = [
        json.loads(line)
        for line in (output_dir / "results.jsonl").read_text().splitlines()
    ]
    summary = json.loads((output_dir / "summary.json").read_text())
    assert [record["status"] for record in records] == ["skipped", "skipped"]
    assert all(
        record["skip_reason"] == "pending (use --run-pending to execute)"
        for record in records
    )
    assert all(record["pending"] for record in records)
    assert {
        record["id"] for record in summary["pending_cases"]
    } == {"t2-finance-dupes", "t2-advisor-prep"}


def test_run_pending_dispatches_to_run_case(tmp_path, monkeypatch):
    class Proxy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def begin_case(self, *_args, **_kwargs):
            self.begun = True

    proxy = Proxy()
    monkeypatch.setattr(live, "BenchProxy", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(live, "serve_timeout_supported", lambda _hands_bin: False)
    monkeypatch.setattr(live, "probe_session", lambda _hands_bin: {
        "skip_reason": None, "session_probe": {"screen_locked": False},
    })
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    async def released(_proxy):
        return True

    monkeypatch.setattr(live, "release_slot_for_case", released)
    monkeypatch.setattr(live, "HandsRuntime", lambda *_args, **_kwargs: object())
    run_calls = []

    async def record_run_case(case, runtime, **_kwargs):
        run_calls.append((case, runtime))
        return {"id": case["id"], "status": "passed", "strict_pass": True}

    monkeypatch.setattr(live, "run_case", record_run_case)
    output_dir = tmp_path / "pending-run"
    args = argparse.Namespace(
        out=output_dir,
        suite=SUITE,
        tier=set(),
        category=set(),
        id=set(),
        repeat=1,
        brain_url="ws://127.0.0.1:8765",
        proxy_port=8790,
        hands_bin="hands",
        no_safety_guard=False,
        setup_bench_calendar=False,
        include_manual=False,
        include_pending=False,
        run_pending=True,
        allow_user_ok=True,
        offline=False,
    )
    case = {
        "id": "pending-run", "tier": "T2", "category": "finance",
        "pending": True, "requires_user_ok": True, "utterance": "run it",
        "setup": [{"shell": "setup"}],
    }

    assert asyncio.run(live._run_live([case], args)) == 0
    assert proxy.begun is True
    assert len(run_calls) == 1
    setup_shell = run_calls[0][0]["setup"][0]["shell"]
    assert setup_shell.startswith(f"cd {REPO_ROOT} && ")
    assert setup_shell.count(f"cd {REPO_ROOT} && ") == 1
    assert callable(run_calls[0][0]["pre_setup_guard"])
    record = json.loads(
        (output_dir / "results.jsonl").read_text().splitlines()[0]
    )
    assert record["status"] == "passed"
    assert record["pending"] is True


def test_unreleased_slot_records_each_case_and_writes_results(tmp_path, monkeypatch):
    class Proxy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr(live, "BenchProxy", lambda *_args, **_kwargs: Proxy())
    monkeypatch.setattr(live, "serve_timeout_supported", lambda _hands_bin: False)
    monkeypatch.setattr(live, "probe_session", lambda _hands_bin: {
        "skip_reason": None, "session_probe": {"screen_locked": False},
    })

    async def held_slot(_proxy):
        return False

    monkeypatch.setattr(live, "release_slot_for_case", held_slot)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    output_dir = tmp_path / "output"
    args = argparse.Namespace(
        out=output_dir,
        suite=SUITE,
        tier=set(),
        category=set(),
        id=set(),
        repeat=1,
        brain_url="ws://127.0.0.1:8765",
        proxy_port=8790,
        hands_bin="hands",
        no_safety_guard=False,
        setup_bench_calendar=False,
        include_manual=False,
        include_pending=False,
        run_pending=True,
        allow_user_ok=True,
        offline=False,
    )
    cases = [
        {
            "id": f"pending-{index}", "tier": "T2", "category": "finance",
            "pending": True, "utterance": "do not run",
            "setup": [{"shell": "must-not-run"}],
        }
        for index in (1, 2)
    ]

    assert asyncio.run(live._run_live(cases, args)) == 0
    results = [
        json.loads(line)
        for line in (output_dir / "results.jsonl").read_text().splitlines()
    ]
    summary = json.loads((output_dir / "summary.json").read_text())
    assert len(results) == 2
    assert all(row["status"] == "harness_timeout" for row in results)
    assert all(row["harness_timeout"]["stage"] == "between_cases" for row in results)
    assert summary["harness_timeouts"] == {
        "count": 2, "ids": ["pending-1", "pending-2"],
    }

    async def failed_slot(_proxy):
        raise RuntimeError("release failed")

    monkeypatch.setattr(live, "release_slot_for_case", failed_slot)
    args.out = tmp_path / "failed-output"
    assert asyncio.run(live._run_live(cases, args)) == 0
    failures = [
        json.loads(line)
        for line in (args.out / "results.jsonl").read_text().splitlines()
    ]
    assert len(failures) == 2
    assert all(row["status"] == "failed" for row in failures)
    assert all(row["error"] == "release failed" for row in failures)
    assert (args.out / "summary.json").is_file()
