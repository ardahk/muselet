# ux digest — pass 37

Heads: main 7065dd3 (merged cloud/comms 6885b7c and cloud/app-ui e150506, both identical to the heads reviewed in pass
35 for lane files; adds live-suite grader fixes and a brain-8 brief), wip/local e29ea7c (adds HandsKit Contacts.swift
and MessagesCompose.swift).

Counts: 0 P0, 0 P1, 10 P2 (1 new).

New
- ux-23: when Messages is in front but its compose field can't be found, MessagesCompose returns `no_text_target`, and
  comms._preview shows "Messages didn't come to the front" for every error except screen_locked. Mapping
  no_text_target to its own copy is a 2-line fix.

Rechecks
- ux-22 is now live on main: the app sends config on every connect, and a saved 35B toggle makes the brain load the 35B
  on the shared MLX worker.
- ux-15 is now in the redesigned Settings on main (counts granted only; shows "Grant" for not-running apps).
- The wip compose/send results (frontmost, body_visible, sent, not_frontmost, screen_locked) otherwise match what
  comms.py expects.
- ux-12, ux-14, ux-16, ux-17, ux-18, ux-19, ux-20: unchanged.
