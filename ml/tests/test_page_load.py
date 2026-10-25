"""web_loaded (AXLoaded) / web_busy are the authoritative page-load signal."""
import asyncio
import time

import pytest
from fakes import FakeServer, FakeEngine
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from test_fallback_planner import CaptureTracer


def _orch(server, tmp_path):
    o = Orchestrator(server, Catalog.load(), CaptureTracer(tmp_path / "t"),
                     engine=FakeEngine())
    o.LOAD_POLL_S, o.LOAD_WAIT_S = 0, 0.05
    return o


def _obs(web_loaded="missing", web_busy="missing", app="Zen",
         window="x"):
    o = {"epoch": 2, "app": app, "window": window, "elements": [],
         "text": f'app: {app} | window: "{window}"', "ax_ms": 1}
    if web_loaded != "missing":
        o["web_loaded"] = web_loaded
    if web_busy != "missing":
        o["web_busy"] = web_busy
    return o


# --- _page_loading matrix ---------------------------------------------------

def test_web_loaded_overrides_loading_title(tmp_path):
    o = _orch(FakeServer(), tmp_path)
    assert o._page_loading(_obs(True, window="New Tab")) is False
    assert o._page_loading(_obs(False)) is True
    assert o._page_loading(_obs(True, True)) is True    # busy extends
    assert o._page_loading(_obs("missing", True)) is True   # busy-only
    assert o._page_loading(_obs("missing", False,
                                window="Inbox")) is False   # busy cleared
    assert o._page_loading(_obs(None)) is False          # null -> heuristics
    assert o._page_loading(_obs(window="")) is True      # no signal -> bare
    assert o._page_loading(_obs(app="Finder")) is False  # non-browser


# --- _await_page_load -------------------------------------------------------

@pytest.mark.anyio
async def test_await_one_observe_when_already_loaded(tmp_path):
    server = FakeServer(observe=lambda: _obs(True))
    o = _orch(server, tmp_path)
    await o._await_page_load()
    assert [m for m, _ in server.rpcs] == ["observe"]


@pytest.mark.anyio
async def test_await_polls_until_loaded(tmp_path):
    states = iter([_obs(False), _obs(False), _obs(True)])
    o_cache = _obs(True)
    server = FakeServer(observe=lambda: next(states, _obs(True)))
    o = _orch(server, tmp_path)
    o._obs_seen = (0.0, o_cache)      # stale cache says loaded; fresh wins
    await o._await_page_load(cap=2)
    assert len([m for m, _ in server.rpcs if m == "observe"]) == 3


@pytest.mark.anyio
async def test_await_busy_only_then_clear(tmp_path):
    states = iter([_obs(web_busy=True), _obs(web_busy=True),
                   _obs(web_busy=False)])
    server = FakeServer(observe=lambda: next(states, _obs(web_busy=False)))
    o = _orch(server, tmp_path)
    await o._await_page_load(cap=2)
    assert len([m for m, _ in server.rpcs if m == "observe"]) == 3


@pytest.mark.anyio
async def test_await_loaded_but_busy_keeps_waiting(tmp_path):
    states = iter([_obs(False), _obs(True, True), _obs(True, False)])
    server = FakeServer(observe=lambda: next(states, _obs(True)))
    o = _orch(server, tmp_path)
    await o._await_page_load(cap=2)
    assert len([m for m, _ in server.rpcs if m == "observe"]) == 3


@pytest.mark.anyio
async def test_await_no_signal_or_none_obs_returns(tmp_path):
    server = FakeServer(observe=lambda: _obs())
    o = _orch(server, tmp_path)
    await o._await_page_load()                    # no signal -> return
    server.observe = lambda: None
    await o._await_page_load()                    # None obs -> safe
    assert len([m for m, _ in server.rpcs if m == "observe"]) == 2


# --- _wait_ms ---------------------------------------------------------------

@pytest.mark.anyio
async def test_wait_plain_sleep_without_signal(tmp_path):
    server = FakeServer(observe=lambda: _obs())
    o = _orch(server, tmp_path)
    o._obs_seen = (0.0, _obs())
    await o._wait_ms(50)
    assert all(m != "observe" for m, _ in server.rpcs)


@pytest.mark.anyio
async def test_wait_floor_counts_inside_deadline(tmp_path, monkeypatch):
    """Virtual clock: total sleep <= requested ms; floor is inside it."""
    slept = []
    now = [0.0]
    async def fake_sleep(s):
        slept.append(s); now[0] += s
    monkeypatch.setattr("brain.orchestrator.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("brain.orchestrator.time.perf_counter",
                        lambda: now[0])
    server = FakeServer(observe=lambda: _obs(True))
    o = _orch(server, tmp_path)
    o._obs_seen = (0.0, _obs(False))
    await o._wait_ms(180)
    assert sum(slept) <= 0.18001 and slept[0] == 0.15


