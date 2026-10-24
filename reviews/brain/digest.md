# brain digest — pass 8 (2026-10-24T07:40Z, PULSE 07:23Z)
Reviewed: cloud/brain-2 741465c (15 suites pass, including test_review_fixes 87; my review tests: 18 pass, the 2 brain-13 worker-level tests fail by design), cloud/grounding 3441ee8 (native-scale zoom capture, 123 pass), cloud/finance-2 dfaf785 (161 pass), cloud/advisor-2 0a65f75. main d8ad966 and wip/local 85ec0df have no ml/ changes; the confirm_cancel frame added to the contract on main is implemented on brain-2 (server sends it on confirm timeout or cancel).

cloud/brain-2 fixes brain-3, -4, -6, -9, -10, -11 and -13. **On main and wip/local they are all still open until brain-2 merges.**

## Open P0/P1 on main / wip/local (ranked)
1. brain-9  P0 Unsafe scripts execute without confirmation (fixed on brain-2)
2. brain-11 P1 5th expect dropped; DONE accepted unverified (fixed on brain-2)
3. brain-14 P1 One confirm unlocks a later dangerous action (P2 residual on brain-2)
4. brain-13 P1 Speculative routes queue ahead of the final route (fixed on brain-2)
5. brain-10 P1 Mute polarity inverted (fixed on brain-2)
6. brain-6  P1 engine.args runs on the event loop (fixed on brain-2)
7. brain-3/brain-4 P1 duration / datetime parsing (fixed on brain-2)
Open on every branch, P2: brain-14 residual, brain-8 last_action quoting, brain-12 pending ASK capture.

## Highest-leverage next moves
- Merge cloud/brain-2 into main/wip: it closes the only open P0 and 6 P1s.
- brain-14: clear the confirm token after any executed action, not just a dangerous one.
- Copy the v2 route_render_samples.jsonl to main/wip so test_route_parity stops xfailing.
- brain-8: always quote string args in last_action, to match training.
