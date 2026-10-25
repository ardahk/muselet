"""Generation / adjudication prompts (SPEC 1.3, 1.4). Text is exact; only braces are filled."""

G1 = """You write realistic things people SAY OUT LOUD to a voice assistant on their Mac.

Target skill: {name} — {description}
Arguments: {arg_signature}
Example requests: {examples}

Write {n} different spoken requests that this skill should fully handle. Return JSON: {{"items": [{{"text": "...", "args": {{...}}}}]}}

Rules:
- Spoken, not typed: casual, sometimes polite, sometimes terse; contractions are fine.
- Vary phrasing heavily: commands, questions ("can you...", "could you..."), indirect needs (e.g. "I can't hear anything" for raising volume), different word orders.
- Vary argument values widely and realistically. Only use apps that commonly exist on a Mac: {app_list}.
- Each request is a single intent that this exact skill fully handles. No requests that need another skill or several steps.
- 2 to 20 words each.
- "args" holds argument values as the user expressed them. For datetime/duration copy the spoken words exactly (e.g. "tomorrow at noon", "ninety seconds"). Enum args use one of: {enum_values}. Omit optional arguments the user did not say. Omit required arguments only if the user did not say them.
- Style for this batch: {style}"""

G2 = """You write realistic things people SAY OUT LOUD to a voice assistant on their Mac.

The assistant has these single-step skills:
{skill_list_with_descriptions}

Write {n} spoken requests that belong to this category: {category_name}
Definition: {category_definition}
Examples: {category_examples}

Return JSON: {{"items": [{{"text": "...", "nearest_skill": "<skill name or none>", "why": "<5-10 words>"}}]}}
Rules: spoken style, 2 to 30 words, varied phrasing and topics. {near_miss} Style for this batch: {style}"""

G2_NEAR_MISS = "Make about half of them near-misses that look similar to a single skill but still belong to {category_name}."
# lead decision (step-3 gate): ASK only
G2_NEAR_MISS_ASK = "Make about half of them near-misses: they name one skill's action but leave out a detail that skill needs (who, what, when, which file or app), so the assistant has to ask before acting."

G3 = """Write {n} short spoken requests whose correct handling depends on which app is frontmost or what is selected. For each, give two contexts that lead to two different handlings.
Skills: {skill_list_with_descriptions}
Special options: MULTI_STEP, ASK, REFUSE, ANSWER.
Return JSON: {{"items": [{{"text": "...", "a": {{"app": "...", "selection": "yes|no", "label": "..."}}, "b": {{"app": "...", "selection": "yes|no", "label": "..."}}}}]}}
Examples: "cut this" (Premiere Pro, selection no -> premiere_command; TextEdit, selection yes -> MULTI_STEP); "play" (Music -> media_control; Premiere Pro -> premiere_command)."""

A1 = """You check training labels for a macOS voice assistant's intent router.
Options (name: description):
{all_options_with_descriptions}

Context: {context_line}
Request: "{utterance}"
Proposed label: {intended_label}
A second model preferred: {teacher_argmax} (probability {p}).

Which single option is correct? If the request is genuinely ambiguous between options, answer ASK unless one option is clearly better. Return JSON: {{"verdict": "keep" | "relabel" | "drop", "label": "<option name>", "reason": "<one sentence>"}}"""

STYLES = [
    "terse imperative",
    "polite full sentence",
    "rambling with filler words and a false start",
    "question form",
    "indirect need with no explicit command",
    "slang or abbreviations",
    "very short (2-4 words)",
    "numbers spelled out in words",
]

CATEGORIES = {
    "MULTI_STEP": {
        "definition": "needs several actions or apps, or UI interaction that no single skill covers.",
        "examples": '"open safari, search flights to tokyo and sort by price"; "in premiere add a cross dissolve between the first two clips"; "rename the screenshots on my desktop by date"; "reply to sam\'s last email saying thanks"; "categorize my october transactions in the budget spreadsheet"; "add up the receipts in my downloads into the expense sheet"; "make a chart of monthly spending in numbers"; "flag duplicate charges in my bank statement"; "fill in the total column with a sum formula"',
        "target": 6000,
    },
    "ASK": {
        "definition": "maps to a skill but a required argument is missing or the referent is unclear and cannot be inferred from context.",
        "examples": '"set a timer"; "text him"; "open that file"; "move it to the folder"',
        "target": 4000,
    },
    "REFUSE": {
        "definition": "harmful, deceptive, privacy-violating, or impossible for a local Mac assistant.",
        "examples": '"read my partner\'s messages without them knowing"; "wipe this mac without asking me"; "make my laptop fly"; "move money out of my mom\'s bank account"',
        "target": 2000,
    },
    "ANSWER": {
        "definition": "a question that needs a spoken answer, not an action: math, unit conversion, how-to questions about macOS, Premiere Pro or spreadsheets, definitions.",
        "examples": '"what\'s 15 percent of 80"; "how do I add a transition in premiere"; "what does command shift 4 do"; "what\'s the formula for compound interest"',
        "target": 4000,
    },
}

# MULTI_STEP domain quotas (SPEC: >=30% spreadsheet/finance, 15% Premiere, 20% browser);
# appended to the {style} slot so the prompt text itself stays exact.
MULTI_STEP_FOCUS = [
    ("spreadsheet/finance tasks in Google Sheets, Numbers or Excel", 0.30),
    ("Premiere Pro editing tasks", 0.15),
    ("browser tasks in Safari or Google Chrome", 0.20),
    ("other macOS tasks across apps and files", 0.35),
]

MAC_APPS = [
    "Finder", "Safari", "Google Chrome", "Notes", "Mail", "Messages", "Calendar", "Music",
    "Premiere Pro", "TextEdit", "System Settings", "Terminal", "Slack", "Spotify", "Zoom",
    "Photos", "Preview", "Numbers", "Pages", "Keynote", "Microsoft Excel", "Microsoft Word",
    "Visual Studio Code", "Xcode", "Notion", "Discord", "FaceTime", "Reminders", "Maps",
    "App Store", "Activity Monitor", "QuickTime Player", "Podcasts", "Firefox",
]
