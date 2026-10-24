import asyncio
import json
from argparse import Namespace

from bench.harness import proxy as proxy_module
from bench.hobbylm import replay


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
