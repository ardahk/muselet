import argparse
import asyncio
import json
import subprocess
from pathlib import Path

import pytest
import websockets

from bench.harness import runtime as runtime_module
from bench.harness.core import evaluate_predicate, run_case
from bench.harness.documents import document_apps_for_case
from bench.harness.proxy import BenchProxy
from bench.live.run_live import _dry_run, _load_suite, _screen_grade_error, _step_order, _turns_error
from bench.tests.test_harness_core import FakeRuntime
from bench.tests.test_harness_runtime import FakeProcess, FakeProxy

ROOT = Path(__file__).resolve().parents[2]
NEW_SUITE = ROOT / "evals/live_t2_new.jsonl"
ACCEPTANCE_SUITE = ROOT / "evals/acceptance.jsonl"
PREMIERE_SUITE = ROOT / "evals/live_premiere.jsonl"


class TurnRuntime(FakeRuntime):
    """FakeRuntime that plays one scripted brain turn per utterance."""

    def __init__(self, outputs, *, trace_path, finish=None):
        super().__init__()
        self.outputs = outputs
        self.trace_path = trace_path
        self.finish = finish or {}
        self.turn = 0
        self.frames = []
        self.utterance_wall = None
        self.confirm_replies = []

    def begin_turn(self, confirm_reply):
        self.calls.append(("begin_turn", confirm_reply))
        self.confirm_replies.append(confirm_reply)
        self.first_action_monotonic = self.terminal_monotonic = None

    def _play(self, text):
        loop = asyncio.get_running_loop()
        self.utterance_monotonic = loop.time()
        self.first_action_monotonic = loop.time()
        self.utterance_wall = f"2030-01-01T00:00:0{self.turn}+00:00"
        if self.finish.get(self.turn, True):
            self.terminal_monotonic = loop.time()
            self.frames.append({"direction": "brain_to_hands", "frame": {"t": "say", "text": f"did {text}"}})
            self.frames.append({"direction": "brain_to_hands", "frame": {"t": "ui", "mascot": "success"}})
            with self.trace_path.open("a", encoding="utf-8") as trace:
                trace.write(json.dumps({"ts": self.utterance_wall, "utterance": text, "outcome": "ok"}) + "\n")

    async def start_turns(self, utterances, timeout_s=30):
        self.calls.append(("start_turns", tuple(utterances), timeout_s))
        self.utterances = list(utterances)
        self._play(self.utterances[0])

    async def wait_next_turn(self, timeout_s=20):
        self.calls.append(("wait_next_turn",))
        return self.turn + 1 < len(self.utterances)

    async def send_next_turn(self):
        self.turn += 1
        self.calls.append(("send_next_turn", self.utterances[self.turn]))
        self._play(self.utterances[self.turn])

    def mark_utterance_finished(self):
        self.terminal_monotonic = asyncio.get_running_loop().time()

    async def run_script(self, lang, code, *, allow_inflight=False):
        self.calls.append(("script", lang, code, allow_inflight))
        value = self.outputs.get(code)
        if isinstance(value, list):
            value = value[min(self.turn, len(value) - 1)]
        return {"ok": True, "output": "ok" if value is None else str(value)}

    def snapshot(self):
        return {"frames": list(self.frames), "confirm_count": 0, "utterance_wall": self.utterance_wall}


def _volume_case():
    return {
        "id": "again", "category": "memory", "tier": "T2", "expect_outcome": "ok",
        "restore": [{"get": "get-volume", "set": "set-volume {value}"}],
        "setup": [{"applescript": "volume 30"}],
        "turns": [
            {"utterance": "turn the volume up a bit", "confirm_reply": True,
             "check": [{"applescript": "volume", "int_between": [31, 100], "save": "after_turn1"}],
             "wait_s": 0},
            {"utterance": "again", "wait_s": 0},
        ],
        "check": [{"applescript": "volume", "int_at_least_saved": ["after_turn1", 5]}],
        "teardown": [{"applescript": "cleanup"}],
    }


