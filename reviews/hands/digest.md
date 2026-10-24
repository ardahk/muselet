# hands — digest (pass 21)

Open findings were re-verified on main 2920225 in pass 15: hands-1 to 9 and 11 to 14 are resolved, and hands-15 is superseded.
Pass 21 checks:
- main d514300 merged HandsKit batch 5, already reviewed on wip/local 630d661/4350185. The only later Swift delta is precompiling the volume-state script and an always-present `label` in timers. The AGENTS.md batch-5 contract matches the code.
- wip/local b63699f is identical to main.
- cloud/brain-5 b752261 handles `not_frontmost` by reading the failure `result`. That works: RPC.swift returns r with r["error"], BrainConnection always sends `result`, and server.rpc returns it with ok=false.
No new defects.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-16 (P2): hobby-gaps' calculator path should use one `type` act (keystroke_app is on main) instead of one `keys` act per character, which costs at least 120 ms of settle per character.
- hands-10 (P2): cap the act ghost-cursor lead at Act.swift:348 with `min(lead, cursor_lead_ms/1000)`.
- Not filed: `appears` still matches substrings and counts other already-open windows of the same app.
