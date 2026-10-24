"""Protocol integration against the real BrainServer and Orchestrator."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "src"))

try:
    from brain import protocol
    from brain.catalog import Catalog
    from brain.orchestrator import Orchestrator
    from brain.server import BrainServer
    from brain.traces import Tracer
except ImportError as exc:  # pragma: no cover - depends on the ML environment
    pytest.skip(f"Brain dependencies unavailable: {exc}", allow_module_level=True)

from bench.harness.core import run_case
from bench.harness.proxy import BenchProxy
from bench.live import run_live


class FakePlanner:
    def __init__(self, turns):
        self.turns = turns
        self.calls = 0

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, script_output=None):
        lines = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        for line in lines:
            if cancel.is_set():
                break
            time.sleep(0.005)
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1, "decode_tok_s": 100,
                "tokens": len(lines), "plan_ms": 5}


class MultiStepEngine:
    def route(self, _text, _ctx):
        return SimpleNamespace(
            probs={"MULTI_STEP": 1.0}, top="MULTI_STEP", p_top=1.0,
            ms={"route_ms": 0.0},
        )


class FakePlannerWorker:
    def submit(self, fn, *args, **kwargs):
        future = concurrent.futures.Future()

        def run():
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as exc:
                future.set_exception(exc)

        threading.Thread(target=run, daemon=True).start()
        return future

    async def submit_async(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)


class FakeHandsRuntime:
    sent_scripts = []

    def __init__(self, proxy, _hands_bin, _log_dir, _case_id, *, cwd=None):
        self.proxy = proxy
        self.client = None
        self.scripts = []

    @property
    def utterance_monotonic(self):
        return self.proxy.capture.utterance_monotonic

    @property
    def first_action_monotonic(self):
        return self.proxy.capture.first_action_monotonic

    @property
    def terminal_monotonic(self):
        return self.proxy.capture.terminal_monotonic

    def snapshot(self):
        return self.proxy.snapshot()

    def mark_utterance_finished(self):
        self.proxy.mark_utterance_finished()

    async def start_scripts(self):
        if self.client is None or self.client.done():
            if self.client is not None:
                await self.proxy.wait_disconnected()
            await self._start_client()

    async def start_utterance(self, utterance):
        await self._stop_client()
        await self.proxy.wait_disconnected()
        await self._start_client(utterance)
        await self.proxy.wait_for_utterance()

    async def run_script(self, lang, code, *, allow_inflight=False):
        self.scripts.append(code)
        self.sent_scripts.append(code)
        return await self.proxy.run_script(
            lang, code, allow_inflight=allow_inflight
        )

    async def prepare_for_cleanup(self):
        if self.proxy.capture.active:
            await self._stop_client()
            self.proxy.mark_utterance_finished()
            await self.proxy.wait_disconnected()
            await self.start_scripts()

    async def stop(self):
        await self._stop_client()

    async def _start_client(self, utterance=None):
        self.client = asyncio.create_task(self._serve(utterance))
        await self.proxy.wait_connected()

    async def _stop_client(self):
        client, self.client = self.client, None
        if client is not None:
            if not client.done():
                client.cancel()
            try:
                await client
            except asyncio.CancelledError:
                pass
            await self.proxy.wait_disconnected()

    async def _serve(self, utterance):
        async with websockets.connect(self.proxy.url) as ws:
            await ws.send(json.dumps({"t": "hello", "screens": []}))
            if utterance is not None:
                await ws.send(json.dumps({
                    "t": "utterance", "id": "live-test", "text": utterance,
                    "final": True,
                }))
            while True:
                message = json.loads(await ws.recv())
                if message.get("t") != "rpc":
                    continue
                method = message.get("method")
                params = message.get("params", {})
                if method == "observe":
                    result = {
                        "epoch": 1,
                        "elements": [
                            {"ref": 1, "role": "button", "label": "Open",
                             "enabled": True, "frame": [0, 0, 10, 10]},
                        ],
                        "text": 'app: Finder | window: "Recents"',
                    }
                elif method == "act" and params.get("op") == "script":
                    code = params.get("code", "")
                    output = "30" if "output volume" in code else "false"
                    if code == "precondition sentinel":
                        output = "no"
                    result = {"output": output}
                elif method == "messages_people":
                    result = {"people": []}
                elif method == "contacts_search":
                    result = {"matches": [{
                        "id": "mom", "name": "Mom", "handles": [{
                            "kind": "phone", "value": "+15550100",
                            "label": "mobile"}]}]}
                elif method == "messages_compose":
                    result = {"ok": True, "frontmost": True,
                              "body_visible": True, "recipient_ok": True,
                              "window_title": "Mom"}
                else:
                    result = {"ok": True}
                await ws.send(json.dumps(protocol.rpc_result(
                    message["id"], True, result
                )))


async def _run_brain_case(text, *, planner=None, engine=None,
                          confirm_reply=None, trace_dir=None, monkeypatch=None):
    if planner is not None and monkeypatch is not None:
        worker = FakePlannerWorker()
        monkeypatch.setitem(
            sys.modules, "brain.planner", SimpleNamespace(worker=lambda: worker)
        )
    brain = BrainServer(port=0)
    await brain.start()
    orch = Orchestrator(
        brain, Catalog.load(), Tracer(trace_dir or ROOT / "runs/test-traces"),
        engine=engine,
    )
    orch.planner = planner
    calls = []
    confirms = []

    async def on_utterance(utterance, final, ctx=None):
        await orch.handle_utterance(utterance, ctx)

    brain.on_utterance = on_utterance
    try:
        async with BenchProxy(f"ws://127.0.0.1:{brain.port}") as proxy:
            await proxy.begin_case("integration", confirm_reply)

            async def hands():
                async with websockets.connect(proxy.url) as ws:
                    await ws.send(json.dumps({"t": "hello", "screens": []}))
                    await proxy.wait_connected()
                    await ws.send(json.dumps({
                        "t": "utterance", "id": "u1", "text": text, "final": True,
                    }))
                    for _ in range(40):
                        message = json.loads(await asyncio.wait_for(ws.recv(), 2))
                        if message.get("t") == "rpc":
                            calls.append(message)
                            method = message.get("method")
                            result = {"ok": True}
                            if method == "observe":
                                result.update({
                                    "epoch": 1, "elements": [
                                        {"ref": 1, "role": "button", "label": "Open",
                                         "enabled": True, "frame": [0, 0, 10, 10]},
                                    ],
                                    "text": 'app: Finder | window: "Recents"',
                                })
                            await ws.send(json.dumps(protocol.rpc_result(
                                message["id"], True, result)))
                        elif message.get("t") == "confirm":
                            confirms.append(message)
                            await ws.send(json.dumps(protocol.confirm_reply(
                                message["id"], bool(confirm_reply))))
                        elif message.get("t") == "ui" and message.get("mascot") in (
                            "success", "confused", "sleeping",
                        ):
                            break
                        elif message.get("t") == "say" and message.get("text") == "Okay, cancelled":
                            break

            await asyncio.wait_for(hands(), 10)
            await asyncio.sleep(0)
            snapshot = proxy.snapshot()
    finally:
        await brain.close()
    trace_path = next(Path(trace_dir).glob("*.jsonl"))
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
    return calls, confirms, snapshot, trace


def test_real_brain_regex_skill_through_bench_proxy(tmp_path):
    async def scenario():
        suite_case = next(
            json.loads(line)
            for line in (ROOT / "evals/live_t1.jsonl").read_text(encoding="utf-8").splitlines()
            if json.loads(line).get("id") == "sys-vol-set"
        )
        calls, confirms, _snapshot, _trace = await _run_brain_case(
            suite_case["utterance"], trace_dir=tmp_path
        )
        assert not confirms
        assert any(
            call["method"] == "skill"
            and call["params"]["name"] == "set_volume"
            and call["params"]["args"]["level"] == 30
            for call in calls
        )

    asyncio.run(scenario())


def test_real_brain_confirm_no_send_refuses_without_rpc(tmp_path, monkeypatch):
    async def scenario():
        calls, confirms, snapshot, trace = await _run_brain_case(
            "delete the old invoices folder",
            planner=FakePlanner([['confirm "Delete it?"', "press #1"]]),
            engine=MultiStepEngine(),
            confirm_reply=False,
            trace_dir=tmp_path,
            monkeypatch=monkeypatch,
        )
        assert snapshot["confirm_count"] == 1
        assert any(
            frame["frame"].get("t") == "confirm"
            and frame["frame"].get("summary") == "Delete it?"
            for frame in snapshot["frames"]
        )
        assert any(call["method"] == "observe" for call in calls)
        assert not any(call["method"] in ("act", "skill") for call in calls)
        assert trace["outcome"] == "cancelled"

    asyncio.run(scenario())


def test_real_brain_planner_path_executes_fake_hands_action(tmp_path, monkeypatch):
    async def scenario():
        calls, confirms, _snapshot, _trace = await _run_brain_case(
            "do it",
            planner=FakePlanner([["press #1"], ['done "all set"', 'expect appears "Open"']]),
            engine=MultiStepEngine(),
            trace_dir=tmp_path,
            monkeypatch=monkeypatch,
        )
        assert not confirms
        assert any(call["method"] == "act" for call in calls)

    asyncio.run(scenario())


def test_precondition_failure_does_not_send_teardown_through_proxy(tmp_path):
    class ProxyRuntime:
        def __init__(self, proxy):
            self.proxy = proxy

        def snapshot(self):
            return self.proxy.snapshot()

        async def start_scripts(self):
            await self.proxy.wait_connected()

        async def run_script(self, lang, code, *, allow_inflight=False):
            return await self.proxy.run_script(
                lang, code, allow_inflight=allow_inflight
            )

        async def stop(self):
            return None

    async def scenario():
        brain = BrainServer(port=0)
        await brain.start()
        received_scripts = []
        try:
            async with BenchProxy(f"ws://127.0.0.1:{brain.port}") as proxy:
                await proxy.begin_case("precondition", None)

                async def hands():
                    async with websockets.connect(proxy.url) as ws:
                        await ws.send(json.dumps({"t": "hello", "screens": []}))
                        while True:
                            message = json.loads(await ws.recv())
                            if message.get("t") != "rpc":
                                continue
                            received_scripts.append(message["params"]["code"])
                            await ws.send(json.dumps(protocol.rpc_result(
                                message["id"], True, {"output": "no"}
                            )))

                client = asyncio.create_task(hands())
                try:
                    result = await run_case(
                        {
                            "id": "precondition-fail",
                            "utterance": "must not run",
                            "precondition": [{"shell": "check precondition", "equals": "yes"}],
                            "teardown": [{"shell": "teardown sentinel"}],
                        },
                        ProxyRuntime(proxy),
                        values={},
                        trace_path=tmp_path / "unused.jsonl",
                    )
                finally:
                    client.cancel()
                    try:
                        await client
                    except asyncio.CancelledError:
                        pass
        finally:
            await brain.close()
        return result, received_scripts

    result, scripts = asyncio.run(scenario())
    assert result["status"] == "skipped"
    assert scripts == ["check precondition"]


def test_run_live_drives_real_brain_and_fake_hands_through_proxy(
    tmp_path, monkeypatch
):
    async def scenario():
        root = tmp_path / "root"
        trace_dir = root / "runs" / "traces"
        trace_dir.mkdir(parents=True)
        output = tmp_path / "output"
        monkeypatch.setattr(run_live, "ROOT", root)
        monkeypatch.setattr(run_live.Path, "home", lambda: tmp_path)
        monkeypatch.setattr(run_live, "HandsRuntime", FakeHandsRuntime)
        monkeypatch.setattr(
            run_live, "probe_session",
            lambda _binary: {
                "skip_reason": None, "session_probe": {"screen_locked": False},
            },
        )
        FakeHandsRuntime.sent_scripts = []
        worker = FakePlannerWorker()
        monkeypatch.setitem(
            sys.modules, "brain.planner", SimpleNamespace(worker=lambda: worker)
        )

        brain = BrainServer(port=0)
        await brain.start()
        orch = Orchestrator(
            brain, Catalog.load(), Tracer(trace_dir)
        )
        orch.planner = FakePlanner([
            ["press #1"],
            ['done "finished"', 'expect appears "Open"'],
        ])

        async def on_utterance(utterance, _final, ctx=None):
            orch.engine = None if utterance == volume_case["utterance"] else MultiStepEngine()
            await orch.handle_utterance(utterance, ctx)

        brain.on_utterance = on_utterance
        suite_path = ROOT / "evals/live_t1.jsonl"
        suite_cases = [
            json.loads(line)
            for line in suite_path.read_text(encoding="utf-8").splitlines()
        ]
        volume_case = next(case for case in suite_cases if case["id"] == "sys-vol-set")
        confirm_case = dict(next(
            case for case in suite_cases if case["id"] == "confirm-no-send"
        ), manual=False)
        cases = [
            volume_case,
            confirm_case,
            {
                "id": "planner-path",
                "tier": "T1",
                "category": "app",
                "utterance": "planner integration",
                "expect_outcome": "ok",
                "check": [],
                "timeout_s": 5,
            },
            {
                "id": "precondition-fail",
                "tier": "T1",
                "category": "system",
                "utterance": "must not run",
                "precondition": [
                    {"shell": "precondition sentinel", "equals": "yes"}
                ],
                "teardown": [{"shell": "teardown sentinel"}],
            },
        ]
        args = SimpleNamespace(
            suite=suite_path,
            tier=set(),
            category=set(),
            id=set(),
            repeat=1,
            brain_url=f"ws://127.0.0.1:{brain.port}",
            proxy_port=0,
            hands_bin="fake-hands",
            include_manual=False,
            include_pending=False,
            allow_user_ok=False,
            offline=False,
            no_safety_guard=False,
            setup_bench_calendar=False,
            out=output,
        )
        try:
            assert await run_live._run_live(cases, args) == 0
        finally:
            await brain.close()
        records = [
            json.loads(line)
            for line in (output / "results.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        return records

    records = asyncio.run(scenario())
    by_id = {record["id"]: record for record in records}
    assert by_id["sys-vol-set"]["strict_pass"] is True
    assert by_id["confirm-no-send"]["observed_outcome"] == "cancelled"
    assert by_id["confirm-no-send"]["confirm_count"] == 1
    assert not any(
        call.get("method") == "skill"
        and call.get("params", {}).get("name") == "send_message"
        for call in by_id["confirm-no-send"]["trace"]["rpc"]
    )
    assert by_id["planner-path"]["strict_pass"] is True
    assert by_id["precondition-fail"]["status"] == "skipped"
    assert "precondition sentinel" in FakeHandsRuntime.sent_scripts
    assert "teardown sentinel" not in FakeHandsRuntime.sent_scripts
