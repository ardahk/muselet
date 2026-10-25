# Lane: agentic-evidence (fast; speed over tests)
Read `cloud/builder_common.md`, `AGENTS.md`. Branch `cloud/agentic-evidence` off latest main (after PR #91 lands), one PR,
open within 60 min, Python only. Targeted tests + one full `ml/tests` pass.

`ml/src/brain/finish.py` now has two checks: `evidence(kind, subject, obs=..., script_stdout=, ocr=, url=)` (used at
`done`) and `progress_evidence(goal, obs_text, baseline)` (auto-done after every action; ends the task as soon as the goal
is visibly reached — this stopped a Clock pause/resume toggle loop and an Amazon cart that went to 11 items). Unify them
into one `evidence(...)` API used by both call sites in orchestrator.py, and extend auto-done to the agentic app kinds that
PR #91 routes to the planner (`app_finish(skill, args)`): timer start (a live row with button "Pause" and a countdown text
within ~10% of the requested duration), reminder (a row/checkbox labelled with the title appears in Reminders), note (the
focused note textarea value contains the topic's key words), event (Calendar shows text with the title), message (the
composer contains the body AND a confirm was asked -> end as awaiting_user, never auto-send), email reply (reply box
contains the text; never send), directions (route text with "min"/"Directions"), play (pause control / player state).
Keep the cart rules (count rises once; never press add-to-cart twice). Each kind: one positive + one negative unit test
using observation text in the AGENTS.md format.
