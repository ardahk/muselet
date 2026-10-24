# Visual grounding candidates (on-device, MLX, <= ~10B)

Task: screenshot + instruction -> one click point, run with `mlx-vlm` on the M5 Pro when the AX tree is blind.
All scores are **published by the cited source** (mostly the model authors, at their own native resolution and
bf16, usually on GPUs via vLLM/transformers). None were measured here; 4-bit MLX at our ~1 MP cap will differ,
which is exactly what `run_screenspot.py` measures. "SSPro" = ScreenSpot-Pro (1581 samples,
[dataset](https://huggingface.co/datasets/likaixin/ScreenSpot-Pro)); "OSW-G" = OSWorld-G (510 samples,
[dataset](https://huggingface.co/datasets/MMInstruction/OSWorld-G)); "OSW-G-R" = OSWorld-G Refined. Both are
**eval sets: never train on them** (AGENTS.md).

## Recommendation: benchmark these 3 first

| # | Model | Params | SSPro | OSW-G | Why |
|---|---|---|---|---|---|
| 1 | `deskmind/eyes-4b` (rev `mlx-4bit`) | 4B | 67.7 no zoom / 77.5 with zoom ([card](https://huggingface.co/deskmind/eyes-4b)) | not reported | Best published 4B SSPro, Apache-2.0, ships an official MLX 4-bit build, 32-token JSON answer (fast decode). It is the DeskMind grounder we must beat. |
| 2 | `inclusionAI/UI-Venus-1.5-8B` -> `mlx-community/UI-Venus-1.5-8B-4bit` | 8B | 68.4 ([report T1](https://arxiv.org/html/2602.09082)) | 69.7 ([report T1](https://arxiv.org/html/2602.09082)) | Best published SSPro+OSW-G at <=8B with a ready MLX conversion and a clean Apache-2.0 licence. |
| 3 | `mPLUG/GUI-Owl-1.5-4B-Instruct` (convert locally) | 4B | 66.8 ([report T4](https://arxiv.org/html/2602.16855)) | 63.7 ([report T5](https://arxiv.org/html/2602.16855)) | Base of eyes-4b and an AGENTS.md grounder candidate; gives the paired baseline for eyes-4b and for our own Qwen3.5-4B grounding LoRA. MIT. No MLX upload: `mlx_vlm.convert` (README). |

Stretch (5th slot if time): `inclusionAI/UI-Venus-2-9B` has the highest published numbers here (SSPro 73.0,
OSW-G-R 78.5, [report T4](https://arxiv.org/html/2609.00028)) and community MLX builds exist, but its licence is
"pending" on the [model card](https://huggingface.co/inclusionAI/UI-Venus-2-9B) and its grounding prompt is not
published, so it is not in the top 3.

## Budget at ~1 MP (all candidates)

Visual tokens = (H/f) * (W/f) after `smart_resize` to multiples of f = patch_size * merge_size, computed by
`brain.grounder.image_tokens` (tested). Qwen3-VL / Qwen3.5 family: patch 16, merge 2 -> **f = 32**
(`preprocessor_config.json` of each repo, e.g. [eyes-4b](https://huggingface.co/deskmind/eyes-4b/blob/main/preprocessor_config.json),
[UI-Venus-1.5-8B](https://huggingface.co/inclusionAI/UI-Venus-1.5-8B/blob/main/preprocessor_config.json),
[GUI-Owl-1.5-4B](https://huggingface.co/mPLUG/GUI-Owl-1.5-4B-Instruct/blob/main/preprocessor_config.json)).
Qwen2.5-VL family (UI-TARS-1.5, GTA1, Holo1.5): patch 14, merge 2 -> **f = 28**
([UI-TARS coordinate guide](https://github.com/bytedance/UI-TARS/blob/main/README_coordinates.md)).

| Input | f = 32 (resized -> tokens) | f = 28 (resized -> tokens) |
|---|---|---|
| HandsKit 1 MP window shot 1264x790 | 1248x768 -> 936 | 1260x784 -> 1260 |
| 3840x2160 SSPro image capped at 1 MP | 1312x736 -> 943 | 1316x728 -> 1222 |
| 0.4x zoom crop (any source) re-capped at 1 MP | ~940 | ~1220 |

Native-resolution evals use far more: GUI-Owl's eval caps at 9800 tokens (`MAX_PIXELS = 9800*32*32`,
[eval_grounding_benchmarks.py](https://github.com/X-PLUG/MobileAgent/blob/main/Mobile-Agent-v3.5/grounding_and_kb/eval_grounding_benchmarks.py));
UI-Venus v1 evaluated at 2.0-4.8 MP ([ui_venus_ground_7b.py](https://github.com/inclusionAI/UI-Venus/blob/main/models/grounding/ui_venus_ground_7b.py));
eyes-4b's MLX deployment uses <= 2 MP ([card](https://huggingface.co/deskmind/eyes-4b)). So a 1 MP cap is
expected to cost accuracy on SSPro's 4K screens; the two-stage zoom is the intended fix.

## Per-candidate details

Convention column: what the raw answer means. `norm1000` = 0..1000 of the image the model saw (resolution
independent); `resized_px` = absolute pixels of the smart-resized image (must be scaled by orig/resized);
both map back with `brain.grounder.model_to_pixels`. The adapter name is the `--models` key.

### DeskMind Eyes 4B — adapter `eyes-4b`
- Scores: SSPro 67.7 (no zoom, full 1581), 77.5 (with zoom); ScreenSpot-v2 95.0; base GUI-Owl-1.5-4B measured on the same platform 64.8 / 76.2 ([card](https://huggingface.co/deskmind/eyes-4b)). OSW-G: not reported.
- Caveats (same card): the deployed `mlx-4bit` build (<= 2 MP) has **no benchmark number**; the instruction-rewriting step "saw some SSPro test instructions (text only)" per its Disclosures.
- Licence Apache-2.0 (base MIT). MLX: `deskmind/eyes-4b` revision `mlx-4bit` (official, 4-bit, group 64).
- Prompt (user turn, image first, no system):
  ```
  Locate the UI element in the screenshot that matches the description, and output its click point in JSON as
  {"point_2d": [x, y]}, with coordinates in 0-1000 relative to the image.
  Description: <instruction>
  ```
- Output `{"point_2d": [x, y]}`, **norm1000**. Resize: Qwen3-VL smart_resize, f = 32.

### GUI-Owl-1.5 4B / 8B Instruct — adapters `gui-owl-1.5-4b`, `gui-owl-1.5-8b`
- Scores ([technical report](https://arxiv.org/html/2602.16855)): SSPro 66.8 (4B), 71.1 (8B) (Table 4, without crop tool); OSW-G 63.7 (4B), 65.8 (8B) (Table 5). With crop-based refinement the flagship reaches SSPro 80.3 (abstract). There is no 7B in the 1.5 family (2B/4B/8B + larger).
- Licence MIT ([card](https://huggingface.co/mPLUG/GUI-Owl-1.5-4B-Instruct)). MLX: **no 4B/8B conversion found** (only `clinan/GUI-Owl-1.5-2B-Instruct-MLX-4bit`; `mlx-community/GUI-Owl-7B-4bit` is v1). Architecture `Qwen3VLForConditionalGeneration`, supported by mlx-vlm 0.7.8 -> convert locally.
- Prompt: system = the `computer_use` tool schema with "The screen's resolution is 1000x1000" and only `left_click`/`mouse_move` (`only_two_action_system_prompt` in the [official eval](https://github.com/X-PLUG/MobileAgent/blob/main/Mobile-Agent-v3.5/grounding_and_kb/eval_grounding_benchmarks.py), copied verbatim as `GUI_OWL_SYSTEM`); user = image + raw instruction.
- Output `<tool_call>{"name":"computer_use","arguments":{"action":"left_click","coordinate":[x,y]}}</tool_call>`, **norm1000** (the eval sets resized size to 1000x1000 for Qwen3-VL). Resize f = 32, eval uses 196..9800 tokens.

### UI-Venus-1.5 2B / 8B, UI-Venus-2 9B — adapters `ui-venus-1.5-2b`, `ui-venus-1.5-8b`, `ui-venus-2-9b`
- Scores: 1.5-8B SSPro 68.4, OSW-G 69.7, OSW-G-R 74.1; 1.5-2B 57.7 / 59.4 / 65.6 ([1.5 report, Table 1](https://arxiv.org/html/2602.09082)). 2-9B SSPro 73.0, OSW-G-R 78.5 ([2 report, Table 4](https://arxiv.org/html/2609.00028)); plain OSW-G not found for 2-9B.
- Licence: 1.5 Apache-2.0 ([card](https://huggingface.co/inclusionAI/UI-Venus-1.5-8B)); 2-9B "pending" ([card](https://huggingface.co/inclusionAI/UI-Venus-2-9B)).
- MLX: `mlx-community/UI-Venus-1.5-8B-4bit` (also `-6bit`, `-bf16`), `mlx-community/UI-Venus-1.5-2B-6bit`; 2-9B: `lethargicgeek/UI-Venus-2-9B-mlx-4bit` (community, unverified).
- Prompt: the 1.5/2 cards publish no grounding prompt. The adapter uses the official v1 grounding prompt
  `Outline the position corresponding to the instruction: <instruction>. The output should be only [x1,y1,x2,y2].`
  ([ui_venus_ground_7b.py](https://github.com/inclusionAI/UI-Venus/blob/main/models/grounding/ui_venus_ground_7b.py)); click = box centre.
- Convention: v1 (Qwen2.5-VL) answers in resized pixels; 1.5 (Qwen3-VL, f = 32) and 2 (Qwen3.5, f = 32) are assumed **norm1000** like their base — **unverified**; check the first raw answers (`raw` in the JSONL) and switch `coord` if values exceed 1000.

### Fara1.5 4B / 9B — adapter `fara1.5-4b`
- Scores ([paper Table 6](https://arxiv.org/html/2606.20785)): SSPro 59.9 (4B), 66.2 (9B) with two-step zoom; 55.3 / 58.0 without zoom; OSW-G-R 68.0 / 69.7. Plain OSW-G not reported.
- Licence MIT ([card](https://huggingface.co/microsoft/Fara1.5-4B)). MLX: `mlx-community/Fara1.5-4B-8bit`, `mlx-community/Fara1.5-4B-OptiQ-4bit`, `runanywhere/Fara1.5-4B-mlx-4bit`; 9B: `mlx-community/Fara1.5-9B-8bit`.
- Prompt: the official system prompt is a long browser-agent prompt with `computer_use` tool calls (`left_click` at `(x, y)`), trained mostly at 1440x900 ([card](https://huggingface.co/microsoft/Fara1.5-4B)). The adapter uses the same tool schema with the real resized resolution; paper says "the model predicts normalized coordinates in pixel space" — exact convention **unverified**, adapter assumes resized pixels.

### UI-TARS-1.5-7B — adapter `ui-tars-1.5-7b`
- Scores: SSPro 49.6 for the 7B ([card](https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B); 61.6 is the larger UI-TARS-1.5); OSW-G 52.8 (measured by UI-Venus, [1.5 report T1](https://arxiv.org/html/2602.09082)); Holo2's card measured 39.0 / 61.0 ([card](https://huggingface.co/Hcompany/Holo2-4B)).
- Licence Apache-2.0. MLX: `mlx-community/UI-TARS-1.5-7B-4bit` (also 6/8-bit).
- Prompt: grounding template from [prompt.py](https://github.com/bytedance/UI-TARS/blob/main/codes/ui_tars/prompt.py) (`GROUNDING_DOUBAO`, action `click(point='<point>x1 y1</point>')`). Output `click(start_box='(x,y)')` or `<point>x y</point>`, **resized_px** of smart_resize f = 28 (min 100*28*28, max 16384*28*28) ([coordinate guide](https://github.com/bytedance/UI-TARS/blob/main/README_coordinates.md)).

### GTA1-7B — adapter `gta1-7b`
- Scores: `HelloKKMe/GTA1-7B` SSPro 55.5, OSW-G 60.1, OSW-G-R 68.8; `Salesforce/GTA1-7B-2507` 50.1 / 55.1 / 67.7 ([card](https://huggingface.co/Salesforce/GTA1-7B-2507)).
- Licence Apache-2.0. MLX: `mlx-community/GTA1-7B-4bit` (of `HelloKKMe/GTA1-7B`).
- Prompt (system): `You are an expert UI element locator. Given a GUI image and a user's element description, provide the coordinates of the specified element as a single (x,y) point. The image resolution is height {height} and width {width}. For elements with area, return the center point.\n\nOutput the coordinate pair exactly:\n(x,y)`; user = image + instruction.
- Output `(x,y)` **resized_px**; smart_resize f = 28 with the processor's min/max pixels ([card](https://huggingface.co/Salesforce/GTA1-7B-2507)).

### Holo2 4B / 8B (and Holo1.5-7B) — adapters `holo2-4b`, `holo2-8b`
- Scores ([Holo2-4B card](https://huggingface.co/Hcompany/Holo2-4B)): Holo2-4B SSPro 57.2, OSW-G 69.4; Holo2-8B 58.9 / 70.1. Holo1.5-7B 57.94 / 66.27 ([card](https://huggingface.co/Hcompany/Holo1.5-7B)).
- Licence Apache-2.0 for 4B/8B (larger Holo2 is non-commercial). MLX: `mlx-community/Holo2-8B-bf16` (bf16 only, ~16 GB); no Holo2-4B conversion; `mlx-community/holo1.5-7b-mlx`.
- Prompt ([Holo2 cookbook](https://github.com/hcompai/hai-cookbook/blob/main/holo2/holo_2_localization_huggingface.ipynb)): `Localize an element on the GUI image according to the provided target and output a click position.\n     * You must output a valid JSON following the format: <ClickCoordinates JSON schema>\n     Your target is:\n<task>`, chat template with `thinking=False`.
- Output `{"x": int, "y": int}` **norm1000**; smart_resize f = 32 with the processor's min/max.

### Qwen3-VL / Qwen3.5 small — adapters `qwen3-vl-4b`, `qwen3.5-4b`
- Scores: Qwen3.5-4B SSPro 60.3, Qwen3.5-9B 65.2 ([4B card](https://huggingface.co/Qwen/Qwen3.5-4B), Visual Agent table); OSW-G not reported. Qwen3-VL-8B-Instruct SSPro 54.6, OSW-G 64.4 (GUI-Owl [report T4/T5](https://arxiv.org/html/2602.16855)); 52.7 / 57.5 measured by UI-Venus ([1.5 report T1](https://arxiv.org/html/2602.09082)); Qwen3-VL-4B-Thinking 41.4 / 56.4 (Holo2 [card](https://huggingface.co/Hcompany/Holo2-4B)).
- Licence Apache-2.0. MLX: `mlx-community/Qwen3-VL-4B-Instruct-4bit`, `mlx-community/Qwen3-VL-8B-Instruct-4bit`, `mlx-community/Qwen3.5-4B-MLX-4bit`, `mlx-community/Qwen3.5-9B-MLX-4bit`.
- Prompt: Qwen does not publish its SSPro prompt; adapter uses the `point_2d` prompt above (Qwen3-VL's native point format), `enable_thinking=False` for Qwen3.5. Output **norm1000**, f = 32. Baseline for the planned Qwen3.5-4B grounding LoRA.

## Summary table

| Model | Params | SSPro | OSW-G | Licence | MLX repo | Conv. | f |
|---|---|---|---|---|---|---|---|
| eyes-4b | 4B | 67.7 / 77.5 zoom [1] | — | Apache-2.0 | `deskmind/eyes-4b@mlx-4bit` | norm1000 | 32 |
| GUI-Owl-1.5-4B | 4B | 66.8 [2] | 63.7 [2] | MIT | none (convert) | norm1000 | 32 |
| GUI-Owl-1.5-8B | 8B | 71.1 [2] | 65.8 [2] | MIT | none (convert) | norm1000 | 32 |
| UI-Venus-1.5-8B | 8B | 68.4 [3] | 69.7 [3] | Apache-2.0 | `mlx-community/UI-Venus-1.5-8B-4bit` | norm1000 (unverified) | 32 |
| UI-Venus-1.5-2B | 2B | 57.7 [3] | 59.4 [3] | Apache-2.0 | `mlx-community/UI-Venus-1.5-2B-6bit` | norm1000 (unverified) | 32 |
| UI-Venus-2-9B | 9B | 73.0 [4] | 78.5 (Refined) [4] | pending | `lethargicgeek/UI-Venus-2-9B-mlx-4bit` | norm1000 (unverified) | 32 |
| Fara1.5-4B | 4B | 59.9 zoom / 55.3 [5] | 68.0 (Refined) [5] | MIT | `mlx-community/Fara1.5-4B-8bit` | resized_px (unverified) | 32 |
| Fara1.5-9B | 9B | 66.2 zoom / 58.0 [5] | 69.7 (Refined) [5] | MIT | `mlx-community/Fara1.5-9B-8bit` | resized_px (unverified) | 32 |
| Holo2-4B | 4B | 57.2 [6] | 69.4 [6] | Apache-2.0 | none | norm1000 | 32 |
| Holo2-8B | 8B | 58.9 [6] | 70.1 [6] | Apache-2.0 | `mlx-community/Holo2-8B-bf16` | norm1000 | 32 |
| Holo1.5-7B | 7B | 57.94 [7] | 66.27 [7] | Apache-2.0 | `mlx-community/holo1.5-7b-mlx` | — (no adapter) | 28 |
| GTA1-7B | 7B | 55.5 [8] | 60.1 [8] | Apache-2.0 | `mlx-community/GTA1-7B-4bit` | resized_px | 28 |
| UI-TARS-1.5-7B | 7B | 49.6 [9] | 52.8 [3] | Apache-2.0 | `mlx-community/UI-TARS-1.5-7B-4bit` | resized_px | 28 |
| Qwen3.5-4B | 4B | 60.3 [10] | — | Apache-2.0 | `mlx-community/Qwen3.5-4B-MLX-4bit` | norm1000 | 32 |
| Qwen3.5-9B | 9B | 65.2 [10] | — | Apache-2.0 | `mlx-community/Qwen3.5-9B-MLX-4bit` | norm1000 | 32 |
| Qwen3-VL-8B | 8B | 54.6 [2] | 64.4 [2] | Apache-2.0 | `mlx-community/Qwen3-VL-8B-Instruct-4bit` | norm1000 | 32 |

[1] https://huggingface.co/deskmind/eyes-4b · [2] https://arxiv.org/html/2602.16855 (Tables 4, 5) ·
[3] https://arxiv.org/html/2602.09082 (Table 1) · [4] https://arxiv.org/html/2609.00028 (Table 4) ·
[5] https://arxiv.org/html/2606.20785 (Table 6) · [6] https://huggingface.co/Hcompany/Holo2-4B ·
[7] https://huggingface.co/Hcompany/Holo1.5-7B · [8] https://huggingface.co/Salesforce/GTA1-7B-2507 ·
[9] https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B · [10] https://huggingface.co/Qwen/Qwen3.5-4B

## Unverified / to check on the Mac
- Every number above is author- or third-party-reported at native resolution; none is for 4-bit MLX at 1 MP.
- UI-Venus-1.5/2 and Fara1.5 coordinate conventions and prompts (see sections). Look at `raw` in the JSONL of the first `--limit 20` run.
- Holo2 chat-template flag name (`thinking=False` from the cookbook) and that mlx-vlm forwards it.
- `apply_chat_template` in mlx-vlm 0.7.8 handling a system message for qwen3_vl / qwen3_5 (read from source, not run).
- That mlx-vlm's Qwen processors keep our pre-resized (factor-aligned, <= 1 MP) image unchanged (inspected in source; min pixels 65536).
- eyes-4b's own disclosure that its instruction rewriter saw some SSPro instruction text.
