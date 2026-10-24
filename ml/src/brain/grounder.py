"""Visual grounder: screenshot + instruction -> click point, fully on device (MLX / mlx-vlm).

Used only when the AX tree is blind (canvas apps, some web content, Premiere's timeline).
Coordinates returned by `Grounder.locate` are screenshot pixels; `to_global` maps them to global
points with the HandsKit screenshot metadata (`global = origin + pixel / scale`).

Each candidate model has an `Adapter` (prompt, parser, coordinate convention, resize factor). Images are
pre-resized with Qwen's `smart_resize` to a multiple of the vision factor (patch * merge) under a pixel cap
(~1 MP per AGENTS.md), so the processor does not resize again and resized-pixel outputs map back exactly.
mlx / mlx-vlm are imported lazily so everything except inference runs on Linux.
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

Point = tuple[float, float]
Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels

DEFAULT_MAX_PIXELS = 1_000_000

NORM_1000 = "norm1000"   # 0..1000 relative to the image the model saw
UNIT = "unit"            # 0..1 relative to the image the model saw
RESIZED_PX = "resized_px"  # absolute pixels of the (smart-resized) image the model saw


# ---------------------------------------------------------------- resize / token math

def smart_resize(height: int, width: int, factor: int = 32, min_pixels: int = 0,
                 max_pixels: int = DEFAULT_MAX_PIXELS) -> tuple[int, int]:
    """Qwen2-VL/2.5-VL/3-VL `smart_resize`: both sides multiples of `factor`, area within
    [min_pixels, max_pixels], aspect ratio kept as closely as possible. Returns (height, width)."""
    if height <= 0 or width <= 0:
        raise ValueError(f"bad image size {width}x{height}")
    if max(height, width) / min(height, width) > 200:
        raise ValueError("aspect ratio must be < 200")
    h_bar = max(factor, round(height / factor) * factor)
    w_bar = max(factor, round(width / factor) * factor)
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = max(factor, math.floor(height / beta / factor) * factor)
        w_bar = max(factor, math.floor(width / beta / factor) * factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = math.ceil(height * beta / factor) * factor
        w_bar = math.ceil(width * beta / factor) * factor
    return h_bar, w_bar


def image_tokens(width: int, height: int, factor: int, max_pixels: int = DEFAULT_MAX_PIXELS) -> int:
    """Visual tokens the LLM sees for one image: one token per (factor x factor) merged patch."""
    h, w = smart_resize(height, width, factor, max_pixels=max_pixels)
    return (h // factor) * (w // factor)


# ---------------------------------------------------------------- coordinate math

def model_to_pixels(pt: Point, convention: str, model_size: tuple[int, int],
                    image_size: tuple[int, int]) -> Point:
    """Map a model-space point to pixels of the image that was resized for the model.
    `model_size` = (w, h) the model saw; `image_size` = (w, h) of the source image."""
    x, y = pt
    mw, mh = model_size
    iw, ih = image_size
    if convention == NORM_1000:
        return x / 1000.0 * iw, y / 1000.0 * ih
    if convention == UNIT:
        return x * iw, y * ih
    if convention == RESIZED_PX:
        return x * iw / mw, y * ih / mh
    raise ValueError(f"unknown coordinate convention {convention!r}")


def pixels_to_model(pt: Point, convention: str, model_size: tuple[int, int],
                    image_size: tuple[int, int]) -> Point:
    """Inverse of `model_to_pixels` (used by the benchmark's oracle dry run and tests)."""
    x, y = pt
    mw, mh = model_size
    iw, ih = image_size
    if convention == NORM_1000:
        return x * 1000.0 / iw, y * 1000.0 / ih
    if convention == UNIT:
        return x / iw, y / ih
    if convention == RESIZED_PX:
        return x * mw / iw, y * mh / ih
    raise ValueError(f"unknown coordinate convention {convention!r}")


def clamp_point(pt: Point, size: tuple[int, int]) -> Point:
    w, h = size
    return min(max(pt[0], 0.0), w - 1.0), min(max(pt[1], 0.0), h - 1.0)


def crop_around(pt: Point, image_size: tuple[int, int], crop_size: tuple[float, float]) -> Box:
    """Crop box of `crop_size` (w, h) centred on `pt`, shifted (not shrunk) to stay inside the image."""
    iw, ih = image_size
    cw, ch = min(crop_size[0], iw), min(crop_size[1], ih)
    x1 = min(max(pt[0] - cw / 2, 0.0), iw - cw)
    y1 = min(max(pt[1] - ch / 2, 0.0), ih - ch)
    return round(x1), round(y1), round(x1 + cw), round(y1 + ch)


def pad_box(box: Box, image_size: tuple[int, int], pad: float = 0.25, min_side: float = 0.0) -> Box:
    """Grow a hint box by `pad` of its size on each side (and to at least `min_side`), clamped to the image."""
    x1, y1, x2, y2 = box
    w, h = max(x2 - x1, min_side), max(y2 - y1, min_side)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    w, h = w * (1 + 2 * pad), h * (1 + 2 * pad)
    return crop_around((cx, cy), image_size, (w, h))


def crop_to_image(pt: Point, box: Box) -> Point:
    """A point in crop pixels -> pixels of the image the crop was taken from."""
    return pt[0] + box[0], pt[1] + box[1]


def point_in_box(pt: Point, box: Box) -> bool:
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def to_global(pt, shot: dict) -> tuple[float, float]:
    """Screenshot pixel -> global screen point (top-left origin, points): origin + pixel / scale.
    Accepts `pt` as (x, y) or a `locate` result dict."""
    if isinstance(pt, dict):
        pt = (pt["x"], pt["y"])
    ox, oy = shot["origin"]
    scale = float(shot.get("scale") or 1.0)
    return ox + pt[0] / scale, oy + pt[1] / scale


def from_global(pt: Point, shot: dict) -> tuple[float, float]:
    ox, oy = shot["origin"]
    scale = float(shot.get("scale") or 1.0)
    return (pt[0] - ox) * scale, (pt[1] - oy) * scale


def zoom_region(pt: Point, shot: dict, frac: float = 0.35, min_points: float = 240.0) -> list[float]:
    """Region [x, y, w, h] in global points around a screenshot-pixel guess, for a fresh
    high-resolution `screenshot {region}` capture (better than upscaling a 1 MP shot)."""
    scale = float(shot.get("scale") or 1.0)
    sw, sh = shot["width"] / scale, shot["height"] / scale
    cw = min(sw, max(min_points, sw * frac))
    ch = min(sh, max(min_points, sh * frac))
    gx, gy = pt[0] / scale, pt[1] / scale
    x1, y1, x2, y2 = crop_around((gx, gy), (sw, sh), (cw, ch))
    ox, oy = shot["origin"]
    return [ox + x1, oy + y1, x2 - x1, y2 - y1]


# ---------------------------------------------------------------- output parsers

_NUM = r"-?\d+(?:\.\d+)?"
_PAIR_BRACKET = re.compile(rf"\[\s*({_NUM})\s*,\s*({_NUM})\s*\]")
_PAIR_PAREN = re.compile(rf"\(\s*({_NUM})\s*,\s*({_NUM})\s*\)")
_QUAD = re.compile(rf"[\[(]\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*[\])]")
_POINT_TAG = re.compile(rf"<point>\s*({_NUM})[\s,]+({_NUM})\s*</point>")


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S)


