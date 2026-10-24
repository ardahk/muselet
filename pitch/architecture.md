# Architecture

Code paths for every box are in `claims.md` §2. Numbers are placeholders from `claims.md` §1.

```mermaid
flowchart LR
  V["Hold Right Option<br/>PushToTalkMonitor"] --> S["STT on ANE<br/>FluidAudio Parakeet TDT v2"]
  S -->|utterance + ctx<br/>ws://127.0.0.1:8765| R{"Router<br/>Qwen3.5-4B LoRA (MLX)<br/>one forward pass"}
  R -->|skill, p >= tau| N["Native skill<br/>skills/catalog.json"]
  R -->|executor: brain| B["Brain tool<br/>finance_review / advisor_prep<br/>Decimal engines + evidence"]
  R -->|MULTI_STEP| P["Planner<br/>AX tree -> DSL batches (<= 5)<br/>streams, acts while decoding"]
  R -->|p < tau: hint 'A or B'| P
  R -->|ASK / missing arg| Q["Ask in bubble"]
  N -->|risk: confirm| C["Confirm in bubble<br/>risky skills, send/delete/buy,<br/>shell + non-allowlisted scripts"]
  P -->|risky action| C
  N -->|safe| H["HandsKit<br/>native skill > AX action > keys > pixel click"]
  B --> H
  P --> H
  C --> H
  H --> X["Verify (actions with expect)<br/>predicate on live AX state"]
  X -->|fail| P
  X -->|ok| M["Mascot bubble (<= 12 words)<br/>+ latency chip (ui.ms) + trace"]
  H -.screenshot only when AX is blind<br/>(<= 1 MP, own windows excluded).-> P
```

Everything above runs on the Mac. The only sockets are loopback (brain `:8765`, Premiere bridge `:8766`).
Models load with `local_files_only=True`.
Gates are scoped, not universal: `verify` runs only for actions with an `expect`; planner `done` is accepted
only after a passing `expect` or a fresh observation (no harness-side goal check); confirm covers the cases in `claims.md` §2.

## Latency budget (instant command, release -> first action)

| Stage | Budget | Measured (p50 / p95) | Source |
|---|---|---|---|
| STT final transcript | target TBD(lead) | TBD(live latency run) | panel "Last release → text" |
| Router (cached prefix + suffix) | ~55 ms (target) | 52 ms (r2) / TBD(route p95, it2) | `route_ms` |
| ARGS extraction | target TBD(lead) | 97 ms (r2) | `args_ms` |
| Ghost cursor lead | 120-220 ms (code constant) | n/a | `GhostCursor.swift:69` |
| HandsKit act + settle | target TBD(lead) | TBD(live latency run) | `act_ms`, `settle_ms` in traces |
| **Release -> first action** | target TBD(lead) | 193 ms p50 / 812 ms p95 (live suite, `runs/bench/live/20261024T161427Z`) | `release_to_first_action_ms` |

Multi-step: planner Qwen3.5-4B-4bit at 83 tok/s (earlier tuned config; TTFT 184.6 ms p50 on v2-holdout with k=1 retrieval, `cloud/handoff/notes/retrieval_eval.md`); first action is executed as soon as its
line is decoded, so release -> first action is STT + route + planner prefill + one line, not a whole batch.
