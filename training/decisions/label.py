from __future__ import annotations

import asyncio
import json
import math
import os
import random
import threading
from pathlib import Path

import httpx

LABEL_SYSTEM = """You are a careful expert decision-maker. Read the state and answer the question by choosing exactly one option. Reply with only
the option id."""
LABEL_USER = """State:
{state}

Question:
{instructions}

Options:
{options}
Answer with the option id only."""

# Official rates per 1M text tokens; source URLs are the provider pricing pages.
# OpenAI: https://developers.openai.com/api/docs/pricing
# Anthropic: https://www.anthropic.com/claude-haiku-5-5 and https://www.anthropic.com/claude-sonnet-5-5
PRICES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-5.5": (5.00, 30.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


class BudgetExceeded(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, budget: float, path: Path, run: str = "default"):
        self.budget, self.path, self.run = budget, path, run
        self.spent = self.reserved = 0.0
        self.lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if row.get("run", "default") == run:
                        self.spent += float(row.get("cost_usd", 0.0))

    def reserve(self, model: str, prompt: str, output_cap: int) -> float:
        inp, out = PRICES[model]
        input_cap = len(prompt.encode("utf-8")) + 256
        estimated = (input_cap * inp + output_cap * out) / 1_000_000
        with self.lock:
            if self.spent + self.reserved + estimated > self.budget:
                raise BudgetExceeded(
                    f"budget reserve would exceed ${self.budget:.2f} (spent ${self.spent:.4f})"
                )
            self.reserved += estimated
        return estimated

    def settle(self, estimate: float, model: str, usage: dict, provider: str, role: str,
               decision_id: str | None = None):
        in_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        out_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        input_price, output_price = PRICES[model]
        cost = (in_tokens * input_price + out_tokens * output_price) / 1_000_000
        row = {"run": self.run, "provider": provider, "model": model, "input_tokens": in_tokens,
               "output_tokens": out_tokens, "input_usd_per_million": input_price,
               "output_usd_per_million": output_price, "cost_usd": cost, "role": role,
               "decision_id": decision_id}
        with self.lock:
            self.reserved -= estimate
            self.spent += cost
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
            if self.spent > self.budget:
                raise BudgetExceeded(f"actual usage exceeded hard budget: ${self.spent:.4f}")
        return row

    def cancel(self, estimate: float):
        with self.lock:
            self.reserved -= estimate


def option_rows(question: dict) -> list[tuple[str, str, str]]:
    kind, criteria = question["type"], question["criteria"]
    if kind == "choice":
        return [(chr(65+i), key, str(description)) for i, (key, description) in enumerate(criteria.items())]
    if kind == "score":
        return [(chr(65+i), str(i), str(description)) for i, description in enumerate(criteria)]
    return [("A", "false", str(criteria["false"])), ("B", "true", str(criteria["true"]))]


def render_question(state: str, question: dict) -> tuple[str, list[str]]:
    rows = option_rows(question)
    text = "\n".join(f"{oid}: {key} - {description}" for oid, key, description in rows)
    return LABEL_USER.format(state=state, instructions=question["instructions"], options=text), [r[0] for r in rows]


def id_distribution(logprobs: list[dict], ids: list[str]) -> dict[str, float] | None:
    mass = {option: 0.0 for option in ids}
    for token in logprobs:
        key = str(token.get("token", "")).strip()
        if key in mass:
            mass[key] += math.exp(float(token["logprob"]))
    total = sum(mass.values())
    if total < 0.5:
        return None
    return {key: value / total for key, value in mass.items()}


def answer_distribution(probabilities: dict[str, float] | None, ids: list[str],
                        rows: list[tuple[str, str, str]]) -> dict[str, float] | None:
    if probabilities is None:
        return None
    by_id = dict(zip(ids, rows))
    return {by_id[oid][1]: value for oid, value in probabilities.items()}


