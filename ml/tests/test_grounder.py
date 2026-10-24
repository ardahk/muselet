import importlib.util
import math
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from brain import grounder as g
from brain.grounder import ADAPTERS, Grounder

ROOT = Path(__file__).resolve().parents[2]


def _load_bench():
    spec = importlib.util.spec_from_file_location("run_screenspot", ROOT / "bench/grounding/run_screenspot.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


bench = _load_bench()


# ---------------------------------------------------------------- resize / tokens

@pytest.mark.parametrize("w,h,factor,cap", [
    (3840, 2160, 32, 1_000_000), (2560, 1440, 28, 1_000_000), (1512, 982, 32, 1_000_000),
    (5120, 2880, 32, 1_000_000), (800, 600, 28, 1_000_000), (1000, 1000, 32, 1_000_000),
])
def test_smart_resize_respects_grid_and_cap(w, h, factor, cap):
    rh, rw = g.smart_resize(h, w, factor, max_pixels=cap)
    assert rh % factor == 0 and rw % factor == 0
    assert rh * rw <= cap
    assert abs(rw / rh - w / h) / (w / h) < 0.05


def test_smart_resize_matches_qwen_reference():
    # Qwen reference rounds when under the cap and floors after scaling when over it.
    assert g.smart_resize(800, 1280, 32, max_pixels=2_000_000) == (800, 1280)
    assert g.smart_resize(790, 1264, 32, max_pixels=1_000_000) == (768, 1248)
    assert g.smart_resize(1080, 1920, 28, max_pixels=12845056) == (1092, 1932)
    assert g.smart_resize(2160, 3840, 32, max_pixels=1_000_000) == (736, 1312)
    assert g.smart_resize(10, 10, 28, min_pixels=3136, max_pixels=1_000_000) == (56, 56)


def test_image_tokens_at_one_megapixel():
    assert g.image_tokens(1280, 800, 32, max_pixels=2_000_000) == 40 * 25
    assert g.image_tokens(1264, 790, 32) == 39 * 24
    assert g.image_tokens(1260, 784, 28) == 45 * 28
    assert g.image_tokens(3840, 2160, 32) == (736 // 32) * (1312 // 32)


# ---------------------------------------------------------------- coordinate conventions

@pytest.mark.parametrize("conv", [g.NORM_1000, g.UNIT, g.RESIZED_PX])
def test_model_pixel_roundtrip(conv):
    model, image = (1288, 728), (3840, 2160)
    for pt in [(0, 0), (1919.5, 1080.25), (3839, 2159), (12.3, 2000.0)]:
        m = g.pixels_to_model(pt, conv, model, image)
        back = g.model_to_pixels(m, conv, model, image)
        assert back == pytest.approx(pt)


def test_conventions_concrete():
    assert g.model_to_pixels((500, 250), g.NORM_1000, (1280, 736), (3840, 2160)) == (1920, 540)
    assert g.model_to_pixels((0.5, 0.25), g.UNIT, (1280, 736), (3840, 2160)) == (1920, 540)
    assert g.model_to_pixels((640, 184), g.RESIZED_PX, (1280, 736), (3840, 2160)) == (1920, 540)
    with pytest.raises(ValueError):
        g.model_to_pixels((1, 1), "bogus", (1, 1), (1, 1))


# ---------------------------------------------------------------- HandsKit screenshot -> global points

def test_to_global_retina_scale_2():
    shot = {"path": "/tmp/s.png", "width": 3024, "height": 1964, "origin": [0, 0], "scale": 2.0}
    assert g.to_global((1512, 982), shot) == (756.0, 491.0)
    assert g.to_global({"x": 100, "y": 50, "conf": 1, "ms": 1}, shot) == (50.0, 25.0)


def test_to_global_negative_origin_secondary_display():
    # Display left of and above the main one: global origin is negative.
    shot = {"width": 1920, "height": 1080, "origin": [-1920, -1080], "scale": 1.0}
    assert g.to_global((0, 0), shot) == (-1920.0, -1080.0)
    assert g.to_global((960, 540), shot) == (-960.0, -540.0)
    retina = {"width": 2560, "height": 1600, "origin": [-1280, 200], "scale": 2.0}
    assert g.to_global((2560, 1600), retina) == (0.0, 1000.0)
    assert g.from_global(g.to_global((321, 77), retina), retina) == pytest.approx((321, 77))


def test_to_global_downscaled_window_shot():
    # A 1 MP-capped capture of a Retina window: HandsKit reports the effective pixels-per-point.
    shot = {"width": 1264, "height": 790, "origin": [100, 60], "scale": 1264 / 1512}
    x, y = g.to_global((1264, 790), shot)
    assert x == pytest.approx(100 + 1512) and y == pytest.approx(60 + 945)


def test_zoom_region_in_global_points():
    shot = {"width": 2000, "height": 1000, "origin": [-1000, 0], "scale": 2.0}
    x, y, w, h = g.zoom_region((1000, 500), shot, frac=0.5)
    assert (w, h) == (500, 250)
    assert (x + w / 2, y + h / 2) == (-500, 250)
    x, y, w, h = g.zoom_region((0, 0), shot, frac=0.5)       # clamped to the display, not shrunk
    assert (x, y) == (-1000, 0) and (w, h) == (500, 250)


# ---------------------------------------------------------------- crop mapping

def test_crop_around_centres_and_clamps():
    assert g.crop_around((500, 400), (1000, 800), (200, 100)) == (400, 350, 600, 450)
    assert g.crop_around((10, 10), (1000, 800), (200, 100)) == (0, 0, 200, 100)
    assert g.crop_around((995, 799), (1000, 800), (200, 100)) == (800, 700, 1000, 800)
    assert g.crop_around((5, 5), (100, 80), (400, 400)) == (0, 0, 100, 80)


def test_crop_to_image_and_pad_box():
    box = g.crop_around((700, 300), (1600, 1000), (400, 300))
    assert g.crop_to_image((200, 150), box) == (700, 300)
    padded = g.pad_box((100, 100, 120, 110), (1000, 1000), pad=0.5)
    assert padded == (90, 95, 130, 115)
    assert g.pad_box((0, 0, 10, 10), (1000, 1000), min_side=200) == (0, 0, 300, 300)


def test_crop_then_resize_maps_back_exactly():
    # Crop 640x400 at (1600, 900) of a 3840x2160 image, upsampled to 1280x800 for the model.
    box = (1600, 900, 2240, 1300)
    model_pt = (0.75 * 1280, 0.5 * 800)                  # resized-pixel answer
    local = g.model_to_pixels(model_pt, g.RESIZED_PX, (1280, 800), (640, 400))
    assert g.crop_to_image(local, box) == (1600 + 480, 900 + 200)
    local = g.model_to_pixels((750, 500), g.NORM_1000, (1280, 800), (640, 400))
    assert g.crop_to_image(local, box) == (2080, 1100)


# ---------------------------------------------------------------- parsers (every adapter)

@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_every_adapter_parses_its_canonical_answer(name):
    a = ADAPTERS[name]
    assert a.parse(a.answer.format(x=417, y=58)) == (417, 58)
    assert a.parse("I cannot find it.") is None


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_every_adapter_prompt_formats(name):
    a = ADAPTERS[name]
    system, user = a.prompt("the Export button", 1280, 800)
    assert "the Export button" in (user + (system or ""))
    if a.coord == g.RESIZED_PX and a.system:
        assert "800" in system and "1280" in system


@pytest.mark.parametrize("text,expected", [
    ('{"point_2d": [523, 87]}', (523, 87)),
    ('```json\n[{"point_2d": [10.5, 990], "label": "Export"}]\n```', (10.5, 990)),
    ('{"bbox_2d": [100, 200, 300, 400]}', (200, 300)),
    ("<think>maybe [1, 2]</think>[640, 360]", (640, 360)),
])
def test_parse_point_2d(text, expected):
    assert g.parse_point_2d(text) == expected


@pytest.mark.parametrize("text,expected", [
    ('<tool_call>\n{"name": "computer_use", "arguments": {"action": "left_click", "coordinate": [512, 64]}}\n'
     '</tool_call>', (512, 64)),
    ('<tool_call>{"name":"computer_use","arguments":{"action":"mouse_move","coordinate":[1,2]}}</tool_call>\n'
     '<tool_call>{"name":"computer_use","arguments":{"action":"left_click","coordinate":[30,40]}}</tool_call>',
     (30, 40)),
    ('<tool_call>\n{"name": "computer_use", "arguments": "{\\"action\\": \\"left_click\\", '
     '\\"coordinate\\": [7, 9]}"}\n</tool_call>', (7, 9)),
    ('left_click "coordinate": [11, 22] (broken json', (11, 22)),
    ("click (5, 6) then (70, 80)", (70, 80)),
    ('<tool_call>{"name": "computer_use", "arguments": {"action": "terminate", "status": "failure"}}</tool_call>',
     None),
])
def test_parse_tool_call(text, expected):
    assert g.parse_tool_call(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("(812,433)", (812, 433)),
    ("(812, 433) and later (1, 1)", (812, 433)),
    ("Action: click(start_box='(197,525)')", (197, 525)),
    ("Action: click(point='<point>197 525</point>')", (197, 525)),
    ("click(start_box='(100,200,300,400)')", (200, 300)),
])
def test_parse_paren_point(text, expected):
    assert g.parse_paren_point(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("[100,200,300,400]", (200, 300)),
    ("[ 10.0, 20.0, 30.0, 60.0 ]", (20, 40)),
    ("[512, 512]", (512, 512)),
])
def test_parse_bbox_center(text, expected):
    assert g.parse_bbox_center(text) == expected


