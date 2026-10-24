# Lane: docs-demo — report, pitch, demo script, submission text (start now, fill numbers as they land)

Brief of record: `cloud/handoff/W10_report_pitch_demo.md`. Branch `cloud/docs-demo` from `main`; open the PR early
and keep pushing. Docs only.

## Do now
- **Demo script** (3 minutes, voice through the real app), covering the definition of done in
  `docs/MASTER_PROMPT.md` §11: instant system commands, a multi-step task, messaging with confirm, a Gmail draft,
  finance review, advisor prep, a safety moment, a memory follow-up ("navigate to wikipedia" → "search for
  history"), Clock timer in front. Exact utterances, what the audience sees, setup and reset steps, and a fallback
  line for each beat.
- **Pitch** (`pitch/`): story, architecture slide text, why on-device, comparison slide vs DeskMind and HobbyLM.
- **Submission text** (Devpost style): what it does, how we built it, challenges, accomplishments, what's next.
- **`docs/REPORT.md` + `pitch/claims.md`:** restructure so every number has a source (run dir / file / HF revision),
  denominators, skipped counts and reasons. Numbers that aren't measured yet are written `TBD(<which run>)`; never
  invent, round up or carry over invalid runs (locked screen, harness bugs, contaminated routers). New today:
  planner retrieval k=1 (`cloud/handoff/notes/retrieval_eval.md`), router it3 export (HF
  `jonsnov/muselet-route-4b-it3-mlx4` @ `e057412`, contamination 0), Tinker total ≈ $136 of $150.
- The lead will message you numbers as they land (router it3, decisions, planner LoRA/think, memory eval, live
  suite, HobbyLM r4); fold each in with its source.

No Tinker, no API spend.
