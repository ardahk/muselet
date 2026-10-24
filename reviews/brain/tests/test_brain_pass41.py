"""Pass 41 repros (cloud/comms-2@265c86d)."""
import asyncio

import pytest

from brain import comms
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer

COMMS = {"messages_people", "contacts_search", "messages_compose", "messages_send"}


def make(tmp_path, goal, matches=None):
    handlers = {
        "messages_people": lambda _: {"people": []},
        "contacts_search": lambda _: {"matches": matches or []},
        "messages_compose": lambda _: {"ok": True, "frontmost": True, "body_visible": True},
        "messages_send": lambda _: {"ok": True, "sent": True},
    }
    server = FakeServer(handlers=handlers)
    o = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"),
                     engine=FakeEngine({goal: ("MULTI_STEP", 0.95)}, {}))
    return o, server


@pytest.mark.parametrize("goal", ["tell finder to empty the trash",
                                  "tell spotify to play jazz",
                                  "text size bigger please",
                                  "note buy milk"])
def test_brain38_non_messaging_command_hijacked_before_router(tmp_path, goal):
    """brain-38: comms.parse_message runs before the router on every utterance."""
    o, server = make(tmp_path, goal)
    asyncio.run(o.handle_utterance(goal))
    hit = [m for m, _ in server.rpcs if m in COMMS]
    assert hit == [], f"{goal!r} went to the Messages flow: {hit}"


def test_brain38_slack_request_composed_in_messages(tmp_path):
    """brain-38: 'on Slack' becomes the iMessage body for contact John."""
    goal = "send a message to John on Slack"
    john = {"id": "j", "name": "John", "handles": [
        {"kind": "phone", "value": "+15550000001", "label": "mobile"}]}
    o, server = make(tmp_path, goal, matches=[john])
    asyncio.run(o.handle_utterance(goal))
    composed = [p for m, p in server.rpcs if m == "messages_compose"]
    assert composed == [], f"composed into Messages: {composed}"


def test_brain38_channel_word_becomes_body():
    assert comms.parse_message("send whatsapp message to ali saying hi")["body"] == "hi"
