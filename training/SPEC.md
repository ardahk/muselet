# Training spec (authored by lead; executors implement, do not redesign)

Read `AGENTS.md` first (goal, observation format, action DSL). This file defines what we train,
on what data, with which prompts and configs. If something here is impossible or a dataset schema
differs from what is assumed, STOP that item and report; do not substitute your own design.

Where things run:
- Cloud VM (fast network): dataset download/conversion, synthetic generation, Tinker training, merge/convert.
- Mac (M5 Pro): inference, live evals, macOS teacher rollouts.
Artifact transport: private Hugging Face repos under `ardahk/` (model weights, small sample files).
Code: branch `cloud/data-pipeline` in github.com/ardahk/muselet, PR into `main`.

Secrets (env only, never printed or committed): TINKER_API_KEY, HF_TOKEN (write), OPENAI_API_KEY, ANTHROPIC_API_KEY.

HARD BUDGET: $150 total Tinker spend for the whole project (training + teacher sampling + storage).
Phase 1 cap: $60. Any pilot run > $8, or any action that would push cumulative spend past the phase cap,
requires lead approval first. Check actual spend with the `tinker billing` CLI after every run and report
it. Report estimated tokens and $ before every non-pilot run.
API teachers (separate budgets): generation = `claude-haiku-5-5` via Message Batches (use `gpt-5.4-nano`
via the OpenAI Batch API for ~30% of generation calls for cross-family diversity); adjudication =
`claude-sonnet-5-5` via Message Batches. Verify the exact model ids on the official model pages first.
DEADLINE: the Phase 1 model must be exported and uploaded by Sat Oct 24, 12:00 PDT (hackathon submission
is Oct 25 09:00 PDT). Prefer smaller data over missing the deadline.
Prices (per 1M tokens, Oct 2026): Qwen3.5-4B train $0.73, prefill $0.33; Qwen3.5-9B train $1.46;
Qwen3.6-35B-A3B train $1.17, prefill $0.45; Qwen3.5-397B-A17B prefill $1.65; cached prefill = 20% of prefill.

---------------------------------------------------------------------------------------------------
## Phase 0 — dataset recon (no training)

For each dataset below: download metadata + the smallest shard needed; report schema (field names and
types), row counts, platform split, license (from the card / LICENSE file), approximate token length of
one converted example, and 3 raw examples. Write `training/recon/<dataset>.md`. Do NOT download large
image archives in full yet (sample one archive if needed for counting).

| Dataset | Use | Notes |
|---|---|---|
| macpaw-research/GUIrilla-Task | ELEMENT decisions (macOS AX) | CC-BY-NC-4.0 (hackathon OK) |
| macpaw-research/GUIrilla-Gold | held-out eval only | never train |
| LangAGI-Lab/Mind2Web-axtree | ELEMENT decisions (web AX) | check license |
| Qwen/WebWorldData | ELEMENT + planner (web AX trajectories) | Apache-2.0, 50.9 GB: sample |
| apurvaga/go-browse-wa | planner (web AX, incl. failures) | MIT |
| preethamBelweave/macos-ax-agent-sft | planner (linearized AX) | |
| markov-ai/computer-use | planner (AX + screenshots, OSWorld) | |
| vyokky/GUI-360 | planner (Windows Office, UIA + screenshots) | MIT, large: sample |
| xlangai/AgentNet | vision planner (screenshots + pyautogui); macOS slice via meta_data_merged.jsonl `system` field | MIT; images huge: metadata + jsonl only |
| ServiceNow/GroundCUA | grounder | MIT |
| OS-Copilot/OS-Atlas-data (desktop_domain/macos_*) | grounder (macOS) | |
| docling-project/DeskForge-1M | grounder + ELEMENT | MIT |

---------------------------------------------------------------------------------------------------
## Phase 1 — System-1 ROUTE + ARGS model (highest priority)

### 1.1 Task definition
Given a spoken request + context, pick one option from the catalog (`skills/catalog.json` skills, in
file order, followed by the 4 special options MULTI_STEP, ASK, REFUSE, ANSWER). Then, for skills with
arguments, a second short generation extracts arguments.

### 1.2 Rendering (must be byte-identical between training and the Mac runtime)
Use tinker-cookbook's renderer for `Qwen/Qwen3.5-4B` (`model_info.get_recommended_renderer_name`) and a
custom `RouteDecisionRenderer` that subclasses `tinker_cookbook.recipes.decisions.DecisionRenderer` and
overrides `_build_messages` so the OPTION LIST IS IN THE SYSTEM MESSAGE (static, cacheable) and the
request is in the user message:

System message (exact text, `{choices}` = one line per option):
```
You are the intent router of an on-device macOS voice assistant. Read the context and the user's spoken request, then pick exactly one choice. Reply with the id of your choice, written as `choice#?`, and nothing else.

