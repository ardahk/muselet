# Phase 2 lab notebook: long-horizon accuracy, then speed, on small local models

Started Sun 2026-10-25 20:15 PDT (post-hackathon, ~12 h autonomous session). Lead: Devin.
Rule (AGENTS.md): every knob change starts from research + a written hypothesis; tuned vs tuned; record
confirmed/refuted. Hypotheses below were written **before** any LH-v1 result existed.

## 0. Starting point (evidence from the repo and the user's own sessions)

- `runs/traces/2026-10-25.jsonl` (640 utterances): System-1 commands (volume, Wi-Fi, dark mode, open app) are
  almost always `ok`. Multi-step tasks are where users lose: "double the speed of this video" (Premiere) was
  cancelled ~25 times, "play some jazz on YouTube" / "navigate to Berkeley on Maps" mostly cancelled or failed,
  "add AAA batteries to my cart on Walmart" sometimes ok.
- Deployed planner = base Qwen3.5-4B, native tool calls, **one action per turn, up to 1024 thinking tokens per
  turn** (`THINK_BUDGET` is hardcoded in tools mode; the `THINK` env does not reach it), and the planner loop is
  capped at **12 turns / 60 s** for non-blind tasks (`orchestrator._planner_loop`). A 10-step task at ~10 s/turn
  cannot finish inside the cap.
- Qwen3.5-4B is natively multimodal (vision tower present in `mlx-community/Qwen3.5-4B-4bit`, 297 vision tensors)
  but is used text-only.
- Existing multi-step evidence is thin: live T2 1/5 and 1/3 (5-6 cases), no long-horizon suite.

## 1. Research digest (5 research agents, 2026-10-25; full notes in `RESEARCH.md`)

Strongest evidence for long-horizon gains at small scale is **harness-level**, not model swaps:
batched actions with live validation (UFO2: -51% LLM calls), code/API actions (CoAct-1: 60.8% OSWorld at
~10 steps), plan recitation / todo (Manus), observation masking over summarization (JetBrains, arXiv 2508.21433),
verified procedural memory (AWM +24-51% rel., ASI +23.5%, SkillWeaver: strong-model skills lift weak agents
+54%), step verification + bounded retry (OS-Oracle, GuidNav). Model side: Qwen3.5-9B (BFCL-v4 66.1 vs 50.3),
GUI-Owl-1.5-4B (OSWorld-Verified 48.2, one model for plan + ground), Gemma-4-E4B, Holo-3.1-4B (Qwen3.5 base,
function calling), LFM2.5-2.6B / MiniCPM5-2B for an 8 GB tier. Speed: thinking tokens dominate; mlx-lm 0.32.2
**drops Qwen3.5 MTP weights** (`sanitize`), so native-MTP speculation is not available on our stack today;
Qwen3.5 GDN layers train through a Python-loop fallback (`use_kernel=not self.training`) -> local LoRA speed must
be probed before planning a fine-tune.

## 2. The benchmark: LH-v1 (`evals/lh_v1.jsonl`, built by `evals/lh_v1_build.py`)

18 live cases (16 offline + 2 online), run only through `bench/live/run_live.py` (mechanical preconditions,
document guard, session probe, case-scoped teardown). Strict pass = final state only (fixture server state,
files, AppleScript reads); milestones = diagnostic partial credit. Families: local shop (6, incl. checkout with
required confirm and a 2-turn follow-up), form fill, webmail reply/compose (required confirm), 2-hop wiki quiz
(fictional facts so prior knowledge can't shortcut), cross-app (bank statement sum -> TextEdit, email facts ->
TextEdit), native (TextEdit save dialog into the sandbox, Finder organize, Numbers SUM formula), online (YouTube
jazz, Wikipedia -> TextEdit). Fixture sites: `bench/fixtures/` (seed + graders lead-authored; grader unit tests
`bench/tests/test_lh_graders.py`).
Reporting: pass@1 per case and suite, pass^k when repeated, milestone fraction, false-done, median wall time,
median actions; Wilson 95% CIs (n is small: 16 cases x 2 repeats -> +/-17 pts at p=.5, so only large or paired,
consistent differences count).

## 3. Pre-registered hypotheses

| id | intervention | prediction | why (evidence) | decision rule |
|---|---|---|---|---|
| H1 | raise planner caps (12 turns/60 s -> 40/480 s) | deployed config +15 pts on LH-v1 offline | caps bind at ~10 s/turn (code + traces) | adopt if pass rate up and no new unsafe actions |
| H2 | adaptive thinking (full budget on turn 0 and after a failure, else 0) | pass within -5 pts of think-all, median task time -40% | most turns are mechanical; thinking is the latency | adopt if both hold |
| H3 | multi-call turns (up to 3 tool calls/turn) | turns -30%, time -25%, pass within -5 pts | UFO2 speculative multi-action -51% calls | adopt if time drops without pass loss |
| H4 | progress line recited each turn | +10 pts on multi-subgoal cases, fewer false-dones | Manus todo recitation; small models lose the goal | adopt if multi-subgoal pass up |
| H5 | frontier planner (claude-sonnet-5-5) in the same harness | >= 80% offline -> harness is fine, the 4B is the bottleneck; < 60% -> fix harness first | control experiment | diagnostic only (never shipped) |
| H6 | bigger local planners (Qwen3.5-9B OptiQ-4bit, Qwen3.6-35B-A3B) | +10 pts vs 4B at <= 2x time | BFCL-v4 66 vs 50; earlier 35B holdout .71 vs .64 | tier recommendation by RAM |
| H7 | local LoRA on verified teacher trajectories (tasks disjoint from LH-v1) | +15 pts in-domain, >= +5 on held-out site families, think=0 at deployed accuracy | AgentTuning / RFT / DAgger literature; prior planner LoRA .850 vs .770 | adopt if held-out families improve |
| H8 | native vision input (Qwen3.5 VLM) | no gain on AX-rich LH-v1; gains only on canvas/blind targets | AX already exposes the fixtures | needs a canvas probe; not judged on LH-v1 |

## 4. Results log

(appended as runs finish; every row names its run dir under `runs/phase2/`)
