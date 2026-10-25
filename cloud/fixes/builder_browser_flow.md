# Lane: browser-flow (fast; speed over tests)
Read `cloud/builder_common.md`, `AGENTS.md`. Branch `cloud/browser-flow` off latest main, one PR, Python only, open it
within 45 min. Run only the test files you touch plus one full `ml/tests` pass at the end. Don't merge.

User live failures: "play some jazz on YouTube" opened youtube.com, then opened the search URL in a NEW tab; another run typed
the query into Zen's address bar (Google search); the base planner opened Safari although the default browser is Zen.
1. **Same tab inside a task.** In `Orchestrator._exec_action` url path (`if op == "url":` block, ~line 3056 on main), when
   `not self._page_task`, the task already navigated once (`self._last_ok_url` non-empty; it is reset per planner task),
   the current observed app (`(self._last_obs or {}).get("app")`) is a browser (`sendgate.is_browser`), the url is http(s),
   no explicit `browser` arg differs from it, and the goal doesn't ask for a new tab (`_NEW_TAB`), send it as
   `skill open_url {url, browser: <front>, same_tab: true}` (same as the page_task branch). Test with a fake server.
2. **Default browser.** New helper `default_browser() -> str | None` (cached): read
   `~/Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist` via `plistlib`, find the
   `LSHandlers` entry with `LSHandlerURLScheme == "https"`, map `LSHandlerRoleAll` bundle id → app name
   (app.zen-browser.zen→Zen, com.apple.safari→Safari, com.google.chrome→Google Chrome, org.mozilla.firefox→Firefox,
   company.thebrowser.browser→Arc, com.brave.browser→Brave Browser, com.microsoft.edgemac→Microsoft Edge); None on any
   error (Linux tests: monkeypatch). Add `Default browser: <name> (use it unless the user names another browser)` to the
   planner context block (`_planner_context_block`, the "Context at request" part; it's always safe to include).
   Also: a planner `open "Safari"` (or any browser) when the goal names no browser and the default is another browser is
   rewritten to the default browser (trace `browser_default_rewrite`).
3. **Compound fallback.** In the compound executor (`compound_routes` path), when a step fails with a recoverable reason
   (`fallback_recoverable`, e.g. `no_text_target` after "Open text edit and write Hello" hit TextEdit's Open dialog),
   hand the WHOLE original utterance to the planner once (reuse `_fallback_to_planner`), instead of stopping. One test.
