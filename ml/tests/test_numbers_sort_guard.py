"""Numbers sort-goal guard: cell-rewrite scripts rejected before RPC."""
import asyncio

import pytest
from fakes import FakeServer, FakeEngine
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from test_fallback_planner import CaptureTracer

BAD = '''tell application "Numbers"
    set value of cell "A1" to "X"
    set value of cell "B1" to 2
end tell'''
BAD_EVERY = '''tell application id "com.apple.Numbers"
    set every cell of range "A1:D5" to missing value
end tell'''
NATIVE = '''tell application "Numbers"
    sort table "T" of sheet 1 of document 1 by column 2 descending
end tell'''
READ = '''tell application "Numbers"
    set headerValues to value of cells of row 1 of table "T"
end tell'''


def _orch(server, tmp_path):
    o = Orchestrator(server, Catalog.load(), CaptureTracer(tmp_path / "t"),
                     engine=FakeEngine())
    o._ctx["app"] = "Numbers"
    o._current_goal = "sort the Amount column largest first"
    return o


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.mark.parametrize("entrypoint", ["exec", "script"])
def test_sort_goal_rejects_cell_rewrite(tmp_path, entrypoint):
    server = FakeServer()
    o = _orch(server, tmp_path)
    if entrypoint == "exec":
        r = run(o._exec_action({"op": "script", "lang": "applescript",
                                "code": BAD}))
        assert r["status"] == "failed"
        assert "native" in r["error"]
    else:
        assert run(o._script({"lang": "applescript", "code": BAD})) != "ok"
    assert all(m != "act" for m, _ in server.rpcs)
    assert not server.confirms


def test_order_goal_and_bundle_id_also_guarded(tmp_path):
    server = FakeServer()
    o = _orch(server, tmp_path)
    o._current_goal = "order rows by Amount descending"
    assert o._numbers_sort_script_error("applescript", BAD_EVERY)


def test_native_sort_and_header_reads_allowed(tmp_path):
    server = FakeServer()
    o = _orch(server, tmp_path)
    assert o._numbers_sort_script_error("applescript", NATIVE) is None
    assert o._numbers_sort_script_error("applescript", READ) is None


def test_set_value_allowed_when_goal_is_edit_not_sort(tmp_path):
    server = FakeServer()
    o = _orch(server, tmp_path)
    o._current_goal = "edit cell A1 to say hello"
    assert o._numbers_sort_script_error("applescript", BAD) is None
    # non-Numbers targets untouched
    o._current_goal = "sort the Amount column largest first"
    assert o._numbers_sort_script_error(
        "applescript", BAD.replace("Numbers", "Excel")) is None
