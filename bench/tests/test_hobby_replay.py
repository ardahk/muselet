import ast
import asyncio
import csv
import json
import shutil
import subprocess
import sys
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from bench.harness import proxy as proxy_module
from bench.hobbylm import replay
from bench.hobbylm.calendar_safety import BENCH_CALENDAR
from bench.hobbylm.coverage import build
from bench.hobbylm.hobby_worker import SafetyBlocked, _guard_native_helpers, run_task
from bench.hobbylm.upstream.hobby import calendar_tool
from bench.hobbylm.vendor import verify_provenance


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "bench/hobbylm/upstream"
R4_FIXTURE = Path(__file__).with_name("hobbylm_r4_expected.tsv")


def _frames(seconds=600, ok=True, duration="10 minutes", timer_id="timer-1", ident="1"):
    result = {"ok": ok, "result": {"timer_id": timer_id}}
    if seconds is not None:
        result["result"]["seconds"] = seconds
    return [
        {"direction": "brain_to_hands", "frame": {
            "t": "rpc", "id": ident, "method": "skill",
            "params": {"name": "start_timer", "args": {"duration": duration}},
        }},
        {"direction": "hands_to_brain", "frame": {
            "t": "rpc_result", "id": ident, **result,
        }},
    ]


def test_timer_grading_uses_rpc_snapshots_and_excludes_preexisting_ids(monkeypatch):
    success = replay._timer_start_results(_frames())
    assert [item["minutes"] for item in success] == [10]
    assert success[0]["seconds"] == 600
    assert success[0]["timer_id"] == "timer-1"
    assert replay._timer_start_results(_frames(ok=False)) == []
    try:
        from brain.decision import parse_duration
    except ImportError as error:
        assert "libmlx.so" in str(error)
        decision = ModuleType("brain.decision")
        decision.parse_duration = lambda duration: (
            90 if duration == "90 seconds" else None)
    else:
        decision = ModuleType("brain.decision")
        decision.parse_duration = parse_duration
    monkeypatch.setitem(sys.modules, "brain.decision", decision)
    fallback = replay._timer_start_results(
        _frames(seconds=None, duration="90 seconds"))
    assert fallback[0]["seconds"] == 90
    assert fallback[0]["minutes"] == 2
    frames = _frames(600, timer_id="first", ident="1") + _frames(
        120, timer_id="second", ident="2")
    assert [item["timer_id"] for item in replay._timer_start_results(frames)] == [
        "first", "second",
    ]


def test_timer_rpc_baseline_grades_only_new_timers_and_orders_by_fires_at():
    runtime = object.__new__(replay._HobbyRuntime)
    runtime.proxy = SimpleNamespace(capture=SimpleNamespace(frames=[]))
    runtime.timer_start_calls = []
    runtime.timer_calls = []
    runtime.timer_grading = None
    runtime.timer_preexisting_ids = set()
    runtime.timer_rpc_available = None
    runtime.timer_after_snapshot = False
    runtime.started_timer_ids = []
    replies = iter([
        {"timers": [{"id": "old", "minutes": 3}]},
        {"timers": [
            {"id": "later", "minutes": 12, "total_s": 720, "fires_at": "b"},
            {"id": "old", "minutes": 3, "fires_at": "a"},
            {"id": "new", "minutes": 10, "total_s": 600, "fires_at": "a"},
        ]},
    ])

    async def run_rpc(method, params):
        assert method == "timers" and params == {}
        return next(replies)

    runtime.run_rpc = run_rpc
    async def scenario():
        await runtime.capture_timer_baseline()
        await runtime.capture_timer_after_case()
    asyncio.run(scenario())
    assert runtime.timer_grading == "hands_timers_rpc"
    assert [item["minutes"] for item in runtime.timer_calls] == [10, 12]
    assert runtime.started_timer_ids == ["new", "later"]


