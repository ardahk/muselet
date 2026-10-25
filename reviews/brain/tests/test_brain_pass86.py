"""brain-74 (main 93ca931): the pre-routing destructive-request gate matches
any delete/remove/format verb followed anywhere by all/every/entire, and any
'all files', so ordinary requests are refused before routing."""
import asyncio
import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer, FakeEngine


@pytest.mark.parametrize("text", [
    "show all files in Downloads",
    "delete all completed reminders",
    "remove all items from my cart",
    "delete the spam email and archive all the others",
])
def test_ordinary_request_is_not_refused_as_destructive(tmp_path, text):
    server = FakeServer()
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"),
                        engine=FakeEngine())
    try:
        asyncio.run(asyncio.wait_for(orch.handle_utterance(
            text, {"app": "Finder", "focused": "none", "selection": False,
                   "online": True}), 20))
    except Exception:
        pass
    assert not any("can't do that" in s for s in server.said), server.said
