"""Grounder wired into the planner loop: DSL `click "<target>"`, screenshot ->
Grounder.locate (zoom = fresh region screenshot) -> global points -> act click,
lazy grounder load, blind-observation hint, `brain serve --grounder-*` flags."""

import asyncio
import os
import sys

import pytest
from PIL import Image, ImageDraw

from brain import dsl, orchestrator as orch_mod
from brain.catalog import Catalog
from brain.cli import build_parser, grounder_cfg
from brain.grounder import Grounder, pixels_to_model, to_global
from brain.orchestrator import BLIND_HINT, Orchestrator, observation_blind
from brain.traces import Tracer
from fakes import FakeServer
from test_planner_loop import FakePlanner


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- DSL

@pytest.mark.parametrize("line,want", [
    ('click "the razor tool"', {"op": "click", "target": "the razor tool", "right": False, "double": False}),
    ('click "clip \\"B\\" on V1" double', {"op": "click", "target": 'clip "B" on V1', "right": False,
                                          "double": True}),
    ('click "timeline ruler" right', {"op": "click", "target": "timeline ruler", "right": True, "double": False}),
    ("click 100,200", {"op": "click", "x": 100.0, "y": 200.0, "right": False, "double": False}),
])
def test_click_target_parse_and_roundtrip(line, want):
    got = dsl.parse(line)
    assert got == [want]
    assert dsl.parse(dsl.serialize(got)) == got


def test_click_target_with_expect_and_errors():
    acts = dsl.parse('click "Export button"\nexpect appears "Export Settings"')
    assert acts[0]["target"] == "Export button" and acts[0]["expect"] == 'appears "Export Settings"'
    assert dsl.serialize(acts) == 'click "Export button"\nexpect appears "Export Settings"'
    for bad in ['click ""', 'click "x" triple', "click hi", 'click "unterminated']:
        with pytest.raises(dsl.DSLError):
            dsl.parse(bad)
    assert dsl.action_line('click "the play head"') == 'click "the play head"'


# ---------------------------------------------------------------- blind observation

@pytest.mark.parametrize("obs,blind", [
    ({"app": "Finder", "elements": []}, True),
    ({"app": "Finder", "elements": [{"ref": 1}]}, False),
    ({"app": "Adobe Premiere Pro 2025", "elements": [{"ref": 1}]}, True),
    ({"app": "Final Cut Pro", "elements": [{"ref": 1}]}, True),
    ({"app": "figma", "elements": [{"ref": 1}]}, True),
    ({"app": "Blender", "elements": [{"ref": 1}]}, True),
    ({"app": "Minecraft", "elements": [{"ref": 1}]}, True),
    ({"app": "Safari", "elements": [{"ref": 1}]}, False),
    (None, False),
])
def test_observation_blind(obs, blind):
    assert observation_blind(obs) is blind


def _obs(app, elements, text=None):
    return lambda: {"epoch": 1, "app": app, "window": "w", "focused_ref": None, "elements": elements,
                    "text": text or f'app: {app} | window: "w"', "ax_ms": 1}


@pytest.mark.parametrize("app,elements,hinted", [
    ("Finder", [], True),
    ("Adobe Premiere Pro 2025", [{"ref": 1, "role": "button", "label": "Play", "frame": [0, 0, 9, 9]}], True),
    ("Finder", [{"ref": 1, "role": "button", "label": "Back", "frame": [0, 0, 9, 9]}], False),
])
def test_planner_user_message_gets_blind_hint(tmp_path, app, elements, hinted):
    srv = FakeServer(observe=_obs(app, elements))
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"))
    o.planner = FakePlanner([['done "ok"']])
    tr = {"utterance": "x", "decisions": []}
    run(o._planner_loop("cut the clip", tr))
    obs = o.planner.user_msgs[0]["obs"]
    assert (BLIND_HINT in obs) is hinted
    assert obs.startswith(f"app: {app}")
    if hinted:
        assert obs.endswith('\nAccessibility tree is empty here: use click "<description>"')
        assert {"blind_observation": 0} in tr["decisions"]


# ---------------------------------------------------------------- click "<target>" end to end (fakes)

DISPLAY = (-1512.0, -200.0, 1512.0, 982.0)   # secondary Retina display, global points
BACKING = 2.0
TARGET_G = (-1512 + 1000.25, -200 + 700.5)