def parse_point_2d(text: str) -> Optional[Point]:
    """Qwen3-VL / DeskMind: {"point_2d": [x, y]} (also accepts a bbox_2d centre, or a bare [x, y])."""
    text = _strip_think(text)
    m = re.search(rf'"point_2d"\s*:\s*\[\s*({_NUM})\s*,\s*({_NUM})\s*\]', text)
    if m:
        return float(m[1]), float(m[2])
    m = re.search(rf'"bbox_2d"\s*:\s*\[\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*\]', text)
    if m:
        return (float(m[1]) + float(m[3])) / 2, (float(m[2]) + float(m[4])) / 2
    m = _PAIR_BRACKET.search(text) or _PAIR_PAREN.search(text)
    return (float(m[1]), float(m[2])) if m else None


def parse_xy_json(text: str) -> Optional[Point]:
    """Holo: {"x": 512, "y": 300}."""
    text = _strip_think(text)
    mx = re.search(rf'"x"\s*:\s*({_NUM})', text)
    my = re.search(rf'"y"\s*:\s*({_NUM})', text)
    if mx and my:
        return float(mx[1]), float(my[1])
    return parse_point_2d(text)


def parse_tool_call(text: str) -> Optional[Point]:
    """Qwen computer_use tool call (GUI-Owl, Fara): <tool_call>{"name": "computer_use",
    "arguments": {"action": "left_click", "coordinate": [x, y]}}</tool_call>. Last call wins."""
    text = _strip_think(text)
    for body in reversed(re.findall(r"<tool_call>(.*?)</tool_call>", text, flags=re.S)):
        try:
            args = json.loads(body.strip()).get("arguments", {})
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                continue
        coord = args.get("coordinate")
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            return float(coord[0]), float(coord[1])
    m = re.search(rf'"coordinate"\s*:\s*\[\s*({_NUM})\s*,\s*({_NUM})\s*\]', text)
    if m:
        return float(m[1]), float(m[2])
    # GUI-Owl's own eval falls back to the last "(x, y)" then "[x, y]".
    pairs = _PAIR_PAREN.findall(text) or _PAIR_BRACKET.findall(text)
    return (float(pairs[-1][0]), float(pairs[-1][1])) if pairs else None


