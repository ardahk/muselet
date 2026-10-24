# Sidekick handoff (credit cut-over) — 2026-10-24 ~14:25 local

## Landed on main (all merged clean, all tests green)
- #36 mascot-animal: merge `7879cdf` — kitten "Muse"; compiled with zero fixes needed.
- #34 clock-timers: merge `f6b52a8` — Clock shortcut + internal fallback + Settings row.
- #35 planner-retrieval: merge `537c4dd` — BM25 opt-in examples, default k=0.
- #33 planner-demos: merge `3c792a5` — training/planner_demos/ tooling.
- Fix commit `0e7b5a8`: ParityFixesTests timer-notification expectation updated
  to [1,2,1,0] (clock-timers cancels per-timer, reporting true intermediates).
- No MERGE_HEAD, no uncommitted files, no remaining compile/test issues.

## Test counts (final, all green)
- Swift `swift test --scratch-path .build-hands`: 236 passed.
- ml pytest: 1506 passed, 2 skipped. bench pytest: 165 passed, 2 skipped.
- `shortcuts list`: "Muselet Start Timer" absent → detection "missing" OK.
- Internal timer snapshot exists ($TMPDIR/muselet-timers/98763.json).

## Mascot screenshots (kitten, 400x400 crop, bottom-right corner)
- /tmp/ui_shots/kitten_{idle,listening,thinking,acting,success,confused,sleeping}.png
- All 7 distinct (md5-verified). Mascot origin {1690,1014} Cocoa; display 1800x1169.
- No hover or reduce-motion debug hooks exist — those shots not taken.

## Processes (all current, healthy)
- Muselet app: pid 6795 (build 0e7b5a8).
- :8765 brain: pids 7372/7377 (tools/serve_brain.sh, it2 router + 4B planner
  + eyes-4b), restarted after #34/#35 landed; app log shows config_ack ok.

## NOT done — planner retrieval eval (never started; no cells run)
Required cells: `--retrieval-k 0|1|2` × sets {v1 tune, v1 holdout, v1 holdout2,
v2-holdout}, 4B default config, default bank `v2-tune`, one model process
at a time (memory level >=40). Record pass/strict/mean prompt tokens/TTFT/
per-turn latency per cell. Commands:
  uv run --project ml python evals/planner_offline.py --history dsl \
    --constrain --done-alone --system-extra prompts/planner_fewshot.md \
    --set <tune|holdout|holdout2> --retrieval-k <0|1|2> --tag ret_k<K>_<set>
  uv run --project ml python evals/planner_v2_run.py --v2-set v2-holdout \
    --model mlx-community/Qwen3.5-4B-4bit --retrieval-k <0|1|2> \
    --tag ret_k<K>_v2holdout
(Verify the exact v1 config flags against `tools/serve_brain.sh` / a recent
ship_* run tag before trusting the flags above.)
Rule (lead applies): ship k>0 only if mean holdout pass (v1-ho, v1-ho2,
v2-ho) improves >=3 pts vs k=0, no set drops >1 scenario, TTFT +<=150ms.

## Next
- Run the retrieval matrix above; evals/planner_retrieval_report.py exists.
- hands probe windows (3876f3a) measured 0.293s over all 27 bundle ids —
  Python inventory switch to it is the lead's.