class ApiClient:
    def __init__(self, concurrency: int = 8):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.unavailable_models: dict[str, dict] = {}

    def mark_unavailable(self, model: str, status_code: int):
        self.unavailable_models[model] = {"status_code": status_code}

    async def _post(self, url: str, headers: dict, body: dict):
        async with self.semaphore:
            for attempt in range(5):
                try:
                    async with httpx.AsyncClient(timeout=120) as client:
                        response = await client.post(url, headers=headers, json=body)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code not in (408, 429) and exc.response.status_code < 500:
                        raise
                    if attempt == 4:
                        raise
                    await asyncio.sleep(min(2 ** attempt, 16) + random.random())
                except (httpx.TransportError, ValueError):
                    if attempt == 4:
                        raise
                    await asyncio.sleep(min(2 ** attempt, 16) + random.random())

    async def generate(self, model: str, prompt: str, ledger: BudgetLedger, max_output_tokens: int = 2048,
                       role: str = "author", decision_id: str | None = None,
                       temperature: float | None = None):
        estimate = ledger.reserve(model, prompt, max_output_tokens)
        try:
            if model.startswith("gpt-"):
                key = os.environ["OPENAI_API_KEY"]
                body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": max_output_tokens,
                        "response_format": {"type": "json_object"}}
                if model == "gpt-5.5":
                    body["reasoning_effort"] = "none"
                data = await self._post("https://api.openai.com/v1/chat/completions",
                                        {"Authorization": f"Bearer {key}"},
                                        body)
                usage = data.get("usage", {})
                result = data["choices"][0]["message"]["content"]
                ledger.settle(estimate, model, usage, "openai", role, decision_id)
                return result, usage
            key = os.environ["ANTHROPIC_API_KEY"]
            body = {"model": model, "max_tokens": max_output_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "thinking": {"type": "between_tools" if model == "claude-sonnet-5-5" else "disabled"}}
            if temperature is not None:
                body["temperature"] = temperature
            data = await self._post("https://api.anthropic.com/v1/messages",
                                    {"x-api-key": key, "anthropic-version": "2023-06-01"},
                                    body)
            usage = data.get("usage", {})
            result = "".join(part.get("text", "") for part in data.get("content", []))
            ledger.settle(estimate, model, usage, "anthropic", role, decision_id)
            return result, usage
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if 400 <= status < 500 and status not in (408, 429):
                self.mark_unavailable(model, status)
            ledger.cancel(estimate)
            raise
        except BudgetExceeded:
            raise
        except Exception:
            ledger.cancel(estimate)
            raise

    async def label(self, model: str, state: str, question: dict, ledger: BudgetLedger,
                    decision_id: str | None = None) -> dict | None:
        if model in self.unavailable_models:
            return None
        prompt, ids = render_question(state, question)
        rows = option_rows(question)
        if model.startswith("gpt-"):
            estimate = ledger.reserve(model, LABEL_SYSTEM + prompt, 1)
            try:
                key = os.environ["OPENAI_API_KEY"]
                data = await self._post("https://api.openai.com/v1/chat/completions",
                                        {"Authorization": f"Bearer {key}"},
                                        {"model": model, "messages": [{"role": "system", "content": LABEL_SYSTEM},
                                         {"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 1,
                                         "logprobs": True, "top_logprobs": 20})
                choice = data["choices"][0]
                usage = data.get("usage", {})
                ledger.settle(estimate, model, usage, "openai", f"teacher:{model}", decision_id)
                tokens = choice.get("logprobs", {}).get("content", [])
                probabilities = id_distribution(tokens[0].get("top_logprobs", []) if tokens else [], ids)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 400 <= status < 500 and status not in (408, 429):
                    self.mark_unavailable(model, status)
                ledger.cancel(estimate)
                raise
            except BudgetExceeded:
                raise
            except Exception:
                ledger.cancel(estimate)
                raise
        else:
            outputs = await asyncio.gather(*[
                self.generate(model, LABEL_SYSTEM + "\n\n" + prompt, ledger, max_output_tokens=4,
                              role=f"teacher:{model}", decision_id=decision_id, temperature=1)
                for _ in range(3)
            ], return_exceptions=True)
            error = next((output for output in outputs if isinstance(output, Exception)), None)
            if error:
                raise error
            counts = {oid: 0 for oid in ids}
            for text, _ in outputs:
                answer = text.strip().split()[0].strip(".,:;") if text.strip() else ""
                if answer in counts:
                    counts[answer] += 1
            total = sum(counts.values())
            probabilities = {key: value / total for key, value in counts.items()} if total else None
        if probabilities is None:
            return None
        return {dict((oid, key) for oid, key, _ in rows)[oid]: value
                for oid, value in probabilities.items()}


async def label_item(item: dict, models: list[str], client: ApiClient, ledger: BudgetLedger) -> tuple[dict, list[dict]]:
    result = {}
    failures = []
    for qid, question in item["questions"].items():
        result[qid] = {}
        for model in models:
            unavailable = client.unavailable_models.get(model)
            if unavailable:
                result[qid][model] = None
                failures.append({"id": item["id"], "qid": qid, "model": model,
                                 "reason": "candidate_unavailable", "status_code": unavailable["status_code"],
                                 "attempted": False})
                continue
            try:
                distribution = await client.label(model, item["state"], question, ledger,
                                                  decision_id=f"{item['id']}:{qid}")
            except BudgetExceeded:
                raise
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                permanent = 400 <= status < 500 and status not in (408, 429)
                if permanent:
                    client.mark_unavailable(model, status)
                result[qid][model] = None
                failures.append({"id": item["id"], "qid": qid, "model": model,
                                 "reason": "permanent_http_4xx" if permanent else "http_error",
                                 "status_code": status, "attempted": True})
            except Exception as exc:
                result[qid][model] = None
                failures.append({"id": item["id"], "qid": qid, "model": model,
                                 "reason": f"{type(exc).__name__}: {exc}", "attempted": True})
            else:
                result[qid][model] = distribution
                if distribution is None:
                    failures.append({"id": item["id"], "qid": qid, "model": model,
                                     "reason": "no_valid_label_mass", "attempted": True})
    return result, failures


def floored(dist: dict[str, float], floor: float = 1e-3) -> dict[str, float]:
    values = {key: max(0.0, value) + floor for key, value in dist.items()}
    total = sum(values.values())
    return {key: value / total for key, value in values.items()}
