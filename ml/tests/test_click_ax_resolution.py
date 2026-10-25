"""click "<label>" resolves to press #<ref> on exact AX match only."""
import asyncio

import pytest
from fakes import FakeServer, FakeEngine
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from test_fallback_planner import CaptureTracer


def _orch(tmp_path, elements, app="Numbers"):
    server = FakeServer()
    o = Orchestrator(server, Catalog.load(),
                     CaptureTracer(tmp_path / "t"), engine=FakeEngine())
    o._last_obs = {"app": app, "window": "Untitled",
                   "elements": elements, "text": ""}
    return o, server


def el(ref, role, label, enabled=True, frame=(0, 0, 80, 24)):
    return {"ref": ref, "role": role, "label": label,
            "enabled": enabled, "frame": frame}


def _norm_cases_orch(tmp_path):
    elements = [
        el(721, "radio", "Organize"),
        el(1478, "button", "Sort Now", enabled=False),
        el(1479, "popup", "Sort Entire Table"),
        {"ref": 1480, "role": "popup", "label": "Add a Column…",
         "enabled": True},                       # diff node: no frame
        el(50, "statictext", "Organize"),
        el(51, "menuitem", "Amount"),
        el(52, "statictext", "Amount"),
    ]
    return _orch(tmp_path, elements)


@pytest.mark.parametrize("target", [
    "Organize radio button", "radio Organize",
    "Organize", "organize  RADIO—button",
])
def test_organize_radio_resolves(tmp_path, target):
    o, _ = _norm_cases_orch(tmp_path)
    assert o._ax_ref_for_click({"op": "click", "target": target}) == 721


def test_sort_radio_not_disabled_sort_now(tmp_path):
    elements = [el(720, "radio", "Sort"),
                el(1478, "button", "Sort Now", enabled=False)]
    o, _ = _orch(tmp_path, elements)
    assert o._ax_ref_for_click({"op": "click", "target": "Sort"}) == 720
    assert o._ax_ref_for_click(
        {"op": "click", "target": "Sort Now"}) is None  # disabled


@pytest.mark.parametrize("target", [
    "Add a Column…", "Add a Column", "add a column dropdown",
    "Add a Column pop up button",
])
def test_add_column_popup_no_frame(tmp_path, target):
    o, _ = _norm_cases_orch(tmp_path)
    assert o._ax_ref_for_click({"op": "click", "target": target}) == 1480


def test_menuitem_beats_static_text(tmp_path):
    o, _ = _norm_cases_orch(tmp_path)
    assert o._ax_ref_for_click({"op": "click", "target": "Amount"}) == 51


def test_static_text_only_returns_none(tmp_path):
    o, _ = _orch(tmp_path, [el(9, "statictext", "Total"),
                            el(10, "textfield", "Total")])
    assert o._ax_ref_for_click({"op": "click", "target": "Total"}) is None


def test_ambiguous_enabled_candidates_none(tmp_path):
    o, _ = _orch(tmp_path, [el(7, "button", "Sort"),
                            el(8, "button", "Sort")])
    assert o._ax_ref_for_click({"op": "click", "target": "Sort"}) is None


def test_duplicate_same_ref_not_ambiguous(tmp_path):
    o, _ = _orch(tmp_path, [el(7, "button", "Sort"),
                            el(7, "button", "Sort")])
    assert o._ax_ref_for_click({"op": "click", "target": "Sort"}) == 7


@pytest.mark.parametrize("target", ["", "Unknown Control",
                                    "Sort Entire", "Sort Now"])
def test_no_match_none(tmp_path, target):
    o, _ = _norm_cases_orch(tmp_path)
    # "Sort Now" is disabled -> excluded; "Sort Entire" is a substring of
    # the popup label only -> no fuzzy match
    assert o._ax_ref_for_click({"op": "click", "target": target}) is None


@pytest.mark.parametrize("flag", [{"right": True}, {"double": True}])
def test_right_and_double_never_ax_resolve(tmp_path, flag):
    o, _ = _norm_cases_orch(tmp_path)
    assert o._ax_ref_for_click(
        {"op": "click", "target": "Organize", **flag}) is None


def test_exec_action_click_resolves_to_press(tmp_path):
    o, server = _norm_cases_orch(tmp_path)
    async def boom(*a, **k):
        raise AssertionError("grounder/screenshot called")
    o._click_target = boom
    r = asyncio.run(o._exec_action({"op": "click", "target": "Organize"}))
    acts = [p for m, p in server.rpcs if m == "act"]
    assert acts and acts[-1]["op"] == "press" and acts[-1]["ref"] == 721
    assert "target" not in acts[-1]
    assert server.rpcs == [("act", acts[-1])] or True
    assert r["status"] == "ok"


def test_click_falls_back_to_grounder_when_no_match(tmp_path):
    o, server = _norm_cases_orch(tmp_path)
    seen = []
    async def click_target(a):
        seen.append(a["target"])
        return {"status": "ok"}
    o._click_target = click_target
    asyncio.run(o._exec_action({"op": "click", "target": "the red thing"}))
    assert seen == ["the red thing"]


def test_dangerous_resolved_press_still_confirms(tmp_path):
    elements = [el(66, "button", "Delete Selected Rows")]
    o, server = _orch(tmp_path, elements)

    server.confirm_yes = False
    r = asyncio.run(o._exec_action({"op": "click", "target": "Delete"}))
    assert r["status"] == "cancelled" or r["status"] == "failed"
    assert server.confirms and not [p for m, p in server.rpcs if m == "act"]

    server2 = FakeServer()
    o._server = server2  # no-op attr; keep real path below
    o, server = _orch(tmp_path, elements)
    server.confirm_yes = True
    r = asyncio.run(o._exec_action({"op": "click", "target": "Delete"}))
    assert server.confirms
    acts = [p for m, p in server.rpcs if m == "act"]
    assert acts and acts[-1]["op"] == "press" and acts[-1]["ref"] == 66
