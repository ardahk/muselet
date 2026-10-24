import asyncio
import threading
import weakref

from brain.orchestrator import Orchestrator
from fakes import FakeServer


def _orch(gate, calls):
    orch = Orchestrator(FakeServer())
    orch.planner = object()
    orch._sysctl_reader = lambda name: {
        "hw.memsize": 64 * 1024 ** 3, "kern.memorystatus_level": 60}[name]

    class Planner:
        pass

    def loader(*args, **kwargs):
        planner = Planner()
        calls.append(weakref.ref(planner))
        assert gate.wait(5)
        return planner

    orch._escalate_loader = loader
    return orch


async def _loading(calls):
    async with asyncio.timeout(5):
        while not calls:
            await asyncio.sleep(0.001)


def test_brain30_toggle_off_during_load_leaves_no_planner():
    gate, calls = threading.Event(), []
    orch = _orch(gate, calls)

    async def scenario():
        on = asyncio.create_task(orch.set_escalation(True))
        await _loading(calls)
        assert await asyncio.wait_for(orch.set_escalation(False), 1) == {"loaded": False}
        gate.set()
        assert await on == {"loaded": False}
        assert orch.planner_escalate is None
        assert calls[0]() is None

    asyncio.run(scenario())


def test_brain30_two_enables_load_one_copy():
    gate, calls = threading.Event(), []
    orch = _orch(gate, calls)

    async def scenario():
        first = asyncio.create_task(orch.set_escalation(True))
        await _loading(calls)
        second = asyncio.create_task(orch.set_escalation(True))
        gate.set()
        assert await asyncio.gather(first, second) == [{"loaded": True}] * 2
        assert len(calls) == 1
        assert orch.planner_escalate is calls[0]()

    asyncio.run(scenario())


def test_escalation_checks_memory_after_waiting_for_lock():
    gate, calls = threading.Event(), []
    orch = _orch(gate, calls)

    async def scenario():
        await orch._escalate_lock.acquire()
        enable = asyncio.create_task(orch.set_escalation(True))
        await asyncio.sleep(0)
        orch._sysctl_reader = lambda name: 0
        orch._escalate_lock.release()
        assert await enable == {"loaded": False, "reason": "needs 48 GB RAM"}
        assert not calls

    asyncio.run(scenario())
