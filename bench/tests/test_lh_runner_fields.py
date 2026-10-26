"""LH-v1 runner fields: milestones, require_confirm, n_actions, setup_failed, evidence hook."""

import asyncio
import json
from datetime import datetime, timezone

import pytest

from bench.harness.core import (
    _count_brain_actions,
    report_math,
    run_case,
)
from bench.live.run_live import _load_suite, _prepare_run_spec

from test_harness_core import FakeRuntime


class DoneRuntime(FakeRuntime):
    """Reaches `passed`: writes an ok trace at t0 and ends at mark_utterance_finished."""

    def __init__(self, trace_path, confirm_count=0, frames=None):
        super().__init__()
        self.trace_path = trace_path
        self.utterance_wall = None
        self.confirm_count = confirm_count
        self.frames = list(frames or [])

    async def start_utterance(self, utterance):
        self.calls.append(("utterance", utterance))
        self.utterance_monotonic = asyncio.get_running_loop().time()
        self.utterance_wall = datetime.now(timezone.utc).isoformat()
        self.trace_path.write_text(
            json.dumps({
                "ts": self.utterance_wall, "utterance": utterance, "outcome": "ok",
                "decisions": [{"planner_turn": 1, "lines": ["done \"ok\""]}],
            }) + "\n",
            encoding="utf-8",
        )

    def snapshot(self):
        return {
            "frames": list(self.frames),
            "confirm_count": self.confirm_count,
            "utterance_wall": self.utterance_wall,
        }

    def mark_utterance_finished(self):
        self.terminal_monotonic = asyncio.get_running_loop().time()


def _done_case(**overrides):
    case = {
        "id": "lh-smoke",
        "utterance": "do the thing",
        "expect_outcome": "ok",
        "check": [{"shell": "probe", "equals": "ok"}],
    }
    case.update(overrides)
    return case


def test_setup_failure_reports_step_index(tmp_path):
    async def scenario():
        runtime = FakeRuntime(fail_script="boom")
        result = await run_case(
            _done_case(setup=[{"shell": "fine"}, {"shell": "boom"}]),
            runtime, values={}, trace_path=tmp_path / "traces.jsonl",
        )
        assert result["status"] == "skipped"
        assert result["skip_reason"] == "setup_failed:1"
        assert not any(call[0] == "utterance" for call in runtime.calls)

    asyncio.run(scenario())


def test_milestones_are_recorded_but_not_graded(tmp_path):
    async def scenario():
        runtime = DoneRuntime(tmp_path / "traces.jsonl")
        case = _done_case(milestones=[
            {"name": "m_pass", "shell": "probe", "equals": "ok"},
            {"name": "m_fail", "shell": "probe", "equals": "never"},
        ])
        result = await run_case(case, runtime, values={}, trace_path=runtime.trace_path)
        assert result["strict_pass"] is True
        assert result["milestones"] == [
            {"name": "m_pass", "passed": True, "actual": "ok"},
            {"name": "m_fail", "passed": False, "actual": "ok"},
        ]
        assert result["milestone_frac"] == 0.5

    asyncio.run(scenario())


def test_require_confirm_needs_a_confirm_asked(tmp_path):
    async def scenario():
        for confirm_count, expected in ((0, False), (1, True)):
            runtime = DoneRuntime(
                tmp_path / f"traces-{confirm_count}.jsonl",
                confirm_count=confirm_count,
            )
            result = await run_case(
                _done_case(require_confirm=True), runtime,
                values={}, trace_path=runtime.trace_path,
            )
            assert result["strict_pass"] is expected
            assert result["require_confirm"] is True

    asyncio.run(scenario())


