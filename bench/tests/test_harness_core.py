import asyncio
import json
import os
import time
from datetime import date, datetime, timezone

import pytest

from bench.harness.core import (
    HarnessTimeout,
    evaluate_predicate,
    find_trace_record,
    outcome_matches,
    report_math,
    run_case,
    template_values,
)


class FakeRuntime:
    def __init__(self, fail_script=None):
        self.calls = []
        self.fail_script = fail_script
        self.first_action_monotonic = None
        self.terminal_monotonic = None
        self.utterance_monotonic = None

    async def start_scripts(self):
        self.calls.append(("start_scripts",))

    async def run_script(self, lang, code, *, allow_inflight=False):
        self.calls.append(("script", lang, code, allow_inflight))
        if code == self.fail_script:
            raise RuntimeError("script failure")
        return {"ok": True, "output": "ok"}

    async def start_utterance(self, utterance):
        self.calls.append(("utterance", utterance))

    async def prepare_for_cleanup(self):
        self.calls.append(("prepare_cleanup",))

    async def stop(self):
        self.calls.append(("stop",))

    def snapshot(self):
        return {"frames": [], "confirm_count": 0}


class HeldSlotTimeoutRuntime(FakeRuntime):
    async def start_utterance(self, utterance):
        raise HarnessTimeout("wait_for_utterance", False)


class ScreenOCRRuntime:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def run_rpc(self, method, params, *, allow_inflight=False):
        self.calls.append((method, params, allow_inflight))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_template_values_use_unpadded_dates_and_strict_next_friday():
    values = template_values(today=date(2026, 1, 2))
    assert values["tomorrow_ymd"] == "2026-1-3"
    assert values["next_friday_ymd"] == "2026-1-9"


def test_planner_outcomes_and_parent_confirm_cancel_are_gradeable():
    trace = {"outcome": "failed", "decisions": [{"lines": ["refuse \"no\""]}]}
    assert outcome_matches("refused", trace)
    assert outcome_matches("cancelled", None, {"confirm_cancelled": True})
    assert not outcome_matches("ok", {"outcome": "fallback"})


def test_held_slot_timeout_skips_all_teardown_and_is_not_scored(tmp_path):
    async def scenario():
        runtime = HeldSlotTimeoutRuntime()
        result = await run_case({
            "id": "timeout-case", "utterance": "hello",
            "teardown": [{"shell": "must-not-run"}],
            "restore": [{"get": "value", "set": "write {value}"}],
        }, runtime, values={}, trace_path=tmp_path / "traces.jsonl")
        assert result["status"] == "harness_timeout"
        assert result["strict_pass"] is False
        assert result["harness_timeout"] == {
            "stage": "wait_for_utterance", "slot_released": False,
        }
        assert result["teardown_incomplete"] is True
        assert any(
            item.get("skipped") == "harness_timeout_slot_held"
            for item in result["teardown_observations"]
        )
        assert any(
            item.get("skipped") == "harness_timeout_slot_held"
            for item in result["restore_observations"]
        )
        assert not any(
            call[0] == "script" and call[2] in ("must-not-run", "write ok")
            for call in runtime.calls
        )

    asyncio.run(scenario())


def test_restore_set_and_teardown_run_when_setup_fails(tmp_path):
    async def scenario():
        runtime = FakeRuntime(fail_script="broken setup")
        case = {
            "id": "partial-setup",
            "utterance": "should not run",
            "restore": [{"get": "get value", "set": "set value {value}"}],
            "setup": [{"shell": "broken setup"}],
            "teardown": [{"shell": "cleanup"}],
        }
        result = await run_case(
            case, runtime, values={}, trace_path=tmp_path / "traces.jsonl"
        )
        assert result["status"] == "failed"
        script_codes = [call[2] for call in runtime.calls if call[0] == "script"]
        assert script_codes == ["get value", "broken setup", "cleanup", "set value ok"]
        assert not any(call[0] == "utterance" for call in runtime.calls)

    asyncio.run(scenario())