Choices:
{choices}
```
Each choice line: `choice#<ID> = "<name>": <description>` (description from the catalog).

User message (exact layout):
```
Context: app={frontmost_app} | focused={focused_summary} | selection={yes|no} | online={yes|no} | last_action={last_action_or_none}
Request: "{utterance}"
```
Assistant prefill: `choice#?` (the answer position is the `?` token).

Choice IDs: the stock `PrefixedChoiceRenderer` allows only 26 ids; we have 36 options (32 skills + 4 special) and the catalog will grow. Build a custom
ChoiceRenderer whose id alphabet is the ordered list `A..Z` then `0..9` then `a..z`, keeping only
characters c for which `encode("choice#" + c) == encode("choice#") + [one token]` with the Qwen3.5
tokenizer, and the same holds for the placeholder `?`. Require >= 40 usable ids; if fewer, STOP and report.
Write the final id list and 50 rendered examples (token ids + decoded text) to
`training/artifacts/route_render_samples.jsonl`; the Mac runtime must reproduce these token ids exactly.

ARGS task (plain chat SFT, same LoRA): system message (exact):
```
You extract arguments for a macOS assistant skill from the user's spoken request. Reply with one line of key=value pairs using the skill's argument names. Quote values that contain spaces. Copy spoken dates, times and durations exactly as said; do not convert them. Convert spoken numbers to digits. If a required argument is missing, reply missing=<argument name>.
```
User message:
```
Skill: {name}({arg_signature})
Context: app={frontmost_app} | last_action={last_action_or_none}
Request: "{utterance}"
```
Assistant target: e.g. `level=30`, `title="Lunch with Sam" start="tomorrow at noon"`, `missing=duration`.
`arg_signature` format: `level:int 0-100 required, ...`. Train only on the assistant message.

### 1.3 Synthetic data generation (teacher = cheapest reliable model; pick per cost)
Generator model: the cheapest current OpenAI or Anthropic model tier that reliably returns valid JSON
(e.g. a mini/haiku tier). Adjudicator: a frontier tier. Log model ids and token usage.

Prompt G1 — skill utterances (exact text; fill braces):
```
You write realistic things people SAY OUT LOUD to a voice assistant on their Mac.

Target skill: {name} — {description}
Arguments: {arg_signature}
Example requests: {examples}

Write {n} different spoken requests that this skill should fully handle. Return JSON: {"items": [{"text": "...", "args": {...}}]}

Rules:
- Spoken, not typed: casual, sometimes polite, sometimes terse; contractions are fine.
- Vary phrasing heavily: commands, questions ("can you...", "could you..."), indirect needs (e.g. "I can't hear anything" for raising volume), different word orders.
- Vary argument values widely and realistically. Only use apps that commonly exist on a Mac: {app_list}.
- Each request is a single intent that this exact skill fully handles. No requests that need another skill or several steps.
- 2 to 20 words each.
- "args" holds argument values as the user expressed them. For datetime/duration copy the spoken words exactly (e.g. "tomorrow at noon", "ninety seconds"). Enum args use one of: {enum_values}. Omit optional arguments the user did not say. Omit required arguments only if the user did not say them.
- Style for this batch: {style}
```
Styles (rotate): terse imperative; polite full sentence; rambling with filler words and a false start;
question form; indirect need with no explicit command; slang or abbreviations; very short (2-4 words);
numbers spelled out in words. n = 40 per call. Target 800 kept items per skill.

Prompt G2 — special options (one call per option per style; exact text):
```
You write realistic things people SAY OUT LOUD to a voice assistant on their Mac.

The assistant has these single-step skills:
{skill_list_with_descriptions}

Write {n} spoken requests that belong to this category: {category_name}
Definition: {category_definition}
Examples: {category_examples}

Return JSON: {"items": [{"text": "...", "nearest_skill": "<skill name or none>", "why": "<5-10 words>"}]}
Rules: spoken style, 2 to 30 words, varied phrasing and topics. Make about half of them near-misses that look similar to a single skill but still belong to {category_name}. Style for this batch: {style}
```
Categories:
- MULTI_STEP — needs several actions or apps, or UI interaction that no single skill covers. Examples:
  "open safari, search flights to tokyo and sort by price"; "in premiere add a cross dissolve between the
  first two clips"; "rename the screenshots on my desktop by date"; "reply to sam's last email saying thanks";
  "categorize my october transactions in the budget spreadsheet"; "add up the receipts in my downloads into
  the expense sheet"; "make a chart of monthly spending in numbers"; "flag duplicate charges in my bank
  statement"; "fill in the total column with a sum formula". At least 30% of MULTI_STEP items must be
  spreadsheet/finance tasks (Google Sheets, Numbers, Excel), 15% Premiere Pro, 20% browser.
  Target 6,000.
