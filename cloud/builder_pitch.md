# Cloud builder: Devpost write-up and 3-minute demo script (Muselet)

Repo `ardahk/muselet`. Read `AGENTS.md`, `skills/catalog.json`, `prompts/planner_system.md`, `cloud/builder_*.md`
and `evals/fixtures/*/README.md` + `evals/fixtures/advisor/DEMO.md` to understand what exists. Muselet is a fully
on-device macOS voice computer-use agent for Apple Silicon: hold Right Option and talk; a mascot answers in a speech
bubble; a ghost cursor shows where it acts; a ~55 ms on-device router (Qwen3.5-4B, Tinker-trained LoRA) handles
instant commands and dispatches whole finance workflows to deterministic code; a planner handles everything else
through the macOS accessibility tree; nothing leaves the Mac. Submission: Cal Hacks, deadline Sun Oct 25 2026,
09:00 PDT; needs a Devpost page, a 3-minute pitch and a demo video.

Work on branch `cloud/pitch` (from `main`), one PR. Only add files under `pitch/`. No API keys needed.

## Hard rule: no invented numbers or claims
Every metric is a placeholder `{{name}}` listed in `pitch/claims.md` with how it will be measured (which script,
which eval file, which machine). Qualitative claims ("fully offline", "no screenshots unless needed") must cite the
code path or doc that makes them true. Competitor facts must cite a URL: HobbyLM-1B Computer Use (Hugging Face
`Hobbylm/hobbylm-1B-computer-use`: 72% = 90/125 live tasks, 0.26 s median decision), DeskMind
(github.com/deskmind-ai, DeskMind Bench 13 tasks), Savvy Wealth "Savvy Intelligence" (savvywealth.com/savvy-intelligence),
Clicky (github.com/farzaa/clicky). Verify each from the source before using it.

## Deliverables in `pitch/`
- `devpost.md`: Devpost sections (Inspiration, What it does, How we built it, Challenges, Accomplishments, What we
  learned, What's next, Built with). Concrete and technical; lead with speed + privacy + "it actually does the work".
- `demo_script.md`: a timed 3:00 script, second by second: spoken lines, what is on screen, what the agent does, and
  a fallback line if a step fails live. Segments: instant commands with a visible latency readout (~20 s); a browser
  task (~30 s); Wi-Fi off, then advisor-mode meeting prep (Savvy-style) and a quick receipt reconciliation (~60 s);
  Premiere cut / marker / export (~30 s); results and benchmark comparison + privacy close (~30 s).
- `track_fit.md`: which Cal Hacks prizes to enter and why, each with the 2-3 sentences that map Muselet to that
  track's stated criteria: Cal Hacks overall / Most Technically Advanced / Most Creative, [Hyphenate] Autonomous
  Systems for Finance (acts when confident, escalates when not, every action carries evidence, works on existing
  systems), [Microsoft] Built for the Real World, [Creao AI] Best AI-First Disruptor, [MLH] Commit Fellowship. Flag any
  track whose eligibility needs a sponsor API we don't use.
- `architecture.md`: a Mermaid diagram (voice -> STT on ANE -> router -> {native skill | brain tool | planner} ->
  HandsKit AX/keys/pixels -> verification) plus a latency budget table with `{{placeholders}}`.
- `claims.md`: the placeholder registry described above.
- `video_shotlist.md`: shots, screen regions to record, captions, and what must be visible (mascot, ghost cursor,
  latency readout, Wi-Fi icon off).
Keep it tight: judges skim. Reply with the PR link.