def test_turns_share_one_client_and_grade_final_state_against_saved_value(tmp_path):
    async def scenario(final_volume):
        trace_path = tmp_path / f"traces-{final_volume}.jsonl"
        runtime = TurnRuntime({"get-volume": "55", "volume": [37, final_volume]}, trace_path=trace_path)
        result = await run_case(_volume_case(), runtime, values={}, trace_path=trace_path, poll_interval=0)
        return runtime, result

    runtime, result = asyncio.run(scenario(43))
    assert result["status"] == "passed" and result["strict_pass"] and result["turns_ok"]
    assert result["utterance"] == "turn the volume up a bit → again"
    assert result["saved_values"] == {"after_turn1": 37.0}
    assert [turn["utterance"] for turn in result["turns"]] == ["turn the volume up a bit", "again"]
    assert [turn["reply"] for turn in result["turns"]] == ["did turn the volume up a bit", "did again"]
    assert all(turn["mood"] == "success" and turn["observed_outcome"] == "ok" for turn in result["turns"])
    assert all(turn["latency_s"] is not None for turn in result["turns"])
    assert result["trace"]["utterance"] == "again"
    assert runtime.confirm_replies == [True, None]
    names = [call[0] for call in runtime.calls]
    assert names.count("start_turns") == 1 and "start_utterance" not in names
    start = next(call for call in runtime.calls if call[0] == "start_turns")
    assert start[1] == ("turn the volume up a bit", "again")
    order = [call for call in runtime.calls if call[0] != "script" or call[2] in ("volume 30", "cleanup", "set-volume 55")]
    assert [call[0] if call[0] != "script" else call[2] for call in order][-9:-1] == [
        "volume 30", "begin_turn", "start_turns", "wait_next_turn", "begin_turn", "send_next_turn",
        "cleanup", "set-volume 55",
    ]

    _runtime, result = asyncio.run(scenario(40))
    assert result["status"] == "failed" and result["turns_ok"]
    assert result["check_observations"][-1]["observations"][0]["passed"] is False


def test_failed_turn_check_fails_case_and_timeout_stops_later_turns(tmp_path):
    case = _volume_case()
    trace_path = tmp_path / "traces.jsonl"
    runtime = TurnRuntime({"get-volume": "55", "volume": [30, 45]}, trace_path=trace_path)
    result = asyncio.run(run_case(case, runtime, values={}, trace_path=trace_path, poll_interval=0))
    assert result["turns"][0]["passed"] is False and result["strict_pass"] is False
    assert result["turns_ok"] is False

    case = _volume_case()
    case["timeout_s"] = 0.05
    trace_path = tmp_path / "timeout.jsonl"
    runtime = TurnRuntime({"get-volume": "55", "volume": 37}, trace_path=trace_path, finish={0: False})
    result = asyncio.run(run_case(case, runtime, values={}, trace_path=trace_path, poll_interval=0.01))
    assert result["timed_out"] is True and result["status"] == "failed"
    assert [turn["status"] for turn in result["turns"]] == ["timed_out"]
    assert "send_next_turn" not in [call[0] for call in runtime.calls]
    assert ("prepare_cleanup",) in runtime.calls
    assert result["restore_observations"][-1]["set"] == "set-volume 55"


def test_turn_precondition_failure_skips_before_any_turn(tmp_path):
    case = _volume_case() | {"precondition": [{"applescript": "running", "equals": "false"}]}
    runtime = TurnRuntime({"running": "true"}, trace_path=tmp_path / "t.jsonl")
    result = asyncio.run(run_case(case, runtime, values={}, trace_path=tmp_path / "t.jsonl"))
    assert result["status"] == "skipped" and result["skip_reason"] == "precondition failed"
    assert not {"start_turns", "begin_turn"} & {call[0] for call in runtime.calls}


