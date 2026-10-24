# W11: Memory: short-term working context, long-term memory, episodic and procedural memory

Repo `ardahk/muselet`. Read `docs/HANDOFF.md`, `AGENTS.md` (architecture, protocol, design rules) and `ml/src/brain/orchestrator.py`
(`handle_utterance`, `_engine_route`, `_planner_loop`, `self._ctx`, `last_action`, `self._pending_task`, `self._comms`,
`self._draft`). This is the user's top new priority for the next org.

## What the user asked for (verbatim intent)
- "Integrate memory into the agent: memory of the previous tasks it has done, long-term memory, and some short-term
  memory of what it has done previously."
- "Make it without bloating the context so it doesn't slow us down, but I believe it'll make us smarter."
- "Example: I say *navigate to wikipedia*, it does it. Then I say *search for history*, and it searches Google. The
  agent should be intuitive about what is happening, smarter."
- "I am willing to sacrifice speed for more intelligence."

So: follow-ups must resolve against what just happened. Here "search for history" should search **Wikipedia**
(the site in front), not Google. Memory has to be compact, retrieved selectively, and on-device.

## Constraints (non-negotiable)
- **100% on-device.** Storage and inference stay local. No cloud memory service.
- **Privacy:**
  - never store secrets, passwords, one-time codes or message bodies beyond what's needed;
  - the user can see and delete memories (Settings › Memory pane), and "forget that" works by voice;
  - memory can be turned off.
- **Speed:** the fast path (unambiguous single commands) must not regress by more than ~10 ms p50. Follow-ups may
  spend up to ~300–500 ms extra for an LLM rewrite. The user accepts that; measure and report it.
- **Router parity:** the trained routers (it2, it3) use a fixed context format (`app`, `focused`, `selection`,
  `online`, `last_action`). Don't inject memory into router prompts unless you retrain (that's phase 3). Resolve
  follow-ups *before* routing by rewriting the utterance into a self-contained command, or by adding the context
  to slots in code.
- Every design choice needs a written hypothesis (expected effect, why) and an ablation that confirms or refutes it.

## Phase 0: research (deliverable `docs/MEMORY_RESEARCH.md`, ≤ 4 pages)
Survey, with citations and what applies to a small on-device model:
- Hierarchical/OS-style memory: MemGPT / Letta.
- Memory stream + reflection + retrieval scored by recency × importance × relevance: Generative Agents, Park et al.
  2023.
- Extraction/update operations (ADD / UPDATE / DELETE / NOOP): Mem0, 2024–25.
- Temporal knowledge graphs: Zep / Graphiti.
- Agentic linking: A-MEM.
- ChatGPT memory: saved memories plus chat-history reference.
- GUI/computer-use agents: Agent Workflow Memory (AWM, Wang et al. 2024: reusable workflows from past
  trajectories), Synapse (trajectory-as-exemplar), Agent S / S2 (experience-augmented planning, episodic and
  narrative memory), UFO / UFO² (experience and demonstration learning), OS-Copilot / FRIDAY (self-improving skills).
- Dialogue state tracking and contextual query rewriting for voice assistants: CANARD/QReCC, plus industry work on
  utterance rewriting for follow-ups and coreference.

End with a recommended design for Muselet, the trade-offs, and the hypotheses to test.

## Phase 1: short-term working memory + follow-up resolution (ship first)
1. **`ml/src/brain/memory/working.py`.** A ring buffer of the last ~8 interactions, kept in memory and mirrored
   to `runs/memory/working.json`.
   - Each entry: `{t, utterance, resolved_text, route/skill, args, outcome, app, window_title, url/site, entities}`.
   - It also keeps a **focus state**:
     - current app, site/URL (from the browser address bar via HandsKit AX, or from the last `open_url`);
     - document;
     - last contact/recipient, last file/folder;
     - last search query;
     - the pending task.
   - Expire focus items after N minutes (start at 10) or when the frontmost app changes away.
2. **HandsKit/app context:** add `url` (front browser tab URL) to the utterance `ctx` for Zen, Safari and Chrome,
   read through AX (web area / address field). Add it to the AGENTS.md protocol. No Apple Events, so no TCC
   prompts.
3. **Follow-up detector**, cheap and in code. Utterances that are elliptical or referential:
   - pronouns: it, that, this, there, him, her, them, the same, again, also, too;
   - verbs with no object;
   - "search for X" / "look up X" while a searchable site is in focus;
   - "the second one", "no, the other one", "go back", "undo";
   - "send it to …", "make it bigger".