def parse_paren_point(text: str) -> Optional[Point]:
    """GTA1 `(x,y)`; UI-TARS `click(start_box='(x,y)')` or `<point>x y</point>`. First match wins
    (GTA1's reference parser takes the first pair)."""
    text = _strip_think(text)
    m = _POINT_TAG.search(text)
    if m:
        return float(m[1]), float(m[2])
    m = _QUAD.search(text)
    if m and "start_box" in text and not _PAIR_PAREN.search(text):
        return (float(m[1]) + float(m[3])) / 2, (float(m[2]) + float(m[4])) / 2
    m = _PAIR_PAREN.search(text) or _PAIR_BRACKET.search(text)
    return (float(m[1]), float(m[2])) if m else None


def parse_bbox_center(text: str) -> Optional[Point]:
    """UI-Venus: `[x1,y1,x2,y2]` -> centre; a bare point is accepted too."""
    text = _strip_think(text)
    m = _QUAD.search(text)
    if m:
        x1, y1, x2, y2 = (float(v) for v in m.groups())
        return (x1 + x2) / 2, (y1 + y2) / 2
    return parse_point_2d(text)


# ---------------------------------------------------------------- adapters

EYES_PROMPT = (
    "Locate the UI element in the screenshot that matches the description, and output its click point in JSON as\n"
    '{{"point_2d": [x, y]}}, with coordinates in 0-1000 relative to the image.\n'
    "Description: {instruction}"
)

# mPLUG eval_grounding_benchmarks.py `only_two_action_system_prompt` (Qwen3-VL computer_use, 1000x1000 space).
GUI_OWL_SYSTEM = (
    "# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
    "You are provided with function signatures within <tools></tools> XML tags:\n<tools>\n"
    '{"type": "function", "function": {"name": "computer_use", "description": "Use a mouse to interact with a computer.\n'
    "* The screen's resolution is 1000x1000.\n"
    "* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. "
    "Don't click boxes on their edges unless asked.\n"
    "* don't use any other computer use tool like type, key, scroll, left_click_drag and so on.\n"
    "* you can only use the left_click and mouse_move action to interact with the computer. if you can't find the "
    'element, you should terminate the task and report the failure.", "parameters": {"properties": {"action": '
    '{"description": "The action to perform. The available actions are:\n* `mouse_move`: Move the cursor to a '
    'specified (x, y) pixel coordinate on the screen.\n* `left_click`: Click the left mouse button with coordinate '
    '(x, y) pixel coordinate on the screen.", "enum": ["mouse_move", "left_click"], "type": "string"}, '
    '"coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) '
    'coordinates to move the mouse to. Required only by `action=mouse_move` and `action=left_click`.", '
    '"type": "array"}}, "required": ["action"], "type": "object"}}}\n</tools>\n\n'
    "For each function call, return a json object with function name and arguments within <tool_call></tool_call> "
    'XML tags:\n<tool_call>\n{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call>\n'
)

# Same tool schema with the real (resized) resolution: for pixel-space computer_use models (Fara).
PIXEL_TOOL_SYSTEM = GUI_OWL_SYSTEM.replace("1000x1000", "{width}x{height}")

