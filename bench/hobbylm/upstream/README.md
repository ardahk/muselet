---
license: apache-2.0
library_name: peft
pipeline_tag: text-generation
base_model: harims95/hobbylm-1B-instruct
language:
  - en
tags:
  - lora
  - mlx
  - mixture-of-experts
  - hobbylm
  - agent
  - macos
  - tool-use
  - computer-use
  - on-device
---

# HobbyLM-1B Computer Use

![HobbyLM-1B Computer Use: plain English in, one Mac action out](assets/hero.png)

**HobbyLM-1B Computer Use** is a LoRA adapter for [HobbyLM-1B Instruct](https://huggingface.co/harims95/hobbylm-1B-instruct).
It turns a plain-English request into actions on a Mac, one step at a time, and runs entirely on the device.
This repository contains the adapter, the app that runs it (Hobby), the evaluation records and the training code.

| | |
|---|---|
| **Base model** | `harims95/hobbylm-1B-instruct` @ `8a90f6eb`, a sparse mixture-of-experts model (8 of 64 experts per token) |
| **Adapter** | LoRA, rank 16, 83 modules, 14 MB in MLX form |
| **Runtime** | Apple MLX on Apple Silicon, FP32, median 0.26 s per decision on a MacBook Air |
| **Evaluation** | 90 of 125 sealed requests completed live on macOS (72%) |
| **Training** | 4 rounds, 60 H100-minutes in total |
| **Version** | v0.1 · Apache-2.0 |

## Contents

- [Skills](#skills)
- [How it works](#how-it-works)
- [Fine-tuning](#fine-tuning)
- [Evaluation](#evaluation)
- [On-device speed](#on-device-speed)
- [Quickstart](#quickstart)
- [Safety design](#safety-design)
- [Scope](#scope)
- [Files](#files)
- [Licence and credits](#licence-and-credits)

## Skills

Every example below is a real request from the sealed round-4 test, or from the recorded demo, with the action the model wrote.

| Skill | Example request | The model writes | What Hobby does |
|---|---|---|---|
| **Calculator** | `split 600 among 4 people` | `OPEN Calculator` → `TYPE 600/4=` → `DONE` | Opens Calculator and types the keys, so Calculator does the arithmetic and shows **150** |
| | `196 divided by 7` | `OPEN Calculator` → `TYPE 196/7=` | Calculator shows **28** |
| **Brightness** | `screen faded, more light needed` | `KEY BRIGHTNESS_UP` | Raises the display brightness |
| | `laptop glow is insane, pull brightness down` | `KEY BRIGHTNESS_DOWN` | Lowers the display brightness |
| **Volume** | `sound is harsh, turn it down a notch` | `KEY VOLUME_DOWN` | Lowers the output volume |
| | `mute everything` | `KEY MUTE` | Mutes the output |
| **Dark mode** | `flip to dark theme, late night work` | `DARK_MODE ON` | Switches macOS to dark appearance |
| | `bring back the light theme` | `DARK_MODE OFF` | Switches back to light appearance |
| **Open an app** | `gotta scribble a quick note` | `OPEN Notes` | Opens Notes |
| | `when is my next meeting` | `OPEN Calendar` | Opens Calendar |
| **Open a folder** | `need papers from documents` | `FOLDER Documents` | Opens Documents in Finder |
| | `show whatever is sitting on desktop` | `FOLDER Desktop` | Opens Desktop in Finder |
| **Timer** | `seven minute timer for eggs` | `TIMER 7` | Starts a 7-minute timer with a notification |
| | `remind me after 4 hours to stretch` | `TIMER 240` | Converts hours to minutes and starts the timer |
| **Screenshot** | `snap my screen` | `SCREENSHOT` | Saves a screenshot to the Desktop |
| **Calendar events** | `coffee with Meera wednesday 10am` | `EVENT Coffee with Meera \| wednesday \| 10:00 \| Meera` | Resolves the date, finds Meera in Contacts, asks **y/n**, then adds the event |
| | `1:1 with Sneha tomorrow 2:30pm IST` | `EVENT 1:1 with Sneha \| tomorrow \| 14:30 IST \| Sneha` | The same flow, honouring the stated time zone |
| **Knowing its limits** | `will it rain in mumbai tonight` | `UNKNOWN` | Replies "I can't do that one offline." |
| | `whatsapp meena that dinner is at 8` | `UNKNOWN` | Does nothing, by design |

A recorded session looks like this:

```text
you › split 600 among 4 people
  0.3s  Hobby → OPEN Calculator
  ↳ Calculator opened.
  0.3s  Hobby → TYPE 600/4=
  ↳ display changed from 0 to 150.
  0.2s  Hobby → DONE
  ✓ done
```

## How it works

![How one step works: request, model, action, harness, checker](assets/how-it-works.png)

1. **The request and the live state go to the model.** Hobby reads the Mac's current state (Calculator display, front app,
   brightness, volume, appearance) and sends it with the request.
2. **The model writes one action** from a fixed vocabulary of ten.
3. **The harness validates the action against an allow-list** and executes it through macOS. Calculator input goes through
   [`mcp-server-macos-use`](https://github.com/mediar-ai/mcp-server-macos-use); everything else uses direct macOS calls.
4. **The result goes back to the model** as `Last action: … Result: …`, and the loop continues until the model writes `DONE`
   (at most 6 steps).

### Prompt format

The model uses HobbyLM's native `SYSTEM:` / `USER:` / `ASSISTANT:` format with greedy decoding. The system prompt lists the allowed
actions (see `hobby/hobbymac_data.py`, `SYSTEM_V2`). A user turn from the evaluation log:

```text
Request: what's 82 plus 47

State:
Calculator: open, display shows 0
Front app: Code
Brightness: 56%  Volume: 100%
Dark mode: on

Last action: OPEN Calculator. Result: Calculator opened.

Next action:
```

The model answers `TYPE 82+47=`, and Calculator shows 129.

### Action vocabulary

| Action | Argument |
|---|---|
| `OPEN` | `Calculator`, `Notes`, `Calendar`, `Finder`, `Music`, `Reminders` |
| `TYPE` | Calculator keys: digits `. + - * / =` |
| `KEY` | `BRIGHTNESS_UP`, `BRIGHTNESS_DOWN`, `VOLUME_UP`, `VOLUME_DOWN`, `MUTE` |
| `DARK_MODE` | `ON`, `OFF` |
| `FOLDER` | `Downloads`, `Desktop`, `Documents` |
| `TIMER` | minutes |
| `SCREENSHOT` | none |
| `EVENT` | `title \| day \| time [timezone] \| person or email` |
| `DONE` | none; the request is complete |
| `UNKNOWN` | none; the request is outside these actions |

## Fine-tuning

The base model is unchanged. All the new behaviour comes from a LoRA adapter trained on synthetic one-step decisions: given a
request and a Mac state, write the single correct next action.

| Setting | Value |
|---|---|
| Method | LoRA, rank 16, alpha 32, dropout 0.05 |
| Target modules | attention `q/k/v/o` in every layer, plus the dense layer-0 MLP `gate/up/down` (83 modules) |
| Frozen | all base weights, including the expert routers (bias updates disabled) |
| Loss | on the action tokens only |
| Data | synthetic (state → next action) decisions generated by `hobby/hobbymac_data.py` |
| Hardware | one NVIDIA H100 per round |

### Four rounds

Each round started from the base model, added coverage informed by the previous round's results, and was evaluated on a **new**
sealed test written for that round.

| Round | What was added | Training examples | H100 minutes | Sealed live test |
|---|---|---|---|---|
| 1 | Core skills: Calculator, brightness, volume, dark mode, apps, folders, timer, screenshot, refusals | 4,712 | 11.2 | 61 / 95 |
| 2 | Number words ("one fifty"), reversed phrasings, hours, meaning-based wording, about 660 near-miss refusals | 6,280 | 10.7 | 67 / 95 |
| 3 | **Calendar events** (1,200 `EVENT` examples), rebalanced refusals, "1 hr 15 min" and "two dozen" forms | 7,568 | 23.8 | 80 / 107 |
| 4 | Calendar: emails copied exactly, "3 nov 10 am" dates, casual phrasing, hours → minutes (1,800 `EVENT` examples) | 7,909 | 14.3 | **90 / 125** |

Each row uses a different test, so the scores in this table aren't directly comparable. Like for like, on the round-4 test:

| Adapter | Total | Calendar | Calculator | Timer |
|---|---|---|---|---|
| Round 3 | 85 / 125 | 14 / 30 | 22 / 30 | 6 / 8 |
| Round 4 | 90 / 125 | 21 / 30 | 20 / 30 | 5 / 8 |

### Keeping the test honest

- **Independent tests.** A separate model (Grok) wrote each round's test requests.
- **Sealed before training.** Each test file was fingerprinted with sha256 before any training example was finalised. The hashes
  are recorded in `validation/`.
- **Lookalikes removed.** Any training example with word-set Jaccard similarity ≥ 0.5 to a test request was dropped (788, 920, 532
  and 791 examples in rounds 1 to 4).
- **Live, not simulated.** Every trial ran on a real MacBook Air. Independent checkers read macOS state: the Calculator display through
  the Accessibility API, display brightness, volume and mute, the appearance setting, the front app, Finder's window path, timers,
  screenshot files and a calendar read-back. The harness restored the Mac after each trial.

## Evaluation

![Round-4 sealed live test results by skill](assets/results.png)

| Skill (round-4 sealed test) | Completed |
|---|---|
| Refuse out-of-scope requests | 14 / 16 |
| Open a folder | 5 / 6 |
| Open an app | 8 / 10 |
| Brightness, volume, mute | 11 / 15 |
| Calendar events | 21 / 30 |
| Dark mode | 4 / 6 |
| Calculator: clean completion, where a hand-written regex baseline gets 5 / 30 | 20 / 30 |
| Timer | 5 / 8 |
| Screenshot | 2 / 4 |
| **All requests** | **90 / 125 (72%)** |

**Pass bars.** Neither pre-registered pass bar was met in round 4:

- **The frozen bar:** every skill had to clear it (Calculator ≥ 90%, refusals ≥ 80%, every other skill ≥ 85%). Only refusals did.
- **The owner's 75% bar:** apps, folders and refusals cleared it.

The score file records both results (`all_pass: false`, `all_pass_owner_75: false`).

**Calendar checks.** In the app, plain code cross-checks each `EVENT` against the user's sentence before asking for confirmation:

- emails are copied exactly
- an explicit am/pm time wins
- the day comes from the sentence
- only people who were named are invited

Re-scored on the same logged outputs, calendar requests complete 27 / 30, with no correct answer changed. These checks were
written after the round-4 run, so 27 / 30 is a post-hoc figure. The headline result is the model alone: 21 / 30.

Per-round scores, training records and parity runs are in `validation/`. The retired test sets are in `data/frozen/`, with
emails replaced by `example.com`.

## On-device speed

![Per-decision latency: PyTorch MPS 3.4 s, MLX 0.26 s](assets/speed.png)

| | PyTorch (MPS), round-1 adapter | **MLX (shipped), round-4 adapter** |
|---|---|---|
| Time per decision, median (about 305 prompt tokens) | 3.4 s | **0.26 s** |
| Time per decision, 90th percentile | — | 0.72 s |
| Calendar decisions, median | — | 0.38 s (up to about 1.4 s) |
| Prefill | about 196 tok/s | **about 1,860 tok/s** |
| Decode | about 1–2 tok/s | **about 47 tok/s** |

**How these were measured:** on a MacBook Air at FP32, as model time only.

- The round-4 figures come from replaying all 262 decisions of the round-4 live run through the release runtime; all 262 came out
  identical. In the live run itself, with apps launching alongside, the logged mean was 0.81 s per decision.
- The PyTorch figures and the MLX-vs-PyTorch parity check (**203 / 203** identical decisions) were measured with the round-1
  adapter.
- The records are in `validation/mlx-speed-r4.json` and `validation/mlx-parity-r2.json`.

The speed-up comes from a KV cache and Apple's MLX runtime, with the LoRA applied in memory from compact A/B matrices.

## Quickstart

**Requirements:** an Apple-silicon Mac, macOS 14 or later, Python 3.10 to 3.13 and the Xcode command-line tools.

```bash
pip3 install -U huggingface_hub
hf download Hobbylm/hobbylm-1B-computer-use --local-dir hobby-mac && cd hobby-mac
chmod +x scripts/setup.sh && ./scripts/setup.sh
.venv/bin/python hobby/hobby_demo.py r4
```

`setup.sh` creates a virtual environment with pinned packages and downloads HobbyLM-1B Instruct at the pinned revision. It also
fetches the MLX runtime, builds `mcp-server-macos-use` at a pinned commit, and compiles the small Swift helpers that read
brightness and the Calculator display. After setup, Hobby runs without a network connection.

**Try these:**

```text
split 600 among 4 people
make my screen bright
I need to write something down
grab a screenshot
turn on dark mode
what's the weather tomorrow
```

**Permissions.** macOS asks you to grant these yourself; Hobby never grants anything.

- **Accessibility**, for the app that runs Hobby (System Settings → Privacy & Security → Accessibility). Hobby checks this at
  startup.
- **Calendar and Contacts**, for calendar events only. Turn the skill on with `HOBBY_ENABLE_CALENDAR=1`, and choose a calendar with
  `HOBBY_CALENDAR="<calendar name>"`.

**Re-run the evaluation:**

```bash
.venv/bin/python hobby/hobbymac_run.py --model trained --round r4 --adapter r4 --runtime mlx
.venv/bin/python hobby/hobbymac_score.py <run folder>
.venv/bin/python hobby/test_harness.py        # 10-action parser and allow-list, no model needed
.venv/bin/python hobby/test_offline.py        # System Settings agent parser, no model needed
```

## Safety design

- **Allow-list execution.** Only the ten actions above can run, and invalid actions are rejected. The harness spells `x`, `×`, `÷`
  and `−` as Calculator keys.
- **Calendar cross-checks.** Calendar fields are checked against your sentence, and any change is shown before you confirm.
- **Confirmation before calendar changes.** Every event is shown in full (title, date, time, time zone, invitee) and needs an
  explicit `y`.
- **Real invites.** If the event has an email address, confirming it sends a real invitation from the calendar you chose.
- **Exact invitees.** Emails are copied from your sentence or resolved from your own Contacts. Hobby invites only people you named.
- **Local by default.** The model, the adapter and every action run on your Mac. Calendar invites are delivered by your own
  calendar account, if you choose one.
- **Independent verification.** In evaluation, results are read back from macOS rather than taken from the model's output.

## Scope

- **Actions:** the ten actions listed above, for the apps and folders named there.
- **Platform:** Apple Silicon running macOS 14 or later, with Accessibility granted.
- **Language:** English, including Indian-English phrasing.
- **Requests:** one task per request; the model completes it in up to six steps.
- **Calendar:** times resolve in the Mac's own time zone unless the request names one.
- **Measurement:** each skill was measured on a set of 4 to 30 sealed requests.
- **Use:** not intended for security, financial or medical decisions.

## Files

| Path | Contents |
|---|---|
| `adapter_model.safetensors`, `adapter_config.json` | PEFT LoRA for `harims95/hobbylm-1B-instruct@8a90f6eb6a3d7c7eb952fd01b512a406821366ab` (base weights sha256 `d0899e0a…`) |
| `mlx/hobby-lora-r4-ab.npz` | The same adapter as compact A/B matrices for the MLX runtime |
| `hobby/` | Hobby app, MLX and PyTorch runtimes, harness, checkers (Swift), calendar tool, evaluation and training code |
| `data/` | Runtime adapter, retired sealed test sets, regex baselines, test fixtures |
| `validation/` | Training records for rounds 1 to 4, live scores and runtime parity |
| `docs/` | Training report, engineering and efficiency write-up, Calculator report, demo script |
| `assets/` | Figures used in this card |
| `scripts/setup.sh` | Reproducible setup with pinned versions |
| `SHA256SUMS.txt` | Checksums for every file |

## Licence and credits

- **Licence:** Apache-2.0 for this adapter and its code. The base model keeps its own licence.
- **Credits:** Built by Hariharan and Prabhurajhan at Fuel Labs. Architecture based on HobbyLM by Harish.
- **Calculator UI actions:** these use
  [`mediar-ai/mcp-server-macos-use`](https://github.com/mediar-ai/mcp-server-macos-use), which `setup.sh` downloads; it is not
  bundled here.
  - **Its licence:** Business Source License 1.1, with the Additional Use Grant "Production use is permitted for non-commercial,
    educational purposes only". It converts to MIT on 2028-04-09.
  - **Commercial use** needs a licence from Mediar.
- **Related work:** UC Berkeley's TinyAgent, on small on-device function calling for the Mac.