def test_trace_predicates_and_refused_outcome_use_recorded_evidence():
    async def scenario():
        context = {
            "trace": {
                "decisions": {"router": {"route_probs": [["REFUSE", 0.9], ["ANSWER", 0.1]]}},
                "rpc": [{"method": "skill", "params": {"name": "create_event", "args": {"title": "Lunch"}}}],
            },
            "capture": {"frames": [
                {"direction": "brain_to_hands", "frame": {"t": "say", "text": "I found lunch."}},
            ]},
        }
        skill = await evaluate_predicate(
            {"trace_skill": {"name": "create_event", "args": {"title": "Lunch"}}},
            None,
            context,
        )
        rpc = await evaluate_predicate(
            {"trace_rpc": {"method": "skill", "name": "create_event"}}, None, context
        )
        say = await evaluate_predicate(
            {"trace_say": {"contains": "found lunch"}}, None, context
        )
        assert skill["passed"] and rpc["passed"] and say["passed"]
        from bench.harness.core import outcome_matches

        assert outcome_matches("refused", context["trace"])

    asyncio.run(scenario())


def test_screen_ocr_predicate_uses_screenshot_and_compares_ocr_text():
    async def scenario():
        screenshot = {"ok": True, "path": "/screens/one.png"}
        ocr = {"ok": True, "lines": [{"text": "shot2 imported"}]}
        runtime = ScreenOCRRuntime([screenshot, ocr])
        predicate = {"ocr_screen": True, "contains": "shot2"}
        passed = await evaluate_predicate(
            predicate, runtime, {}, allow_inflight=True)
        assert passed["passed"] and passed["actual"] == "shot2 imported"
        assert passed["rpc_result"] == ocr
        assert runtime.calls == [
            ("screenshot", {"window": False, "max_pixels": 4_000_000}, True),
            ("ocr", {"path": "/screens/one.png"}, True),
        ]

        runtime = ScreenOCRRuntime([
            screenshot, {"ok": True, "text": "different screen"},
        ])
        failed = await evaluate_predicate(
            {"ocr_screen": True, "equals": "expected"}, runtime, {})
        assert failed["passed"] is False
        assert failed["actual"] == "different screen"

        runtime = ScreenOCRRuntime([RuntimeError("screenshot failed")])
        error = await evaluate_predicate(
            {"ocr_screen": True, "contains": "anything"}, runtime, {})
        assert error["passed"] is False
        assert error["error"] == "screenshot failed"
        assert runtime.calls == [
            ("screenshot", {"window": False, "max_pixels": 4_000_000}, False),
        ]

    asyncio.run(scenario())


def test_find_trace_requires_matching_utterance_and_case_start(tmp_path):
    path = tmp_path / "traces.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in [
            {"ts": "2026-01-01T00:00:00+00:00", "utterance": "same", "outcome": "old"},
            {"ts": "2026-01-01T00:00:02+00:00", "utterance": "other", "outcome": "wrong"},
            {"ts": "2026-01-01T00:00:03+00:00", "utterance": "same", "outcome": "new"},
        ]) + "\n",
        encoding="utf-8",
    )
    record = find_trace_record(path, "same", "2026-01-01T00:00:01+00:00")
    assert record["outcome"] == "new"


def test_find_trace_interprets_naive_brain_timestamp_as_local(tmp_path, monkeypatch):
    if not hasattr(time, "tzset"):
        return
    old_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Etc/GMT+5")
    time.tzset()
    try:
        path = tmp_path / "traces.jsonl"
        path.write_text(
            json.dumps({
                "ts": "2026-01-01T00:00:03",
                "utterance": "same",
                "outcome": "ok",
            }) + "\n",
            encoding="utf-8",
        )
        record = find_trace_record(path, "same", "2026-01-01T04:00:00+00:00")
        assert record["outcome"] == "ok"
    finally:
        if old_tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", old_tz)
        time.tzset()


def test_pass_k_excludes_skipped_repeats_and_reports_latency_quantiles():
    records = [
        {"id": "a", "tier": "T1", "category": "system", "kind": "volume",
         "repeat": 1, "status": "passed", "strict_pass": True,
         "first_action_latency_s": 0.1, "verified_latency_s": 0.2},
        {"id": "a", "tier": "T1", "category": "system", "kind": "volume",
         "repeat": 2, "status": "failed", "strict_pass": False,
         "first_action_latency_s": 0.3, "verified_latency_s": 0.4, "false_done": True},
        {"id": "b", "tier": "T2", "category": "apps", "kind": "open",
         "repeat": 1, "status": "skipped", "strict_pass": False},
    ]
    report = report_math(records, repeats=2)
    assert report["pass^k"] == {"k": 2, "eligible": 1, "passed": 0, "rate": 0.0}
    assert report["by_tier"]["T1"]["strict_pass_rate"] == 0.5
    assert report["false_done"] == 1
    assert report["latency_s"]["first_action_p50"] == 0.2