class GroundingServer(FakeServer):
    """FakeServer + HandsKit-like `screenshot` (window or region, backing scale, pixel cap)."""

    def __init__(self, tmp_path, **kw):
        super().__init__(**kw)
        self.tmp = tmp_path
        ox, oy, w, h = DISPLAY
        self.native = Image.new("RGB", (int(w * BACKING), int(h * BACKING)), "white")
        cx, cy = (TARGET_G[0] - ox) * BACKING, (TARGET_G[1] - oy) * BACKING
        ImageDraw.Draw(self.native).rectangle([cx - 4, cy - 4, cx + 3, cy + 3], fill=(255, 0, 0))
        self.shots = []

    def _shot(self, src, max_pixels):
        import math
        ox, oy, _, _ = DISPLAY
        sx, sy, sw, sh = src
        pw, ph = sw * BACKING, sh * BACKING
        k = min(1.0, math.sqrt(max_pixels / (pw * ph)))
        w, h = max(1, round(pw * k)), max(1, round(ph * k))
        crop = self.native.crop((round((sx - ox) * BACKING), round((sy - oy) * BACKING),
                                 round((sx - ox + sw) * BACKING), round((sy - oy + sh) * BACKING)))
        img = crop.resize((w, h)) if (w, h) != crop.size else crop
        path = self.tmp / f"shot{len(self.shots)}.png"
        img.save(path)
        self.shots.append(str(path))
        return {"path": str(path), "width": w, "height": h, "origin": [sx, sy], "scale": w / sw, "ok": True}

    async def rpc(self, method, params, timeout=30):
        if method != "screenshot":
            return await super().rpc(method, params, timeout)
        self.rpcs.append((method, params))
        r = params.get("region")
        if r is None:
            return self._shot(DISPLAY, params["max_pixels"])
        dx, dy, dw, dh = DISPLAY
        x1, y1 = max(r[0], dx), max(r[1], dy)
        x2, y2 = min(r[0] + r[2], dx + dw), min(r[1] + r[3], dy + dh)
        return self._shot((x1, y1, x2 - x1, y2 - y1), params["max_pixels"])

    def acts(self):
        return [p for m, p in self.rpcs if m == "act"]


class RedBackend:
    """Fake model: finds the red square in the image it is given (first guess biased)."""

    def __init__(self):
        self.bias, self.calls, self.thread = (9, -6), 0, None

    def __call__(self, image, system, user, adapter):
        import threading
        self.calls += 1
        self.thread = threading.current_thread().name
        px = image.load()
        pts = [(x, y) for y in range(image.height) for x in range(image.width)
               if px[x, y][0] > 200 and px[x, y][1] < 120]
        cx = sum(p[0] for p in pts) / len(pts) + 0.5 + self.bias[0]
        cy = sum(p[1] for p in pts) / len(pts) + 0.5 + self.bias[1]
        self.bias = (0, 0)
        x, y = pixels_to_model((cx, cy), adapter.coord, image.size, image.size)
        return adapter.answer.format(x=round(x, 3), y=round(y, 3))


def _orch(tmp_path, model="eyes-4b", max_pixels=1_000_000, act=None):
    srv = GroundingServer(tmp_path, act=act)
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"))
    o.grounder_cfg = {"model": model, "repo": None, "max_pixels": max_pixels, "zoom_frac": 0.4}
    o.screens = [{"id": 2, "frame": list(DISPLAY), "scale": BACKING}]
    g = o._get_grounder()
    g.backend = be = RedBackend()
    return o, srv, be


class SafetyGateServer(FakeServer):
    def __init__(self, tmp_path, *, ocr_text="Cancel", ocr_error=None):
        super().__init__()
        self.shot = {
            "path": str(tmp_path / "gate-shot.png"),
            "width": 300,
            "height": 120,
            "origin": [10.0, 20.0],
            "scale": 2.0,
            "ok": True,
        }
        self.ocr_text = ocr_text
        self.ocr_error = ocr_error

    def acts(self):
        return [params for method, params in self.rpcs if method == "act"]

    async def rpc(self, method, params, timeout=30):
        if method == "screenshot":
            self.rpcs.append((method, params))
            return dict(self.shot)
        if method == "ocr":
            self.rpcs.append((method, params))
            if self.ocr_error:
                raise self.ocr_error
            return {"text": self.ocr_text}
        return await super().rpc(method, params, timeout)


