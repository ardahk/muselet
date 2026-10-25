# Memory for Muselet: research notes (W11, phase 0)

Scope: what the literature says about agent memory that a **4B on-device planner** with a **frozen router** can use.
Each entry: idea → what we take / leave.

## 1. General LLM-agent memory
- **MemGPT / Letta** (Packer et al. 2023, arXiv:2310.08560). OS-style hierarchy: a small always-in-context "core"
  block plus archival/recall stores the model pages in with function calls.
  *Take:* a tiny always-present working block (our ≤ 5 "Recent:" lines) and an out-of-context store.
  *Leave:* model-driven paging via tool calls — each call is a full decode on a 4B model (hundreds of ms) and small
  models are unreliable at deciding when to page. We page deterministically in code.
- **Generative Agents** (Park et al., UIST 2023, arXiv:2304.03442). Memory stream; retrieval score =
  recency (exponential decay) + importance (LLM-rated 1–10) + relevance (embedding cosine), min-max normalized;
  periodic "reflections". *Take:* the scoring formula for phase-2 retrieval, with importance assigned
  **deterministically by memory type** (corrections/people > preferences > episodes) instead of an LLM call.
  *Leave:* reflections (expensive, low value for short command sessions).
- **Mem0** (Chhikara et al. 2025, arXiv:2504.19413). Extract candidate facts from each exchange, retrieve similar
  memories, and let an LLM choose ADD / UPDATE / DELETE / NOOP; reports lower latency and tokens than full-context
  baselines on LOCOMO. *Take:* the four-operation update vocabulary, applied by **deterministic keys**
  (`person:mom`, `pref:browser`) so UPDATE/DELETE are exact; LLM extraction only offline/idle, never on the hot path.
- **Zep / Graphiti** (Rasmussen et al. 2025, arXiv:2501.13956). Temporal knowledge graph with validity intervals
  on edges; facts are invalidated, not overwritten. *Take:* `valid_from`/`superseded` columns so "forget that" and
  updates are auditable. *Leave:* the graph DB and LLM entity resolution (too heavy for the demo).
- **A-MEM** (Xu et al. 2025, arXiv:2502.12110). Zettelkasten-style notes that an LLM links and evolves.
  *Leave:* link evolution needs repeated LLM passes; our memories are few and typed.
- **ChatGPT memory** (OpenAI, "Memory and new controls for ChatGPT", Feb 2024; Apr 2025 update adding chat-history
  reference). Two tiers: explicit *saved memories* (user-visible, deletable, "remember that…") and implicit
  reference to past chats. *Take:* the UX contract — visible list, delete, off switch, a short "Got it" notice.

## 2. GUI / computer-use agents
- **Agent Workflow Memory, AWM** (Wang et al. 2024, arXiv:2409.07429). Induces reusable, abstracted workflows from
  successful trajectories and adds them to the agent's context; +24.6% / +51.1% relative success on Mind2Web /
  WebArena. *Take:* phase-2 procedural memory = successful planner traces, de-specified (values → slots), fed into
  the existing BM25 plan bank (`ml/src/brain/plan_bank.py`, already +7.2 pts holdout at k = 1).
- **Synapse** (Zheng et al., ICLR 2024, arXiv:2306.07863). State abstraction + trajectory-as-exemplar prompting +
  exemplar memory retrieved by similarity. *Take:* already in our planner (one retrieved exemplar); compact state.
- **Agent S / S2** (Agashe et al. 2024, arXiv:2410.08164; 2025, arXiv:2504.00906). Experience-augmented
  hierarchical planning with *narrative* memory (task-level summaries) and *episodic* memory (subtask steps),
  retrieved by task similarity. *Take:* episodic summaries ("opened Q3 budget in Numbers, ok") as a memory type.
- **UFO / UFO²** (Zhang et al. 2024, arXiv:2402.07939; 2025, arXiv:2504.14603). Windows agents that learn from
  help documents, past execution logs and user demonstrations via retrieval. *Take:* traces as the write source.