def test_harness_timeout_is_excluded_from_rates_and_pass_k():
    report = report_math([
        {"id": "timed", "tier": "T2", "category": "apps", "kind": "open",
         "status": "harness_timeout", "strict_pass": False},
        {"id": "good", "tier": "T1", "category": "system", "kind": "volume",
         "status": "passed", "strict_pass": True},
        {"id": "pending", "tier": "T2", "pending": True, "category": "finance",
         "kind": "fixture", "status": "passed", "strict_pass": True,
         "first_action_latency_s": 0.1},
    ], repeats=1)
    assert report["executed"] == 1
    assert report["pass^k"]["eligible"] == 1
    assert report["harness_timeouts"] == {"count": 1, "ids": ["timed"]}
    assert report["pending"]["by_tier"]["T2"]["strict_pass_rate"] == 1.0
    assert report["by_tier"]["T1"]["executed"] == 1
    assert report["by_tier"]["T2"]["executed"] == 0


def test_trace_ends_case_and_final_check_records_verified_latency(tmp_path):
    class TraceRuntime(FakeRuntime):
        def __init__(self):
            super().__init__()
            self.utterance_wall = None

        async def start_utterance(self, utterance):
            self.calls.append(("utterance", utterance))
            self.utterance_monotonic = asyncio.get_running_loop().time()
            self.utterance_wall = datetime.now(timezone.utc).isoformat()
            self.trace_path.write_text(
                json.dumps({
                    "ts": self.utterance_wall, "utterance": utterance, "outcome": "ok",
                }) + "\n",
                encoding="utf-8",
            )

        def snapshot(self):
            return {
                "frames": [], "confirm_count": 0,
                "utterance_wall": self.utterance_wall,
            }

        def mark_utterance_finished(self):
            self.terminal_monotonic = asyncio.get_running_loop().time()

    async def scenario():
        runtime = TraceRuntime()
        runtime.trace_path = tmp_path / "traces.jsonl"
        case = {
            "id": "answer",
            "utterance": "answer only",
            "expect_outcome": "ok",
            "check": [lambda _runtime, _context: {"passed": True}],
        }
        result = await run_case(
            case, runtime, values={}, trace_path=runtime.trace_path
        )
        assert result["status"] == "passed"
        assert result["verified_latency_s"] is not None
        assert result["timed_out"] is False

    asyncio.run(scenario())


def test_replay_strict_pass_uses_state_not_reported_outcome(tmp_path):
    class ReplayRuntime(FakeRuntime):
        def __init__(self, outcome):
            super().__init__()
            self.outcome = outcome
            self.utterance_wall = None

        async def start_utterance(self, utterance):
            self.calls.append(("utterance", utterance))
            self.utterance_monotonic = asyncio.get_running_loop().time()
            self.utterance_wall = datetime.now(timezone.utc).isoformat()
            self.trace_path.write_text(
                json.dumps({
                    "ts": self.utterance_wall,
                    "utterance": utterance,
                    "outcome": self.outcome,
                }) + "\n",
                encoding="utf-8",
            )

        def snapshot(self):
            return {
                "frames": [], "confirm_count": 0,
                "utterance_wall": self.utterance_wall,
            }

        def mark_utterance_finished(self):
            self.terminal_monotonic = asyncio.get_running_loop().time()

    async def scenario():
        for outcome, expected_pass, expected_false_done in (
            ("failed", True, False),
            ("ok", False, True),
        ):
            runtime = ReplayRuntime(outcome)
            runtime.trace_path = tmp_path / f"{outcome}.jsonl"
            result = await run_case(
                {
                    "id": "replay",
                    "kind": "calc",
                    "utterance": "answer only",
                    "check": [lambda _runtime, _context: {"passed": outcome == "failed"}],
                },
                runtime,
                values={},
                trace_path=runtime.trace_path,
            )
            assert result["strict_pass"] is expected_pass
            assert result["false_done"] is expected_false_done

    asyncio.run(scenario())