@pytest.mark.parametrize("text,expected", [
    ('{"x": 412, "y": 77}', (412, 77)),
    ('{"y": 77, "x": 412}', (412, 77)),
    ("<think>\n</think>\n{\"x\": 0, \"y\": 1000}", (0, 1000)),
])
def test_parse_xy_json(text, expected):
    assert g.parse_xy_json(text) == expected


# ---------------------------------------------------------------- Grounder (fake backend)

class FakeBackend:
    """Points at a fixed source-image pixel, answering in the adapter's own convention."""

    def __init__(self, target, offset=(0, 0)):
        self.target, self.offset = target, offset
        self.calls = []
        self.box = None
        self.region = None

    def __call__(self, image, system, user, adapter):
        self.calls.append((image.size, system, user))
        box, region = self.box, self.region
        local = (self.target[0] - box[0] + self.offset[0], self.target[1] - box[1] + self.offset[1])
        x, y = g.pixels_to_model(local, adapter.coord, image.size, region)
        return adapter.answer.format(x=round(x, 3), y=round(y, 3))


class TrackingGrounder(Grounder):
    def ground(self, image, instruction, box=None, name="full"):
        b = box or (0, 0, image.width, image.height)
        self.backend.box = b
        self.backend.region = (int(b[2]) - int(b[0]), int(b[3]) - int(b[1]))
        return super().ground(image, instruction, box, name)