class FixedGateGrounder:
    async def alocate(self, path, target, *, shot=None, hint_box=None):
        return {"x": 0.0, "y": 0.0, "conf": 0.99, "ms": 0.1}


def _safety_gate_orch(tmp_path, *, app="Finder", window="Window",
                      elements=None, ocr_text="Cancel", ocr_error=None):
    server = SafetyGateServer(
        tmp_path, ocr_text=ocr_text, ocr_error=ocr_error)
    tracer = Tracer(tmp_path / "gate-trace")
    tracer.begin("click safely")
    orch = Orchestrator(server, Catalog.load(), tracer)
    orch.grounder_cfg = {"max_pixels": 1_000_000}
    orch.grounder = FixedGateGrounder()
    orch.screens = []
    orch._last_obs = {
        "app": app, "window": window, "elements": elements or [],
    }
    orch._ctx["app"] = app
    return orch, server


def _click(orch, target="the app icon"):
    return run(orch._exec_action({
        "op": "click", "target": target, "right": False, "double": False,
    }))


def test_grounded_click_send_element_confirms_smallest_label(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[
            {"ref": 1, "role": "group", "label": "Toolbar",
             "frame": [0, 0, 100, 100]},
            {"ref": 2, "role": "button", "label": "Send",
             "frame": [10, 20, 10, 10]},
        ],
    )

    result = _click(orch, "the paper plane icon")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "Send"?']
    assert len(server.acts()) == 1
    assert not any(method == "ocr" for method, _ in server.rpcs)
    decision = orch.tracer.current["decisions"][-1]
    assert decision["grounded_click_gate"] == "label"
    assert decision["ms"] >= 0


def test_grounded_click_safe_element_skips_ocr_and_confirmation(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[{"ref": 1, "role": "button", "label": "Bold",
                   "frame": [10, 20, 10, 10]}],
    )

    result = _click(orch, "the formatting icon")

    assert result["status"] == "ok"
    assert server.confirms == []
    assert not any(method == "ocr" for method, _ in server.rpcs)
    assert orch.tracer.current["decisions"][-1]["hit"] == "Bold"


def test_grounded_click_unlabeled_button_falls_through_to_ocr(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[
            {"role": "group", "label": "Conversation",
             "frame": [0, 0, 100, 100]},
            {"role": "button", "label": "",
             "frame": [10, 20, 10, 10]},
        ],
        ocr_text="Send",
    )

    result = _click(orch, "the paper plane icon")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "Send"?']
    assert any(method == "ocr" for method, _ in server.rpcs)
    assert orch.tracer.current["decisions"][-1]["grounded_click_gate"] == "ocr"


def test_grounded_click_container_only_falls_through_to_ocr(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[{"role": "group", "label": "Toolbar",
                   "frame": [0, 0, 100, 100]}],
        ocr_text="Cancel",
    )

    result = _click(orch, "the formatting area")

    assert result["status"] == "ok"
    assert server.confirms == []
    assert any(method == "ocr" for method, _ in server.rpcs)
    assert orch.tracer.current["decisions"][-1]["grounded_click_gate"] == "none"


def test_grounded_click_uses_smallest_decisive_element(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[
            {"role": "button", "label": "Send",
             "frame": [0, 0, 100, 100]},
            {"role": "button", "label": "Bold",
             "frame": [10, 20, 10, 10]},
        ],
    )

    result = _click(orch, "the formatting icon")

    assert result["status"] == "ok"
    assert server.confirms == []
    assert not any(method == "ocr" for method, _ in server.rpcs)
    assert orch.tracer.current["decisions"][-1]["hit"] == "Bold"


def test_grounded_click_ocr_send_confirms_with_region_clamped_at_edge(tmp_path):
    orch, server = _safety_gate_orch(tmp_path, ocr_text="Send")

    result = _click(orch, "the app icon")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "Send"?']
    assert [params["region"] for method, params in server.rpcs
            if method == "ocr"] == [[10.0, 20.0, 80.0, 30.0]]


def test_grounded_click_ocr_cancel_does_not_confirm(tmp_path):
    orch, server = _safety_gate_orch(tmp_path, ocr_text="Cancel")

    result = _click(orch, "the app icon")

    assert result["status"] == "ok"
    assert server.confirms == []
    assert any(method == "ocr" for method, _ in server.rpcs)


