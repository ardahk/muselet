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
| STT final transcript | `{{stt_budget_ms}}` | `{{stt_ms_p50}}` | panel "Last release → text" |
| Router (cached prefix + suffix) | ~55 ms (target) | `{{route_ms_p50}}` / `{{route_ms_p95}}` | `route_ms` |
| ARGS extraction | `{{args_budget_ms}}` | `{{args_ms_p50}}` | `args_ms` |
| Ghost cursor lead | 120-220 ms (code constant) | n/a | `GhostCursor.swift:69` |
| HandsKit act + settle | `{{act_budget_ms}}` | `{{act_ms_p50}}` | `act_ms`, `settle_ms` in traces |
| **Release -> first action** | `{{e2e_budget_ms}}` | `{{instant_e2e_ms_p50}}` | `release_to_first_action_ms` |

Multi-step: planner `{{planner_model}}` at `{{planner_tok_s}}` tok/s; first action is executed as soon as its
line is decoded, so release -> first action is STT + route + planner prefill + one line, not a whole batch.