@pytest.mark.final_settle
def test_final_checks_settle_on_state_the_agent_already_caused(tmp_path):
    class LoadingRuntime(FakeRuntime):
        def __init__(self, trace_path):
            super().__init__()
            self.trace_path, self.utterance_wall = trace_path, None

        async def start_utterance(self, utterance):
            self.utterance_monotonic = asyncio.get_running_loop().time()
            self.utterance_wall = datetime.now(timezone.utc).isoformat()
            self.trace_path.write_text(json.dumps(
                {"ts": self.utterance_wall, "utterance": utterance, "outcome": "ok"}) + "\n", encoding="utf-8")

        def snapshot(self):
            return {"frames": [], "confirm_count": 0, "utterance_wall": self.utterance_wall}

        def mark_utterance_finished(self):
            self.terminal_monotonic = asyncio.get_running_loop().time()

    calls = []

    def page_loaded(_runtime, _context):   # e.g. a browser title that updates after open_url returned
        calls.append(1)
        return {"passed": len(calls) >= 3}

    async def scenario():
        runtime = LoadingRuntime(tmp_path / "traces.jsonl")
        result = await run_case(
            {"id": "web", "kind": "stateful", "utterance": "open a page", "check": [page_loaded],
             "expect_outcome": "ok", "settle_s": 2.0},
            runtime, values={}, trace_path=runtime.trace_path, poll_interval=0.01)
        assert result["strict_pass"] is True and result["false_done"] is False
        assert [o["phase"] for o in result["check_observations"]] == ["settle", "settle", "final"]

    asyncio.run(scenario())


def test_case_launched_apps_and_finder_windows_are_closed_but_preexisting_ones_never():
    from bench.harness.core import _close_case_launched, _launch_snapshot

    class LaunchRuntime:
        def __init__(self):
            self.running = [{"name": "Finder", "bundle_id": "com.apple.finder"}, {"name": "TextEdit"}]
            self.finder = "11"
            self.calls = []

        async def run_rpc(self, method, params, **_):
            return {"ok": True, "running": list(self.running)}

        async def run_skill(self, name, args, **_):
            self.calls.append((name, args))
            return {"ok": True, "terminated": True}

        async def run_script(self, lang, code, **_):
            if "get id of every Finder window" in code:
                return {"ok": True, "output": self.finder}
            self.calls.append(("script", code))
            return {"ok": True, "output": ""}

    async def scenario():
        runtime = LaunchRuntime()
        baseline = await _launch_snapshot(runtime)
        runtime.running += [{"name": "Notes", "bundle_id": "com.apple.Notes"}, {"name": "Zen"}]
        runtime.finder = "11, 42"
        result = {"teardown_observations": []}
        await _close_case_launched(runtime, baseline, result)
        assert ("quit_app", {"app": "Notes"}) in runtime.calls
        assert not any(call[0] == "quit_app" and call[1]["app"] == "TextEdit" for call in runtime.calls)
        scripts = [call[1] for call in runtime.calls if call[0] == "script"]
        assert len(scripts) == 1 and "{42}" in scripts[0] and "11" not in scripts[0]
        assert not result.get("teardown_incomplete")

    asyncio.run(scenario())


def test_wait_disconnected_latch_frees_the_slot_instead_of_failing_the_case():
    from bench.harness.runtime import HandsRuntime

    class LatchedProxy:
        def __init__(self):
            self.capture = type("C", (), {"active": True})()
            self.released = False
            self.forced = 0

        def mark_utterance_finished(self):
            self.capture.active = False

        async def wait_disconnected(self, timeout=10):
            raise asyncio.TimeoutError()

        async def release_slot(self, timeout=5.0):
            return False

        async def force_release(self):
            self.forced += 1

    async def scenario():
        runtime = HandsRuntime.__new__(HandsRuntime)
        runtime.proxy = LatchedProxy()
        calls = []

        async def note(name):
            calls.append(name)
        runtime._stop_client = lambda: note("stop")
        runtime._terminate_client = lambda: note("terminate")
        runtime.start_scripts = lambda: note("scripts")
        await runtime.prepare_for_cleanup()
        assert runtime.proxy.forced == 1 and calls == ["stop", "terminate", "scripts"]

    asyncio.run(scenario())