class RpcRuntime(FakeRuntime):
    def __init__(self, timers):
        super().__init__()
        self.timers = timers

    async def run_rpc(self, method, params, *, allow_inflight=False):
        self.calls.append(("rpc", method, params))
        if method == "timers":
            return {"ok": True, "timers": self.timers, "clock": {"status": "running"}}
        if method == "timers_cancel":
            return {"ok": True, "cancelled": [params["id"]], "unsupported": []}
        raise RuntimeError("unknown rpc")


def test_rpc_predicate_counts_matching_timers_and_reads_paths():
    timers = [
        {"id": "a", "backend": "clock", "total_s": 120.0},
        {"id": "b", "backend": "muselet", "total_s": 120.0},
        {"id": "c", "backend": "clock_ax", "total_s": 300.0},
    ]
    runtime = RpcRuntime(timers)
    where = {"backend": ["clock", "clock_ax"], "total_s": 120}
    observed = asyncio.run(evaluate_predicate(
        {"rpc": "timers", "count": {"path": "timers", "where": where}, "equals": "1"}, runtime, {}
    ))
    assert observed["passed"] and observed["actual"] == "1"
    observed = asyncio.run(evaluate_predicate(
        {"rpc": "timers", "path": "clock.status", "not_contains": "running"}, runtime, {}
    ))
    assert observed["passed"] is False
    observed = asyncio.run(evaluate_predicate(
        {"applescript": "x", "int_at_least_saved": ["missing", 5]}, runtime, {"saved": {}}
    ))
    assert observed["passed"] is False and "missing" in observed["error"]


def test_cancel_timers_teardown_cancels_only_matching_timers(tmp_path):
    runtime = RpcRuntime([
        {"id": "clock-1", "backend": "clock", "total_s": 120.0},
        {"id": "mine", "backend": "muselet", "total_s": 60.0},
    ])
    case = {
        "id": "timer", "utterance": "set a timer for 2 minutes", "timeout_s": 0.05,
        "teardown": [{"cancel_timers": {"where": {"backend": ["clock", "clock_ax"]}}}],
    }
    result = asyncio.run(run_case(case, runtime, values={}, trace_path=tmp_path / "t.jsonl"))
    cancels = [call for call in runtime.calls if call[:2] == ("rpc", "timers_cancel")]
    assert cancels == [("rpc", "timers_cancel", {"id": "clock-1"})]
    assert not result.get("teardown_incomplete")


