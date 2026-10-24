## Handoff

- **State:**
  - The comms-2 Python side is done and merged as PR #37 (`ardahk/muselet#37`, branch `cloud/comms-2`, last branch commit `c65ee70`).
  - The lead followed up on main with two commits:
    - `3876f3a`: Swift HandsKit adds `messages_people`, `contacts_search fuzzy`, and `messages_compose name`.
    - `ff1a4b6`: parser fixes for saying-first phrasings, "quick" adjectives, "tell X to Y" and assistant names; bench fakes now answer the comms RPCs.
  - In flight: nothing.
  - Not started: nothing assigned to this lane.
- **Verified on main `ff1a4b6` (Linux, fakes):**
  - `ml/tests`: 1418 passed, 55 skipped.
  - `bench/tests`: 165 passed, 2 skipped, 38 subtests passed.
  - The 2 `confirm-no-send` bench failures noted in PR #37 were fixed by the lead in `ff1a4b6`.
- **Resume steps (about 5 min):**
  1. Clone and set up:
     ```bash
     gh repo clone ardahk/muselet && cd muselet
     uv sync --project ml
     uv pip install --python ml/.venv/bin/python mlx-cpu==0.32.4   # Linux only, no Metal
     ```
  2. Verify:
     ```bash
     uv run --no-sync --project ml python -m pytest ml/tests -q
     uv run --no-sync --project ml python -m pytest bench/tests -q
     ```
- **Next steps:** none assigned. Live verification of the evidence table on the Mac (W5, `cloud/handoff/W5_comms.md`) is the lead's team's job.
- **Artifacts:**
  - branch `cloud/comms-2` (merged), commit `c65ee70`; main at `ff1a4b6`;
  - spec: `cloud/builder_comms2.md`;
  - code: `ml/src/brain/comms.py` (`parse_message`, `is_messaging`, `start`, `send_message`, `resolve_answer`) and `ml/src/brain/orchestrator.py` (`message_redirect`, `channel_fix`, planner Mail block);
  - tests: `ml/tests/test_comms.py`, `ml/tests/test_comms_parser.py`.
  - No HF repos, Tinker runs or run dirs: this lane is code only.
- **Spend:** no Tinker, HF or OpenAI/Anthropic API spend. The only cost is Devin session time.
- **Open questions for the lead:**
  - In the pending-body state, a reply is treated as a new command when the router gives p >= 0.8 for another skill. Short bodies that look like commands ("open the door") could be misread as commands.
  - `fuzzy:true` contacts scoring happens on the Swift side. Python only uses the order of the returned matches; it does not re-check `score`.
- **Gotchas:**
  - Linux has no Metal. Install `mlx-cpu==0.32.4` into the ml env, then run `uv run --no-sync --project ml python -m pytest ml/tests -q` and `uv run --no-sync --project ml python -m pytest bench/tests -q`. A plain `uv run` re-syncs the environment and removes `mlx-cpu` (`libmlx.so` ImportError).
  - Messaging utterances (text/message/imessage/sms, and no email/mail/gmail) never reach the planner or email skills, so planner-confirm tests must use a non-messaging request.
  - `prompts/` and `evals/` are off-limits for this lane.
