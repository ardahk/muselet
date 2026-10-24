import os
import time

import pytest

from bench.live.run_live import _local_ymd_hour


@pytest.fixture
def pacific():
    old = os.environ.get("TZ")
    os.environ["TZ"] = "America/Los_Angeles"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


def test_utc_start_graded_in_local_time(pacific):
    # live run 20261024T222159Z: a correct "friday at 3pm" event was failed by the UTC string check
    assert _local_ymd_hour("2026-10-30T22:00:00Z") == ("2026-10-30", 15)


def test_unpadded_date_and_naive_local_start(pacific):
    assert _local_ymd_hour("2027-01-08T15:30:00") == ("2027-1-8", 15)
    assert _local_ymd_hour("not a date") is None