def test_timer_rpc_absence_falls_back_and_cancels_only_started_ids():
    runtime = object.__new__(replay._HobbyRuntime)
    runtime.proxy = SimpleNamespace(capture=SimpleNamespace(frames=_frames()))
    runtime.timer_start_calls = []
    runtime.timer_calls = []
    runtime.timer_grading = None
    runtime.timer_preexisting_ids = set()
    runtime.timer_rpc_available = None
    runtime.timer_after_snapshot = False
    runtime.started_timer_ids = []
    requests = []

    async def missing(method, params):
        raise RuntimeError("unknown method: timers")
    runtime.run_rpc = missing
    async def scenario():
        await runtime.capture_timer_baseline()
        await runtime.capture_timer_after_case()
    asyncio.run(scenario())
    assert runtime.timer_grading == "proxied_start_timer_ok_results"
    assert [item["minutes"] for item in runtime.timer_calls] == [10]

    runtime.started_timer_ids = ["timer-1", "timer-2"]
    async def cancel(method, params):
        requests.append((method, params))
        if params["id"] == "timer-2":
            raise RuntimeError("unknown_timer: timer-2")
        return {"cancelled": [params["id"]]}
    runtime.run_rpc = cancel
    result = asyncio.run(replay._timer_teardown(runtime, {}))
    assert requests == [
        ("timers_cancel", {"id": "timer-1"}),
        ("timers_cancel", {"id": "timer-2"}),
    ]
    assert result["cancelled_ids"] == ["timer-1"]
    assert result["errors"] == [{"id": "timer-2", "error": "unknown_timer: timer-2"}]


def test_calculator_setup_precedes_utterance_and_fails_closed():
    class Runtime:
        def __init__(self):
            self.calls = []
        async def start_scripts(self):
            self.calls.append("start")
        async def run_script(self, lang, code):
            self.calls.append((lang, code))
            return {"output": "ok"}
        async def start_utterance(self, text):
            self.calls.append(("utterance", text))

    class Helper:
        def __init__(self, display="0"):
            self.current_display = display
        def sh(self, *args):
            return "Calculator"
        def display(self):
            return self.current_display

    async def scenario():
        runtime = Runtime()
        assert await replay._prepare_calculator(runtime, Helper())
        await runtime.start_utterance("11 plus 4")
        assert runtime.calls[0] == "start"
        assert 'tell application "Calculator" to activate' in runtime.calls[1][1]
        assert "key code 53" in runtime.calls[2][1]
        assert runtime.calls[-1] == ("utterance", "11 plus 4")

        failed = Runtime()
        skip = await replay._calculator_case_setup(
            failed, Helper("7"), timeout_s=0.001)
        assert skip["skip_reason"] == "calc_setup_failed"
        assert skip["status"] == "skipped"
        assert not any(isinstance(call, tuple) and call[0] == "utterance"
                       for call in failed.calls)

    asyncio.run(scenario())


def test_calc_setup_is_disclosed_in_dry_plan_and_run_metadata():
    tasks = [{"id": "C01", "kind": "calc", "text": "11 plus 4"}]
    plan = replay.plan("muselet", "r4", tasks, 1, 8765)
    assert plan[0]["calc_setup"] == "calculator_open_cleared"
    assert plan[0]["session"] == "session: hands probe session (skip if locked/asleep)"
    assert replay._run_metadata(tasks) == {"calc_setup": "calculator_open_cleared"}
    assert replay._run_metadata([{"kind": "timer"}]) == {
        "timer_grading": "hands_timers_rpc",
    }


def test_skip_record_preserves_setup_reason_over_session_none():
    session = {"skip_reason": None, "session_probe": {"screen_locked": False}}
    setup_skip = {
        "status": "skipped", "strict_pass": False,
        "skip_reason": "calc_setup_failed",
        "calc_setup": "calculator_open_cleared",
    }
    rec = replay._skip_record(
        {"id": "C01", "kind": "calc"}, 1, session, setup_skip)
    assert rec["skip_reason"] == "calc_setup_failed"
    assert rec["session_probe"] == {"screen_locked": False}
    excluded = replay._skip_record(
        {"id": "C01", "kind": "calc"}, 1, session,
        {"skip_reason": replay._exclude_reason("calc")})
    assert excluded["skip_reason"] == "harness_calc_checker_ax_blind"


def test_excluded_kinds_parses_commas_and_alias():
    assert replay._excluded_kinds("") == set()
    assert replay._excluded_kinds("calculator") == {"calc"}
    assert replay._excluded_kinds("calc, event") == {"calc", "event"}
    assert replay._exclude_reason("event") == "excluded_kind:event"


