# Grounding bench (ScreenSpot-Pro / OSWorld-G)

Measures on-device grounders (screenshot + instruction -> click point) under Muselet's real budget:
mlx-vlm, 4-bit, screenshots capped at ~1 MP, optional two-stage zoom. Candidate research and the cited
published scores are in [CANDIDATES.md](CANDIDATES.md). Runtime interface: `ml/src/brain/grounder.py`.

ScreenSpot-Pro and OSWorld-G are **eval sets: never train on them** (or on crops / instructions derived
from them). Data goes to `data/grounding/` and results to `runs/grounding/` (both gitignored).

## 1. Setup (Mac, from the repo root)

```bash
uv sync --project ml
# optional, avoids HF rate limits (no key is needed for these public repos)
# export HF_TOKEN=...
```

## 2. Download the top-3 candidates (~2.5 + ~5 + ~2.5 GB)

```bash
# 1) DeskMind Eyes 4B, official MLX 4-bit build (branch mlx-4bit)
uv run --project ml hf download deskmind/eyes-4b --revision mlx-4bit --local-dir models/eyes-4b-mlx

# 2) UI-Venus-1.5-8B, mlx-community 4-bit
uv run --project ml hf download mlx-community/UI-Venus-1.5-8B-4bit --local-dir models/ui-venus-1.5-8b-4bit

# 3) GUI-Owl-1.5-4B-Instruct: no MLX upload exists, convert + quantize locally (4-bit, group 64)
uv run --project ml python -m mlx_vlm.convert --hf-path mPLUG/GUI-Owl-1.5-4B-Instruct \
    --mlx-path models/gui-owl-1.5-4b-mlx-4bit --quantize --q-bits 4 --q-group-size 64
```

## 3. Pipeline check without a model (seconds; also runs on Linux)

The oracle answers with the ground-truth centre in each adapter's own output format, so it exercises data
loading, resize, prompt, parser and coordinate mapping (incl. zoom) for every adapter. Expect 100%.

```bash
uv run --project ml python bench/grounding/run_screenspot.py --models all --oracle --zoom --limit 20
uv run --project ml pytest ml/tests/test_grounder.py -q
```

## 4. Run the benchmark

```bash
M="eyes-4b=models/eyes-4b-mlx ui-venus-1.5-8b=models/ui-venus-1.5-8b-4bit gui-owl-1.5-4b=models/gui-owl-1.5-4b-mlx-4bit"

# smoke: 20 samples, eyeball the `raw` answers in runs/grounding/*.jsonl (coordinate convention check)
uv run --project ml python bench/grounding/run_screenspot.py --models $M --limit 20

# full ScreenSpot-Pro (1581), single pass at 1 MP, then two-stage zoom
uv run --project ml python bench/grounding/run_screenspot.py --models $M
uv run --project ml python bench/grounding/run_screenspot.py --models $M --zoom

# slices relevant to the demo (matches group / application / platform / ui_type)
uv run --project ml python bench/grounding/run_screenspot.py --models $M --zoom --category premiere,Creative

# OSWorld-G (510, public parquet on HF)
uv run --project ml python bench/grounding/run_screenspot.py --dataset osworld-g --models $M --zoom

# resolution sensitivity (published numbers use native res; Muselet captures at <= 1 MP)
uv run --project ml python bench/grounding/run_screenspot.py --models $M --limit 300 --max-pixels 2000000
```

Each run writes `runs/grounding/<dataset>_<model>[_zoom]_<stamp>.jsonl` (one row per sample: point, hit,
per-stage ms, raw output, model input size) and a `.summary.json` with: overall point-in-box accuracy,
accuracy by group / application / ui_type / platform, stage-1 accuracy before zoom, parse failures, load
time, and latency p50/p95 for each stage (`full`, `zoom`) and in total.

## Flags

| flag | meaning |
|---|---|
| `--models` | adapter names from `brain.grounder.ADAPTERS`, `name=local/mlx/dir` to override weights, or `all` |
| `--dataset` | `screenspot-pro` (default) or `osworld-g` |
| `--limit N`, `--category a,b` | first N samples after filtering; category matches group/application/platform/ui_type |
| `--zoom`, `--zoom-frac 0.4` | stage 2 re-locates in a crop of `zoom-frac` x the image side around stage 1's guess |
| `--max-pixels 1000000` | pixel cap per model call (AGENTS.md: ~1 MP) |
| `--oracle` | no model; ground-truth answers through the full adapter pipeline |

## Bench zoom vs runtime zoom

The bench's `--zoom` crops the dataset's full-resolution image around the stage-1 guess. At runtime the
grounder does the equivalent on the live screen: given the HandsKit `shot` and a `capture`
(`brain.grounder.handskit_capture(server.rpc)`), stage 2 requests `screenshot {region, max_pixels}` for a
region sized by `native_zoom_region` so it comes back at the display's native backing scale (Retina 2 px/pt)
under the cap. It never re-crops the ~1 MP downscaled shot, which would add no detail; a downscaled shot
without `capture` skips zoom. So the bench zoom gain carries over to runtime.

```python
g = Grounder("eyes-4b", capture=handskit_capture(server.rpc), screens=hello["screens"])
shot = await server.rpc("screenshot", {"window": True, "max_pixels": 1_000_000})
pt = await g.alocate(shot["path"], "the razor tool", shot=shot)     # {x, y, conf, ms} in shot pixels
x, y = to_global(pt, shot)                                          # global points for `click`
```

Other adapters (`ui-venus-2-9b`, `ui-venus-1.5-2b`, `gui-owl-1.5-8b`, `holo2-8b`, `holo2-4b`, `qwen3-vl-4b`,
`qwen3.5-4b`, `fara1.5-4b`, `gta1-7b`, `ui-tars-1.5-7b`) load their MLX repo from HF by default
(`holo2-4b` / `gui-owl-1.5-8b` need a local `mlx_vlm.convert` like step 2.3).