- **OS-Copilot / FRIDAY** (Wu et al. 2024, arXiv:2402.07456). Self-improving tool library from successful runs.
  *Take:* the frequent-workflow → catalog-skill path we already use (`executor: brain`).

## 3. Follow-up resolution in voice assistants (the phase-1 problem)
- **CANARD** (Elgohary et al., EMNLP 2019) and **QReCC** (Anantha et al., NAACL 2021, arXiv:2010.04898):
  conversational question *rewriting* into self-contained questions; rewriting lets an unchanged downstream system
  (search, QA) handle follow-ups. *Take:* rewrite **before** the frozen router, so router prompts never change.
- **Query reformulation for DST** (Rastogi et al., NAACL 2019 industry; Alexa) and **CREAD** (Tseng et al.,
  NAACL 2021; Apple): joint ellipsis + anaphora resolution by rewriting; industry systems gate the rewriter with a
  *trigger* classifier because most turns are self-contained and rewriting them is pure risk.
  *Take:* (a) a cheap detector gates everything — no detection ⇒ zero added work; (b) measure **false-rewrite
  rate** explicitly; (c) prefer copying spans from context over generating new content.
- Common finding across this line of work: rewrites must be conservative — a wrong rewrite of a self-contained
  command is worse than no rewrite; abstaining ("UNCHANGED") must be a first-class output.

## 4. Recommended design (details in `docs/MEMORY_DESIGN.md`)
1. **Working memory** (8-turn ring + focus state: app, site/URL, contact, file, query, pending task) with TTL
   (10 min) and app-switch expiry.
2. **Detector → rules → LLM** cascade before routing. Rules cover the high-frequency, high-precision cases
   (site-scoped search URL templates, again, undo, him/her/it/that). The LLM (the already-loaded 4B planner, greedy,
   ≤ 40 tokens, cached static prefix) only sees detected follow-ups that rules could not resolve, and may answer
   `UNCHANGED` or `ASK`.
3. **Safety guard** on every rewrite: it may not introduce an irreversible verb/skill and never bypasses confirm.
4. **Planner context**: ≤ 5 "Recent:" lines in the dynamic part of the planner prompt only.
5. **Long-term (phase 2)**: SQLite FTS5 (BM25), typed memories, deterministic writes keyed for exact
   UPDATE/DELETE, retrieval = recency × importance × BM25 relevance, ≤ 3 items / ≤ 150 tokens, read by planner,
   comms and the rewriter only. Embeddings only if they beat BM25 on the tune split.

## 5. Trade-offs
- Rules are fast and precise but brittle; the LLM generalizes but costs ~200–500 ms and can hallucinate. The
  cascade pays LLM cost only on detected, unresolved follow-ups.
- Rewriting into text keeps router parity but loses structure; for rule hits we also keep a *direct* action
  (e.g. `open_url`) and skip routing (faster, deterministic).
- A detector that is too eager raises false rewrites; one that is too strict misses follow-ups. The detector is
  tuned only on the tune split.

## 6. Hypotheses (each gets an ablation row: none / rules / rules+LLM / +long-term)
- **H1** Rules alone resolve ≥ 60% of tune follow-ups (site search, again, undo, person pronouns dominate the quotas)
  with ≈ 0% false rewrites (they fire only on explicit patterns with a live referent).
- **H2** Adding the LLM raises resolution to ≥ 85% at ≤ 2% false rewrites, because the detector keeps
  self-contained commands away from it and `UNCHANGED` is allowed.
- **H3** The fast path adds < 1 ms p50 (precompiled regexes over one utterance, no I/O).
- **H4** Long-term memory mainly lifts the `longterm` category (nickname → contact, STT corrections) and is neutral
  elsewhere.
- **H5** ≤ 5 Recent lines add ≤ 120 prompt tokens and ≤ 40 ms planner TTFT (dynamic tokens only; prefix stays
  cached), and help planner turns that refer to prior work.
