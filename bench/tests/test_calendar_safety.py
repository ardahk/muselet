import json
import subprocess

import pytest

from bench.hobbylm import calendar_safety
from bench.live.run_live import _is_event_case


@pytest.mark.parametrize(
    "result",
    [
        {"exists": False, "source_type": None, "is_default_for_new_events": False},
        {"exists": True, "source_type": "caldav", "is_default_for_new_events": True},
        {"exists": True, "source_type": "local", "is_default_for_new_events": False},
    ],
)
def test_event_cases_are_eligible_only_for_local_default_calendar(result):
    assert not calendar_safety.is_local_default(result)


def test_local_default_calendar_is_eligible():
    assert calendar_safety.is_local_default({
        "exists": True,
        "source_type": "local",
        "source_title": "On My Mac",
        "is_default_for_new_events": True,
    })


def test_live_event_case_identification_is_narrow():
    assert _is_event_case({"id": "time-event", "category": "time"})
    assert _is_event_case({"id": "x", "category": "event"})
    assert not _is_event_case({"id": "time-agenda", "category": "time"})


def test_calendar_setup_refuses_remote_source_under_mock(monkeypatch):
    monkeypatch.setattr(calendar_safety.sys, "platform", "darwin")
    monkeypatch.setattr(
        calendar_safety,
        "_eventkit",
        lambda action: {
            "exists": True,
            "source_type": "caldav",
            "source_title": "iCloud",
            "is_default_for_new_events": True,
        },
    )
    with pytest.raises(RuntimeError, match="outside a local Calendar source"):
        calendar_safety.setup_bench_calendar()


def test_calendar_setup_refuses_when_local_source_is_unavailable(monkeypatch):
    monkeypatch.setattr(calendar_safety.sys, "platform", "darwin")

    def no_local_source(_action):
        raise RuntimeError(
            "No local Calendar source (On My Mac) is available; no calendar was created."
        )

    monkeypatch.setattr(calendar_safety, "_eventkit", no_local_source)
    with pytest.raises(RuntimeError, match="no calendar was created"):
        calendar_safety.setup_bench_calendar()


def test_eventkit_probe_parses_output_without_following_remote_calendar(monkeypatch):
    monkeypatch.setattr(calendar_safety.sys, "platform", "darwin")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0], 0,
            stdout=json.dumps({
                "exists": True,
                "source_type": "exchange",
                "source_title": "Work",
                "is_default_for_new_events": True,
            }),
            stderr="",
        )

    monkeypatch.setattr(calendar_safety.subprocess, "run", fake_run)
    result = calendar_safety.probe_bench_calendar()
    assert result["source_type"] == "exchange"
    assert not calendar_safety.is_local_default(result)
