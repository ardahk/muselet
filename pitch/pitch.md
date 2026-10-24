# Pitch deck text (3 minutes + 2 min Q&A)

Numbers: only filled values from `pitch/claims.md` (each has a source there). `TBD(...)` cells are shown as
"running" or dropped, never estimated. Demo flow: `pitch/demo_script.md`.

## Slide 1 — Story (spoken over the live demo opening)
Every Mac assistant either explains where the menu is, or ships your screen to a cloud model. Muselet does the
thing: hold Right Option, say it, and a small kitten on your desktop does it in your real apps, with a ghost cursor
that shows where it acts. Everything runs on the Mac: speech, the models, the clicks. It works with Wi-Fi off.

Two speeds, on purpose. Single commands ("volume thirty", "dark mode") are instant: one forward pass picks the skill
and deterministic code does it. Chained tasks get a planner that is allowed to think: a few seconds per step if
that is what it takes to get it right, checking each step against the screen before moving on.

## Slide 2 — Who it's for
People who can't paste client data into a chatbot: a financial advisor preparing a client review, a freelancer
reconciling receipts. They use Calendar, Finder, Numbers, Notes, Messages and Gmail today; Muselet works inside
those apps, no migration, nothing uploaded.

## Slide 3 — Architecture (slide text)
- **Ears:** push-to-talk, Parakeet speech-to-text on the Neural Engine (FluidAudio).
- **System 1 — one forward pass:** a 4B router we fine-tuned on Tinker reads the request plus app context and
  outputs probabilities over 37 skills + MULTI_STEP / ASK / REFUSE / ANSWER. Confident -> act now. No generation.
- **System 2 — the planner:** a local 4B model reads the macOS accessibility tree and writes up to 5 actions per
  batch, each with an `expect` check; execution starts while it is still decoding. It retrieves one solved
  example per request (BM25).
- **Eyes:** a 4B grounding model only when the accessibility tree is blind (screenshot <= 1 MP, two-stage zoom).
- **Brain tools:** finance review and advisor prep are whole workflows picked in one router pass; `Decimal` code
  computes every number, the model only phrases.
- **Memory:** follow-ups ("search for history" after opening Wikipedia) are resolved against what just happened,
  before routing. (Say only once PR #50 is merged.)
- **Hands:** Swift HandsKit: native skill > accessibility action > keys > pixel click; risky actions wait for a
  spoken yes.

## Slide 4 — Why on-device
1. **Privacy by construction:** the brain listens on 127.0.0.1 only; models load with `local_files_only=True`;
   client portfolios and bank statements never leave the laptop (`claims.md` §2).
2. **Speed:** no network round trip; routing is one forward pass over a cached prefix (router p50 52 ms, r2,
   `claims.md` §1a; it2 TBD(router latency on it2)).
3. **Works offline:** the demo turns Wi-Fi off before the finance beats.
4. **Cost:** no per-request API bill; training cost us about $136 of Tinker compute in total (console, Sat 14:30
   PDT; `claims.md` §1).

## Slide 5 — Comparison (same Mac where marked; "published" = their number, their harness)

| | Muselet | DeskMind | HobbyLM-1B Computer Use |
|---|---|---|---|
| Runs fully local | yes | yes | yes ("local by default") |
| Input | voice, push-to-talk | not verified, don't say | not verified, don't say |
| Decision model | 4B LoRA router, one forward pass | 0.8B decides each step, unsure -> 4B (README) | 1B, median 0.26 s per decision (card, MacBook Air) |
| Their own benchmark | HobbyLM sealed r4: TBD(HobbyLM r4 rerun, it2) /125 | DeskMind Bench diag: published 39/39, step p50 2.85 s (M4 Pro) | published 90/125 (72%) |
| DeskMind Bench on our Mac | TBD(DeskMind diag, zh-Hans) /39 | TBD(same-Mac rerun) | – |
| Decision benchmarks (same Mac) | base 4B: JevBench .719, typed-decisions .569; decisions LoRA TBD(decisions-2) | brain-4b .831 / .658 | – |
| Finance workflows | advisor prep, receipts, duplicates, budget | – | – |

Spoken rule: DeskMind leads on decision benchmarks today (say so if asked). Our head-to-head claim is only made
where the cell is filled and same-Mac.

## Slide 6 — Results we can show today (each from `claims.md`)
- Router (it2, Tinker LoRA): route accuracy .913 on 103 clean held-out requests vs .767 for the base model.
- Planner (4B + 1 retrieved example): holdout .714 (10/14), holdout2 .750 (9/12), v2-holdout .462 (60/130).
- Live suite on the Mac, graded by final state: T1 19/22, T2 1/5 (morning run, 27 of 43 ran); first action p50
  193 ms.
- Grounding, ScreenSpot-Pro 200-sample subset: 63.5% at 1 MP with two-stage zoom.
- Pending, fill or drop: HobbyLM r4, DeskMind diag, router it3, decisions LoRA, memory eval.

## Slide 7 — Close
"Hold a key, say it, it's done. On your Mac, with Wi-Fi off."
