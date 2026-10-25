| config | v1-tune | v1-holdout | v1-holdout2 | v2-holdout | holdout mean | step p50 ms | step p95 ms | think tokens mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 35b-t0-greedy-all | - | 9/14 (0.643) | 8/12 (0.667) | 64/130 (0.492) | 0.601 | 440 | 3291 | 0.0 |
| 35b-t512-greedy-all | - | 12/14 (0.857) | 10/12 (0.833) | 95/130 (0.731) | 0.807 | 5954 | 9565 | 342.1 |
| 4b-t1024-greedy-all | - | 12/14 (0.857) | 10/12 (0.833) | 78/130 (0.600) | 0.763 | 1687 | 5414 | 152.8 |
| 4b-t512-greedy-all | - | 12/14 (0.857) | 10/12 (0.833) | 78/130 (0.600) | 0.763 | 1743 | 5656 | 152.7 |
| 4b-t512-greedy-retry | - | 10/14 (0.714) | 8/12 (0.667) | 62/130 (0.477) | 0.619 | 306 | 1903 | 18.0 |
| 4b-t512-qwen-all | - | 11/14 (0.786) | 11/12 (0.917) | 79/130 (0.608) | 0.770 | 2596 | 7776 | 172.9 |
DECISION: ship 4b-t512-qwen-all
35b-t0-greedy-all: FAIL (holdout mean 0.601 < 0.672)
35b-t512-greedy-all: FAIL (step p50 5954 ms > 3000)
4b-t1024-greedy-all: PASS
4b-t512-greedy-all: PASS
4b-t512-greedy-retry: FAIL (holdout mean 0.619 < 0.672)
4b-t512-qwen-all: PASS

## Run details (sidekick, 2026-10-24)
- Worktree /tmp/wt-think @ cloud/planner-think (3677348), PYTHONPATH=ml/src; runs in /tmp/wt-think/runs/planner_offline/think-*.json.
- Sets: v1-holdout/v1-holdout2 (planner_offline) + v2-holdout (planner_v2_run); shipped config incl. retrieval k=1. Tune cells were trimmed per lead; 4b t0 k=1 baseline from retrieval eval: .714/.750/.462.
- think_closed distribution (t512 runs, v2holdout):
runs/planner_offline/think-35b-t0-greedy-all-v2holdout.json:
Counter({None: 130})
runs/planner_offline/think-35b-t512-greedy-all-v2holdout.json:
Counter({'model': 51, 'budget': 41, 'loop': 38})
runs/planner_offline/think-4b-t1024-greedy-all-v2holdout.json:
Counter({'model': 127, 'loop': 3})
runs/planner_offline/think-4b-t512-greedy-all-v2holdout.json:
Counter({'model': 126, 'loop': 3, 'budget': 1})
runs/planner_offline/think-4b-t512-greedy-retry-v2holdout.json:
Counter({None: 114, 'model': 16})
runs/planner_offline/think-4b-t512-qwen-all-v2holdout.json:
Counter({'model': 126, 'loop': 4})

## Extras (requested in PR #56)
- think_closed, v2-holdout rows: 4b-t512-greedy {model:126, loop:3, budget:1}; 4b-t512-qwen {model:126, loop:4}; 4b-t1024-greedy {model:127, loop:3}; 4b-t512-retry {model:16, none:114}; 35b-t512 {model:51, budget:41, loop:38}; 35b-t0 {none:130}. 4B self-closes ~97% (mean 152-173 think tokens — t1024 is identical to t512 because the model never uses the extra budget); 35B fails to self-close on 79/130, which is where its 6 s p50 comes from.
- Sample failure think_text (4b-t512-greedy): v2-premiere-start — reasons "use premiere_command go_to_start" then emits wrong first action; v2-reminders-no-enter — notices value already present but re-types. (35b-t512) v2-calendar-month, v2-url-not-front — coherent reasoning, action still wrong.
- Notable: t1024 == t512 scores exactly; retry gate too narrow (mean .619, most cases never think); 35b t0 (.601) is below the 4B baseline (.642).