HOLO_SCHEMA = (
    "{'properties': {'x': {'description': 'The x coordinate, normalized between 0 and 1000.', 'maximum': 1000, "
    "'minimum': 0, 'title': 'X', 'type': 'integer'}, 'y': {'description': 'The y coordinate, normalized between 0 "
    "and 1000.', 'maximum': 1000, 'minimum': 0, 'title': 'Y', 'type': 'integer'}}, 'required': ['x', 'y'], "
    "'title': 'ClickCoordinates', 'type': 'object'}"
)
HOLO_PROMPT = (
    "Localize an element on the GUI image according to the provided target and output a click position.\n"
    "     * You must output a valid JSON following the format: " + HOLO_SCHEMA.replace("{", "{{").replace("}", "}}")
    + "\n     Your target is:\n{instruction}"
)

GTA1_SYSTEM = (
    "You are an expert UI element locator. Given a GUI image and a user's element description, provide the "
    "coordinates of the specified element as a single (x,y) point. The image resolution is height {height} and "
    "width {width}. For elements with area, return the center point.\n\nOutput the coordinate pair exactly:\n(x,y)"
)

UI_TARS_PROMPT = (
    "You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the "
    "next action to complete the task. \n\n## Output Format\n\nAction: ...\n\n\n## Action Space\n"
    "click(point='<point>x1 y1</point>'')\n\n## User Instruction\n{instruction}"
)

VENUS_PROMPT = ("Outline the position corresponding to the instruction: {instruction}. "
                "The output should be only [x1,y1,x2,y2].")


@dataclass(frozen=True)
class Adapter:
    name: str
    repo: str                      # MLX weights (HF repo id, or local dir produced by mlx_vlm.convert)
    source: str                    # original (non-MLX) HF repo
    parse: Callable[[str], Optional[Point]]
    coord: str                     # NORM_1000 | UNIT | RESIZED_PX
    user: str                      # template: {instruction}, {width}, {height}
    system: Optional[str] = None
    factor: int = 32               # patch_size * merge_size (Qwen3-VL/3.5: 16*2, Qwen2.5-VL: 14*2)
    revision: Optional[str] = None
    max_tokens: int = 64
    chat_kwargs: dict = field(default_factory=dict)
    answer: str = ""               # canonical model output for a point, {x} {y} (oracle runs + parser tests)

    def prompt(self, instruction: str, width: int, height: int) -> tuple[Optional[str], str]:
        fmt = dict(instruction=instruction, width=width, height=height)
        return (self.system.format(**fmt) if self.system else None), self.user.format(**fmt)

    def to_pixels(self, raw: Point, model_size: tuple[int, int], image_size: tuple[int, int]) -> Point:
        return model_to_pixels(raw, self.coord, model_size, image_size)


def _literal(text: str, *placeholders: str) -> str:
    """Escape braces for str.format, keeping the given placeholders live."""
    out = text.replace("{", "{{").replace("}", "}}")
    for p in placeholders:
        out = out.replace("{{" + p + "}}", "{" + p + "}")
    return out


_NO_THINK = {"enable_thinking": False}
POINT_2D = '{{"point_2d": [{x}, {y}]}}'
TOOL_CALL = ('<tool_call>\n{{"name": "computer_use", "arguments": {{"action": "left_click", '
             '"coordinate": [{x}, {y}]}}}}\n</tool_call>')
XY_JSON = '{{"x": {x}, "y": {y}}}'
BBOX = "[{x},{y},{x},{y}]"


def _a(name, repo, source, parse, coord, user, answer, **kw) -> Adapter:
    return Adapter(name, repo, source, parse, coord, user, answer=answer, **kw)


