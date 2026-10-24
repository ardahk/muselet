# Lane: brain-9 — fixes from tonight's live run (runs/bench/live/20261024T222159Z)

Branch `cloud/brain-9` from `main`, one PR. Python (`ml/src/brain`) plus one small Swift change (uncompiled; put the
compile/test under `## Mac requests`). Other lanes are editing `orchestrator.py` too (planner-verify: `_planner_loop`
done/recovery; memory: `handle_utterance`); keep your edits local to the functions named here and rebase often.

## 1. "search for flights to tokyo in safari" ran in Zen (the default browser)
Trace: router MULTI_STEP → planner `open "Safari"` → `skill web_search query="flights to Tokyo"` → HandsKit opened the
search in the default browser (Zen); Safari stayed on `favorites://`, then the planner clicked links in Zen until
the case timed out. HandsKit `Launch.openURL` always uses `launcher.defaultApp(for:)`.
- Swift: optional `browser` arg for the `open_url` and `web_search` skills (open with that app when it is
  installed, else the default; result reports the browser actually used). Add it to `skills/catalog.json` as an
  optional string arg and to the RPC docs in `AGENTS.md`. Keep the existing `title_changed` wait.
- Brain: when the utterance/goal names a browser (`_goal_mentions_browser` / `_browser_name` already exist), pass
  `browser=<that app>` on every `open_url` / `web_search` skill call and on the planner's `url` op; with no named
  browser, the default browser stays. Tests with fake Hands.
- Router parity: adding an optional catalog arg must not change the rendered router prompt for it2/it3 (check the
  route-parity tests; if the arg would change the prompt, keep it out of the router-visible catalog text).

## 2. Web answers read the page too early
"look up when the golden gate bridge opened": `_web_answer` observed 219 characters of AX text right after the search
(Zen's web tree wasn't filled yet), skipped OCR (threshold `< 200`), and answered NOT_FOUND.
- Before reading: wait for the page (re-observe until `web_ax_pending` is false and the text stops growing, or the
  title changed; cap 3 s).
- OCR the window when the AX text is under 1,500 characters or contains none of the query's content words; use the
  longer/richer text (or both, delimited).
- Keep the ≤ 12-word, answer-only-from-page rule. Tests with fake observations.

## 3. Cold first planner call
The first planner turn after brain start had TTFT 3,266 ms (later turns 130–1,500 ms). Warm the planner at startup
(build the static-prefix cache, load the retrieval bank, one dummy decode) in the background so the first real request
doesn't pay it; trace `planner.warm_ms`. Same for the 35B escalation planner when it loads.

No Tinker, no API spend.
