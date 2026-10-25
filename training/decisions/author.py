from __future__ import annotations

import asyncio
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

_choice = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "const": "choice"},
        "instructions": {"type": "string"},
        "criteria": {"type": "array", "minItems": 2, "maxItems": 26, "items": {
            "type": "object", "properties": {"key": {"type": "string"},
                                             "description": {"type": "string"}},
            "required": ["key", "description"], "additionalProperties": False,
        }},
        "answer": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["type", "instructions", "criteria", "answer", "rationale"],
    "additionalProperties": False,
}
_noul = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "const": "noul"},
        "instructions": {"type": "string"},
        "criteria": {"type": "object", "properties": {"false": {"type": "string"},
                                                       "true": {"type": "string"}},
                     "required": ["false", "true"], "additionalProperties": False},
        "answer": {"anyOf": [
            {"type": "string", "enum": ["false", "true"]},
            {"type": "boolean"},
        ]},
        "rationale": {"type": "string"},
    },
    "required": ["type", "instructions", "criteria", "answer", "rationale"],
    "additionalProperties": False,
}
_score = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "const": "score"},
        "instructions": {"type": "string"},
        "criteria": {"type": "array", "minItems": 3, "maxItems": 6, "items": {"type": "string"}},
        "answer": {"type": "integer", "minimum": 0, "maximum": 5},
        "rationale": {"type": "string"},
    },
    "required": ["type", "instructions", "criteria", "answer", "rationale"],
    "additionalProperties": False,
}
AUTHOR_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string"},
        "questions": {"type": "array", "minItems": 3, "maxItems": 6,
                      "items": {"anyOf": [_choice, _noul, _score]}},
    },
    "required": ["state", "questions"],
    "additionalProperties": False,
}


def author_prompt(family: str, description: str, domain: str, n_questions: int, types: list[str]) -> str:
    return AUTHOR_PROMPT.replace("{family_description}", description).replace("{family}", family).replace(
        "{domain}", domain).replace("{length_hint}", "long enough to contain all relevant records and exceptions").replace(
        "{n_questions}", str(n_questions)).replace("{types}", str(types)).replace(
        "{n_options}", "4-7").replace("{n_levels}", "3-5")


def _parse_item(raw: str, rng: random.Random, author: str) -> dict:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), str):
        raise ValueError("author response must be an object with a state string")
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not 3 <= len(raw_questions) <= 6:
        raise ValueError("author response must contain 3–6 questions")
    questions, authored = {}, {}
    for index, item in enumerate(raw_questions, start=1):
        qid = f"q{index}"
        kind = item["type"]
        criteria = item["criteria"]
        if kind == "choice":
            if isinstance(criteria, list):
                criteria = {entry["key"]: entry["description"] for entry in criteria}
            if not isinstance(criteria, dict):
                raise ValueError(f"{qid}: choice criteria are not a map")
            if not 2 <= len(criteria) <= 26:
                raise ValueError(f"{qid}: choice questions require 2–26 criteria")
            entries = list(criteria.items())
            rng.shuffle(entries)
            criteria = dict(entries)
        elif kind == "noul" and isinstance(criteria, dict):
            entries = list(criteria.items())
            rng.shuffle(entries)
            criteria = dict(entries)
        elif kind == "score" and not 3 <= len(criteria) <= 6:
            raise ValueError(f"{qid}: score questions require 3–6 levels")
        answer = item["answer"]
        if isinstance(answer, bool):
            answer = "true" if answer else "false"
        if kind == "score":
            answer = str(answer)
        question = {"type": kind, "instructions": item["instructions"], "criteria": criteria}
        questions[qid] = question
        authored[qid] = answer
    normalized = parse_request({"state": payload["state"], "questions": questions})
    for qid, answer in authored.items():
        if str(answer) not in normalized.questions[qid].options:
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


async def author_items(count: int, rng: random.Random, client: ApiClient, ledger: BudgetLedger,
                       *, full_mix: bool = False, start_index: int = 0) -> tuple[list[dict], list[dict]]:
    family_cycle = []
    for family, _ in AUTHOR_FAMILIES:
        family_cycle.extend([family] * (17 if family in ("agent_step", "ordinal_rubric") else 9))
    family_cycle.extend([family_cycle[-1]] * (100 - len(family_cycle)))
    plans = []
    for offset in range(count):
        index = start_index + offset
        item_rng = random.Random(rng.getrandbits(64))
        family = family_cycle[index % 100] if full_mix else AUTHOR_FAMILIES[index % len(AUTHOR_FAMILIES)][0]
        description = dict(AUTHOR_FAMILIES)[family]
        domain = item_rng.choice(DOMAINS)
        n_questions = item_rng.randint(3, 6) if full_mix else 5
        if full_mix:
            types = [("choice", "noul", "score")[i % 3] for i in range(n_questions)]
            item_rng.shuffle(types)
        else:
            types = [item_rng.choice(("choice", "noul", "score")) for _ in range(n_questions)]
        prompt = author_prompt(family, description, domain, n_questions, types)
        if full_mix:
            option_count = 26 if item_rng.random() < 0.05 else item_rng.randint(2, 12)
            prompt = prompt.replace("4-7", str(option_count))
        model = "claude-sonnet-5-5" if (index + 1) % 5 == 0 else "gpt-5.4-mini"
        plans.append({
            "index": index, "family": family, "prompt": prompt, "model": model,
            "parse_rng": random.Random(item_rng.getrandbits(64)),
        })

    async def create(plan: dict):
        family, model = plan["family"], plan["model"]
        if model in client.unavailable_models:
            return None, {"family": family, "model": model, "reason": "candidate_unavailable",
                          "status_code": client.unavailable_models[model]["status_code"]}
        try:
            text, _ = await client.generate(
                model, plan["prompt"], ledger, max_output_tokens=8000, role="author",
                decision_id=f"author:{plan['index']}",
                reasoning_effort="low" if model == "gpt-5.4-mini" else None,
                response_schema=AUTHOR_SCHEMA,
            )
            item = _parse_item(text, plan["parse_rng"], family)
            item["author_model"] = model
            return item, None
        except Exception as exc:
            return None, {"family": family, "model": model,
                          "reason": f"{type(exc).__name__}: {exc}"}

    results = await asyncio.gather(*(create(plan) for plan in plans), return_exceptions=True)
    items, rejected = [], []
    for plan, result in zip(plans, results):
        if isinstance(result, Exception):
            rejected.append({"family": plan["family"], "model": plan["model"],
                             "reason": f"{type(result).__name__}: {result}"})
        else:
            item, rejection = result
            if item is not None:
                items.append(item)
            if rejection is not None:
                rejected.append(rejection)
    return items, rejected
