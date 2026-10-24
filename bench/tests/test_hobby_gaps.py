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


def test_timer_grading_uses_successful_proxied_start_timer_results(monkeypatch, tmp_path):
    monkeypatch.setattr(replay, "CATALOG_PATH", tmp_path / "empty-catalog.json")
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


def test_timer_teardown_discloses_missing_cancel_skill_and_sends_nothing(
        monkeypatch, tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"skills": []}))
    monkeypatch.setattr(replay, "CATALOG_PATH", catalog)

    class Runtime:
        timer_start_calls = [{"timer_id": "owned"}]
        async def run_skill(self, *args, **kwargs):
            raise AssertionError("must not probe absent cancel_timers")

    runtime = Runtime()
    result = asyncio.run(replay._timer_teardown(runtime, {}))
    assert result == {
        "timer_teardown": "not_cancelled_no_cancel_timers_skill",
        "timer_ids": ["owned"],
    }


def test_catalogued_list_and_cancel_timer_skills_are_used(monkeypatch, tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"skills": [
        {"name": "list_timers", "args": []},
        {"name": "cancel_timers", "args": [
            {"name": "timer_ids", "type": "array", "required": True},
        ]},
    ]}))
    monkeypatch.setattr(replay, "CATALOG_PATH", catalog)
    proxy = SimpleNamespace(capture=SimpleNamespace(frames=_frames(), active=False))
    runtime = object.__new__(replay._HobbyRuntime)
    runtime.proxy = proxy
    runtime.timer_calls = []
    runtime.timer_start_calls = []
    runtime.timer_grading = None
    requested = []

    async def run_skill(name, args, **kwargs):
        requested.append((name, args))
        return {"ok": True, "result": {"timers": [
            {"seconds": 600, "timer_id": "listed"},
        ]}}

    runtime.run_skill = run_skill
    state = {}
    asyncio.run(runtime._capture_timers(state))
    assert runtime.timer_grading == "list_timers"
    assert state["timers"] == [10]
    assert requested == [("list_timers", {})]

    runtime.timer_start_calls = [{"timer_id": "owned-1"}]
    runtime.timer_teardown = None
    assert asyncio.run(replay._timer_teardown(runtime, {}))["timer_teardown"] == "cancel_timers"
    assert requested[-1] == ("cancel_timers", {"timer_ids": ["owned-1"]})


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
    assert replay._run_metadata(tasks) == {"calc_setup": "calculator_open_cleared"}
    assert replay._run_metadata([{"kind": "timer"}]) == {
        "timer_grading": "proxied_start_timer_ok_results",
    }
