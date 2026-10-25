# Lane: cool-tasks — longer cross-app demo tasks (fast; merged without review)
Read `cloud/builder_common.md`, `AGENTS.md`. Branch `cloud/cool-tasks` off latest main, one PR within 60 min, Python +
prompts. The planner (Qwen3.6-35B-A3B, think 512, AX observation up to 350 nodes) operates apps agentically.
The user wants 2-3 impressive, non-repetitive LONGER demo tasks beyond: rapid-fire System-1 skills, YouTube jazz, Maps
directions, Amazon/Target cart, iMessage "hello" to Caleb, Premiere. Candidates (pick the 3 best, make them work):
- "Look up the weather in Tokyo and text it to Caleb" (web -> read -> Messages draft + confirm, never send).
- "Summarize this article into a new note" (current browser page -> Notes).
- "Find a highly rated sushi place nearby in Maps and text the address to Caleb".
- "Make a packing list for a 3-day trip to Tokyo in Notes".
What to build so these work: (1) the planner must be able to carry text it read on one screen into a later `type`
(check the planner prompt/history keeps the relevant page text or add a `note "<text>"` DSL op that stores a
working-memory scratch line rendered in later turns' prompts; keep it tiny); (2) multi-app finish criteria in
`finish.criterion` for "<lookup> and text it to <person>" = Messages draft contains the looked-up value + confirm asked;
(3) router/compound: these utterances must reach the planner as one task (not split into a skill + a fragment) — add
tests with the exact sentences; (4) app hints for Weather/Maps place search if missing. Add the chosen tasks to
`pitch/demo_script.md` marked `[needs live check]`. Unit tests with fakes.