4. **Resolution**, both paths traced as `memory.followup: {rule|llm, before, after, ms}`:
   - **Rules first.** Site-scoped search: "search for history" with focus `site=wikipedia.org` becomes
     `open_url https://en.wikipedia.org/w/index.php?search=history`. Use a table of site search URL templates
     (wikipedia, youtube, amazon, github, reddit, google maps, ...).
     Also: "again" repeats the last action, "undo" reverses the last reversible action (volume, dark mode,
     brightness, window layout), and "him/her" means the last contact.
   - **LLM rewrite when rules don't resolve.** Prompt the planner model (4B; the 35B when enabled) with ≤ 6 compact
     working-memory lines plus the utterance. Ask it to "Rewrite into one self-contained command, or reply
     UNCHANGED". Use greedy decoding, ≤ 40 tokens out, and keep the static prefix cached. Then route the rewritten
     text normally.
   - Never let a rewrite add an irreversible action. Confirm gates still apply.
5. **Planner context:** add ≤ 5 compact "Recent:" lines from working memory to the planner's dynamic state, after
   the cached prefix. Measure the token and TTFT cost.

## Phase 2: long-term memory (on-device store)
- **Store:** SQLite with FTS5 (BM25) at `~/Library/Application Support/Muselet/memory.db`, plus optional semantic
  retrieval with a small local embedding model via MLX (e.g. bge-small / gte-small, ≤ 40 MB). Benchmark whether
  embeddings beat BM25 on your eval before adding them.
- **Types:**
  - **profile/preferences:** default browser, preferred apps, units, sign-off name;
  - **people:** nicknames → contact ("mom" → a specific contact and handle, learned when the user picks one),
    including STT corrections ("Orda" → "Arda");
  - **facts the user states:** "my coworkers are …";
  - **episodic:** a task summary with outcome and timestamp;
  - **procedural:** successful multi-step plans as reusable workflows (AWM-style). Feed these into the planner
    retrieval bank (`ml/src/brain/plan_bank.py`, PR #35).
- **Write policy:**
  - deterministic extraction after each interaction (comms choices, corrections, explicit "remember that …");
  - optional background LLM extraction (Mem0-style ADD/UPDATE/DELETE/NOOP) when idle, never on the hot path;
  - importance scoring, dedupe/merge, decay.
- **Read policy:** per request, retrieve ≤ 3 items by recency × importance × relevance (Generative Agents), render
  them as ≤ 150 tokens, and only for the planner, comms and the follow-up rewriter. The router gets them only
  through rewritten text.
- **UX:**
  - Settings › Memory: list, search, delete, and an off toggle;
  - a voice "forget that" / "forget what I told you about X" (with confirm);
  - a short bubble when something is remembered ("Got it, Mom is Jane").

## Phase 3 (optional, needs Tinker budget): router trained with recent context
Generate multi-turn router data where the context includes the last 1–2 actions and focus (site/app/contact).
Train it4 so routing itself is context-aware. Only do this if phase 1 + 2 evals show the rewrite step is a
bottleneck.

## Evaluation (build before tuning; `evals/memory_followups.jsonl`, frozen, never trained on)
- **Offline multi-turn set:** 150+ sequences of 2–5 turns, each with screen state / focus and the expected
  resolved command per turn. Categories:
  - site-scoped search;
  - pronoun recipients/files;
  - again / undo;
  - corrections ("no, the other one");
  - learned preferences ("text mom" after a prior pick);
  - stale focus that must NOT be used;
  - plain unrelated commands, which must stay unchanged (a false-rewrite guard).
- **Metrics:**
  - resolution accuracy;
  - **false-rewrite rate** (unchanged commands that were changed);
  - added latency p50/p95;
  - prompt tokens.
  Ablations: none / rules / rules + LLM / + long-term.
- **Live multi-turn cases** through `bench/live/run_live.py`. Add a multi-utterance case type if needed, with
  mechanical preconditions and final-state checks. Example: "navigate to wikipedia" → "search for history" → check
  that the front tab URL contains `wikipedia.org` and `search=history`.
- **Pre-registered ship rule:**
  - resolution accuracy ≥ 85% on the frozen holdout half;
  - false-rewrite rate ≤ 2%;
  - fast-path p50 regression ≤ 10 ms.

## Deliverables
- `docs/MEMORY_RESEARCH.md` and `docs/MEMORY_DESIGN.md`.
- Phase 1 code + tests: the follow-up eval passing the ship rule, and live cases green.
- Phase 2 code + Settings UI (Swift needs a Mac compile) + tests.
- One PR per phase, with a numbers table.
