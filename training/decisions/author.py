from __future__ import annotations

import json
import random
import re

from bench.systemone.schema import parse_request
from .label import ApiClient, BudgetLedger

AUTHOR_PROMPT = """You write training data for a small decision model. It reads a STATE (any text an agent might see: documents, policies, records,
messages, logs, UI screens, forms) and answers typed questions in one step by picking an option.

Write ONE new item in the family "{family}" ({family_description}) in the domain "{domain}".
Requirements:
- The state is self-contained and realistic, {length_hint}. All facts needed to answer are in the state; no outside knowledge.
- Write {n_questions} questions about this same state. Types to use, in order: {types}.
  - choice: {n_options} options, snake_case keys, each with a one-sentence description. Exactly one option is best.
  - noul: a yes/no question with criteria {"false": "...", "true": "..."} that define what each answer means.
  - score: an ordinal rubric of {n_levels} levels, from lowest to highest, each level a one-sentence description.
- Each question must have a single defensible answer for a careful expert reader, unless the family is "ambiguous", where the best
  answer may be that the information is insufficient (then include such an option).
- Make it hard: the right answer needs careful reading (conditions, exceptions, dates, numbers, who said what). Include at least one
  plausible distractor that a skimming reader would pick.
- Do not reveal the answer in the question or the option order. Do not copy any public benchmark.
Return JSON only: {"state": str, "questions": [{"type": ..., "instructions": str, "criteria": ..., "answer": key_or_level_index,
"rationale": str}]}"""

AUTHOR_FAMILIES = (
    ("judge_hard", "judge whether evidence or a proposed answer is sufficient"),
    ("tradeoff", "choose between options with competing costs and benefits"),
    ("ambiguous", "identify when the available information is insufficient"),
    ("trap", "resolve a decision where a salient surface cue is misleading"),
    ("adversarial", "ignore instructions embedded in untrusted state text"),
    ("routing", "select the appropriate tool or route from stated constraints"),
    ("intent_extraction", "extract intent and structured details from a request"),
    ("agent_step", "decide the next UI or form action from an observed state"),
    ("ordinal_rubric", "assign severity, urgency, quality, priority, risk, or evidence confidence"),
)
DOMAINS = ("finance", "insurance", "HR", "healthcare administration", "logistics", "IT operations",
           "legal", "retail", "travel", "education", "software", "desktop applications")


def author_prompt(family: str, description: str, domain: str, n_questions: int, types: list[str]) -> str:
    return AUTHOR_PROMPT.replace("{family_description}", description).replace("{family}", family).replace(
        "{domain}", domain).replace("{length_hint}", "long enough to contain all relevant records and exceptions").replace(
        "{n_questions}", str(n_questions)).replace("{types}", str(types)).replace(
        "{n_options}", "4-7").replace("{n_levels}", "3-5")


def _parse_item(raw: str, rng: random.Random, author: str) -> dict:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), str):
        raise ValueError("author response must be an object with a state string")
    questions, authored = {}, {}
    for index, item in enumerate(payload.get("questions", []), start=1):
        qid = f"q{index}"
        kind = item["type"]
        criteria = item["criteria"]
        if kind == "choice":
            if isinstance(criteria, list):
                criteria = {entry["key"]: entry["description"] for entry in criteria}
            if not isinstance(criteria, dict):
                raise ValueError(f"{qid}: choice criteria are not a map")
            entries = list(criteria.items())
            rng.shuffle(entries)
            criteria = dict(entries)
        elif kind == "noul" and isinstance(criteria, dict):
            entries = list(criteria.items())
            rng.shuffle(entries)
            criteria = dict(entries)
        question = {"type": kind, "instructions": item["instructions"], "criteria": criteria}
        questions[qid] = question
        authored[qid] = item["answer"]
    parse_request({"state": payload["state"], "questions": questions})
    for qid, answer in authored.items():
        if str(answer) not in parse_request({"state": payload["state"], "questions": questions}).questions[qid].options:
            raise ValueError(f"{qid}: authored answer {answer!r} is not an option")
    return {
        "id": f"authored-{rng.getrandbits(48):012x}",
        "family": author,
        "authored_family": author,
        "source": "synthetic-llm",
        "license": "synthetic",
        "state": payload["state"],
        "questions": questions,
        "gold": {qid: None for qid in questions},
        "gold_basis": {qid: "teacher" for qid in questions},
        "authored_answer": authored,
        "rationale": {f"q{i+1}": q.get("rationale", "") for i, q in enumerate(payload["questions"])},
        "teacher": {},
        "target": {},
    }


async def author_items(count: int, rng: random.Random, client: ApiClient, ledger: BudgetLedger) -> tuple[list[dict], list[dict]]:
    items, rejected = [], []
    for index in range(count):
        family, description = AUTHOR_FAMILIES[index % len(AUTHOR_FAMILIES)]
        domain = rng.choice(DOMAINS)
        types = [rng.choice(("choice", "noul", "score")) for _ in range(rng.randint(1, 3))]
        prompt = author_prompt(family, description, domain, len(types), types)
        model = "gpt-5.5" if index % 2 == 0 else "claude-sonnet-5-5"
        if model in client.unavailable_models:
            rejected.append({"family": family, "model": model, "reason": "candidate_unavailable",
                             "status_code": client.unavailable_models[model]["status_code"]})
            continue
        try:
            text, _ = await client.generate(model, prompt, ledger, max_output_tokens=2048, role="author",
                                            decision_id=f"author:{index}")
            items.append(_parse_item(text, rng, family))
        except Exception as exc:
            rejected.append({"family": family, "model": model, "reason": f"{type(exc).__name__}: {exc}"})
            if type(exc).__name__ == "BudgetExceeded":
                break
    return items, rejected