def _args(tmp_path):
    hobby = tmp_path / "upstream" / "hobby"
    hobby.mkdir(parents=True)
    (hobby / "hobbymac_run.py").write_text(
        "from pathlib import Path\n"
        "ROOT = Path('.')\nWORK = ROOT / 'data'\nTEST_CAL = 'x'\n"
        "def snapshot():\n"
        "    return {'work_is_path': isinstance(WORK, Path),\n"
        "            'tool': str(WORK / 'brightness')}\n"
        "def running(app):\n    return False\n"
    )
    return SimpleNamespace(hobby_root=tmp_path / "upstream", hobby_dir=hobby,
                           work_dir=tmp_path / "tools")


def test_state_script_sets_work_as_a_path(tmp_path):
    args = _args(tmp_path)
    out = subprocess.run(replay._hobby_state_script(args, "dark"), shell=True,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert '"work_is_path": true' in out.stdout
    assert str(tmp_path / "tools" / "brightness") in out.stdout


def test_restore_script_sets_root_and_work_as_paths(tmp_path):
    script = replay._hobby_restore_script(_args(tmp_path), {}, {}, {})
    assert "helper.ROOT = Path(" in script and "helper.WORK = Path(" in script
    assert "from pathlib import Path" in script


class GradeHelper:
    @staticmethod
    def unused():
        return None


def test_worker_strict_grade_uses_parent_snapshot_not_upstream_completion(monkeypatch):
    monkeypatch.setattr(
        replay, "_grade_final_state",
        lambda *_args, **_kwargs: (True, {"front": "Calculator"}),
    )
    result = replay._worker_snapshot_grade(
        GradeHelper(),
        {"kind": "app", "expected": "OPEN Calculator", "text": "open calculator"},
        {},
        {"front": "Calculator"},
        first_action=True,
    )
    assert result["passed"] is True
    assert "upstream_completed" not in result


def test_worker_grade_marks_missing_required_snapshot_ungradable():
    result = replay._worker_snapshot_grade(
        GradeHelper(),
        {"kind": "none", "expected": "NONE", "text": "do nothing"},
        {"bright": 50},
        {"bright": 50},
    )
    assert result["passed"] is False
    assert result["ungradable"] is True
    assert "calendar_events" in result["missing_snapshots"]


def test_held_slot_marks_every_replay_case_and_writes_results(tmp_path, monkeypatch):
    class Proxy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr(
        proxy_module, "BenchProxy", lambda *_args, **_kwargs: Proxy()
    )

    async def held_slot(_proxy):
        return False

    monkeypatch.setattr(replay, "release_slot_for_case", held_slot)
    monkeypatch.setattr(replay, "probe_session", lambda _hands_bin: {
        "skip_reason": None,
    })
    monkeypatch.setattr(replay, "_run_metadata", lambda _tasks: {})
    monkeypatch.setattr(replay, "serve_timeout_supported", lambda _hands_bin: False)
    args = Namespace(
        repeats=1,
        port=8765,
        proxy_port=8790,
        round="r4",
        hands_bin="hands",
        hobby_tools_dir=tmp_path / "tools",
        hobby_helper_source="vendored",
    )
    tasks = [
        {"id": f"case-{index}", "kind": "system", "text": "noop", "expected": "noop"}
        for index in (1, 2)
    ]
    run_root = tmp_path / "replay"

    assert asyncio.run(replay._run_muselet_cases(
        args, tasks, run_root, helper=None,
    )) == 0
    payload = json.loads((run_root / "results.json").read_text())
    assert [row["status"] for row in payload["results"]] == [
        "harness_timeout", "harness_timeout",
    ]
    assert all(
        row["harness_timeout"] == {
            "stage": "between_cases", "slot_released": False,
        }
        for row in payload["results"]
    )
    assert payload["summary"]["harness_timeouts"] == {
        "count": 2, "ids": ["case-1", "case-2"],
    }


def _vendored_tree(tmp_path):
    upstream = tmp_path / "upstream"
    hobby = upstream / "hobby"
    hobby.mkdir(parents=True)
    (hobby / "hobbymac_run.py").write_text("ROOT = None\nWORK = None\nTEST_CAL = None\n")
    for tool in replay.MUSELET_HELPER_TOOLS:
        (hobby / f"{tool}.swift").write_text(f"// {tool}\n")
    return upstream, hobby


def test_vendored_helper_compiles_once_and_reuses_source_hash_cache(
    monkeypatch, tmp_path
):
    upstream, hobby = _vendored_tree(tmp_path)
    monkeypatch.setattr(replay, "VENDORED_UPSTREAM", upstream)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    monkeypatch.delenv("HOBBY_HOME", raising=False)
    monkeypatch.setitem(sys.modules, "hobbymac_run", ModuleType("hobbymac_run"))
    calls = []

    def fake_compile(command, **kwargs):
        calls.append((command, kwargs))
        cache = tmp_path / "runs/bench/hobbylm/tools"
        for path in cache.glob("*"):
            for tool in replay.MUSELET_HELPER_TOOLS:
                (path / tool).write_text("binary")
        return subprocess.CompletedProcess(command, 0, "", "")

    args = Namespace(hobby_home=None)
    first = replay.resolve_muselet_helper(args, compile=fake_compile)
    second = replay.resolve_muselet_helper(args, compile=fake_compile)

    assert first[0] is second[0]
    assert first[1] == hobby
    assert first[2] == args.work_dir
    assert args.hobby_helper_source == "vendored"
    assert len(calls) == 1
    assert first[0].ROOT == upstream
    assert first[0].WORK == first[2]
    assert first[0].TEST_CAL == BENCH_CALENDAR


def test_vendored_helper_reports_missing_swift_compiler(monkeypatch, tmp_path):
    upstream, _hobby = _vendored_tree(tmp_path)
    monkeypatch.setattr(replay, "VENDORED_UPSTREAM", upstream)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    monkeypatch.delenv("HOBBY_HOME", raising=False)

    def missing_compiler(*_args, **_kwargs):
        raise FileNotFoundError("swiftc")

    with pytest.raises(RuntimeError, match=r"pass --hobby-home.*xcode-select --install"):
        replay.resolve_muselet_helper(
            Namespace(hobby_home=None), compile=missing_compiler
        )


def test_invalid_explicit_home_names_missing_helper_path(tmp_path):
    home = tmp_path / "bad-home"
    with pytest.raises(RuntimeError, match="hobbymac_run.py"):
        replay.resolve_muselet_helper(Namespace(hobby_home=home))


def test_vendored_helper_has_no_module_level_mlx_or_torch_imports():
    helper = replay.VENDORED_UPSTREAM / "hobby/hobbymac_run.py"
    tree = ast.parse(helper.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".", 1)[0]]
        else:
            continue
        assert not {"mlx", "torch"} & set(names)