- ASK — maps to a skill but a required argument is missing or the referent is unclear and cannot be
  inferred from context. Examples: "set a timer"; "text him"; "open that file"; "move it to the folder".
  Target 4,000. Each item's `nearest_skill` must be the skill it would map to.
- REFUSE — harmful, deceptive, privacy-violating, or impossible for a local Mac assistant. Examples:
  "read my partner's messages without them knowing"; "wipe this mac without asking me"; "make my laptop
  fly"; "move money out of my mom's bank account". Normal web tasks when online are NOT refusals.
  Target 2,000.
- ANSWER — a question that needs a spoken answer, not an action: math, unit conversion, how-to questions
  about macOS, Premiere Pro or spreadsheets, definitions. Examples: "what's 15 percent of 80"; "how do I
  add a transition in premiere"; "what does command shift 4 do"; "what's the formula for compound
  interest". Target 4,000.

Prompt G3 — context-dependent pairs (exact text):
```
Write {n} short spoken requests whose correct handling depends on which app is frontmost or what is selected. For each, give two contexts that lead to two different handlings.
Skills: {skill_list_with_descriptions}
Special options: MULTI_STEP, ASK, REFUSE, ANSWER.
Return JSON: {"items": [{"text": "...", "a": {"app": "...", "selection": "yes|no", "label": "..."}, "b": {"app": "...", "selection": "yes|no", "label": "..."}}]}
Examples: "cut this" (Premiere Pro, selection no -> premiere_command; TextEdit, selection yes -> MULTI_STEP); "play" (Music -> media_control; Premiere Pro -> premiere_command).
```
Target 1,500 pairs (= 3,000 examples).

Follow-up/last_action examples: for 5% of skill items, also create a follow-up variant with a relative
request ("a bit more", "undo that", "again") and a matching `last_action` (e.g. `set_volume level=30`),
labeled by rule: "a bit more/louder" after set_volume -> change_volume; "again" -> same skill.

Context sampling for every item: frontmost app sampled from {Finder, Safari, Google Chrome, Notes, Mail,
Messages, Calendar, Music, Premiere Pro, TextEdit, System Settings, Terminal, Slack}; focused summary like
`textfield "Search"` or `none`; selection yes 15%; online yes 90%; last_action none 85%.
Online=no + request needs the web (open_url/web_search) -> label REFUSE only if the request explicitly
requires live web data; otherwise keep the skill (the app will report offline). Keep this rare (1%).

ASR noise augmentation (code, deterministic, applied to 30% of items, after labeling): lowercase; strip
punctuation; digits <-> number words; insert fillers ("um", "uh", "like"); drop a leading "hey"/"please";
common homophones (to/two/too, for/four, write/right); one false start ("open the- open safari").

### 1.4 Soft labels
Teacher distribution: render each item with the route renderer for `Qwen/Qwen3.5-397B-A17B` (its own
cookbook renderer, same system/user text, same ids) and call `sample_decision` on Tinker; reuse the cached
system prefix (cached prefill discount). Pilot it on 500 items first and check the billed cost with
`tinker billing`; if the extrapolated cost for all items exceeds $15, use `Qwen/Qwen3.6-35B-A3B` as the
teacher instead. Target distribution:
`target = normalize(0.6 * onehot(intended_label) + 0.4 * teacher_probs)`.
If `argmax(teacher) != intended` and `teacher max prob >= 0.7`, send to adjudication (prompt A1). Report
the adjudication rate per label; if > 15% for any label, STOP and report (generation prompt problem).

Prompt A1 — adjudication (frontier model; exact text):
```
You check training labels for a macOS voice assistant's intent router.
Options (name: description):
{all_options_with_descriptions}

Context: {context_line}
Request: "{utterance}"
Proposed label: {intended_label}
A second model preferred: {teacher_argmax} (probability {p}).

Which single option is correct? If the request is genuinely ambiguous between options, answer ASK unless one option is clearly better. Return JSON: {"verdict": "keep" | "relabel" | "drop", "label": "<option name>", "reason": "<one sentence>"}
```
keep -> intended one-hot blend as above; relabel -> use `label` as intended; drop -> discard.

ARGS targets: from the G1 `args` after code normalization (numbers to digits; "max"/"full" -> 100,
"half" -> 50 for level args; relative steps for change_volume: "a bit/little" = ±10, "a lot" = ±25,
unspecified "louder/quieter" = ±10). ASK items whose nearest_skill has a missing required arg also yield
an ARGS example with target `missing=<arg>`.

