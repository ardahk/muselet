import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace

from bench.hobbylm import replay


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
    assert "id" not in requests[0][1] or requests[0][1]["id"] == "timer-1"
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


def test_live_record_merge_keeps_case_skip_reason():
    base = {"id": "x", "skip_reason": None, "utterance": "u"}
    record = {"status": "skipped", "skip_reason": "user_documents_open"}
    record.update({k: v for k, v in base.items()
                   if not (k == "skip_reason" and not v)})
    assert record["skip_reason"] == "user_documents_open"