ADAPTERS: dict[str, Adapter] = {a.name: a for a in [
    _a("eyes-4b", "deskmind/eyes-4b", "deskmind/eyes-4b", parse_point_2d, NORM_1000, EYES_PROMPT, POINT_2D,
       revision="mlx-4bit", max_tokens=32),
    _a("gui-owl-1.5-4b", "models/gui-owl-1.5-4b-mlx-4bit", "mPLUG/GUI-Owl-1.5-4B-Instruct", parse_tool_call,
       NORM_1000, "{instruction}", TOOL_CALL, system=_literal(GUI_OWL_SYSTEM), max_tokens=96),
    _a("gui-owl-1.5-8b", "models/gui-owl-1.5-8b-mlx-4bit", "mPLUG/GUI-Owl-1.5-8B-Instruct", parse_tool_call,
       NORM_1000, "{instruction}", TOOL_CALL, system=_literal(GUI_OWL_SYSTEM), max_tokens=96),
    _a("ui-venus-1.5-8b", "mlx-community/UI-Venus-1.5-8B-4bit", "inclusionAI/UI-Venus-1.5-8B", parse_bbox_center,
       NORM_1000, VENUS_PROMPT, BBOX),
    _a("ui-venus-1.5-2b", "mlx-community/UI-Venus-1.5-2B-6bit", "inclusionAI/UI-Venus-1.5-2B", parse_bbox_center,
       NORM_1000, VENUS_PROMPT, BBOX),
    _a("ui-venus-2-9b", "lethargicgeek/UI-Venus-2-9B-mlx-4bit", "inclusionAI/UI-Venus-2-9B", parse_bbox_center,
       NORM_1000, VENUS_PROMPT, BBOX, chat_kwargs=_NO_THINK),
    _a("holo2-8b", "mlx-community/Holo2-8B-bf16", "Hcompany/Holo2-8B", parse_xy_json, NORM_1000, HOLO_PROMPT,
       XY_JSON, chat_kwargs={"thinking": False}),
    _a("holo2-4b", "models/holo2-4b-mlx-4bit", "Hcompany/Holo2-4B", parse_xy_json, NORM_1000, HOLO_PROMPT,
       XY_JSON, chat_kwargs={"thinking": False}),
    _a("qwen3-vl-4b", "mlx-community/Qwen3-VL-4B-Instruct-4bit", "Qwen/Qwen3-VL-4B-Instruct", parse_point_2d,
       NORM_1000, EYES_PROMPT, POINT_2D, max_tokens=32),
    _a("qwen3.5-4b", "mlx-community/Qwen3.5-4B-MLX-4bit", "Qwen/Qwen3.5-4B", parse_point_2d, NORM_1000,
       EYES_PROMPT, POINT_2D, max_tokens=32, chat_kwargs=_NO_THINK),
    _a("fara1.5-4b", "mlx-community/Fara1.5-4B-8bit", "microsoft/Fara1.5-4B", parse_tool_call, RESIZED_PX,
       "{instruction}", TOOL_CALL, system=_literal(PIXEL_TOOL_SYSTEM, "width", "height"), max_tokens=256,
       chat_kwargs=_NO_THINK),
    _a("gta1-7b", "mlx-community/GTA1-7B-4bit", "HelloKKMe/GTA1-7B", parse_paren_point, RESIZED_PX,
       "{instruction}", "({x},{y})", system=GTA1_SYSTEM, factor=28, max_tokens=32),
    _a("ui-tars-1.5-7b", "mlx-community/UI-TARS-1.5-7B-4bit", "ByteDance-Seed/UI-TARS-1.5-7B", parse_paren_point,
       RESIZED_PX, UI_TARS_PROMPT, "Action: click(start_box='({x},{y})')", factor=28, max_tokens=48),
]}


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        raise KeyError(f"unknown grounder {name!r}; known: {', '.join(ADAPTERS)}") from None


# ---------------------------------------------------------------- backends

class Backend(Protocol):
    def __call__(self, image, system: Optional[str], user: str, adapter: Adapter) -> str: ...


class MLXBackend:
    """mlx-vlm inference; imports and loads lazily on first call."""

    def __init__(self, repo: str, revision: Optional[str] = None):
        self.repo, self.revision = repo, revision
        self.model = self.processor = None

    def load(self) -> None:
        if self.model is None:
            from mlx_vlm import load
            self.model, self.processor = load(self.repo, revision=self.revision)

    def __call__(self, image, system, user, adapter):
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        self.load()
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        prompt = apply_chat_template(self.processor, self.model.config, msgs, num_images=1, **adapter.chat_kwargs)
        res = generate(self.model, self.processor, prompt, image=[image], max_tokens=adapter.max_tokens,
                       temperature=0.0, verbose=False)
        return getattr(res, "text", res)


# ---------------------------------------------------------------- grounder

@dataclass
class Stage:
    name: str            # "full" | "hint" | "zoom"
    box: Box             # region of the source image the model saw (source pixels)
    model_size: tuple[int, int]
    raw: str
    point: Optional[Point]  # source-image pixels
    ms: float


