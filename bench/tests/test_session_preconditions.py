import asyncio
import json
import subprocess
from argparse import Namespace
from types import SimpleNamespace

import pytest

from bench.harness.session import probe_session
from bench.hobbylm import replay
from bench.live import run_live
from bench.deskmind import run_muselet


def _completed(payload, code=0):
    return subprocess.CompletedProcess([], code, json.dumps(payload), "")


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"screen_locked": True}, "screen_locked"),
        ({"screen_locked": False, "main_display_asleep": True}, "screen_locked"),
        ({"screen_locked": False, "main_display_asleep": False}, None),
        ({"screen_locked": "false"}, "session_unverifiable"),
    ],
)
def test_session_probe_classifies_locked_asleep_and_unlocked(payload, reason):
    seen = {}
    result = probe_session(
        "/fake/hands",
        run=lambda command, **kwargs: (
            seen.update(command=command, **kwargs) or _completed(payload)
        ),
    )
    assert seen["command"] == ["/fake/hands", "probe", "session"]
    assert seen["timeout"] == 5
    assert result["skip_reason"] == reason


@pytest.mark.parametrize("failure", [
    subprocess.CompletedProcess([], 1, "{}", ""),
    subprocess.CompletedProcess([], 0, "garbage", ""),
    subprocess.TimeoutExpired("hands probe session", 5),
])
def test_session_probe_failures_are_unverifiable(failure):
    def run(*args, **kwargs):
        if isinstance(failure, BaseException):
            raise failure
        return failure
    assert probe_session("hands", run=run)["skip_reason"] == "session_unverifiable"


def test_live_locked_session_skips_before_creating_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(run_live.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(run_live, "_git_sha", lambda: "test")
    monkeypatch.setattr(
        run_live, "probe_session",
        lambda _binary: {"skip_reason": "screen_locked", "session_probe": {"screen_locked": True}},
    )
    class Proxy:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(run_live, "BenchProxy", lambda *args, **kwargs: Proxy())
    monkeypatch.setattr(run_live, "HandsRuntime", lambda *args, **kwargs: pytest.fail("runtime started"))
    args = Namespace(
        out=tmp_path / "out", brain_url="ws://localhost", proxy_port=1,
        no_safety_guard=False, repeat=1, hands_bin="hands",
        suite=run_live.ROOT / "evals/live_t1.jsonl",
        setup_bench_calendar=False, tier=set(), category=set(), id=set(),
        include_manual=False, include_pending=False, offline=False,
        allow_user_ok=False,
    )
    asyncio.run(run_live._run_live([{"id": "case", "utterance": "x"}], args))
    record = json.loads((args.out / "results.jsonl").read_text())
    assert record["skip_reason"] == "screen_locked"
    assert record["session_probe"] == {"screen_locked": True}


def test_replay_muselet_locked_session_does_not_start_runtime(monkeypatch, tmp_path, capsys):
    class Proxy:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def wait_disconnected(self): pytest.fail("case runtime started")
    import bench.harness.proxy
    monkeypatch.setattr(bench.harness.proxy, "BenchProxy", Proxy)
    monkeypatch.setattr(
        replay, "probe_session",
        lambda _binary: {"skip_reason": "screen_locked", "session_probe": {"screen_locked": True}},
    )
    args = Namespace(
        port=1, proxy_port=2, repeats=1, hands_bin="hands", round="r4",
        timeout=1, setup_bench_calendar=False,
    )
    task = {"id": "T01", "kind": "timer", "text": "timer"}
    asyncio.run(replay._run_muselet_cases(args, [task], tmp_path, object()))
    assert '"skip_reason": "screen_locked"' in capsys.readouterr().out


def test_replay_hobbylm_locked_task_never_reaches_worker(monkeypatch):
    class Input:
        def write(self, _value): pytest.fail("locked task sent to worker")
        async def drain(self): pytest.fail("worker drained")
    monkeypatch.setattr(
        replay, "probe_session",
        lambda _binary: {"skip_reason": "screen_locked", "session_probe": {"screen_locked": True}},
    )
    record = asyncio.run(replay._run_hobby_worker_case(
        SimpleNamespace(stdin=Input()), object(),
        {"id": "N01", "kind": "none", "text": "nothing", "expected": "NONE"},
        1, hands_bin="hands",
    ))
    assert record["skip_reason"] == "screen_locked"


def test_hobbylm_event_calendar_probe_is_lazy_and_cached_across_cases(monkeypatch):
    sessions = iter([
        {"skip_reason": "screen_locked", "session_probe": {"screen_locked": True}},
        {"skip_reason": None, "session_probe": {"screen_locked": False}},
        {"skip_reason": None, "session_probe": {"screen_locked": False}},
    ])
    monkeypatch.setattr(replay, "probe_session", lambda _binary: next(sessions))
    calls = []
    monkeypatch.setattr(
        replay, "_probe_hobby_event_calendar",
        lambda setup: calls.append(setup) or False,
    )
    cache = {"checked": False, "allowed": None}
    proc = object()
    helper = object()
    tasks = [
        {"id": f"E{index}", "kind": "event", "expected": "EVENT",
         "text": "create an event"}
        for index in range(1, 4)
    ]

    async def scenario():
        records = []
        for task in tasks:
            records.append(await replay._run_hobby_worker_case(
                proc, helper, task, 1, hands_bin="hands",
                setup_bench_calendar=True, event_probe_cache=cache,
            ))
        return records

    records = asyncio.run(scenario())
    assert [record["skip_reason"] for record in records] == [
        "screen_locked", "bench calendar not local default",
        "bench calendar not local default",
    ]
    assert calls == [True]


def test_deskmind_locked_session_is_logged_without_document_guard(monkeypatch, tmp_path):
    monkeypatch.setattr(
        run_muselet, "probe_session",
        lambda _binary: {"skip_reason": "screen_locked", "session_probe": {"screen_locked": True}},
    )
    monkeypatch.setattr(run_muselet.asyncio, "run", lambda *_: pytest.fail("document guard ran"))
    task = SimpleNamespace(id="D1", goal="task")
    assert run_muselet._guard_before_run(
        task, 1, tmp_path, tmp_path / "run", "hands"
    ) is None
    record = json.loads((tmp_path / "skipped.jsonl").read_text())
    assert record["skip_reason"] == "screen_locked"
    assert record["session_probe"] == {"screen_locked": True}
