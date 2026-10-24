# Lane: memory-eval — the frozen multi-turn follow-up evaluation set (data only)

Read `cloud/handoff/W11_memory.md` (Evaluation section), `skills/catalog.json` (skill names and args),
`ml/src/brain/sites.py` (site names) and `AGENTS.md` (utterance `ctx` fields). Branch `cloud/memory-eval` from
`main`, one PR. You produce **data only**: the lead owns the scorer `evals/memory_eval.py`; a different agent builds
the memory system and must never see your holdout items, so don't share them anywhere except this PR.

## Deliverables
1. `evals/memory_followups.jsonl`: **200 sequences** of 2–5 turns, one JSON object per line:
```json
{"id": "mf-0001", "split": "tune", "category": "site_search", "longterm": [],
 "turns": [
  {"utterance": "navigate to wikipedia",
   "ctx": {"app": "Zen", "focused": "none", "selection": false, "online": true, "url": "https://www.google.com/", "window_title": "Google", "t": 0},
   "outcome": {"skill": "open_url", "args": {"url": "https://www.wikipedia.org"}, "ok": true},
   "expect": {"type": "unchanged"}},
  {"utterance": "search for history",
   "ctx": {"app": "Zen", "focused": "none", "selection": false, "online": true, "url": "https://www.wikipedia.org/", "window_title": "Wikipedia", "t": 9},
   "outcome": {"skill": "open_url", "args": {"url": "https://en.wikipedia.org/w/index.php?search=history"}, "ok": true},
   "expect": {"type": "rewrite", "all": [["wikipedia"], ["history"]], "none": ["google"]}}
 ]}
```
   - `ctx` = what the app captures at push-to-talk (fields above; `url` empty when no browser is frontmost, `t` in
     seconds since the first turn). `outcome` = what correctly happened after the turn (used as history for later
     turns). Use real catalog skill names and argument names, or `planner` for multi-step tasks.
   - `expect` per turn, one of:
     - `{"type": "unchanged"}` — must be routed exactly as said (self-contained commands, unrelated commands);
     - `{"type": "rewrite", "all": [[alternatives...], ...], "none": [...]}` — the resolved command must contain at
       least one alternative from **every** group and none of the `none` terms (case-insensitive substrings).
       Groups name the referent, not a wording: e.g. `[["wikipedia"], ["history"]]`, `[["jane", "mom"], ["running late"]]`.
       Make groups robust to valid paraphrases (both a URL form and a phrase form must pass);
     - `{"type": "not_resolved"}` — the context does not determine the referent (e.g. "send it to him" with no prior
       person, or clearly stale focus); passing means the resolver did NOT invent one (it may leave the text
       unchanged or ask).
   - The first turn of a sequence is usually `unchanged`.
   - Category quotas (sequences): `site_search` 30, `pronoun_person` 20, `pronoun_item` (file/folder/note/app/
     window) 20, `again` 15, `undo` 15 (volume, brightness, dark mode, window layout), `correction` ("no, the other
     one", "I meant Safari") 15, `refinement` ("make it louder", "a bit more", "now in dark mode too") 15,
     `stale` (≥ 30 min gap or the user clearly moved to an unrelated app; expect `not_resolved` or `unchanged`) 15,
     `unrelated` (self-contained commands right after a context they could be wrongly tied to: "search google for
     flights" while on Wikipedia, "open Safari", "turn the volume up" after a Messages turn, "text Caleb hello"
     after talking about Arda; expect `unchanged`) 30, `longterm` (needs seeded `longterm` memories,
     e.g. `{"type": "person", "key": "mom", "value": "Jane Kim"}` then "text mom I'm running late") 25.
   - Diverse apps (Zen, Safari, Chrome, Finder, Notes, Messages, Mail, Music, Numbers, Premiere Pro, System
     settings), spoken style with occasional STT noise, no real personal data.
   - `split`: stratified 50/50 tune/holdout per category, assigned with a fixed seed.
2. **Quality gate:** write items with one provider and have the other provider judge every item blind ("does the
   expectation match what a reasonable user means? is the `all` grouping fair to valid paraphrases?"). Drop or fix
   disagreements; report the agreement rate per category. Dedupe near-identical sequences.
3. `evals/memory_followups_lint.py`: structure checks only (schema, categories, quotas, splits, catalog skill
   names, non-empty groups) + a test in `bench/tests/`. Not a scorer.
4. `evals/memory_followups_REPORT.md`: counts per category/split, judge agreement, generation recipe and seeds, and
   20 random tune-split examples for the lead's review.
5. Add `evals/memory_followups.jsonl` to the never-train lists (the decontamination reference lists and the
   relevant docs).

No Tinker. API cap: $30 per provider.
