# W9: Safety + robustness backlog (from the reviewer lanes and live traces)

Repo `ardahk/muselet`. Reviewer findings live on `origin/review/<lane>` in `reviews/<lane>/{findings.jsonl,digest.md}`.
The findings logs are append-only, so the **digest.md** of each lane holds the current open list. Re-verify every
item against current `main` before fixing it; many were fixed by later merges.

## Highest value (verify, then fix with regression tests)
1. **Script confirm bypasses** (evals-safety-2, brain-9). `orchestrator.script_needs_confirm` must confirm any
   script with side effects:
   - shell always;
   - AppleScript/JXA with do shell script, keystroke, click, delete, send, make new, open location, System
     Events UI scripting, and raw events.
   Add tests for each bypass the reviewers listed.
2. **"done" is trusted** (evals-safety-11, brain-11). Done must be backed by a passing `expect`, or by a fresh
   observation that satisfies the goal's predicate. The 5th action's expect must not be dropped.
3. **One confirm unlocks the whole batch** (brain-14). Each dangerous action needs its own confirm.
4. **The voice confirm parser** (hands-2) must read "not right now" / "ok cancel" as NO. Verify that
   `YesNo.swift` handles negation-first.
5. **Calculator keys can hit the wrong app** (brain-25). Check that Calculator is frontmost before posting keys.
6. **Fuzzy destructive path lookup can pick a sibling file** (brain-24). `move_to_trash` must use exact
   resolution or ask, with the confirm showing the full path (already true; verify).
7. **The 35B escalation load races** (brain-30). Serialize enable/disable; never two copies loaded.
8. **Sites rewrite opens the website for installed apps** (brain-29). Prefer an installed app (Zoom, Teams,
   Outlook) unless the user said website/go to/navigate. A failed `apps` RPC must not cache an empty list for
   60 s.
9. **`appears` predicate matches substrings and other windows** (hands-12). Scope it to the target window.

## Process
- One PR per 2–3 items, with tests.
- Python changes are testable on Linux with fakes. Swift changes need a Mac compile (`swift test
  --scratch-path .build-hands`).