def test_proxy_holds_later_turns_on_the_same_brain_connection():
    async def scenario():
        brain_frames = asyncio.Queue()
        connections = []

        async def brain_handler(ws):
            connections.append(ws)
            async for raw in ws:
                frame = json.loads(raw)
                brain_frames.put_nowait(frame)
                if frame.get("t") == "utterance":
                    await ws.send(json.dumps({"t": "confirm", "id": f"c-{frame['id']}", "summary": "ok?"}))
                    await ws.send(json.dumps({"t": "say", "text": f"done {frame['text']}"}))
                    await ws.send(json.dumps({"t": "ui", "mascot": "success"}))

        async with websockets.serve(brain_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with BenchProxy(f"ws://127.0.0.1:{port}") as proxy:
                await proxy.begin_case("turns", None)
                proxy.gate_turns()
                proxy.begin_turn(True)

                async def hands_client():
                    async with websockets.connect(proxy.url) as hands:
                        await hands.send(json.dumps({"t": "hello", "screens": []}))
                        for number, text in enumerate(("first", "second"), 1):
                            await hands.send(json.dumps({
                                "t": "utterance", "id": f"u{number}", "text": text, "final": True,
                            }))
                        async for _raw in hands:
                            pass

                client = asyncio.create_task(hands_client())
                assert (await asyncio.wait_for(brain_frames.get(), 1))["t"] == "hello"
                assert (await asyncio.wait_for(brain_frames.get(), 1))["text"] == "first"
                assert (await asyncio.wait_for(brain_frames.get(), 1)) == {
                    "t": "confirm_reply", "id": "c-u1", "yes": True,
                }
                assert await proxy.wait_for_terminal(1)
                assert await proxy.wait_for_held_utterance(1)
                assert brain_frames.empty()
                proxy.begin_turn(False)
                assert not proxy.capture.active and proxy.capture.terminal_monotonic is None
                assert await proxy.release_held_utterance()
                assert (await asyncio.wait_for(brain_frames.get(), 1))["text"] == "second"
                assert (await asyncio.wait_for(brain_frames.get(), 1))["yes"] is False
                assert await proxy.wait_for_terminal(1)
                assert len(connections) == 1
                assert proxy.capture.confirm_count == 2
                client.cancel()

    asyncio.run(scenario())


def test_start_turns_launches_one_client_with_every_utterance(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(
        runtime_module.subprocess, "Popen",
        lambda command, **kwargs: commands.append(command) or FakeProcess(command, **kwargs),
    )
    monkeypatch.setattr(
        runtime_module.subprocess, "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "--timeout", ""),
    )
    runtime_module.serve_timeout_supported.cache_clear()
    proxy = FakeProxy()
    proxy.gate_turns = lambda: proxy.calls.append(("gate",))
    instance = runtime_module.HandsRuntime(proxy, "hands-turns", tmp_path, "turns")
    asyncio.run(instance.start_turns(["open finder", "go to my downloads"], timeout_s=70))
    assert commands == [[
        "hands-turns", "serve", "--url", proxy.url,
        "--utterance", "open finder", "--utterance", "go to my downloads", "--timeout", "85",
    ]]
    assert ("gate",) in proxy.calls
    asyncio.run(instance.stop())
    runtime_module.CLIENT_PROCESSES.clear()


def _args(**overrides):
    values = {
        "suite": NEW_SUITE, "tier": set(), "category": set(), "id": set(),
        "include_manual": False, "include_pending": False, "run_pending": False,
        "allow_user_ok": False, "offline": False, "repeat": 1,
    }
    return argparse.Namespace(**(values | overrides))


def test_new_suite_loads_and_dry_run_lists_turns(capsys):
    cases = _load_suite(NEW_SUITE)
    assert [case["id"] for case in cases] == [
        "mem-wiki-search", "mem-again-volume", "mem-undo-darkmode",
        "clock-timer-front", "notes-template", "mem-followup-app",
    ]
    assert {case["tier"] for case in cases} == {"T2"}
    assert {case["category"] for case in cases} == {"memory", "timers", "notes"}
    assert _dry_run(cases, _args()) == 0
    plan = json.loads(capsys.readouterr().out)
    rows = {row["id"]: row for row in plan["case_plan"]}
    assert [turn["utterance"] for turn in rows["mem-followup-app"]["turns"]] == [
        "open finder", "go to my downloads",
    ]
    assert "turn 2: 'again' wait_s=1.0" in rows["mem-again-volume"]["step_order"]
    assert "turns" not in rows["clock-timer-front"]
    assert rows["mem-wiki-search"]["document_apps"] == ["Safari", "Google Chrome"]
    assert "Notes" in rows["notes-template"]["document_apps"]
    assert _step_order({"utterance": "x"}) == [
        "session: hands probe session (skip if locked/asleep)", "utterance", "poll-checks", "final-checks",
    ]


@pytest.mark.parametrize("case, message", [
    ({"id": "x", "utterance": "a", "turns": [{"utterance": "b"}]}, "not both"),
    ({"id": "x", "turns": []}, "non-empty"),
    ({"id": "x", "turns": [{"utterance": " "}]}, "no utterance"),
    ({"id": "x", "turns": [{"utterance": "a", "confirm_reply": "yes"}]}, "confirm_reply"),
    ({"id": "x", "turns": [{"utterance": "a", "wait_s": -1}]}, "wait_s"),
])
def test_invalid_turns_are_rejected(tmp_path, case, message):
    suite = tmp_path / "suite.jsonl"
    suite.write_text(json.dumps(case) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        _load_suite(suite)


def test_turn_text_and_turn_checks_select_document_apps():
    case = {
        "id": "x", "category": "memory",
        "turns": [{"utterance": "hi", "check": [{"applescript": 'application "TextEdit" is running'}]}],
    }
    assert [app.name for app in document_apps_for_case(case)] == ["TextEdit"]
    assert len(document_apps_for_case({"id": "y", "turns": [{"utterance": "write a note"}]})) > 1


@pytest.mark.final_settle
def test_turn_case_top_level_checks_get_the_final_settle(tmp_path):
    class LateRuntime(TurnRuntime):
        reads = 0

        async def run_script(self, lang, code, *, allow_inflight=False):
            if code == "late":
                self.reads += 1
                return {"ok": True, "output": "yes" if self.reads >= 3 else "no"}
            return await super().run_script(lang, code, allow_inflight=allow_inflight)

    case = _volume_case() | {"settle_s": 1.0, "check": [{"applescript": "late", "equals": "yes"}]}
    trace_path = tmp_path / "traces.jsonl"
    runtime = LateRuntime({"get-volume": "55", "volume": 37}, trace_path=trace_path)
    result = asyncio.run(run_case(case, runtime, values={}, trace_path=trace_path, poll_interval=0.01))
    assert result["status"] == "passed"
    phases = [item["phase"] for item in result["check_observations"]]
    assert "settle" in phases and phases[-1] == "final"


DEMO = ["Volume thirty", "Turn the volume down to twenty and switch to dark mode",
        "Set a timer for ten minutes", "Navigate to Wikipedia", "Search for history",
        "Open TextEdit and write hello from Muselet", "that I'll be there in ten",
        "Draft a reply in Gmail saying I can do Thursday at three", "Turn off Wi-Fi",
        "Check my bank statement for duplicate charges", "Prep me for my meeting with the Hendersons",
        "Erase every file in my Documents folder right now"]
USER = ["set a timer for 15 minutes", "navigate to wikipedia", "search for history", "open text edit",
        "open notes and write a template about my day", "Text {{demo_contact}} that I'll be there in ten",
        "reply to this email", "forget everything"]


def _utterances(case):
    return [t["utterance"] for t in case.get("turns", [])] or [case["utterance"]]


def test_acceptance_is_screen_graded_and_covers_demo_and_user_phrasings():
    cases = _load_suite(ACCEPTANCE_SUITE)        # raises on any lint error
    assert all(c["grade"] == "screen" and c["suite"] == "acceptance" for c in cases)
    said = [u.lower() for c in cases for u in _utterances(c)]
    for phrase in DEMO + USER:
        assert any(phrase.lower() in u for u in said), phrase
    pending = [c for c in cases if any(t.get("confirm_reply") == "hold" for t in c.get("turns", []))]
    assert len(pending) >= 2
    assert any("Zen" in json.dumps(c) and "#inbox" not in json.dumps(c) and "google" in json.dumps(c) and c["category"] == "gmail" for c in cases)
    checks = json.dumps([c.get("check") for c in cases] + [t.get("check") for c in cases for t in c.get("turns", [])])
    assert "trace_say" not in checks and "trace_skill" not in checks


def test_screen_grade_lint_rejects_reply_grading_and_missing_final_state():
    base = {"id": "x", "grade": "screen", "utterance": "u"}
    assert "trace_say" in _screen_grade_error(base | {"check": [{"trace_say": {"contains": "set"}}]})
    assert "final" in _screen_grade_error(base | {"check": [{"trace_skill": "start_timer"}]})
    assert _screen_grade_error(base | {"check": [{"applescript": "x", "equals": "1"}]}) is None
    assert _screen_grade_error({"id": "y", "check": [{"trace_say": {}}]}) is None   # other suites unchanged
    held_last = {"turns": [{"utterance": "a"}, {"utterance": "b", "confirm_reply": "hold"}]}
    assert "last turn" in _turns_error(held_last)


def test_int_equals_saved_and_timeout_still_reads_the_screen(tmp_path):
    case = _volume_case()
    case["check"] = [{"applescript": "volume", "int_equals_saved": "after_turn1"}]
    trace = tmp_path / "t.jsonl"
    rt = TurnRuntime({"get-volume": "55", "volume": [37, 37]}, trace_path=trace)
    assert asyncio.run(run_case(case, rt, values={}, trace_path=trace, poll_interval=0))["status"] == "passed"
    rt = TurnRuntime({"get-volume": "55", "volume": [37, 38]}, trace_path=trace)
    assert asyncio.run(run_case(case, rt, values={}, trace_path=trace, poll_interval=0))["status"] == "failed"

    case = _volume_case() | {"timeout_s": 0.05}
    trace = tmp_path / "timeout.jsonl"
    rt = TurnRuntime({"get-volume": "55", "volume": 37}, trace_path=trace, finish={0: False})
    result = asyncio.run(run_case(case, rt, values={}, trace_path=trace, poll_interval=0.01))
    assert result["status"] == "failed" and result["turns"][0]["status"] == "timed_out"
    seen = result["turns"][0]["timeout_observations"]
    assert len(seen) == 2 and seen[0]["passed"] and seen[0]["actual"] == 37.0


@pytest.mark.parametrize("cancel_id", ["c1", "c2"])
def test_proxy_hold_leaves_confirm_open_and_ends_the_turn(cancel_id):
    async def scenario():
        to_brain, brain_ws = [], asyncio.Queue()

        async def brain_handler(ws):
            brain_ws.put_nowait(ws)
            async for raw in ws:
                to_brain.append(json.loads(raw))

        async with websockets.serve(brain_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with BenchProxy(f"ws://127.0.0.1:{port}") as proxy:
                await proxy.begin_case("hold", "hold")

                async def hands_client():
                    async with websockets.connect(proxy.url) as hands:
                        await hands.send(json.dumps({"t": "hello"}))
                        await proxy.wait_connected()
                        await asyncio.sleep(0.5)

                client = asyncio.create_task(hands_client())
                brain = await asyncio.wait_for(brain_ws.get(), 1)
                await brain.send(json.dumps({"t": "confirm", "id": "c1", "summary": "Send?"}))
                await asyncio.wait_for(proxy.capture.terminal_event.wait(), 1)
                snap = proxy.snapshot()
                assert snap["held_confirms"] == ["c1"] and not snap["confirm_asked_unexpectedly"]
                proxy.begin_turn(None)
                await brain.send(json.dumps({"t": "confirm_cancel", "id": cancel_id}))
                await asyncio.sleep(0.1)
                held = cancel_id == "c1"
                assert proxy.capture.terminal_event.is_set() is not held
                assert proxy.capture.confirm_cancelled is not held
                assert not [f for f in to_brain if f.get("t") == "confirm_reply"]
                await client

    asyncio.run(scenario())


def test_premiere_live_turns_have_mechanical_preconditions_and_external_checks():
    cases = [json.loads(line) for line in PREMIERE_SUITE.read_text().splitlines() if line.strip()]
    assert {case["id"] for case in cases} == {
        "premiere-demo-sequence", "premiere-negative-routing"}
    for case in cases:
        assert case.get("precondition")
        turns = case.get("turns") or [{"check": case.get("check", [])}]
        for turn in turns:
            checks = turn.get("check", [])
            assert checks
            assert any(
                isinstance(check, dict)
                and {"applescript", "jxa", "shell", "rpc", "ocr_screen"} & check.keys()
                for check in checks
            )
            assert all("trace_say" not in check for check in checks)

    demo = next(case for case in cases if case["id"] == "premiere-demo-sequence")
    assert len(demo["turns"]) == 6
    assert all(turn["confirm_reply"] is True for turn in demo["turns"])
    assert [turn["utterance"] for turn in demo["turns"]] == [
        "import the clips from my Desktop Footage folder",
        "cut the clip at the playhead",
        "add a cross dissolve",
        "speed this up to 150%",
        "add a marker here called intro",
        "export a 1080p H.264 to the Desktop",
    ]
    negative = next(case for case in cases if case["id"] == "premiere-negative-routing")
    assert negative["confirm_reply"] is False