@pytest.mark.anyio
async def test_wait_respects_busy(tmp_path):
    states = iter([_obs(True, True), _obs(True, False)])
    server = FakeServer(observe=lambda: next(states, _obs(True)))
    o = _orch(server, tmp_path)
    o._obs_seen = (0.0, _obs(False))
    await o._wait_ms(400)
    assert len([m for m, _ in server.rpcs if m == "observe"]) == 2


@pytest.mark.anyio
async def test_wait_busy_only_and_deadline(tmp_path, monkeypatch):
    """busy-only signal: clear counts as done; deadline bounds the loop."""
    now = [0.0]
    async def fake_sleep(s):
        now[0] += s
    monkeypatch.setattr("brain.orchestrator.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("brain.orchestrator.time.perf_counter",
                        lambda: now[0])
    # busy clears -> exit before deadline
    states = iter([_obs(web_busy=True), _obs(web_busy=False)])
    server = FakeServer(observe=lambda: next(states, _obs(web_busy=False)))
    o = _orch(server, tmp_path)
    o.LOAD_POLL_S = 0.1
    o._obs_seen = (0.0, _obs(web_busy=True))
    await o._wait_ms(900)
    assert now[0] < 0.9
    # never clears -> stops at the deadline, not past it
    server.observe = lambda: _obs(web_busy=True)
    o._obs_seen = (0.0, _obs(web_busy=True))
    now[0] = 0.0
    await o._wait_ms(250)
    assert now[0] <= 0.251


# --- _repoll_loading --------------------------------------------------------

@pytest.mark.anyio
async def test_repoll_stops_on_loaded_signal(tmp_path):
    states = iter([_obs(False), _obs(True)])
    server = FakeServer(observe=lambda: next(states, _obs(True)))
    o = _orch(server, tmp_path)
    vres, loading = await o._repoll_loading('appears "x"',
                                          {"ok": False, "observed": {}})
    assert loading is False                    # page loaded -> stopped
    # busy-only clearing also stops the wait
    states = iter([_obs(web_busy=True), _obs(web_busy=False)])
    server.observe = lambda: next(states, _obs(web_busy=False))
    vres, loading = await o._repoll_loading('appears "x"',
                                          {"ok": False, "observed": {}})
    assert loading is False


# --- navigation hook in _rpc_action -----------------------------------------

@pytest.mark.anyio
async def test_nav_hook_invoked_once_for_url_and_skill(tmp_path):
    server = FakeServer(observe=lambda: _obs(True))
    o = _orch(server, tmp_path)
    calls = []
    async def counter():
        calls.append(1)
    o._await_page_load = counter
    await o._rpc_action("act", {"op": "url", "url": "https://x"},
                        {"op": "url", "url": "https://x"})
    await o._rpc_action("skill", {"name": "open_url",
                                  "args": {"url": "https://x"}},
                        {"op": "skill", "name": "open_url"})
    assert len(calls) == 2


@pytest.mark.anyio
async def test_nav_hook_browser_only_for_press(tmp_path):
    server = FakeServer(observe=lambda: _obs(True))
    o = _orch(server, tmp_path)
    calls = []
    async def counter():
        calls.append(1)
    o._await_page_load = counter
    o._obs_seen = (0.0, _obs(app="TextEdit"))    # non-browser cached
    await o._rpc_action("act", {"op": "press", "ref": 3},
                        {"op": "press", "ref": 3})
    o._obs_seen = (0.0, _obs(app="Zen"))         # browser cached
    await o._rpc_action("act", {"op": "press", "ref": 4},
                        {"op": "press", "ref": 4})
    assert len(calls) == 1


@pytest.mark.anyio
async def test_nav_hook_type_enter_and_keys(tmp_path):
    server = FakeServer(observe=lambda: _obs(True))
    o = _orch(server, tmp_path)
    calls = []
    async def counter():
        calls.append(1)
    o._await_page_load = counter
    o._obs_seen = (0.0, _obs(app="Zen"))
    for action in ({"op": "type", "ref": 3, "text": "q", "enter": True},
                   {"op": "keys", "combo": "return"},
                   {"op": "keys", "combo": "Enter"}):
        params = {k: v for k, v in action.items() if k != "op"}
        await o._rpc_action("act", params, action)
    assert len(calls) == 3


@pytest.mark.anyio
async def test_nav_hook_same_tab_skill_via_exec(tmp_path):
    """A url op inside an open page task resolves to `skill open_url
    same_tab`; the navigation hook fires exactly once."""
    server = FakeServer(observe=lambda: _obs(True))
    o = _orch(server, tmp_path)
    calls = []
    async def counter():
        calls.append(1)
    o._await_page_load = counter
    o._page_task = {"app": "Zen", "site": "example.com",
                    "url": "https://example.com"}
    o._ctx["app"] = "Zen"
    o._current_goal = "open example.com"
    o._obs_seen = (0.0, _obs(app="Zen"))
    await o._exec_action({"op": "url",
                          "url": "https://example.com/other"})
    skills = [p for m, p in server.rpcs if m == "skill"]
    assert (len(calls) == 1 and skills and
            skills[-1].get("name") == "open_url" and
            (skills[-1].get("args") or {}).get("same_tab") is True)
