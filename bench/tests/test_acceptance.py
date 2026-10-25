"""evals/acceptance.jsonl and the runner support it needs: held confirms,
screen-only grading lint, int_equals_saved, screen read on timeout."""
import asyncio
import json
from pathlib import Path

import pytest
import websockets

from bench.harness.core import run_case
from bench.harness.proxy import BenchProxy
from bench.live.run_live import _load_suite, _screen_grade_error, _turns_error
from bench.tests.test_live_turns import TurnRuntime, _volume_case

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "evals/acceptance.jsonl"
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
    cases = _load_suite(SUITE)        # raises on any lint error
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
