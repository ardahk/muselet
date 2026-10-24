from pathlib import Path

import pytest

from bench.hobbylm.hobby_worker import SafetyBlocked, run_task


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
    from bench.hobbylm.hobby_worker import _guard_native_helpers

    _guard_native_helpers(FakeHelper, mcp, events.append)
    with pytest.raises(SafetyBlocked, match="blocked by bench safety guard"):
        mcp.call("send_message", {})
    with pytest.raises(SafetyBlocked, match="blocked by bench safety guard"):
        FakeHelper.CAL.create_event(None, "Muselet Bench", "UTC", with_invite=True)
    assert [event["ev"] for event in events] == ["safety_blocked", "safety_blocked"]


def test_worker_refuses_and_records_confirmation_requests():
    events = []
    from bench.hobbylm.hobby_worker import _guard_native_helpers

    mcp = FakeMCP()
    _guard_native_helpers(FakeHelper, mcp, events.append)
    result = mcp.call("confirm_send", {})
    assert result == {"ok": False, "confirmed": False, "yes": False}
    assert events == [{"ev": "confirm_asked", "helper": "confirm_send"}]
