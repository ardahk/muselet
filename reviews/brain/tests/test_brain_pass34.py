"""Pass 34 repros for cloud/brain-7 13432fe (run with PYTHONPATH=ml/src:ml/tests)."""
import asyncio
import threading

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from fakes import FakeServer

INSTALLED = ["Calendar", "Notes", "Safari", "Slack", "zoom.us",
             "Microsoft Teams", "Microsoft Outlook"]


@pytest.mark.parametrize("app,utterance", [
    ("Zoom", "open zoom"),
    ("Teams", "open teams"),
    ("Outlook", "open outlook"),
])
def test_brain29_installed_native_app_opens_website(app, utterance):
    """brain-29: installed Zoom/Teams/Outlook are replaced by their web apps."""
    async def go():
        server = FakeServer(apps={"running": [], "installed": INSTALLED})
        orch = Orchestrator(server, Catalog.load())
        orch._utterance = utterance
        await orch._run_skill("open_app", {"app": app}, utterance,
                              {"decisions": []})
        return server.skills()[-1]
    sk = asyncio.run(go())
    assert sk["name"] == "open_app", sk


def test_brain29_apps_rpc_failure_turns_every_site_name_into_url():
    """brain-29: one failed `apps` RPC caches [] and Slack (installed) opens slack.com."""
    async def go():
        def boom():
            raise RuntimeError("rpc timeout")
        server = FakeServer(apps=boom)
        orch = Orchestrator(server, Catalog.load())
        orch._utterance = "open slack"
        await orch._run_skill("open_app", {"app": "Slack"}, "open slack",
                              {"decisions": []})
        return server.skills()[-1]
    sk = asyncio.run(go())
    assert sk["name"] == "open_app", sk


def _orch_for_escalation(load_gate, calls):
    orch = Orchestrator(FakeServer(), Catalog.load())
    orch.planner = object()
    orch._sysctl_reader = lambda n: {"hw.memsize": 64 * 1024 ** 3,
                                     "kern.memorystatus_level": 60}[n]

    def loader(*a, **k):
        calls.append(1)
        load_gate.wait(5)
        return object()
    orch._escalate_loader = loader
    return orch


def test_brain30_toggle_off_during_load_leaves_35b_loaded():
    """brain-30: off arrives while the 35B loads; the load still installs it."""
    gate, calls = threading.Event(), []
    orch = _orch_for_escalation(gate, calls)

    async def go():
        on = asyncio.create_task(orch.set_escalation(True))
        await asyncio.sleep(0.05)
        off = await orch.set_escalation(False)
        gate.set()
        await on
        return off
    asyncio.run(go())
    assert orch.planner_escalate is None


def test_brain30_two_enables_load_two_35b_copies():
    """brain-30: two overlapping config frames load the 35B twice."""
    gate, calls = threading.Event(), []
    orch = _orch_for_escalation(gate, calls)

    async def go():
        a = asyncio.create_task(orch.set_escalation(True))
        b = asyncio.create_task(orch.set_escalation(True))
        await asyncio.sleep(0.05)
        gate.set()
        await asyncio.gather(a, b)
    asyncio.run(go())
    assert len(calls) == 1