@pytest.fixture
def shot(tmp_path):
    img = Image.new("RGB", (3024, 1964), "white")
    ImageDraw.Draw(img).rectangle([2000, 1500, 2030, 1520], fill="black")
    path = tmp_path / "shot.png"
    img.save(path)
    return str(path)


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_locate_full_image_every_adapter(shot, name):
    gr = TrackingGrounder(name, zoom=False, backend=FakeBackend((2015, 1510)))
    out = gr.locate(shot, "the black box")
    assert set(out) == {"x", "y", "conf", "ms"}
    tol = 3024 / 1000 if gr.adapter.coord == g.NORM_1000 else 3
    assert abs(out["x"] - 2015) <= tol and abs(out["y"] - 1510) <= tol
    (w, h), _, _ = gr.backend.calls[0]
    assert w * h <= g.DEFAULT_MAX_PIXELS and w % gr.adapter.factor == 0 and h % gr.adapter.factor == 0


class SeqBackend(FakeBackend):
    """Stage 1 answers `offset` px off target; later stages are exact."""

    def __call__(self, image, system, user, adapter):
        out = super().__call__(image, system, user, adapter)
        self.offset = (0, 0)
        return out


def test_locate_zoom_refines_and_maps_back(shot):
    gr = TrackingGrounder("gta1-7b", zoom=True, backend=SeqBackend((2015, 1510), offset=(40, -25)))
    stages = gr.run(Image.open(shot).convert("RGB"), "the black box")
    assert [s.name for s in stages] == ["full", "zoom"]
    assert stages[0].point == pytest.approx((2055, 1485), abs=3)
    assert stages[1].point == pytest.approx((2015, 1510), abs=1)
    zb = stages[1].box
    assert zb[0] <= 2055 <= zb[2] and zb[1] <= 1485 <= zb[3]
    assert (zb[2] - zb[0]) == round(3024 * 0.4)
    conf = Grounder.confidence(stages)
    assert 0.9 < conf < 1.0


