import pytest

import bench.harness.core as core


def pytest_configure(config):
    config.addinivalue_line("markers", "final_settle: keep the harness final-check settle window")


@pytest.fixture(autouse=True)
def _no_final_settle(monkeypatch, request):
    """Fake runtimes never change state after the outcome, so the final-check settle only adds wall time."""
    if "final_settle" not in request.keywords:
        monkeypatch.setattr(core, "FINAL_SETTLE_S", 0.0)
