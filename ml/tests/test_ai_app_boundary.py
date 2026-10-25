"""App/analysis intents always plan; no coded engine can execute them."""
import asyncio
import sys
import types

import pytest
from fakes import FakeServer, FakeEngine
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from test_fallback_planner import CaptureTracer
from test_planner_loop import FakePlanner, run, trace_for


def _orch(server, tmp_path):
    return Orchestrator(server, Catalog.load(),
                        CaptureTracer(tmp_path / "t"), engine=FakeEngine())


@pytest.mark.parametrize("skill", ["finance_review", "advisor_prep",
                                   "premiere_edit", "draft_email"])
def test_exec_action_skill_rejected_pre_rpc(tmp_path, skill):
    server = FakeServer()
    o = _orch(server, tmp_path)
    r = run(o._exec_action({"op": "skill", "name": skill, "args": {}}))
    assert r["status"] == "failed" and "operate" in r["error"]
    assert all(m not in ("act", "skill") for m, _ in server.rpcs)


@pytest.mark.parametrize("flag", [True, False])
def test_flag_cannot_reenable_engines(tmp_path, flag):
    o = _orch(FakeServer(), tmp_path)
    o.agentic_apps = flag
    assert o._agentic_app("finance_review") is True
    assert o._agentic_app("advisor_prep") is True


@pytest.mark.parametrize("skill", ["finance_review", "advisor_prep"])
def test_tools_run_delegates_never_executes(tmp_path, monkeypatch, skill):
    """A poisoned tools.<name> module must never be imported/executed."""
    bad = types.ModuleType(f"brain.tools.{skill}")
    async def boom(*a, **k):
        raise AssertionError("coded engine executed")
    bad.run = boom
    monkeypatch.setitem(sys.modules, f"brain.tools.{skill}", bad)
    from brain import tools
    o = _orch(FakeServer(), tmp_path)
    seen = []
    async def agentic(name, args, text, trace):
        seen.append(name)
        return "ok"
    o._agentic_route = agentic
    out = run(tools.run(o, skill, {}, "do the thing"))
    assert out == "ok" and seen == [skill]


def test_rapid_fire_system_skills_unaffected(tmp_path):
    server = FakeServer()
    o = _orch(server, tmp_path)
    r = run(o._exec_action({"op": "skill", "name": "set_volume",
                            "args": {"level": 30}}))
    assert r["status"] == "ok"
    assert [p for m, p in server.rpcs if m == "skill"] == [
        {"name": "set_volume", "args": {"level": 30}}]


@pytest.mark.parametrize("skill", ["finance_review", "advisor_prep"])
def test_engine_route_finance_hits_planner_once(tmp_path, skill):
    """A routed finance/advisor intent delegates to _planner_loop with the
    original utterance — zero act/skill RPCs, no coded engine."""
    text = f"run {skill.replace('_', ' ')} please"
    engine = FakeEngine(routes={text: (skill, 0.99)})
    server = FakeServer()
    o = _orch(server, tmp_path)
    o.engine = engine
    seen = []
    async def planner_loop(t, trace, hint=None, finish_criterion=None):
        seen.append(t)
        return "ok"
    o._planner_loop = planner_loop
    out = run(o._engine_route(text, {"decisions": []}))
    assert out == "ok" and seen == [text]
    assert all(m not in ("act", "skill") for m, _ in server.rpcs)


def test_brain_tool_shim_delegates(tmp_path, monkeypatch):
    """_brain_tool hands legacy callers to the agentic route, not the
    (possibly poisoned) tools module."""
    bad = types.ModuleType("brain.tools.finance_review")
    bad.run = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("executed"))
    monkeypatch.setitem(sys.modules, "brain.tools.finance_review", bad)
    o = _orch(FakeServer(), tmp_path)
    seen = []
    async def agentic(name, args, text, trace):
        seen.append(name)
        return "ok"
    o._agentic_route = agentic
    assert run(o._brain_tool("finance_review", {}, "check my books")) == "ok"
    assert seen == ["finance_review"]


def test_exec_action_rejects_with_flag_false(tmp_path):
    o = _orch(FakeServer(), tmp_path)
    o.agentic_apps = False
    r = run(o._exec_action({"op": "skill", "name": "advisor_prep",
                            "args": {}}))
    assert r["status"] == "failed" and "operate" in r["error"]


def test_planner_hides_app_skills_in_schema(tmp_path):
    """catalog_desc with app_skills hidden never offers them as actions;
    system skills stay."""
    from brain.planner import catalog_desc
    cat = Catalog.load()
    desc = catalog_desc(cat, lambda _n: "", cat.app_skills())
    for label in ("finance_review", "advisor_prep", "premiere_edit",
                  "compose_text", "draft_email"):
        assert label not in desc
    assert "set_volume" in desc
    # app_skills() itself covers app AND analysis kinds
    kinds = {cat.kind(n) for n in cat.app_skills()}
    assert kinds <= {"app", "analysis"}
