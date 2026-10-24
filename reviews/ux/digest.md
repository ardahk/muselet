# ux digest — pass 34

Heads: main cf53292 (merged brain-7 #25, report #22, native-research #23, and new briefs), wip/local e14fa54 (this
snapshot predates the brain-7 merge in lane files), new cloud/comms 956d4ac, cloud/report-2 3c25e78 (docs),
cloud/decisions 43abfa3 and cloud/data-pipeline f8b721a (no lane files).

Counts: 0 P0, 1 P1, 9 P2. None new.

- ux-21 P1: brain-7's config_ack (no `ok`, has `loaded`) is now on main. app-ui still reads `ok ?? false`, so a loaded
  35B shows "Not available", and app-ui's own server.py/cli.py config handler conflicts with main. Fix before merging
  app-ui.
- ux-22 P2: brain-7's load-on-toggle (on the shared MLX worker) is on main. It is dormant until app-ui sends config
  frames on every connect.
- cloud/comms: the contacts-first Messages flow and the email drafts handle confirm timeouts (`except RuntimeError` ->
  "Left it as a draft", idle), name the recipient and excerpt the body in the confirm, and use specific failure copy
  ("Messages isn't in front, so I didn't send"). This is the pattern ux-19 needs. Its new asks and the Gmail sign-in
  prompt add to ux-12 (listening mood while the mic is off). Edge case: an 8-word excerpt plus a two-word name and a
  label is 13 words.
- ux-14, ux-15, ux-16, ux-17, ux-18, ux-19, ux-20: unchanged on main.
