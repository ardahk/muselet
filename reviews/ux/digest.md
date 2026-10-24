# ux digest — pass 32

Heads: main c949565, wip/local 4ec066f (= main for lane files), cloud/decisions e125c13; others unchanged.

- main 5292608..c949565: only `cloud/builder_appui.md` and `cloud/builder_comms.md` (briefs, no code). No lane change.
- cloud/decisions: no app/brain changes since merge base (training reports only).
- Note on `cloud/builder_appui.md`: it redesigns Panel/ and Mascot/ and adds a typed-utterance pill and a
  `config`/`config_ack` frame. It keeps "the current rows (Automation grants included)", so ux-15 (`.notRunning` shown
  as "Grant") would carry over unless the builder is told to fix it. Will review the code when `cloud/app-ui` lands.

Counts: 0 P0, 0 P1, 8 P2 open (all on main): ux-12, ux-14, ux-15, ux-16, ux-17, ux-18, ux-19, ux-20. Re-checked: no lane
file changed since pass 31, so all remain open at the same evidence lines.

Top: ux-19 (unanswered screenshot-click confirm -> "Something went wrong", orchestrator.py:1361/1419, ~5 min),
ux-20 (grounder lazy load, no bubble), ux-16 (relative brightness -> bare "Done", ~10 min).