def r4_tasks():
    with R4_FIXTURE.open(encoding="utf-8") as source:
        return {
            row["kind"]: {
                "id": row["id"], "kind": row["kind"],
                "text": row["text"], "expected": row["expected"],
            }
            for row in csv.DictReader(source, delimiter="\t", fieldnames=("id", "kind", "text", "expected"))
        }


class MockGraderHelper:
    CAL = calendar_tool
    LOCAL_TZ = "Asia/Kolkata"

    @staticmethod
    def as_num(value):
        try:
            return float((value or "").replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def finder_path():
        return ""


def test_plan_expands_repeats_and_keeps_port():
    tasks = [{"id": "C01", "kind": "calc", "text": "two plus two"}]
    rows = replay.plan("muselet", "r4", tasks, 2, 8877)
    assert len(rows) == 2
    assert [row["repeat"] for row in rows] == [1, 2]
    assert {row["port"] for row in rows} == {8877}
    assert {row["text"] for row in rows} == {"two plus two"}
    input_row = replay.plan(
        "muselet", "r4",
        [{"id": "I01", "kind": "input", "text": "type a short phrase"}],
        1, 8877,
    )[0]
    assert "Numbers" in input_row["document_apps"]


def test_report_math_reports_pass_k_false_done_and_latency():
    rows = [
        {"id": "C01", "kind": "calc", "pass": True, "completed": True,
         "pass_final_state": True, "false_done": False,
         "utterance_latency_s": 2.0, "first_action_latency_s": 0.4, "completion_latency_s": 1.8},
        {"id": "C01", "kind": "calc", "pass": False, "completed": False,
         "pass_final_state": False, "false_done": True,
         "utterance_latency_s": 3.0, "first_action_latency_s": 0.8, "completion_latency_s": None},
    ]
    result = replay.report_math(rows, 2)
    assert result["n"] == 2
    assert result["pass_rate"] == 0.5
    assert result["completed_rate"] == 0.5
    assert result["pass_final_state_rate"] == 0.5
    assert result["pass_k_by_kind"]["calc"] == 0.0
    assert result["completed_k_by_kind"]["calc"] == 0.0
    assert result["false_done"] == 1
    assert result["utterance_latency_s"]["p50"] == 2.5
    assert result["first_action_latency_s"]["p95"] == 0.78


def test_grades_real_r4_expected_strings_for_every_kind(subtests):
    tasks = r4_tasks()
    assert set(tasks) == {"calc", "device", "dark", "app", "folder", "timer", "screenshot", "none", "event"}
    if (replay.DEFAULT_HOME / "data/frozen/hobbymac-sealed-test-r4.tsv").is_file():
        source_tasks = {
            task["id"]: task for task in replay.load_tasks(replay.DEFAULT_HOME, "r4")
        }
        for task in tasks.values():
            assert task["expected"] == source_tasks[task["id"]]["expected"]

    helper = MockGraderHelper()
    test_now = datetime(2025, 1, 6, 9, tzinfo=ZoneInfo(helper.LOCAL_TZ))
    for kind, record in tasks.items():
        start = {
            "bright": 0.5, "vol": (50, False), "dark": False, "front": "Finder",
            "finder_windows": 1, "running": {"Finder": True, "Notes": False},
            "screenshot_files": ["/tmp/existing.png"],
            "calendar_now": test_now.isoformat(),
            "calendar_events": [{"identifier": "existing"}],
        }
        current = dict(start)
        current["calendar_events"] = list(start["calendar_events"])
        if kind == "calc":
            current["display"] = "129"
        elif kind == "device":
            current["bright"] = 0.3
        elif kind == "dark":
            current["dark"] = True
        elif kind == "app":
            current["front"] = "Notes"
        elif kind == "folder":
            current["finder_path"] = "/Users/test/Downloads"
        elif kind == "timer":
            current["timers"] = [18]
        elif kind == "screenshot":
            current["screenshot_files"] = start["screenshot_files"] + ["/tmp/new.png"]
        elif kind == "event":
            expected = record["expected"].removeprefix("EVENT ").strip()
            plan = helper.CAL.plan_event(expected, test_now, helper.LOCAL_TZ, lookup=lambda _name: [])
            current["calendar_events"] = start["calendar_events"] + [{
                "identifier": "new-event", "title": plan.title,
                "start": plan.start.isoformat(), "notes": "", "attendees": [],
            }]
        elif kind == "none":
            current["screenshot_files"] = list(start["screenshot_files"])

        with subtests.test(kind=kind, outcome="pass"):
            passed, _ = replay._grade_final_state(helper, record, start, current)
            assert passed

        failed = dict(current)
        if kind == "calc":
            failed["display"] = "0"
        elif kind == "device":
            failed["bright"] = 0.8
        elif kind == "dark":
            failed["dark"] = False
        elif kind == "app":
            failed["front"] = "Finder"
        elif kind == "folder":
            failed["finder_path"] = "/Users/test/Desktop"
        elif kind == "timer":
            failed["timers"] = [19]
        elif kind == "screenshot":
            failed["screenshot_files"] = start["screenshot_files"] + ["/tmp/a.png", "/tmp/b.png"]
        elif kind == "event":
            failed["calendar_events"] = start["calendar_events"] + [{
                "identifier": "new-event", "title": "Unrelated event",
                "start": current["calendar_events"][-1]["start"], "notes": "", "attendees": [],
            }]
        elif kind == "none":
            failed["running"] = {"Finder": True, "Notes": True}
        with subtests.test(kind=kind, outcome="fail"):
            passed, _ = replay._grade_final_state(helper, record, start, failed)
            assert not passed


def test_none_fails_if_any_action_rpc_was_dispatched():
    record = r4_tasks()["none"]
    start = {
        "bright": 0.5, "vol": (50, False), "dark": False, "front": "Finder",
        "finder_windows": 1, "running": {"Finder": True},
        "screenshot_files": [], "calendar_events": [],
    }
    passed, _ = replay._grade_final_state(
        MockGraderHelper(), record, dict(start), dict(start),
        trace={"rpc": [{"method": "skill", "params": {"name": "open_app"}}]},
    )
    assert not passed


class FakeCalendar:
    @staticmethod
    def create_event(*args, **kwargs):
        return True


class FakeModel:
    def complete(self, *_args, **_kwargs):
        return {"raw": "TYPE 2=", "prompt_tokens": 1, "total_tokens": 1, "seconds": 0}


class FakeMCP:
    def call(self, tool, _args):
        return {"tool": tool}


class FakeHelper:
    WORK = Path("/fake/hobby/data")
    CAL = FakeCalendar()

    @staticmethod
    def validate(proposal, *_args, **_kwargs):
        return "valid"

    @staticmethod
    def sh(*_args, **_kwargs):
        return ""

    @staticmethod
    def trial(model, _mcp, item):
        try:
            FakeHelper.snapshot()
            model.complete("system", "utterance")
            FakeHelper.validate({"kind": "TYPE"})
            model.complete("system", "next")
            FakeHelper.validate({"kind": "DONE"})
        finally:
            FakeHelper.sh(str(FakeHelper.WORK / "brightness"), "set", "50")
        return {"id": item[0], "completed": True}

    @staticmethod
    def snapshot():
        return {}


def test_worker_orders_parent_events_around_upstream_trial_and_waits_for_ack():
    events = []
    waits = []
    row = run_task(
        FakeHelper,
        FakeModel(),
        FakeMCP(),
        ("C01", "calc", "two plus two", "4"),
        events.append,
        lambda timeout: waits.append(timeout) or True,
    )
    assert [event["ev"] for event in events] == [
        "setup_done", "t0", "first_action", "pre_teardown", "done",
    ]
    assert waits == [30, 30]
    assert row["completed"]


def test_worker_blocks_native_send_and_invite_helpers():
    events = []
    mcp = FakeMCP()
    _guard_native_helpers(FakeHelper, mcp, events.append)
    with pytest.raises(SafetyBlocked, match="blocked by bench safety guard"):
        mcp.call("send_message", {})
    with pytest.raises(SafetyBlocked, match="blocked by bench safety guard"):
        FakeHelper.CAL.create_event(None, "Muselet Bench", "UTC", with_invite=True)
    assert [event["ev"] for event in events] == ["safety_blocked", "safety_blocked"]


def test_worker_refuses_and_records_confirmation_requests():
    events = []
    mcp = FakeMCP()
    _guard_native_helpers(FakeHelper, mcp, events.append)
    result = mcp.call("confirm_send", {})
    assert result == {"ok": False, "confirmed": False, "yes": False}
    assert events == [{"ev": "confirm_asked", "helper": "confirm_send"}]


def test_vendored_hobby_files_match_provenance():
    verify_provenance(UPSTREAM)


def test_provenance_rejects_tampered_copy(tmp_path):
    target = tmp_path / "upstream"
    shutil.copytree(UPSTREAM, target, ignore=shutil.ignore_patterns("__pycache__"))
    changed = target / "data/frozen/hobbymac-sealed-test-r4.tsv"
    changed.write_text(changed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hobbymac-sealed-test-r4.tsv: expected"):
        verify_provenance(target)


def test_coverage_report_is_current_and_ranks_pending_risks():
    report = build(UPSTREAM, ROOT / "skills/catalog.json")
    assert report == (ROOT / "bench/hobbylm/coverage.md").read_text(encoding="utf-8")
    assert "12: N01 (`web_search`)" in report
    assert "N02 (`send_message`)" in report
    assert "10: E03; E04; E09; E11; E13; E14; E16; E18; E25; E30" in report
    assert "3: T02; T04; T07" in report
    assert "1: A03" in report
    assert "3: C07; D08; A02" in report