def test_n_actions_and_planner_turns_come_from_brain_frames(tmp_path):
    frames = [
        {"direction": "brain_to_hands", "frame": {"t": "rpc", "id": "r1",
                                                  "method": "observe", "params": {}}},
        {"direction": "brain_to_hands", "frame": {"t": "rpc", "id": "r2",
                                                  "method": "act", "params": {"op": "press"}}},
        {"direction": "brain_to_hands", "frame": {"t": "rpc", "id": "r3",
                                                  "method": "skill", "params": {"name": "open_app"}}},
        {"direction": "brain_to_hands", "frame": {"t": "rpc", "id": "r4",
                                                  "method": "act", "params": {"op": "ocr"}}},
        {"direction": "runner_to_hands", "frame": {"t": "rpc", "id": "bench-9",
                                                   "method": "act", "params": {"op": "script"}}},
        {"direction": "brain_to_hands", "frame": {"t": "rpc", "id": "bench-7",
                                                  "method": "act", "params": {"op": "script"}}},
        {"direction": "hands_to_brain", "frame": {"t": "rpc_result", "id": "r2", "ok": True}},
    ]
    assert _count_brain_actions({"frames": frames}) == 2

    async def scenario():
        runtime = DoneRuntime(tmp_path / "traces.jsonl", frames=frames)
        result = await run_case(
            _done_case(), runtime, values={}, trace_path=runtime.trace_path,
        )
        assert result["n_actions"] == 2
        assert result["planner_turns"] == 1

    asyncio.run(scenario())


def test_before_teardown_hook_runs_first_and_never_fails_the_case(tmp_path):
    order = []

    def hook(_runtime, _result):
        order.append("hook")
        _result["evidence_marker"] = True

    async def scenario():
        runtime = DoneRuntime(tmp_path / "traces.jsonl")
        result = await run_case(
            _done_case(before_teardown=hook, teardown=[{"shell": "cleanup"}]),
            runtime, values={}, trace_path=runtime.trace_path,
        )
        assert result["strict_pass"] is True
        assert result["evidence_marker"] is True
        assert order == ["hook"]
        script_codes = [call[2] for call in runtime.calls if call[0] == "script"]
        assert script_codes.index("cleanup") >= 0

        def bad_hook(_runtime, _result):
            raise RuntimeError("no screen")

        runtime2 = DoneRuntime(tmp_path / "traces2.jsonl")
        result2 = await run_case(
            _done_case(before_teardown=bad_hook), runtime2,
            values={}, trace_path=runtime2.trace_path,
        )
        assert result2["strict_pass"] is True
        assert result2["evidence_error"] == "no screen"

    asyncio.run(scenario())


def test_summary_medians_and_milestone_frac_mean():
    report = report_math([
        {"id": "a", "status": "passed", "strict_pass": True,
         "utterance_latency_s": 4.0, "n_actions": 6, "milestone_frac": 0.5},
        {"id": "b", "status": "failed", "strict_pass": False,
         "utterance_latency_s": 10.0, "n_actions": 12, "milestone_frac": 1.0},
        {"id": "c", "status": "skipped", "strict_pass": False},
    ], repeats=1)
    assert report["medians"]["latency_s"] == 7.0
    assert report["medians"]["n_actions"] == 9.0
    assert report["milestone_frac_mean"] == 0.75


def test_milestone_and_require_confirm_shape_are_validated(tmp_path):
    good = tmp_path / "good.jsonl"
    good.write_text(json.dumps(_done_case(
        milestones=[{"name": "m", "shell": "x", "equals": "y"}],
        require_confirm=True,
    )) + "\n", encoding="utf-8")
    assert len(_load_suite(good)) == 1

    for bad in (
        {"milestones": [{"shell": "x", "equals": "y"}]},
        {"milestones": [{"name": ""}]},
        {"milestones": "nope"},
        {"require_confirm": "yes"},
    ):
        path = tmp_path / "bad.jsonl"
        path.write_text(json.dumps(_done_case(**bad)) + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            _load_suite(path)


def test_prepare_run_spec_wires_the_screenshot_hook(tmp_path, monkeypatch):
    import bench.live.run_live as live

    def fake_screencapture(command, **_kwargs):
        (tmp_path / "shots" / "x-r1.png").write_bytes(b"png")
        return type("P", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(live.subprocess, "run", fake_screencapture)
    spec = _prepare_run_spec(_done_case(), shots_dir=tmp_path / "shots", shot_name="x-r1")
    assert callable(spec["before_teardown"])
    result = {}
    spec["before_teardown"](None, result)
    assert result["evidence_screenshot"].endswith("shots/x-r1.png")
    assert (tmp_path / "shots" / "x-r1.png").is_file()
