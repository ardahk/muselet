# Lane: premiere-demo — a reliable, impressive Premiere Pro beat for the demo

Premiere Pro has never been tested end to end. Branch `cloud/premiere-demo`, PR; Python + any Swift in its own commit
(uncompiled; `## Mac requests`). Read `skills/catalog.json` (premiere_* skills), `ml/src/brain/tools/` and the
architect-27 safety change (Premiere timeline edits confirm; Timeline focused before shortcuts).
1. Propose (in the PR) a 20-30 s voice sequence that looks great on stage on a prepared project, e.g. "import the
   clips from my Desktop Footage folder", "cut the clip at the playhead", "add a cross dissolve", "speed this up to
   150%", "add a marker here called intro", "export a 1080p H.264 to the Desktop". Prefer what can be done reliably
   with keyboard shortcuts (default keymap), menus over AX, and Premiere's ExtendScript/UXP only if verified.
2. Implement the missing pieces as deterministic `executor: brain` tools or skills with verification (AX of the
   Timeline/Project panels, file exists for export), with the planner as fallback.
3. A setup script `pitch/premiere_setup.md` + `bench/demo/premiere_project/` instructions (sample clips, project
   file) so the Mac can prepare the exact project; live acceptance cases for each utterance (checked from the screen
   or files, never from the brain's reply).
