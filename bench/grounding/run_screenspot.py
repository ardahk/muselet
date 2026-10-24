"""ScreenSpot-Pro / OSWorld-G grounding benchmark for Muselet's on-device grounders (MLX).

EVAL ONLY: ScreenSpot-Pro and OSWorld-G are evaluation sets. Never train on them or on anything derived
from them (AGENTS.md); downloads go to data/ (gitignored), results to runs/grounding/.

  uv run --project ml python bench/grounding/run_screenspot.py --models eyes-4b ui-venus-1.5-8b --limit 50
  uv run --project ml python bench/grounding/run_screenspot.py --models eyes-4b --zoom --category CAD,premiere
  uv run --project ml python bench/grounding/run_screenspot.py --dataset osworld-g --models eyes-4b
  uv run --project ml python bench/grounding/run_screenspot.py --models all --oracle --limit 20   # no model, CI-safe

Sources: ScreenSpot-Pro = HF dataset `likaixin/ScreenSpot-Pro` (annotations/*.json + images/, 1581 samples,
bbox = [x1, y1, x2, y2] original pixels). OSWorld-G = HF dataset `MMInstruction/OSWorld-G` (one parquet, 510
samples; `bbox` = [x, y, w, h], `polygon` = flat [x1, y1, x2, y2, ...]).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "src"))

from brain.grounder import (  # noqa: E402
    ADAPTERS, Adapter, Box, Grounder, Point, Stage, get_adapter, pixels_to_model,
)

SSP_REPO = "likaixin/ScreenSpot-Pro"
OSG_REPO = "MMInstruction/OSWorld-G"
OSG_FILE = "data/test-00000-of-00001.parquet"


# ---------------------------------------------------------------- targets

@dataclass(frozen=True)
class Target:
    kind: str                 # "bbox" (x1, y1, x2, y2) | "polygon" (flat x, y list)
    coords: tuple[float, ...]

    def contains(self, pt: Optional[Point]) -> bool:
        if pt is None:
            return False
        if self.kind == "bbox":
            x1, y1, x2, y2 = self.coords
            return x1 <= pt[0] <= x2 and y1 <= pt[1] <= y2
        return point_in_polygon(pt, list(zip(self.coords[0::2], self.coords[1::2])))

    def center(self) -> Point:
        xs, ys = self.coords[0::2], self.coords[1::2]
        if self.kind == "bbox":
            return (xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2
        return sum(xs) / len(xs), sum(ys) / len(ys)


def point_in_polygon(pt: Point, poly: list[Point]) -> bool:
    """Ray casting; points on an edge count as inside. Two-vertex 'polygons' are boxes."""
    if len(poly) == 2:
        (x1, y1), (x2, y2) = poly
        return min(x1, x2) <= pt[0] <= max(x1, x2) and min(y1, y2) <= pt[1] <= max(y1, y2)
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        if min(xa, xb) <= x <= max(xa, xb) and min(ya, yb) <= y <= max(ya, yb):
            if abs((xb - xa) * (y - ya) - (yb - ya) * (x - xa)) < 1e-9:
                return True
        if (ya > y) != (yb > y) and x < (xb - xa) * (y - ya) / (yb - ya) + xa:
            inside = not inside
    return inside


@dataclass
class Sample:
    id: str
    instruction: str
    target: Target
    load_image: Callable          # () -> PIL.Image (opened lazily; never cached)
    application: str = ""
    group: str = ""
    platform: str = ""
    ui_type: str = ""
    image_size: tuple[int, int] = (0, 0)


# ---------------------------------------------------------------- loaders

def ssp_sample(row: dict, image_root: Path) -> Sample:
    def load():
        from PIL import Image
        with Image.open(image_root / row["img_filename"]) as im:
            return im.convert("RGB")
    return Sample(id=row["id"], instruction=row["instruction"], target=Target("bbox", tuple(map(float, row["bbox"]))),
                  load_image=load, application=row.get("application", ""), group=row.get("group", ""),
                  platform=row.get("platform", ""), ui_type=row.get("ui_type", ""),
                  image_size=tuple(row.get("img_size") or (0, 0)))


def osg_target(box_type: str, coords) -> Target:
    c = tuple(float(v) for v in coords)
    if box_type == "bbox":
        x, y, w, h = c
        return Target("bbox", (x, y, x + w, y + h))
    if box_type == "polygon":
        return Target("polygon", c)
    raise ValueError(f"unknown OSWorld-G box_type {box_type!r}")


def osg_sample(row: dict) -> Sample:
    img = row.get("image") or {}

    def load():
        from PIL import Image
        with Image.open(io.BytesIO(img["bytes"])) as im:
            return im.convert("RGB")
    gui = row.get("GUI_types") or []
    return Sample(id=row["id"], instruction=row["instruction"], target=osg_target(row["box_type"], row["box_coordinates"]),
                  load_image=load, application="", group=gui[0] if gui else "", platform="linux",
                  ui_type=",".join(gui), image_size=tuple(row.get("image_size") or (0, 0)))


def matches(sample: Sample, categories: list[str]) -> bool:
    if not categories:
        return True
    keys = {sample.group.lower(), sample.application.lower(), sample.platform.lower(), sample.ui_type.lower()}
    keys |= {t.lower() for t in sample.ui_type.split(",")}
    return any(c.lower() in keys for c in categories)


def select(samples: list[Sample], categories: list[str], limit: Optional[int]) -> list[Sample]:
    out = [s for s in samples if matches(s, categories)]
    return out[:limit] if limit else out


def load_screenspot_pro(data_dir: Path, categories: list[str], limit: Optional[int]) -> list[Sample]:
    from huggingface_hub import snapshot_download
    root = data_dir / "screenspot_pro"
    snapshot_download(SSP_REPO, repo_type="dataset", allow_patterns=["annotations/*.json"], local_dir=root)
    rows = []
    for f in sorted((root / "annotations").glob("*.json")):
        rows.extend(json.loads(f.read_text()))
    samples = select([ssp_sample(r, root / "images") for r in rows], categories, limit)
    wanted = sorted({r["img_filename"] for r in rows if any(r["id"] == s.id for s in samples)})
    missing = [w for w in wanted if not (root / "images" / w).exists()]
    if missing:
        snapshot_download(SSP_REPO, repo_type="dataset", allow_patterns=[f"images/{w}" for w in missing],
                          local_dir=root)
    return samples


def load_osworld_g(data_dir: Path, categories: list[str], limit: Optional[int]) -> list[Sample]:
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq
    path = hf_hub_download(OSG_REPO, OSG_FILE, repo_type="dataset", local_dir=data_dir / "osworld_g")
    rows = pq.read_table(path).to_pylist()
    return select([osg_sample(r) for r in rows], categories, limit)


DATASETS = {"screenspot-pro": load_screenspot_pro, "osworld-g": load_osworld_g}


# ---------------------------------------------------------------- oracle (no model)

class OracleBackend:
    """Answers with the ground-truth centre in the adapter's own output format: exercises resize, prompt,
    parsing and coordinate conversion end to end without a model."""

    def __init__(self):
        self.target: Optional[Point] = None
        self.box: Box = (0, 0, 0, 0)
        self.region: tuple[int, int] = (0, 0)

    def __call__(self, image, system, user, adapter: Adapter) -> str:
        assert self.target is not None
        local = (self.target[0] - self.box[0], self.target[1] - self.box[1])
        x, y = pixels_to_model(local, adapter.coord, image.size, self.region)
        return adapter.answer.format(x=round(x), y=round(y))


class OracleGrounder(Grounder):
    def ground(self, image, instruction, box=None, name="full") -> Stage:
        b = box or (0, 0, image.width, image.height)
        self.backend.box = b
        self.backend.region = (int(b[2]) - int(b[0]), int(b[3]) - int(b[1]))
        return super().ground(image, instruction, box, name)


# ---------------------------------------------------------------- metrics

def percentile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)


def summarize(results: list[dict]) -> dict:
    def acc(rows):
        return {"n": len(rows), "acc": round(100.0 * sum(r["hit"] for r in rows) / len(rows), 2) if rows else None}

    out = {"overall": acc(results), "parse_fail": sum(r["point"] is None for r in results)}
    for key in ("group", "application", "ui_type", "platform"):
        buckets = defaultdict(list)
        for r in results:
            if r.get(key):
                buckets[r[key]].append(r)
        if buckets:
            out[f"by_{key}"] = {k: acc(v) for k, v in sorted(buckets.items())}
    for st in ("full", "hint", "zoom"):
        stage_hits = [r for r in results if st in r["stage_ms"]]
        if stage_hits and st != "full":
            out[f"acc_before_{st}"] = acc([{**r, "hit": r["hit_stage1"]} for r in stage_hits])
    lat = defaultdict(list)
    for r in results:
        for st, ms in r["stage_ms"].items():
            lat[st].append(ms)
        lat["total"].append(r["ms"])
    out["latency_ms"] = {k: {"p50": percentile(v, 50), "p95": percentile(v, 95), "n": len(v)} for k, v in lat.items()}
    return out


def evaluate(grounder: Grounder, samples: list[Sample], zoom: bool, log=None) -> list[dict]:
    results = []
    for i, s in enumerate(samples):
        image = s.load_image()
        if isinstance(grounder.backend, OracleBackend):
            grounder.backend.target = s.target.center()
        t0 = time.perf_counter()
        stages = grounder.run(image, s.instruction, zoom=zoom)
        ms = (time.perf_counter() - t0) * 1000
        del image
        pt = Grounder.final_point(stages)
        r = dict(id=s.id, group=s.group, application=s.application, ui_type=s.ui_type, platform=s.platform,
                 point=[round(pt[0], 1), round(pt[1], 1)] if pt else None, hit=s.target.contains(pt),
                 hit_stage1=s.target.contains(stages[0].point), ms=round(ms, 1),
                 stage_ms={st.name: round(st.ms, 1) for st in stages},
                 raw=[st.raw for st in stages], model_size=[list(st.model_size) for st in stages])
        results.append(r)
        if log:
            log.write(json.dumps(r) + "\n")
            log.flush()
        if (i + 1) % 25 == 0:
            done = sum(x["hit"] for x in results)
            print(f"  [{i + 1}/{len(samples)}] acc={100.0 * done / len(results):.1f}%", file=sys.stderr, flush=True)
    return results


def parse_model_arg(spec: str) -> tuple[str, Optional[str]]:
    """`name` or `name=local/path` (e.g. a mlx_vlm.convert output dir)."""
    name, _, repo = spec.partition("=")
    get_adapter(name)
    return name, repo or None


def table(name: str, summary: dict) -> str:
    lines = [f"| {name} | overall | {summary['overall']['acc']} | {summary['overall']['n']} |"]
    for k, v in summary.get("by_group", {}).items():
        lines.append(f"| {name} | {k} | {v['acc']} | {v['n']} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True, help=f"adapter names (or name=path), or 'all': {', '.join(ADAPTERS)}")
    ap.add_argument("--dataset", choices=sorted(DATASETS), default="screenspot-pro")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--category", default="", help="comma list matched against group/application/platform/ui_type")
    ap.add_argument("--zoom", action="store_true", help="two-stage: full image -> crop around guess -> re-locate")
    ap.add_argument("--zoom-frac", type=float, default=0.4, help="crop side as a fraction of the image side")
    ap.add_argument("--max-pixels", type=int, default=1_000_000, help="pixel cap per model call (AGENTS.md: ~1 MP)")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "grounding")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "runs" / "grounding")
    ap.add_argument("--oracle", action="store_true", help="no model: answer with ground truth (pipeline check)")
    args = ap.parse_args(argv)

    models = list(ADAPTERS) if args.models == ["all"] else args.models
    specs = [parse_model_arg(m) for m in models]
    categories = [c.strip() for c in args.category.split(",") if c.strip()]
    samples = DATASETS[args.dataset](args.data_dir, categories, args.limit)
    print(f"{args.dataset}: {len(samples)} samples (EVAL ONLY, never train on these)", file=sys.stderr)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = {}
    for name, repo in specs:
        kw = dict(repo=repo, max_pixels=args.max_pixels, zoom=args.zoom, zoom_frac=args.zoom_frac)
        if args.oracle:
            g = OracleGrounder(name, backend=OracleBackend(), **kw)
            load_s = 0.0
        else:
            g = Grounder(name, **kw)
            t0 = time.perf_counter()
            g.backend.load()
            load_s = round(time.perf_counter() - t0, 1)
        tag = f"{args.dataset}_{name}{'_zoom' if args.zoom else ''}{'_oracle' if args.oracle else ''}_{stamp}"
        with open(args.out_dir / f"{tag}.jsonl", "w") as log:
            results = evaluate(g, samples, args.zoom, log)
        summary = summarize(results)
        summary.update(model=name, repo=repo or g.adapter.repo, dataset=args.dataset, zoom=args.zoom,
                       max_pixels=args.max_pixels, load_s=load_s, oracle=args.oracle)
        report[name] = summary
        (args.out_dir / f"{tag}.summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps({name: {"overall": summary["overall"], "latency_ms": summary["latency_ms"]}}), flush=True)
        del g
    print("\n| model | slice | acc % | n |\n|---|---|---|---|")
    for name, s in report.items():
        print(table(name, s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