def test_locate_hint_box_crops_first(shot):
    be = FakeBackend((2015, 1510))
    gr = TrackingGrounder("eyes-4b", zoom=False, backend=be)
    out = gr.locate(shot, "the black box", hint_box=(1900, 1450, 2100, 1550))
    (w, h), _, _ = be.calls[0]
    assert len(be.calls) == 1
    assert out["x"] == pytest.approx(2015, abs=1) and out["y"] == pytest.approx(1510, abs=1)
    assert w * h <= g.DEFAULT_MAX_PIXELS


def test_locate_parse_failure(shot):
    gr = Grounder("eyes-4b", backend=lambda *a: "no idea")
    assert gr.locate(shot, "x") == {"x": None, "y": None, "conf": 0.0, "ms": pytest.approx(0, abs=1e9)}


def test_out_of_range_answers_are_clamped(shot):
    gr = Grounder("eyes-4b", zoom=False, backend=lambda *a: '{"point_2d": [1200, -5]}')
    out = gr.locate(shot, "x")
    assert out["x"] == 3023 and out["y"] == 0


def test_mlx_is_lazy():
    gr = Grounder("eyes-4b")
    assert isinstance(gr.backend, g.MLXBackend) and gr.backend.model is None
    assert gr.backend.repo == "deskmind/eyes-4b" and gr.backend.revision == "mlx-4bit"
    assert "mlx_vlm" not in sys.modules


def test_confidence_agreement():
    s = g.Stage
    full = s("full", (0, 0, 1000, 1000), (1000, 1000), "", (500, 500), 1)
    near = s("zoom", (300, 300, 700, 700), (1000, 1000), "", (505, 500), 1)
    far = s("zoom", (300, 300, 700, 700), (1000, 1000), "", (690, 690), 1)
    assert Grounder.confidence([full]) == 0.5
    assert Grounder.confidence([full, near]) > Grounder.confidence([full, far])
    assert math.isclose(Grounder.confidence([s("full", (0, 0, 9, 9), (9, 9), "", None, 1)]), 0.0)


# ---------------------------------------------------------------- benchmark harness

def test_ssp_and_osworld_targets():
    t = bench.Target("bbox", (10, 20, 30, 40))
    assert t.contains((10, 20)) and t.contains((30, 40)) and not t.contains((31, 40)) and not t.contains(None)
    assert t.center() == (20, 30)
    o = bench.osg_target("bbox", [1422.9, 326.4, 26.68, 28.4])
    assert o.coords == pytest.approx((1422.9, 326.4, 1449.58, 354.8))
    p = bench.osg_target("polygon", [1192.98, 350.4, 1212.94, 369.0])
    assert p.contains((1200, 360)) and not p.contains((1100, 360))
    tri = bench.Target("polygon", (0, 0, 100, 0, 0, 100))
    assert tri.contains((10, 10)) and tri.contains((50, 50)) and not tri.contains((60, 60))
    with pytest.raises(ValueError):
        bench.osg_target("refusal", [])


