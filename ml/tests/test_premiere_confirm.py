import asyncio

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer


def make_orch(tmp_path, **kwargs):
    return Orchestrator(FakeServer(**kwargs), Catalog.load(),
                        Tracer(tmp_path / "traces"))


async def execute(orch, entry, args):
    action = {"op": "skill", "name": "premiere_command", "args": args}
    if entry == "planner":
        return (await orch._exec_one(action))["status"]
    return await orch.execute_actions([action])


@pytest.mark.parametrize("command", [
    "razor_at_playhead", "undo", "add_marker", "export",
])
@pytest.mark.parametrize("entry", ["planner", "fast"])
@pytest.mark.parametrize("yes", [True, False])
def test_architect27_edits_require_named_confirm(tmp_path, command, entry, yes):
    orch = make_orch(tmp_path)
    orch.server.confirm_yes = yes
    orch._batch_confirmed = True
    summary = f"Premiere: {command.replace('_', ' ')}?"

    def skill(params):
        assert orch.server.confirms == [summary]
        assert params["args"]["confirmed"] is True
        return {"ok": True, "result": {}}

    orch.server.handlers["skill"] = skill
    status = asyncio.run(execute(
        orch, entry, {"command": command, "confirmed": True}))

    assert orch.server.confirms == [summary]
    assert status == ("ok" if yes else "cancelled")
    assert len(orch.server.skills()) == int(yes)


@pytest.mark.parametrize("command", ["play_toggle", "go_to_start", "go_to_end"])
@pytest.mark.parametrize("entry", ["planner", "fast"])
def test_architect27_playback_and_navigation_stay_safe(tmp_path, command, entry):
    orch = make_orch(tmp_path)
    assert asyncio.run(execute(orch, entry, {"command": command})) == "ok"
    assert orch.server.confirms == []
    assert len(orch.server.skills()) == 1


@pytest.mark.parametrize("args", [{}, {"command": ""}, {"command": "ripple_delete"}])
def test_architect27_unknown_commands_default_to_confirm(tmp_path, args):
    orch = make_orch(tmp_path)
    assert orch._skill_risk("premiere_command", args) == "confirm"


@pytest.mark.parametrize("entry", ["planner", "fast"])
def test_architect27_confirm_timeout_never_executes(tmp_path, entry):
    orch = make_orch(tmp_path, confirm_raises=True)
    try:
        status = asyncio.run(execute(orch, entry, {"command": "undo"}))
        assert status == "cancelled"
    except RuntimeError as error:
        assert str(error) == "timeout"
    assert orch.server.confirms == ["Premiere: undo?"]
    assert orch.server.skills() == []


def test_architect27_empty_command_asks_for_command_without_executing(tmp_path):
    orch = make_orch(tmp_path)
    assert asyncio.run(execute(orch, "fast", {})) == "awaiting_user"
    assert orch.server.skills() == []


def test_architect27_never_downgrades_catalog_risk(tmp_path):
    orch = make_orch(tmp_path)
    orch.catalog.skills["premiere_command"]["risk"] = "confirm"
    assert orch._skill_risk("premiere_command", {"command": "play_toggle"}) == "confirm"