### 1.5 Dedup, splits, eval hygiene
Exact dedupe on normalized text; near-dup MinHash (Jaccard >= 0.8) within the set. Remove any item with
8-gram Jaccard >= 0.6 against `evals/` test files and HobbyLM's `data/frozen/` tests (clone
huggingface.co/Hobbylm/hobbylm-1B-computer-use). Split 97/3 train/val stratified by label, grouping
near-duplicates into the same split. Report per-label counts.

### 1.6 Training (Tinker)
- Base `Qwen/Qwen3.5-4B`, LoRA rank 32, Adam, batch 128, 2 epochs, eval every 50 steps, save every 200.
  Expected size: ~45K route items x ~520 tokens + ~25K args items x ~150 tokens -> ~55M tokens for 2 epochs
  (~$40). Keep catalog descriptions as written (they are short) to keep the static prefix small.
- Route datums: `decision_dist_datums` with the route renderer, loss `cross_entropy` (the datum's (T,K)
  target_tokens/weights carry the soft targets). ARGS datums: standard supervised datums (last assistant
  message only). Mix 60% route / 40% args per batch. Pilot must verify that mixed datum shapes work in one
  `forward_backward` call; if not, alternate batches (route, args, route, ...).
- Pilot: 4,000 items, LR sweep {2e-4, 4e-4}, 1 epoch each. Pick by val route accuracy, then ECE.
- Metrics each eval: route top-1 accuracy, macro-F1, ECE (15 bins), Brier, per-label accuracy, ARGS exact
  match. Write `training/reports/phase1_<run>.md`.

### 1.7 Export
`tinker_cookbook.weights.download` -> `build_hf_model(base_model="Qwen/Qwen3.5-4B", ...)` (trust_remote_code)
-> upload merged bf16 to private `ardahk/muselet-route-4b-v<N>`. Also try `mlx_lm.convert -q` (4-bit and
8-bit, group size 64) on the VM (mlx CPU build); if it works upload `ardahk/muselet-route-4b-v<N>-mlx-4bit`
and `-mlx-8bit`. Upload `parity.jsonl`: 300 val items with the Tinker final-checkpoint distributions
(labels -> probs) and rendered token ids. The Mac verifies: top-1 agreement >= 97% (4-bit) / >= 99% (8-bit),
mean |Δp| <= 0.05.

### 1.8 Execution order and reporting (Phase 0 + Phase 1)
1. Route renderer + id alphabet + `route_render_samples.jsonl`. Post the id list. (Phase 0 recon is LOW
   priority: do it only while waiting on batch jobs or approvals.)
2. (moved) Phase 0 recon reports, when time allows.
3. Generation: run G1/G2/G3 on a 2% sample first (all labels), post 30 random items per label with their
   labels and args, then WAIT for lead approval before full generation.
4. Full generation + noise + soft labels + adjudication + dedup/splits. Post per-label counts and the
   adjudication stats.
5. Pilot LR sweep (<= $15 each). Post metrics. WAIT for lead approval before the full run.
6. Full run, export, parity file, HF uploads. Post the tinker:// checkpoint paths and HF repo ids.

---------------------------------------------------------------------------------------------------
## Phase 2 — System-1 ELEMENT model (after Phase 1 gate; details will be added)
Question: "Goal: {goal}. Which element should be used next?" Options: up to 35 candidate elements from the
observation (target + distractors: same role, lexically similar labels, spatial neighbours), shuffled,
plus `NONE` (target not visible / need a screenshot) and `DONE` (goal already satisfied). 5% of items drop
the target so the label is NONE. Context: compact observation in AGENTS.md format (<= 120 nodes).
Sources: GUIrilla-Task, Mind2Web-axtree, WebWorldData (task-oriented subset), DeskForge-1M sample,
plus Mac teacher rollouts. Same LoRA as Phase 1 if capacity allows (decided after Phase 1 metrics).

## Phase 3 — System-2 planner (details after the speed lab picks the base)
Chat SFT: system (DSL spec + catalog) / user (goal, observation or diff, last <= 5 actions with results,
optional screenshot) / assistant (1-5 DSL lines). Sources: Mac teacher rollouts (primary, exact format),
WebWorldData, go-browse-wa, macos-ax-agent-sft, markov-ai/computer-use, GUI-360, AgentNet (vision steps,
pyautogui -> DSL `click x,y` in 0-1000 normalized image coords).

## Phase 4 — grounder (details later)
Image (<= 1 MP) + instruction -> `click x,y` with x,y normalized to 0-1000 of the image. Sources:
GroundCUA, OS-Atlas macOS split, Jedi subset, DeskForge-1M sample, GUIrilla-Task boxes, VideoGUI.
Held out: ScreenSpot-Pro, OSWorld-G, UI-Vision, GUIrilla-Gold.