@pytest.mark.parametrize(("app", "window", "labels", "goal"), [
    ("Microsoft Outlook", "Inbox", [], ""),
    ("Google Chrome", "Inbox - Outlook", [], ""),
    ("Google Chrome", "Messaging | LinkedIn", [], ""),
    ("Unknown App", "Window", ["To:"], ""),
    ("Unknown App", "Window", ["Cc"], ""),
    ("Unknown App", "Window", ["Subject"], ""),
    ("Unknown App", "Window", ["Message"], ""),
    ("Unknown App", "Window", ["Reply"], ""),
    ("Unknown App", "Window", ["Compose"], ""),
    ("Unknown App", "Window", ["Send"], ""),
    ("Unknown App", "Window", ["Recipient field"], ""),
    ("Unknown App", "Window", [], "send this to Alex"),
    ("Unknown App", "Window", [], "reply to Alex"),
    ("Unknown App", "Window", [], "messaging Alex"),
])
@pytest.mark.parametrize("ocr_error", [None, RuntimeError("Vision unavailable")])
@pytest.mark.parametrize("intent_source", ["_utterance", "_current_goal"])
def test_brain27_unlabeled_composer_click_requires_confirm(
        tmp_path, app, window, labels, goal, ocr_error, intent_source):
    orch, server = _safety_gate_orch(
        tmp_path, app=app, window=window, ocr_text="", ocr_error=ocr_error,
        elements=[{"role": "textfield", "label": label} for label in labels])
    setattr(orch, intent_source, goal)
    server.confirm_yes = False

    result = _click(orch, "the paper plane icon")

    assert result["status"] == "cancelled"
    assert server.confirms == ['Click "the paper plane icon"?']
    assert server.acts() == []


@pytest.mark.parametrize("app", ["Finder", "Notes"])
@pytest.mark.parametrize("ocr_text", ["", "   ", "Cancel"])
def test_brain27_non_composer_icon_click_does_not_confirm(tmp_path, app, ocr_text):
    orch, server = _safety_gate_orch(
        tmp_path, app=app, window="Welcome to my workspace", ocr_text=ocr_text,
        elements=[{"role": "button", "label": "Toolbar", "frame": [100, 100, 10, 10]}])
    server.confirm_yes = False

    result = _click(orch, "the toolbar icon")

    assert result["status"] == "ok"
    assert server.confirms == []
    assert len(server.acts()) == 1


def test_grounded_click_ocr_failure_confirms_and_traces_error(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path, ocr_error=RuntimeError("Vision unavailable"))

    result = _click(orch, "the app icon")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "the app icon"?']
    decision = orch.tracer.current["decisions"][-1]
    assert decision["grounded_click_gate"] == "ocr"
    assert decision["error"] == "Vision unavailable"


@pytest.mark.parametrize(("app", "window"), [
    ("Slack", "Workspace"),
    ("Google Chrome", "Checkout - Amazon"),
])
def test_grounded_click_context_confirms_neutral_target(tmp_path, app, window):
    orch, server = _safety_gate_orch(tmp_path, app=app, window=window)

    result = _click(orch, "the app icon")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "the app icon"?']
    assert not any(method == "ocr" for method, _ in server.rpcs)
    assert orch.tracer.current["decisions"][-1]["grounded_click_gate"] == "context"


def test_grounded_click_observed_url_confirms_payment_context(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path, app="Google Chrome", window="Product page")
    orch._last_obs["url"] = "https://shop.example/payment"

    result = _click(orch, "the app icon")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "the app icon"?']
    assert not any(method == "ocr" for method, _ in server.rpcs)


def test_grounded_click_decline_prevents_act(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[{"ref": 1, "role": "button", "label": "Send",
                   "frame": [10, 20, 10, 10]}],
    )
    server.confirm_yes = False

    result = _click(orch, "the paper plane icon")

    assert result["status"] == "cancelled"
    assert server.confirms == ['Click "Send"?']
    assert server.acts() == []


def test_planner_confirm_covers_grounded_click_gate(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[{"ref": 1, "role": "button", "label": "Send",
                   "frame": [10, 20, 10, 10]}],
    )
    orch._batch_confirmed = True

    result = _click(orch, "the paper plane icon")

    assert result["status"] == "ok"
    assert server.confirms == []
    assert len(server.acts()) == 1


