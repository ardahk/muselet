"""brain-63 (cloud/browser-flow 3620880): the web UI guard refuses any url
with '?' on the host the browser already shows, including opening a result
(youtube watch?v=, an amazon product link with a query string)."""
import pytest
from brain.orchestrator import Orchestrator


@pytest.mark.parametrize("current,url", [
    ("https://www.youtube.com/results?search_query=lofi",
     "https://www.youtube.com/watch?v=jfKfPfyJRdk"),
    ("https://www.amazon.com/s?k=usb+c+cable",
     "https://www.amazon.com/dp/B0ABC12345?th=1"),
])
def test_opening_a_result_link_is_not_a_hand_built_search(current, url):
    if not hasattr(Orchestrator, "_hand_built_search"):
        pytest.skip("no web UI guard on this branch")
    o = Orchestrator.__new__(Orchestrator)
    o._last_ok_url, o._page_task = current, None
    o._ctx, o._focus_ctx = {"app": "Safari"}, {}
    assert not o._hand_built_search(url, "Safari")
