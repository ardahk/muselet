# Memory design (W11)

Package `ml/src/brain/memory/`. On-device only; nothing leaves the Mac. Config: `brain serve --memory/--no-memory`
(default on; `MEMORY=0` in `tools/serve_brain.sh`) and `--memory-llm/--no-memory-llm` (LLM fallback, default on).

## Phase 1 — working memory + follow-up resolution
```
utterance + ctx ──► detect (regex, < 1 ms) ──no──► route as said            (fast path)
                         │yes
                         ▼
                    rules (site search, again, undo, pronouns) ──hit──► rewrite (+ direct action)
                         │miss
                         ▼
                    LLM rewrite (planner model, greedy, ≤ 40 tok) ──► UNCHANGED | ASK <q> | <command>
                         ▼
                    guard (no new irreversible verb, confirm gates intact) ──► route rewritten text
```
- `working.py` — `WorkingMemory`: ring of 8 turns `{t, utterance, resolved, skill, args, ok, said, app,
  window_title, url, site}` + `Focus` (app, url/site, contact, file, query, pending; each stamped). Items expire
  after 600 s, and site/url are dropped when the frontmost app is no longer a browser. A live `ctx.url` always
  wins over remembered URLs. Mirrored to `runs/memory/working.json`.
- `detect.py` — `detect(text, wm) -> reason | None`: pronouns (it/that/this/there/him/her/them/the same/one),
  again/repeat/also/too, undo/revert/go back, ordinals/"the other one", "search for X / look up X" while a
  searchable site is in focus, corrections ("no, I meant …"). Idioms the router already handles ("turn it up",
  "what time is it") are exempt.
- `rules.py` — site search URL templates (`SEARCH_URLS`, host → template), again (repeat last turn; direct only
  for `risk: safe` skills), undo (inverse table: dark_mode/mute/wifi/bluetooth toggle, change_volume −delta,
  set_volume/set_brightness → previous level from the outcome, window_layout → ask), person pronouns → last
  contact, item pronouns → last file/app/folder.
- `rewrite.py` — static prompt prefix (instructions + 6 examples, cached) + dynamic block (≤ 6 lines: focus,
  recent turns, utterance). Output `UNCHANGED`, `ASK: <question>` or one command line.
- `guard.py` — rejects a rewrite that adds an irreversible verb (send, delete, trash, empty, buy, post, pay,
  quit…) not present in the original; rewrites never execute directly when the skill is `risk != safe`.
- `__init__.py` — `resolve(...)` used by the orchestrator, `eval_adapter(...)` used by `evals/memory_eval.py`.
- Planner: ≤ 5 `Recent:` lines (≤ 80 chars each) in the dynamic user message.
- Trace: `decisions += {"memory.followup": {path, reason, before, after, ms}}`.
- Router prompts and `ctx` keys sent to the router are unchanged (`url`/`window_title` are kept out of the router
  ctx).

## Phase 2 — long-term memory
SQLite + FTS5 at `~/Library/Application Support/Muselet/memory.db` (`MUSELET_MEMORY_DB` overrides; tests use tmp).
Table `memories(id, type, key, value, importance, created, used, superseded)` + FTS5 on `key value`.
Types: `person` (nickname → contact, STT `correction`), `preference`, `fact`, `episode`, `workflow`.
Write (deterministic, after each turn): comms pick → `person`; "remember that …" → `fact`; "no, I meant X" →
`correction`; successful planner run → `workflow` (plan bank) + `episode`. Never: passwords, codes, message bodies.
Read: score = recency (0.995^hours) × importance(type) × BM25 relevance; ≤ 3 items, ≤ 150 tokens; consumers are
the planner, comms and the rewriter only. "forget that" / "forget what I told you about X" → confirm → delete.
Settings › Memory: list, search, delete, off toggle (`{"t":"config","memory":false}`).

## Ship rule (lead, holdout, Mac)
Resolution ≥ 85%, false rewrite ≤ 2%, fast-path p50 regression ≤ 10 ms. Ablation: none / rules / rules+LLM /
+long-term.