def test_ssp_row_parsing_and_filters(tmp_path):
    row = {"img_filename": "premiere_windows/a.png", "bbox": [612, 228, 885, 254], "instruction": "cut clip",
           "id": "premiere_windows_0", "application": "premiere", "platform": "windows", "img_size": [3840, 2160],
           "ui_type": "icon", "group": "Creative"}
    s = bench.ssp_sample(row, tmp_path)
    assert s.target.kind == "bbox" and s.image_size == (3840, 2160)
    other = bench.ssp_sample({**row, "id": "x", "application": "word", "group": "Office", "ui_type": "text"}, tmp_path)
    assert bench.select([s, other], ["creative"], None) == [s]
    assert bench.select([s, other], ["word", "premiere"], 1) == [s]
    assert bench.select([s, other], [], None) == [s, other]


def test_percentile_and_summary():
    assert bench.percentile([], 50) is None
    assert bench.percentile([1, 2, 3, 4], 50) == 2.5
    assert bench.percentile(list(range(1, 101)), 95) == pytest.approx(95.05, abs=0.06)
    rows = [dict(id=str(i), group="CAD" if i % 2 else "Dev", application="a", ui_type="icon", platform="mac",
                 point=[1, 1], hit=i < 3, hit_stage1=i < 1, ms=10.0 * (i + 1),
                 stage_ms={"full": 5.0 * (i + 1), "zoom": 5.0}) for i in range(4)]
    s = bench.summarize(rows)
    assert s["overall"] == {"n": 4, "acc": 75.0}
    assert s["by_group"]["CAD"] == {"n": 2, "acc": 50.0}
    assert s["acc_before_zoom"]["acc"] == 25.0
    assert s["latency_ms"]["full"]["p50"] == 12.5 and s["latency_ms"]["zoom"]["p95"] == 5.0


@pytest.mark.parametrize("zoom", [False, True])
@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_oracle_pipeline_hits_every_target(tmp_path, name, zoom):
    img = Image.new("RGB", (3840, 2160), "white")
    rows = []
    for i, box in enumerate([(100, 100, 130, 118), (3700, 2100, 3712, 2112), (1910, 1075, 1930, 1085)]):
        rows.append(bench.Sample(id=str(i), instruction="t", target=bench.Target("bbox", box),
                                 load_image=lambda: img.copy(), group="CAD"))
    gr = bench.OracleGrounder(name, zoom=zoom, backend=bench.OracleBackend())
    res = bench.evaluate(gr, rows, zoom)
    assert all(r["hit"] for r in res), [(r["point"], r["raw"]) for r in res]
    assert all(("zoom" in r["stage_ms"]) == zoom for r in res)


# ---------------------------------------------------------------- runtime zoom: native-scale region capture

def test_native_scale_at_uses_hello_screens():
    screens = [{"id": 1, "frame": [0, 0, 1512, 982], "scale": 2.0},
               {"id": 2, "frame": [-1920, -1080, 1920, 1080], "scale": 1.0}]
    assert g.native_scale_at((100, 100), screens) == 2.0
    assert g.native_scale_at((-10, -10), screens) == 1.0
    assert g.native_scale_at((5000, 5000), screens, default=2.0) == 2.0


def test_native_zoom_region_fits_cap_at_native_scale():
    shot = {"width": 1248, "height": 811, "origin": [-1512, -200], "scale": 1248 / 1512}
    pt = (600, 400)
    x, y, w, h = g.native_zoom_region(pt, shot, native_scale=2.0, max_pixels=1_000_000, frac=0.4)
    assert w * h * 4 <= 1_000_000 + 1e-6
    gx, gy = g.to_global(pt, shot)
    assert (x + w / 2, y + h / 2) == pytest.approx((gx, gy))
    # near a corner it shifts inside the shot instead of shrinking
    x, y, w2, h2 = g.native_zoom_region((0, 0), shot, native_scale=2.0, frac=0.4)
    assert (x, y) == (-1512, -200) and (w2, h2) == pytest.approx((w, h))
    # non-Retina display: frac-limited, not cap-limited
    flat = {"width": 1000, "height": 500, "origin": [0, 0], "scale": 1.0}
    assert g.native_zoom_region((500, 250), flat, native_scale=1.0, frac=0.4)[2:] == pytest.approx([400, 200])


