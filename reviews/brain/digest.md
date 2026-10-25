# Brain lane review: pass 80 (2026-10-25T08:25Z)

Open: P0 0, P1 13, P2 25. New: brain-65, brain-66, brain-67.

## Branches
- main 3e323a9: #101 Spotify play (gated double-click, accent folding, player-state done check) and opt-in PLANNER=35b.
- wip/local b8eeec4: snapshot on main; lane identical.
- cloud/agentic-fixes2 b9cd089 (new, on cef8797): content hints, content-ask rejection, pending-task app check, invalid-expect drop, site-title loading, YouTube play evidence.

## New
- brain-65 (P2, main): the Spotify done check needs the subject in the track name. Artist, genre and playlist requests are always "not finished". Repro: test_brain_pass80.py, 3/3 fail.
- brain-66 (P2, agentic-fixes2): the draft_email hint says 'type exactly: "the meeting"' for the topic. Repro fails.
- brain-67 (P2, agentic-fixes2, code reading): _no_strike refusals skip the same-action loop guard, so repeats run to the 12-turn/60 s cap.

## Rechecked
- brain-60 (P1): main's Spotify play now checks the subject; other play targets and the email To field don't. fixes2 adds subject-free YouTube evidence and accepts auto-done with verify off.
- All other open findings: unchanged.

## Tests
18 MLX-only suite failures on main (2471 passed) and fixes2 (2477). Review repros: main 60 failed, 53 passed; fixes2 59 failed, 55 passed.