def test_grounded_click_dangerous_target_confirms_once(tmp_path):
    orch, server = _safety_gate_orch(tmp_path)

    result = _click(orch, "the Delete button")

    assert result["status"] == "ok"
    assert server.confirms == ['Click "the Delete button"?']
    assert not any(method == "ocr" for method, _ in server.rpcs)
    assert orch.tracer.current["decisions"][-1]["grounded_click_gate"] == "target"


def test_grounded_click_uses_last_url_from_url_action(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path, app="Google Chrome", window="Product page")

    run(orch._exec_action({
        "op": "url", "url": "https://shop.example/checkout",
    }))
    result = _click(orch, "the app icon")

    assert result["status"] == "ok"
    assert orch._last_url == "https://shop.example/checkout"
    assert server.confirms == ['Click "the app icon"?']
    assert not any(method == "ocr" for method, _ in server.rpcs)


def test_grounded_click_gate_latency_label_vs_instant_ocr(tmp_path):
    orch, server = _safety_gate_orch(
        tmp_path,
        elements=[{"ref": 1, "role": "button", "label": "Bold",
                   "frame": [10, 20, 10, 10]}],
    )
    label = run(orch._grounded_click_gate(
        10.0, 20.0, server.shot, "the formatting icon"))
    assert not any(method == "ocr" for method, _ in server.rpcs)

    orch._last_obs["elements"] = []
    ocr = run(orch._grounded_click_gate(
        10.0, 20.0, server.shot, "the app icon"))

    assert label["gate"] == "none" and ocr["gate"] == "none"
    assert any(method == "ocr" for method, _ in server.rpcs)
    assert label["ms"] >= 0 and ocr["ms"] >= 0
    print(
        "grounded-click gate latency: "
        f"label={label['ms']:.2f}ms, instant fake OCR={ocr['ms']:.2f}ms")


@pytest.mark.parametrize("model", ["eyes-4b", "ui-venus-1.5-8b", "gta1-7b"])
def test_click_target_screenshot_locate_zoom_act(tmp_path, model):
    o, srv, be = _orch(tmp_path, model)
    r = run(o._exec_action(dsl.parse('click "the red square"\nexpect appears "Razor"')[0]))
    assert r["status"] == "ok", r
    shots = [p for m, p in srv.rpcs if m == "screenshot"]
    assert shots[0] == {"window": True, "max_pixels": 1_000_000}
    assert set(shots[1]) == {"region", "max_pixels"}                  # stage 2: fresh region screenshot
    rx, ry, rw, rh = shots[1]["region"]
    assert rw * rh * BACKING ** 2 <= 1_000_000                        # at native scale, under the cap
    assert be.calls == 2 and be.thread == "mlx-worker"                # model runs on the MLX worker
    (act,) = srv.acts()
    assert act["op"] == "click" and not act["right"] and not act["double"]
    assert "expect" not in act
    assert (act["x"], act["y"]) == pytest.approx(TARGET_G, abs=0.6)    # global points
    assert ("verify", {"expect": 'appears "Razor"'}) in srv.rpcs
    assert srv.methods() == ["screenshot", "screenshot", "ocr", "act", "verify"]
    assert not any(os.path.exists(p) for p in srv.shots)              # screenshots never kept
    assert r["_log"].startswith("click target=the red square") and " at " in r["_log"]


def test_click_target_right_double_and_2mp(tmp_path):
    o, srv, _ = _orch(tmp_path, max_pixels=2_000_000)
    r = run(o._exec_action(dsl.parse('click "the red square" right double')[0]))
    assert r["status"] == "ok"
    shots = [p for m, p in srv.rpcs if m == "screenshot"]
    assert shots[0]["max_pixels"] == 2_000_000 and shots[1]["max_pixels"] == 2_000_000
    (act,) = srv.acts()
    assert act["right"] and act["double"]


def test_click_target_maps_through_shot_metadata(tmp_path):
    """Grounder pixel -> to_global(origin + px / scale) is exactly what is sent."""
    o, srv, _ = _orch(tmp_path)
    o.grounder.zoom = False
    seen = {}
    orig = o.grounder.alocate

    async def spy(path, target, *, shot=None, hint_box=None):
        pt = await orig(path, target, shot=shot)
        seen.update(pt=pt, shot=shot)
        return pt

    o.grounder.alocate = spy
    assert run(o._exec_action({"op": "click", "target": "x", "right": False, "double": False}))["status"] == "ok"
    gx, gy = to_global(seen["pt"], seen["shot"])
    (act,) = srv.acts()
    assert (act["x"], act["y"]) == (round(gx, 1), round(gy, 1))
    assert seen["shot"]["origin"] == [-1512.0, -200.0] and seen["shot"]["scale"] < BACKING


