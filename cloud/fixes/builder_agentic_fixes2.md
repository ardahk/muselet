# Lane: agentic-fixes2 — fast, merged without review (user's call)
Read `cloud/builder_common.md`, `AGENTS.md`. Branch `cloud/agentic-fixes2` off latest main, one PR within 45 min, Python
only. Targeted tests only + one full `ml/tests` pass. Main already routes agentic-app tasks to the 35B blind planner.
User live failures (traces summarised):
1. **Ask for content that was already given.** "Reply to this email saying I can do Thursday at three": planner pressed
   Reply, then `ask "What text should I write in the reply?"` (twice). The text was in the agentic args
   (`draft_email {about: "I can do Thursday at three", reply: true}`) and in the hint. Fix: (a) `agentic.hint()` must
   state the exact text to type, e.g. `type exactly: "I can do Thursday at three"` (body/about/text/message/title args);
   (b) guard in the ask path: when the current task is an agentic app task whose args contain such content, reject an
   `ask` about what to write/say/type/search once with `the text is: "<value>" — type it` (no loop strike).
2. **Invalid expect kills a valid action.** `press #1181` with `expect radio "Timers" checked` failed with
   `invalid params: bad expect predicate`. Validate expects in the brain (dsl predicates: title~, focused, value, app,
   appears, gone); an invalid expect is dropped (trace `expect_dropped`) and the action still runs.
3. **Wrong app hints.** For "can you trim this video to be 5 seconds" with Premiere frontmost, the planner got app hints
   `['spotify','premiere','search_then_act']` and copied the Spotify tips. Find why `app_hints.match_hints` (or its
   caller, which may pass extra text like the previous goal / retrieved demo / observation) selected spotify, and fix so
   hints only come from the current goal + current app. Test with that exact goal and app "Adobe Premiere".
4. **YouTube "couldn't verify".** The video was playing (window title = the video title, url youtube.com/watch?v=...),
   but `finish.evidence(play)` found no Pause button (YouTube hides player controls from AX while idle / truncation).
   Add play evidence: browser page url (obs url or last ok url or ctx url) matching `youtube\.com/watch\?v=` AND window
   title not ending in a search title (`<query> - YouTube`) counts as playing. Also make the auto-done path
   (`progress_evidence`) handle `play` so the task ends right after the video opens instead of searching again.
5. **Navigation-click expects checked too early.** After pressing a link in a browser, an expect on the title failed
   because the title was still the transitional "(2) YouTube"/"YouTube". In `_page_loading`, treat a browser window
   title equal to the site's bare name (optionally with a "(N) " notification prefix) as loading so the existing
   re-poll (5 s) applies.