class Grounder:
    """`locate(image_path, instruction, *, hint_box=None) -> {x, y, conf, ms}` in screenshot pixels.

    Stage 1 runs on the full screenshot (or on `hint_box`, padded, when the caller already knows the area).
    With `zoom`, stage 2 crops `zoom_frac` of the screenshot around the first guess, upsamples it to the
    pixel cap, re-locates, and maps back. `conf` is a heuristic (agreement between stages), not a probability.
    Images are never retained between calls.
    """

    def __init__(self, model: str = "eyes-4b", *, repo: Optional[str] = None, max_pixels: int = DEFAULT_MAX_PIXELS,
                 zoom: bool = True, zoom_frac: float = 0.4, min_crop: int = 448, backend: Optional[Backend] = None):
        self.adapter = get_adapter(model)
        self.max_pixels = max_pixels
        self.zoom, self.zoom_frac, self.min_crop = zoom, zoom_frac, min_crop
        self.backend = backend or MLXBackend(repo or self.adapter.repo,
                                             None if repo else self.adapter.revision)

    def prepare(self, image):
        """Resize to the adapter's factor grid under the pixel cap; returns (resized, (w, h))."""
        from PIL import Image
        h, w = smart_resize(image.height, image.width, self.adapter.factor, max_pixels=self.max_pixels)
        if (w, h) != image.size:
            image = image.resize((w, h), Image.Resampling.LANCZOS)
        return image, (w, h)

    def ground(self, image, instruction: str, box: Optional[Box] = None, name: str = "full") -> Stage:
        """One model call on `box` of `image` (PIL); the point comes back in `image` pixels."""
        if box is None:
            box = (0, 0, image.width, image.height)
        region = image if box == (0, 0, image.width, image.height) else image.crop(tuple(int(v) for v in box))
        t0 = time.perf_counter()
        resized, size = self.prepare(region)
        system, user = self.adapter.prompt(instruction, *size)
        raw = self.backend(resized, system, user, self.adapter)
        ms = (time.perf_counter() - t0) * 1000
        pt = self.adapter.parse(raw)
        if pt is not None:
            local = self.adapter.to_pixels(pt, size, region.size)
            local = clamp_point(local, region.size)
            pt = crop_to_image(local, box)
        return Stage(name, box, size, raw, pt, ms)

    def zoom_box(self, pt: Point, image_size: tuple[int, int]) -> Box:
        iw, ih = image_size
        cw = max(self.min_crop, iw * self.zoom_frac)
        ch = max(self.min_crop, ih * self.zoom_frac)
        return crop_around(pt, image_size, (cw, ch))

    def run(self, image, instruction: str, *, hint_box: Optional[Box] = None,
            zoom: Optional[bool] = None) -> list[Stage]:
        zoom = self.zoom if zoom is None else zoom
        if hint_box is not None:
            box = pad_box(hint_box, image.size, min_side=self.min_crop / 2)
            stages = [self.ground(image, instruction, box, "hint")]
        else:
            stages = [self.ground(image, instruction)]
        first = stages[0]
        if zoom and first.point is not None:
            zb = self.zoom_box(first.point, image.size)
            seen = first.box
            if (zb[2] - zb[0]) * (zb[3] - zb[1]) < (seen[2] - seen[0]) * (seen[3] - seen[1]):
                stages.append(self.ground(image, instruction, zb, "zoom"))
        return stages

    @staticmethod
    def confidence(stages: list[Stage]) -> float:
        if not stages or stages[-1].point is None:
            if len(stages) > 1 and stages[0].point is not None:
                return 0.25
            return 0.0
        if len(stages) == 1:
            return 0.5
        a, b = stages[0].point, stages[-1].point
        if a is None:
            return 0.5
        bx = stages[-1].box
        half_diag = math.hypot(bx[2] - bx[0], bx[3] - bx[1]) / 2
        return round(max(0.0, 1.0 - math.dist(a, b) / half_diag), 3)

    @staticmethod
    def final_point(stages: list[Stage]) -> Optional[Point]:
        for s in reversed(stages):
            if s.point is not None:
                return s.point
        return None

    def locate(self, image_path: str, instruction: str, *, hint_box: Optional[Box] = None) -> dict:
        from PIL import Image
        t0 = time.perf_counter()
        with Image.open(image_path) as im:
            image = im.convert("RGB")
        stages = self.run(image, instruction, hint_box=hint_box)
        del image
        pt = self.final_point(stages)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if pt is None:
            return {"x": None, "y": None, "conf": 0.0, "ms": ms}
        return {"x": round(pt[0], 1), "y": round(pt[1], 1), "conf": self.confidence(stages), "ms": ms}
