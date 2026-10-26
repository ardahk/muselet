# Phase 2 research digest (2026-10-25)

Five research agents surveyed HF, papers, leaderboards, GitHub and X. Their claims are summarized here with
sources; **[verified]** = the lead checked it on this Mac or via the HF API, **[unverified]** = reported only.
Benchmark numbers are as published by the model authors unless stated.

## A. Planner candidates (<= ~10B active)

| model | MLX build | size 4-bit | why it is interesting |
|---|---|---|---|
| Qwen3.5-4B (current) | `mlx-community/Qwen3.5-4B-4bit` [verified local], `-OptiQ-4bit` [verified exists] | ~2.9 GB | BFCL-v4 50.3, tau2 79.9; natively multimodal [verified] |
| Qwen3.5-9B | `mlx-community/Qwen3.5-9B-OptiQ-4bit` [verified exists], `-4bit` [verified local] | 5.5-6.6 GB | BFCL-v4 66.1, tau2 79.1; same template/arch as the 4B |
| Qwen3.6-35B-A3B | `mlx-community/Qwen3.6-35B-A3B-4bit` [verified local] | 19 GB | MoE ~3B active; earlier planner holdout .71 vs 4B .64 (`docs/REPORT.md`) |
| GUI-Owl-1.5-4B / 8B | `mPLUG/GUI-Owl-1.5-4B-Instruct` [verified exists, MIT], no MLX quant | ~2.4 / 4.7 GB | OSWorld-Verified 48.2 (4B) / 52.3 (8B); one model plans and grounds |
| Gemma-4-E4B-it | `mlx-community/gemma-4-e4b-it-4bit` [verified exists] | 5.2 GB | native function calling + vision + audio; best on two independent local-agent benches [unverified] |
| Holo-3.1-4B / 0.8B | `Hcompany/Holo-3.1-4B`, `-0.8B` [verified exist, Apache-2.0], no MLX quant | ~2.5 GB | Qwen3.5 base, function-calling action model, AndroidWorld ~71 |
| Nemotron-3-Nano-4B | `mlx-community/NVIDIA-Nemotron-3-Nano-4B-4bit` [verified exists] | 2.9 GB | hybrid Mamba (flat KV over long histories), BFCL-v3 61.1, text only |
| LFM2.5-2.6B | `LiquidAI/LFM2.5-2.6B-MLX-4bit` [verified exists] | 1.5 GB | agent-harness trained; 8 GB-Mac tier |
| MiniCPM5-2B | `openbmb/MiniCPM5-2B-MLX` [verified exists] | 1.5 GB | vendor claims 4B parity [unverified] |
| UI-Venus-2-9B | `inclusionAI/UI-Venus-2-9B` [verified exists], no MLX quant | ~5 GB | Qwen3.5-9B base; SS-Pro 73.0 claimed; unified grounding + navigation |
| Fara1.5-4B | `mlx-community/Fara1.5-4B-8bit` [verified exists, MIT] | ~4.5 GB (8-bit) | best <= 4B browser agent (screenshot-only; web only) |

Quantization: Qwen-family holds tool-call validity at 4-bit; OptiQ (sensitivity-aware mixed 4/8 bit with a
tool-call calibration domain) and DWQ (`mlx_lm.dwq`, KL-distilled 4-bit) recover most 4-bit loss
[unverified for our tasks]. For non-Qwen families prefer OptiQ or 8-bit for the planner.

## B. Grounding (canvas / blind apps)

Best open <= 8B on ScreenSpot-Pro: GUI-Owl-1.5-8B 68.9, UI-Venus-1.5-8B 68.4 (`mlx-community/UI-Venus-1.5-8B-4bit`
[verified local]); ours eyes-4b 63.5 @1 MP / 67.5 @2 MP (200-sample subset). Crop/zoom refinement is the largest
inference-time lever (+6-7 pts reported). Single-model plan+ground at 4B is credible (GUI-Owl-1.5, Holo-3.1,
UI-Venus). Closed HuzzleWorld-3B reports 72.4 but has no weights [unverified].

## C. Architecture and memory for long horizons (what the leaders do)

1. **Batched actions with live re-validation**: UFO2/UFO3 predict several actions per call and validate each
   against the live control tree (-51% LLM calls). Our DSL mode does this; tools mode does not.
