# evals-safety digest — pass 35 (main@c949565)

Open: P0 0 · P1 2 · P2 9   (resolved this pass: -6 and -30, brain-6 merged)

## Open P0/P1 (ranked)
1. **-25** live document guard skips 9/43 cases (any Chrome/Slack/Messages window) and drops skips from the denominator; matters for the morning live runs. bench/harness/documents.py, bench/live/run_live.py.
2. **-11** `done` accepted after a passed expect or a fresh observation; no harness final-state check (pitch already scopes this as partial).

P2: -8, -12, -20, -21, -22, -23, -24, -28, -31.

## Next moves (max 5)
1. Count skips in the live denominator (report passed/43 and skipped), or narrow the document guard to the case's own apps (-25).
2. Before the morning live runs, close other document apps on the designated Mac so the 9 guarded cases execute (-25 mitigation).
3. Report planner holdout2 with the prompt sha (-31).
4. Add positive state checks to the 8 trace-only live cases (-24).
5. Leave Tinker headroom for billing lag on any large late run (-23).

Pass 34: main 5292608 only updates the AGENTS.md DeskMind overlap note (0 real, CJK-aware gate), which is consistent with -32 being resolved. wip/local matches main. No code changes, so -25 and -11 stand.

Pass 35: main c949565 adds briefs only. The comms brief requires contacts-first resolution and confirm "Send '<body>' to <Full Name>?" before send, and points at sendgate.py; good. decisions e125c13: generation spend is $52.89 of the $57 cap (OpenAI/Anthropic, not Tinker). Decontam is fail-closed and removed 1,925/3,673 labeled states by 13-gram; surviving code-gold has 0 counting/multi-hop/long-policy states (the report discloses this; it's an accuracy skew for the decisions model, not leakage). -25 and -11 stand (no code changes on main).
