"""Shared helpers for the data-route builder: LLM calls with a spend ledger, it2b loading, catalog-v3 options.

Run everything with the cloud/data-pipeline checkout's env (muselet_train + evals/route_v2 live there):
  MUSELET_DP=~/repos/dp MUSELET_CATALOG=$MUSELET_DP/training/artifacts/catalog_v3.json \
    uv run --project $MUSELET_DP/training python training/data_route/<stage>.py
"""

from __future__ import annotations

import concurrent.futures as cf
import gzip
import json
import os
import random
import re
import threading
import time
from pathlib import Path

DATA = Path(os.environ.get("DATA_ROUTE_DIR", Path.home() / "data" / "route"))
IT2B = Path(os.environ.get("IT2B_DIR", Path.home() / "data" / "it2b"))
LEDGER = DATA / "spend.jsonl"

JUDGE_OPENAI = "gpt-5.6-sol"
JUDGE_ANTHROPIC = "claude-opus-5-5"
ADJUDICATOR = "gpt-5.5"
# USD per 1M tokens (input, output), from the official pricing pages on 2026-10-24. gpt-5.5 is not listed on the
# current page; priced conservatively above gpt-5.6-sol.
PRICES = {"gpt-5.6-sol": (4.0, 20.0), "claude-opus-5-5": (4.0, 20.0), "gpt-5.5": (5.0, 30.0),
          "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "gpt-5.4-mini": (0.75, 4.5)}
_lock = threading.Lock()
BUDGET_STOP = 76.0  # hard cap is $80 (OpenAI + Anthropic)


def provider(model: str) -> str:
    return "anthropic" if model.startswith("claude") else "openai"


def spend() -> dict:
    tot: dict = {}
    if LEDGER.exists():
        for x in map(json.loads, LEDGER.read_text().splitlines()):
            t = tot.setdefault(x["model"], {"calls": 0, "input": 0, "output": 0, "usd": 0.0})
            t["calls"] += 1
            t["input"] += x["input"]
            t["output"] += x["output"]
            pi, po = PRICES[x["model"]]
            t["usd"] += (x["input"] * pi + x["output"] * po) / 1e6
    return tot


def total_usd() -> float:
    return sum(t["usd"] for t in spend().values())


def call(model: str, prompt: str, stage: str, max_tokens: int = 16000, effort: str = "medium",
         tries: int = 6) -> str | None:
    import anthropic
    import openai

    if total_usd() > BUDGET_STOP:
        raise RuntimeError(f"API spend above ${BUDGET_STOP}: stopping")
    for k in range(tries):
        try:
            if provider(model) == "anthropic":
                m = anthropic.Anthropic(max_retries=0, timeout=600).messages.create(
                    model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
                text, ui, uo = "".join(c.text for c in m.content if c.type == "text"), m.usage.input_tokens, m.usage.output_tokens
            else:
                o = openai.OpenAI(max_retries=0, timeout=600).chat.completions.create(
                    model=model, max_completion_tokens=max_tokens, reasoning_effort=effort,
                    response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
                text, ui, uo = o.choices[0].message.content, o.usage.prompt_tokens, o.usage.completion_tokens
            with _lock, LEDGER.open("a") as f:
                f.write(json.dumps({"t": time.time(), "model": model, "stage": stage, "input": ui, "output": uo}) + "\n")
            return text
        except (anthropic.RateLimitError, openai.RateLimitError, anthropic.InternalServerError,
                anthropic.APIConnectionError, openai.APIConnectionError, openai.InternalServerError,
                anthropic.APITimeoutError, openai.APITimeoutError):
            time.sleep(min(60, 2 ** k + random.random()))
    return None


def parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def pmap(fn, xs, conc: int = 12):
    with cf.ThreadPoolExecutor(conc) as ex:
        return list(ex.map(fn, xs))


def load_it2b() -> tuple[list[dict], list[dict]]:
    route = [json.loads(x) for x in gzip.open(IT2B / "route.jsonl.gz", "rt")]
    args = [json.loads(x) for x in gzip.open(IT2B / "args.jsonl.gz", "rt")]
    return route, args


def ctx_line(c: dict) -> str:
    from muselet_train.route_render import RouteContext
    return RouteContext(**c).line().removeprefix("Context: ")


def option_block() -> str:
    from muselet_train.catalog import arg_signature, options
    from muselet_train.it3gen import _desc
    return "\n".join(f"- {o.name}: {_desc(o)}" + (f" [{arg_signature(o)}]" if o.args else "") for o in options())


def jdump(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def jload(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