2. **Code/API as an action**: CoAct-1 (GUI operator + programmer agent) 60.8% OSWorld at ~10 steps vs ~15;
   Agent S3 native coding agent 62.6%, with Behavior Best-of-N 69.9% (human 72%). Meta Muse (Mac) and Grok Bot are
   API/connector-first with computer use as fallback.
3. **Plan recitation**: Manus keeps a todo.md near the end of context; Anthropic recommends structured notes +
   compaction. Small models lose the goal fastest.
4. **Context**: observation masking (keep the action record, drop old observations) matched or beat LLM
   summarization at half the cost (JetBrains, arXiv 2508.21433). Keep the prefix stable for KV-cache hits; mask
   tools instead of changing the tool list (Manus).
5. **Verification and retry**: step-level critics help even at 7B (OS-Oracle-7B, GuidNav +33%); keep failures in
   context so the model doesn't repeat them; bounded retries with a *different* action.
6. **Procedural memory**: AWM +24.6%/+51.1% rel. (Mind2Web/WebArena), ASI +23.5% with verified programmatic skills,
   SkillWeaver: skills written by a strong model lift weak agents +54.3%, BREW +10-20% on OSWorld from distilled
   recipes. Retrieve top-1 by app + intent; irrelevant memories hurt.
7. **Test-time scaling**: bBoN works through *diverse* rollouts judged by behaviour narratives; for a 4B, a
   second attempt with a different strategy only after a verified failure.
8. **User memory**: OpenClaw-style small curated USER.md / MEMORY.md files beat raw transcripts.

## D. Speed on Apple Silicon (our stack: mlx 0.32.4, mlx-lm 0.32.2, mlx-vlm 0.7.8)

- Thinking tokens dominate per-turn latency (~1024 tokens/turn today). Fewer turns (batching) and fewer thought
  tokens (adaptive thinking, fine-tuned no-think policies) are the big levers.
- Native MTP speculative decoding (Qwen3.5 has `mtp_num_hidden_layers: 1`) is reported for newer mlx-lm, but
  **our mlx-lm 0.32.2 strips `mtp.*` weights in `qwen3_5.sanitize` and our 4-bit checkpoint has none** [verified].
  Would need an mlx-lm upgrade + re-conversion; ~1.5x reported at temp 0.6 [unverified here].
- Draft-model speculation (0.8B -> 4B) ~1.2-1.4x on reasoning text; prompt-lookup speculation helps echo-heavy
  outputs (tool args copied from the AX tree) [unverified here].
- M5 neural accelerators speed up prefill (large-M matmuls), not M=1 decode [reported by Apple].
- ANE (CoreML/Anemll) decode is ~30-60 tok/s, slower than the GPU path: not for latency.

## E. Local fine-tuning

- mlx-lm LoRA/DoRA/full with `chat`/`tools` datasets; `--mask-prompt` masks only up to the last assistant turn,
  so train one sample per planner turn.
- **Qwen3.5 GDN layers backprop through a Python-loop fallback** (`gated_delta_update(..., use_kernel=not
  self.training)` in mlx-lm 0.32.2 [verified]) -> potentially slow; probe throughput before committing.
- Agent SFT recipes: 1-2 epochs, LR ~1e-5 (full-FT equivalent; LoRA typically 1e-4..2e-4), mask everything except
  assistant tool calls, filter to successful trajectories (RFT), relabel the student's own states with a teacher
  (DAgger) to fix compounding errors, mix some general data.

## F. Benchmarks

- Nobody publishes a no-VM, physical-Mac long-horizon suite; macOSWorld (202 tasks) and MacArena (MacPaw, 421
  tasks, UTM VMs) are the macOS references; OSWorld-Verified / OSWorld 2.0 are VM-only.
- Best practices adopted in LH-v1: execution-based checkers in the harness (never the agent's claim), milestones
  for partial credit, pass^k reliability, false-done rate, Wilson CIs, local deterministic fixtures, separate
  online cases, guards against the agent editing its own evidence.

## G. Competitors (Oct 2026)

- DeskMind: OSS stack (Eyes 4B grounder, Brain 0.8B-4B router, Hands AX+OCR), 39/39 on its 13-task bench, JevBench
  .835 [their numbers].
- HobbyLM-1B Computer Use v0.1: LoRA on a 1B MoE, 90/125 on sealed round 4 [their harness].
- Meta Muse for Mac (`com.meta.endo`, installed here) and Grok Bot (`com.anysphere.sand`, installed here) are
  cloud-model agents; Muse Spark Open is 816B/42B-active. Our differentiator stays fully local + open source.
