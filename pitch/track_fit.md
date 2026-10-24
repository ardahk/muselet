# Track fit (Cal Hacks 13.0)

Source for prize names and judging criteria: https://cal-hacks-13-0.devpost.com/ (fetched 2026-10-24).
General criteria: Application, Intentionality, Functionality, Creativity, Technical Complexity. Requirements:
team of 2-4, GitHub repo, 3-minute pitch + 2 minutes Q&A, recorded or live demo, submit by Oct 25 09:00 PDT.

| Prize | Enter | Sponsor API needed? |
|---|---|---|
| Cal Hacks First/Second/Third Overall | yes | no |
| Cal Hacks Most Technically Advanced Hack | yes | no |
| Cal Hacks Most Creative Project | yes | no |
| [Hyphenate] The Hyphenated Enterprise: Autonomous Systems for Finance | yes (primary) | none listed |
| [Microsoft] Built for the Real World | yes | none listed; criteria text not on Devpost, confirm at the booth |
| [Creao AI] Best AI-First Disruptor | yes | none listed; criteria text not on Devpost, confirm at the booth |
| [MLH] Commit Fellowship Prize Category | yes | no; needs a team, opt-in on submission **and** a supplemental form |

## Pitch lines per track

**Overall.** Muselet does the work, not the explaining: hold a key, speak, and a fully on-device agent operates
your real Mac apps in `{{instant_e2e_ms_p50}}` ms for instant commands and finishes multi-app finance workflows
with Wi-Fi off. Live demo, strict final-state graders, and head-to-head reruns of HobbyLM and DeskMind on our Mac.

**Most Technically Advanced.** A Tinker-trained Qwen3.5-4B LoRA routes in one MLX forward pass over a cached
static prefix (`{{route_ms_p50}}` ms), a streaming planner acts on the accessibility tree while it is still
decoding, and actions carry `expect` predicates checked against live UI state. STT runs on the Neural
Engine; training/runtime prompt rendering is token-identical.

**Most Creative.** A mascot with a speech bubble and a ghost cursor that flies to each target before it clicks:
you see where the agent acts and why. The twist on computer use: do as little "AI" as possible; one forward pass,
then deterministic code.

**[Hyphenate] Autonomous Systems for Finance.** *Acts when confident*: the router dispatches `advisor_prep` /
`finance_review` in one pass and deterministic `Decimal` engines do every calculation. *Escalates when not*: router
ambiguous requests get a question,
router `p < 0.55` goes to the planner instead of acting, categorization below 0.6 becomes "ask", and sending,
deleting and shell scripts wait for a yes. *Evidence*: every
flag carries its rows/lots and the rule that fired (wash sale: the IRA buy 12 days earlier, IRS Pub. 550).
*Existing systems*: Calendar, Finder, Numbers, Notes, a bank CSV and receipt photos; no migration, no cloud.

**[Microsoft] Built for the Real World.** Built for people who cannot send data to a cloud model: an advisor with
client portfolios, anyone with bank statements. Runs on a laptop with no network, on the apps they already use,
its steps carry checks against the live UI, and we grade it on final state, not on what it says.

**[Creao AI] Best AI-First Disruptor.** Savvy Intelligence sells advisor meeting prep as a platform you join; we
do the same prep on the advisor's own Mac, in their own files, with no model provider in the loop. AI-first means
the interface is your voice and the product is the finished artifact (the Notes brief, the highlighted sheet).

**[MLH] Commit Fellowship.** Real problem: regulated professionals (advisors, accountants) want agents but cannot
ship client data off-device. Working prototype today; next step is customer discovery with independent RIAs.

## Flags
- None of the listed tracks name a required sponsor API on Devpost. Microsoft and Creao publish only titles and
  rewards there: confirm criteria and eligibility in person before claiming fit.
- Not entered: sponsor tracks that require their product (e.g. Fetch.ai, Gemini, Snowflake, Apify, Elastic,
  Convex, Cartesia). [CRS] Best Financial AI Agent looks relevant but likely requires the CRS API: check first.
