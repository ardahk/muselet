# Lane: planner-verify — never report a false "done"; verify, then replan

User priority: "better planning, smarter, even if it takes a few seconds; better than something that doesn't work."
The live suite had false-done results (the agent said it was done when the final state was wrong). Branch
`cloud/planner-verify` from `main`, one PR, Python only. You own W9 item 2 ("done is trusted"); the safety-2 lane
skips it.

## Build (`ml/src/brain/orchestrator.py` `_planner_loop` and helpers)
1. **Verified done.** When the planner emits `done`, accept it only if (a) the last consequential action carried an
   `expect` that passed, or (b) a verification step says yes: take a fresh observation (plus OCR of the window if the
   AX text is short, as `_web_answer` does), then ask the planner model one `bool` question through the existing
   decision API (`decide`) on a compact state: goal, the actions taken, the fresh observation; "Is the goal achieved?".
   Use the probability with a threshold (constant, default 0.5, traced). No → put a one-line
   `verification failed: <what is missing>` into the planner history and replan.
2. **Bounded recovery.** On a failed `expect`, an action error, or a failed verification: replan with the error in
   the history, at most 2 recovery rounds per request (constant), keeping the existing 3-identical-actions rule and
   the step cap. When the budget is spent, say honestly what is left undone (≤ 12 words) with mood `confused`,
   never `success`.
3. **The 5th action's `expect` is never dropped** (W9 item 2 detail).
4. Never let verification or replanning skip a confirm, the permission-prompt gate, the sign-in guard or the
   document rules.
5. Trace `planner.verify: {method: expect|model, p_yes, ms, result}` and `planner.recover: {round, reason}`.
6. Flag `brain serve --verify-done on|off` (default **on**) + env `VERIFY_DONE` in `tools/serve_brain.sh`, so the old
   behaviour stays selectable.

## Tests
Fake Hands + fake models (existing patterns in `ml/tests`): done with passing expect is accepted without a model
call; done without expect and verifier "no" triggers a replan; the recovery budget ends in an honest failure reply;
confirm gates still fire on replanned actions; the 5th expect survives.

## Measurement
The lead measures false_done and pass on the live suite (`bench/live/run_live.py`) with on vs off. Write in the PR
what you expect and why, and the per-request latency cost of the verification step.

No Tinker, no API spend.
