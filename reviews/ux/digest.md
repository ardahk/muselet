# ux digest — pass 35

Heads: main e56582b (no lane change since cf53292), wip/local 73f7044 (= main), cloud/app-ui ae9ce5e (merged main and
added a HandsKit import), cloud/comms c94a407 (merged main and fixed a test fake; its UX diff is the same as pass 34),
new cloud/bench-fix, data-planner and data-route (no lane files), cloud/decisions 694c198 (no lane files).

Counts: 0 P0, 0 P1, 9 P2 (8 on main, ux-22 dormant on main and live once app-ui merges).

- ux-21 resolved: app-ui now uses main's config handler unchanged and parses `loaded`. Against main's acks this gives
  Loaded, Off, or the brain's reason (for example "needs 48 GB RAM").
- ux-22 open: once app-ui merges, a persisted 35B toggle loads the model on the shared MLX worker on every brain
  connect, with no bubble while it loads.
- ux-12, ux-14, ux-15 (still present in the app-ui redesign), ux-16, ux-17, ux-18, ux-19, ux-20: unchanged.

From a UX view, app-ui and comms look ready to merge. Swift was not compiled here; ae9ce5e says it fixes the MuseletApp
build.