DISPLAY = (-1512.0, -200.0, 1512.0, 982.0)   # secondary Retina display left of main, global points
BACKING = 2.0
TARGET_G = (-1512 + 1000.25, -200 + 700.5)    # 4x4 pt red square centre, global points


class FakeDesktop:
    """Mimics HandsKit Screenshot.captureImage: region intersected with its display, captured at backing
    scale, downscaled only if w*h > max_pixels; scale = px per point."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        ox, oy, w, h = DISPLAY
        self.native = Image.new("RGB", (int(w * BACKING), int(h * BACKING)), "white")
        cx, cy = (TARGET_G[0] - ox) * BACKING, (TARGET_G[1] - oy) * BACKING
        ImageDraw.Draw(self.native).rectangle([cx - 4, cy - 4, cx + 3, cy + 3], fill=(255, 0, 0))
        self.calls = []

    def _shot(self, src, max_pixels, name):
        ox, oy, _, _ = DISPLAY
        sx, sy, sw, sh = src
        pw, ph = sw * BACKING, sh * BACKING
        k = min(1.0, math.sqrt(max_pixels / (pw * ph)))
        w, h = max(1, round(pw * k)), max(1, round(ph * k))
        crop = self.native.crop((round((sx - ox) * BACKING), round((sy - oy) * BACKING),
                                 round((sx - ox + sw) * BACKING), round((sy - oy + sh) * BACKING)))
        img = crop.resize((w, h), Image.Resampling.LANCZOS) if (w, h) != crop.size else crop
        path = self.tmp / f"{name}.png"
        img.save(path)
        return {"path": str(path), "width": w, "height": h, "origin": [sx, sy], "scale": w / sw}

    def full(self, max_pixels=1_000_000):
        return self._shot(DISPLAY, max_pixels, "full")

    def capture(self, region, max_pixels):
        self.calls.append((list(region), max_pixels))
        dx, dy, dw, dh = DISPLAY
        x1, y1 = max(region[0], dx), max(region[1], dy)
        x2, y2 = min(region[0] + region[2], dx + dw), min(region[1] + region[3], dy + dh)
        return self._shot((x1, y1, x2 - x1, y2 - y1), max_pixels, f"region{len(self.calls)}")


class RedBackend:
    """'Model' that finds the red square in whatever image it is given; the first call is `bias` px off
    (in the pixels it saw), like a coarse full-screen guess."""

    def __init__(self, bias=(9, -6)):
        self.bias, self.sizes = bias, []

    def __call__(self, image, system, user, adapter):
        self.sizes.append(image.size)
        px = image.load()
        pts = [(x, y) for y in range(image.height) for x in range(image.width)
               if px[x, y][0] > 200 and px[x, y][1] < 120 and px[x, y][2] < 120]
        cx = sum(p[0] for p in pts) / len(pts) + 0.5 + self.bias[0]
        cy = sum(p[1] for p in pts) / len(pts) + 0.5 + self.bias[1]
        self.bias = (0, 0)
        x, y = g.pixels_to_model((cx, cy), adapter.coord, image.size, image.size)
        return adapter.answer.format(x=round(x, 3), y=round(y, 3))


@pytest.mark.parametrize("name", ["eyes-4b", "gta1-7b", "ui-venus-1.5-8b"])
def test_runtime_zoom_captures_native_region_not_recrop(tmp_path, name):
    desk = FakeDesktop(tmp_path)
    shot = desk.full()
    assert shot["width"] * shot["height"] <= 1_001_000 and shot["scale"] < BACKING   # downscaled ~1 MP shot
    be = RedBackend()
    gr = Grounder(name, backend=be, capture=desk.capture,
                  screens=[{"id": 2, "frame": list(DISPLAY), "scale": BACKING}])
    image = Image.open(shot["path"]).convert("RGB")
    stages = gr.run(image, "the red square", shot=shot)
    assert [s.name for s in stages] == ["full", "zoom"]

    # exactly one region screenshot, sized to come back at native backing scale under the cap
    assert len(desk.calls) == 1
    region, mp = desk.calls[0]
    assert mp == gr.max_pixels and region[2] * region[3] * BACKING ** 2 <= mp + 1e-6
    rx, ry, rw, rh = region
    gx, gy = g.to_global(stages[0].point, shot)
    assert rx <= gx <= rx + rw and ry <= gy <= ry + rh
    # stage 2 saw native pixels (2 px/pt), not an upsampled crop of the 1 MP shot (~0.83 px/pt)
    region_px = (round(rw * BACKING), round(rh * BACKING))
    h2, w2 = g.smart_resize(region_px[1], region_px[0], gr.adapter.factor, max_pixels=gr.max_pixels)
    assert be.sizes[1] == (w2, h2)

    truth = g.from_global(TARGET_G, shot)
    assert math.dist(stages[1].point, truth) < 0.6
    assert math.dist(stages[0].point, truth) > 3
    bx = stages[1].box
    assert bx[0] <= truth[0] <= bx[2] and bx[1] <= truth[1] <= bx[3]
    assert g.to_global(stages[1].point, shot) == pytest.approx(TARGET_G, abs=0.5)


def test_locate_with_shot_returns_screenshot_pixels(tmp_path):
    desk = FakeDesktop(tmp_path)
    shot = desk.full()
    gr = Grounder("eyes-4b", backend=RedBackend(), capture=desk.capture)
    out = gr.locate(shot["path"], "the red square", shot=shot)
    truth = g.from_global(TARGET_G, shot)
    assert math.dist((out["x"], out["y"]), truth) < 0.6
    assert g.to_global(out, shot) == pytest.approx(TARGET_G, abs=0.5)
    assert out["conf"] > 0.5


def test_downscaled_shot_without_capture_does_not_recrop(tmp_path):
    desk = FakeDesktop(tmp_path)
    shot = desk.full()
    be = RedBackend(bias=(0, 0))
    gr = Grounder("eyes-4b", backend=be)
    stages = gr.run(Image.open(shot["path"]).convert("RGB"), "x", shot=shot)
    assert [s.name for s in stages] == ["full"] and len(be.sizes) == 1


def test_native_shot_without_capture_crops_locally(tmp_path):
    desk = FakeDesktop(tmp_path)
    shot = desk.full(max_pixels=10_000_000)                       # already native (scale 2.0)
    assert shot["scale"] == BACKING
    gr = Grounder("eyes-4b", backend=RedBackend())
    stages = gr.run(Image.open(shot["path"]).convert("RGB"), "x", shot=shot)
    assert [s.name for s in stages] == ["full", "zoom"]
    assert math.dist(stages[1].point, g.from_global(TARGET_G, shot)) < 0.6


def test_alocate_with_async_handskit_capture(tmp_path):
    import asyncio
    desk = FakeDesktop(tmp_path)
    shot = desk.full()
    sent = []

    async def rpc(method, params):
        sent.append((method, params))
        return desk.capture(params["region"], params["max_pixels"])

    gr = Grounder("gta1-7b", backend=RedBackend(), capture=g.handskit_capture(rpc))
    out = asyncio.run(gr.alocate(shot["path"], "the red square", shot=shot))
    assert sent and sent[0][0] == "screenshot" and set(sent[0][1]) == {"region", "max_pixels"}
    assert math.dist((out["x"], out["y"]), g.from_global(TARGET_G, shot)) < 0.6
    with pytest.raises(TypeError):
        gr.locate(shot["path"], "the red square", shot=shot)       # async capture needs alocate
