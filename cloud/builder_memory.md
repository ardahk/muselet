# Lane: memory — working memory + follow-up resolution (phase 1), then long-term memory (phase 2)

Brief of record: `cloud/handoff/W11_memory.md` (read it fully; it has the user's intent, constraints, design and
ship rule). This is the user's top priority. Branch `cloud/memory` from `main`; one PR per phase.

## Compressed timeline (deadline Sun 09:00 PDT)
1. `docs/MEMORY_RESEARCH.md` (≤ 3 pages, concise, cited) + `docs/MEMORY_DESIGN.md` — push within ~90 minutes.
   Don't wait for review; continue straight into phase 1.
2. **Phase 1 PR by ~21:00 PDT Sat:** working memory + focus state, follow-up detector, rule resolution
   (site-scoped search URL templates, again, undo, him/her/it/that), LLM-rewrite fallback using the planner model
   that is already loaded in the brain (no extra model process; greedy, ≤ 40 output tokens, cached static prefix),
   ≤ 5 "Recent:" lines in the planner's dynamic state, tracing `memory.followup`, a config flag to turn memory
   off, and the `url` field in the utterance `ctx` (HandsKit/app part in a separate uncompiled Swift commit, AX
   only, no Apple Events; update the protocol section of `AGENTS.md`).
3. **Phase 2 PR by ~03:00 PDT Sun:** SQLite FTS5 store at `~/Library/Application Support/Muselet/memory.db`, typed
   memories (preferences, people/nicknames/STT corrections, stated facts, episodic summaries, procedural workflows
   feeding `ml/src/brain/plan_bank.py`), deterministic write policy, ≤ 3 retrieved items / ≤ 150 tokens for the
   planner, comms and rewriter only, "forget that" by voice with confirm, Settings › Memory pane (uncompiled Swift).

## Hard constraints
- Router prompts never change (it2/it3 parity tests must stay green): resolve **before** routing by rewriting the
  utterance or filling slots in code.
- A rewrite can never add an irreversible action or skip a confirm gate. Never store secrets, codes, passwords or
  message bodies.
- Fast path (no follow-up detected) adds ≤ 10 ms p50; measure it with a micro-benchmark in tests.

## Evaluation contract (lead-owned; do not author or edit eval items)
A separate agent is writing `evals/memory_followups.jsonl` (multi-turn sequences, `split` = `tune` | `holdout`)
and the lead owns the scorer `evals/memory_eval.py`. **Develop only against `split == "tune"` items; never open or
print holdout items.** Until the set lands, write your own unit tests from the W11 examples.
The scorer imports this exact adapter, which you must provide:

```python
# ml/src/brain/memory/__init__.py
def eval_adapter(utterance: str, ctx: dict, history: list[dict], longterm: list[dict] | None = None,
                 llm: Callable[[str, int], str] | None = None) -> dict:
    """Return {"text": str, "changed": bool, "path": "none"|"rule"|"llm"|"ask", "ask": str|None, "ms": float}."""
```
- `ctx`: the utterance ctx as the app sends it plus `url`, `window_title` and `t` (seconds since the sequence start).
- `history`: prior turns, oldest first, each `{"utterance", "ctx", "outcome": {"skill", "args", "ok", "said"?}}`
  (what actually happened; `skill` is a `skills/catalog.json` name, or `planner` for multi-step tasks).
- `longterm`: seeded long-term memories for phase 2, each `{"type", "key", "value"}`
  (types: `person`, `preference`, `fact`, `correction`, `workflow`). Phase 1 may ignore it.
- `llm`: a prompt → completion callable (greedy, max tokens). `None` = rules only. The Mac runs it with the 4B planner.
- `changed` is False when the text should be routed as said. `path == "ask"` means the resolver wants to ask the
  user (put the question in `ask`) instead of guessing.
Ship rule (pre-registered, holdout half, measured by the lead on the Mac): resolution accuracy ≥ 85%,
false-rewrite ≤ 2%, fast-path p50 regression ≤ 10 ms. Report the ablation none / rules / rules+LLM / +long-term.

No Tinker. API cap: $10 per provider (research only).
