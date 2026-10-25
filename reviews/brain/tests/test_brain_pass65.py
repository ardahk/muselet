"""brain-49: _page_task_for preempts messaging/reminders whenever a browser page is focused."""
import pytest
from brain.orchestrator import Orchestrator


@pytest.mark.parametrize("text", [
    "text mom what's on this page",
    "message john I found the charger on this page",
    "remind me to check the price on this page tomorrow",
])
def test_non_page_requests_are_not_page_tasks(text):
    if not hasattr(Orchestrator, "_page_task_for"):
        pytest.skip("no _page_task_for on this branch")
    o = Orchestrator.__new__(Orchestrator)
    o._ctx = {"app": "Safari"}
    o._focus_ctx = {"url": "https://www.amazon.com/s?k=usb"}
    assert o._page_task_for(text) is None, o._page_task_for(text)