def test_click_target_not_found_fails_without_act(tmp_path):
    o, srv, _ = _orch(tmp_path)
    o.grounder.backend = lambda *a: "I can't see it"
    r = run(o._exec_action({"op": "click", "target": "ghost", "right": False, "double": False}))
    assert r["status"] == "failed" and "target not found" in r["error"]
    assert srv.acts() == []


def test_click_target_dangerous_needs_confirm(tmp_path):
    o, srv, _ = _orch(tmp_path)
    srv.confirm_yes = False
    r = run(o._exec_action({"op": "click", "target": "the Delete button", "right": False, "double": False}))
    assert r["status"] == "cancelled" and srv.confirms == ['Click "the Delete button"?']
    assert "screenshot" not in srv.methods()


def test_click_target_in_planner_loop(tmp_path):
    o, srv, _ = _orch(tmp_path)
    srv.observe = _obs("Adobe Premiere Pro 2025", [])
    o.planner = FakePlanner([['click "the red square"'], ['done "ok"']])
    assert run(o._planner_loop("select the clip", {"utterance": "x", "decisions": []})) == "ok"
    assert srv.acts() and BLIND_HINT in o.planner.user_msgs[0]["obs"]
    assert any("at " in ln for ln in o.planner.user_msgs[1]["last_batch"])


def test_pixel_click_unchanged(tmp_path):
    o, srv, _ = _orch(tmp_path)
    r = run(o._exec_action(dsl.parse("click 10,20")[0]))
    assert r["status"] == "failed" and r["error"] == "no screenshot attached"
    assert "screenshot" not in srv.methods()


# ---------------------------------------------------------------- lazy load + CLI

def test_grounder_is_lazy(tmp_path):
    o = Orchestrator(FakeServer(), Catalog.load(), Tracer(tmp_path / "t"))
    assert o.grounder_cfg == orch_mod.DEFAULT_GROUNDER and o.grounder is None
    g = o._get_grounder()
    assert g.adapter.name == "eyes-4b" and g.max_pixels == 1_000_000 and g.zoom_frac == 0.4 and g.zoom
    assert g.backend.model is None                     # weights load on the first locate
    assert "mlx_vlm" not in sys.modules
    assert o._get_grounder() is g


def test_grounder_disabled(tmp_path):
    o = Orchestrator(FakeServer(), Catalog.load(), Tracer(tmp_path / "t"))
    o.grounder_cfg = None
    r = run(o._exec_action({"op": "click", "target": "x", "right": False, "double": False}))
    assert r["status"] == "failed" and r["error"] == "no grounder configured"


def test_serve_grounder_flags():
    args, _ = build_parser(["serve"])
    assert grounder_cfg(args) == {"model": "eyes-4b", "repo": None, "max_pixels": 1_000_000, "zoom_frac": 0.4}
    args, _ = build_parser(["serve", "--grounder-model", "ui-venus-1.5-8b", "--grounder-max-pixels", "2000000"])
    assert grounder_cfg(args)["model"] == "ui-venus-1.5-8b" and grounder_cfg(args)["max_pixels"] == 2_000_000
    args, _ = build_parser(["serve", "--grounder-model", "eyes-4b=models/eyes-4b-mlx"])
    assert grounder_cfg(args)["repo"] == "models/eyes-4b-mlx"
    assert grounder_cfg(build_parser(["serve", "--grounder-model", "none"])[0]) == {}
    with pytest.raises(KeyError):
        grounder_cfg(build_parser(["serve", "--grounder-model", "nope"])[0])
    assert "mlx_vlm" not in sys.modules


def test_cli_serve_passes_grounder(monkeypatch):
    from brain import cli
    seen = {}

    async def fake_serve(port, model, pmodel, pkw, args_model=None,
                         escalate_model=None, grounder=None,
                         verify_done=True, open_ended_route=False,
                         planner_aux_model=None, **_kw):
        seen["g"] = grounder

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: m)
    cli.run_cmd(*cli.build_parser(["serve", "--grounder-model", "ui-venus-1.5-8b",
                                   "--grounder-max-pixels", "2000000"]))
    assert seen["g"] == {"model": "ui-venus-1.5-8b", "repo": None, "max_pixels": 2_000_000, "zoom_frac": 0.4}
