"""brain-48: _resolve_open adds 'app' to act open params, but HandsKit reads params["name"] first."""
import asyncio
import pytest
from brain.orchestrator import Orchestrator


def test_act_open_sends_resolved_name():
    if not hasattr(Orchestrator, "_resolve_open"):
        pytest.skip("no _resolve_open on this branch")
    o = Orchestrator.__new__(Orchestrator)
    o._apps = (1e18, ["Visual Studio Code", "Google Chrome"])

    async def names():
        return o._apps[1]
    o._app_names = names
    out = asyncio.run(o._resolve_open("act", {"op": "open", "name": "vscode"}))
    # Act.swift: params["name"] as? String ?? params["app"] as? String
    assert (out.get("name") or out.get("app")) == "Visual Studio Code", out
