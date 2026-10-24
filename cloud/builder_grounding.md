# Cloud builder: visual grounding path (research + harness + interface) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` first. Muselet is a fully on-device macOS agent (MLX on an M5 Pro, 64 GB).
It acts through the accessibility (AX) tree; when AX is blind (canvas apps, some web content, Premiere's timeline)
it needs a grounder: screenshot + instruction -> a point to click, entirely on device. AGENTS.md design rules: cap
screenshots at ~1 MP, zoom-crop for small targets, never keep old screenshots. HandsKit's `screenshot` RPC returns
`{path, width, height, origin:[x,y], scale}` where global point = origin + pixel / scale.

Work on branch `cloud/grounding` from `main`, one PR. Add files only under `bench/grounding/`,
`ml/src/brain/grounder.py`, `ml/tests/test_grounder.py`. No API keys. The Mac runs the models later; here you build
and unit-test everything that doesn't need Metal.

1. **Candidate research** (`bench/grounding/CANDIDATES.md`, cite every number with a URL): local GUI grounding
   models that can run in MLX (`mlx-vlm`) on Apple Silicon at <= ~10B params: e.g. GUI-Owl-1.5 (4B/7B), Fara 1.5
   (4B/9B), DeskMind `eyes-4b`, UI-TARS family, Qwen3-VL / Qwen3.5-VL small sizes, GTA1, UI-Venus, Holo. For each:
   ScreenSpot-Pro and OSWorld-G scores, license, whether an MLX conversion exists on Hugging Face (repo id), expected
   image-token budget at ~1 MP, the exact prompt format and the coordinate convention it outputs (absolute pixels
   of the resized image vs 0-1000 normalized vs [0,1]), and any resize rule (e.g. smart_resize to multiples of 28).
   Recommend a top 3 to benchmark.
2. **ScreenSpot-Pro harness** `bench/grounding/run_screenspot.py`: loads the official ScreenSpot-Pro data from its
   published source (find it; it is an EVAL set: never use it for training), supports `--models` with per-model
   adapters (prompt + output parsing + coordinate conversion back to original pixels), `--limit/--category`, optional
   two-stage zoom (full image -> crop around the first guess -> re-locate in the crop -> map back), and reports
   point-in-box accuracy overall and per application/category, plus latency p50/p95 per stage. Also an OSWorld-G
   adapter if its data is public. Unit-test the coordinate math and parsers for every adapter with synthetic cases.
3. **Runtime interface** `ml/src/brain/grounder.py`: `class Grounder: locate(image_path, instruction, *, hint_box=None)
   -> {x, y, conf, ms}` in screenshot pixels, plus `to_global(pt, shot)` using `{origin, scale}`, and the zoom-crop
   refinement; MLX/mlx-vlm imported lazily so tests run on Linux. Tests for coordinate conversion (Retina scale 2.0,
   negative-origin secondary displays) and crop mapping.
4. `bench/grounding/README.md`: the exact Mac commands to download the top-3 candidates and run the benchmark.
Reply with the PR link, the recommended top 3 with their cited scores, and anything unverified.
