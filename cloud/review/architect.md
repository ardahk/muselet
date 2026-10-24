
## Your lane: `architect` — goal alignment, system design, demo risk
Scope: the whole system as it exists across `main`, `wip/local` and `cloud/*`, judged against the goal.
Read `AGENTS.md`, `prompts/planner_system.md`, `skills/catalog.json`, `training/SPEC.md`,
the benchmark code in `bench/` (`runs/` is gitignored, so measured numbers are quoted below), and skim the
brain and app code.
Reference points: HobbyLM-1B Computer Use (0.26 s median decision latency, 72% = 90/125 live tasks, fixed
action vocabulary, no vision/mouse); DeskMind (github.com/deskmind-ai/deskmind: brain-0.8b/4b decision
models, eyes-4b grounder, DeskMind Bench 13 macOS tasks). Our measured: Qwen3.5-0.8B cached decision ~15 ms on
the M5 Pro.
Each pass, look for:
- Contract drift between Swift and Python, or between code and `AGENTS.md` (one side changed, the other not).
- The end-to-end latency budget for (a) an instant command and (b) a 5-step task: where the milliseconds go
  today, what is serialized that could overlap (speculative prefill on partial utterances, executing the
  first action while the planner still decodes, AX observe fused with act).
- Planner prompt quality (`prompts/planner_system.md`): ambiguity in the DSL, missing recipes for the demo
  (Numbers finance, Premiere shortcuts, browser), rules the executor cannot actually enforce.
- Demo risk: the four demo flows (instant macOS command, browser task, Numbers finance, Premiere) plus the
  "Wi-Fi off" moment — what is most likely to fail live, and what is still missing with the deadline in view.
- Benchmark plan: can we actually run HobbyLM's 125 tasks, DeskMind Bench, JevBench and the typed-decisions
  benchmark through a `/v1/systemone` shim, and is the comparison fair?
In `digest.md`, your "highest-leverage next moves" list is the most important output: ranked, concrete,
each with expected payoff and rough effort.
