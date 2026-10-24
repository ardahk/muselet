from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import threading
from collections import Counter
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

# Official rates per 1M text tokens; Haiku 5.5 values are for prompts <=100k tokens.
# OpenAI: https://developers.openai.com/api/docs/pricing
# Anthropic: https://www.anthropic.com/claude-haiku-5-5 and https://docs.anthropic.com/en/docs/about-claude/pricing
PRICES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-mini": (0.75, 4.50),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


class BudgetExceeded(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, budget: float, path: Path, run: str = "default", round_id: str | None = None,
                 cumulative_budget: float | None = None):
        self.budget, self.path, self.run, self.round_id = budget, path, run, round_id
        self.cumulative_budget = cumulative_budget
        self.spent = self.reserved = self.cumulative_spent = 0.0
        self.lock = threading.Lock()
        self.phase_cumulative_budget: float | None = None
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    cost = float(row.get("cost_usd", 0.0))
                    self.cumulative_spent += cost
                    if row.get("run", "default") == run and (
                        round_id is None or row.get("round_id") == round_id
                    ):
                        self.spent += cost

    def reserve(self, model: str, prompt: str, output_cap: int) -> float:
        inp, out = PRICES[model]
        input_cap = len(prompt.encode("utf-8")) + 256
        estimated = (input_cap * inp + output_cap * out) / 1_000_000
        with self.lock:
            if self.spent + self.reserved + estimated > self.budget:
                raise BudgetExceeded(
                    f"budget reserve would exceed ${self.budget:.2f} (spent ${self.spent:.4f})"
                )
            if self.cumulative_budget is not None and (
                self.cumulative_spent + self.reserved + estimated > self.cumulative_budget
            ):
                raise BudgetExceeded(
                    f"cumulative budget reserve would exceed ${self.cumulative_budget:.2f} "
                    f"(spent ${self.cumulative_spent:.4f})"
                )
            if self.phase_cumulative_budget is not None and (
                self.cumulative_spent + self.reserved + estimated > self.phase_cumulative_budget
            ):
                raise BudgetExceeded(
                    f"phase cumulative budget reserve would exceed "
                    f"${self.phase_cumulative_budget:.2f} (spent ${self.cumulative_spent:.4f})"
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
        if self.round_id:
            row["round_id"] = self.round_id
        with self.lock:
            self.reserved -= estimate
            self.spent += cost
            self.cumulative_spent += cost
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
            if self.spent > self.budget:
                raise BudgetExceeded(f"actual usage exceeded hard budget: ${self.spent:.4f}")
            if self.cumulative_budget is not None and self.cumulative_spent > self.cumulative_budget:
                raise BudgetExceeded(
                    f"actual cumulative usage exceeded hard budget: ${self.cumulative_spent:.4f}"
                )
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


def first_option_id(text: str, ids: list[str]) -> str | None:
    pattern = re.compile(r"(?<![A-Za-z0-9])([A-Z])(?![A-Za-z0-9])")
    return next((match.group(1) for match in pattern.finditer(text) if match.group(1) in ids), None)


class ApiClient:
    def __init__(self, concurrency: int = 32, retry_log: Path | None = None):
        self.semaphores = {
            "openai": asyncio.Semaphore(concurrency),
            "anthropic": asyncio.Semaphore(concurrency),
        }
        self.retry_log = retry_log
        self.unavailable_models: dict[str, dict] = {}

    def mark_unavailable(self, model: str, status_code: int):
        self.unavailable_models[model] = {"status_code": status_code}

    def _log_retry(self, provider: str, model: str, status_code: int | None, attempt: int,
                   reason: str | None = None):
        if self.retry_log is None:
            return
        self.retry_log.parent.mkdir(parents=True, exist_ok=True)
        with self.retry_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "provider": provider, "model": model, "status_code": status_code,
                "attempt": attempt, "reason": reason,
            }) + "\n")

    async def _post(self, url: str, headers: dict, body: dict):
        provider = "openai" if "openai.com" in url else "anthropic"
        model = str(body.get("model", "unknown"))
        semaphore = self.semaphores[provider]
        for attempt in range(5):
            try:
                async with semaphore:
                    async with httpx.AsyncClient(timeout=120) as client:
                        response = await client.post(url, headers=headers, json=body)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in (408, 429) and status < 500:
                    raise
                if attempt == 4:
                    raise
                self._log_retry(provider, model, status, attempt + 1)
                try:
                    retry_after = float(exc.response.headers.get("retry-after", 0) or 0)
                except ValueError:
                    retry_after = 0.0
                delay = min(2 ** attempt, 16) + random.random()
                await asyncio.sleep(max(delay, min(retry_after, 60)))
            except (httpx.TransportError, ValueError) as exc:
                if attempt == 4:
                    raise
                self._log_retry(provider, model, None, attempt + 1, type(exc).__name__)
                await asyncio.sleep(min(2 ** attempt, 16) + random.random())

    async def generate(self, model: str, prompt: str, ledger: BudgetLedger, max_output_tokens: int = 2048,
                       role: str = "author", decision_id: str | None = None,
                       temperature: float | None = None, reasoning_effort: str | None = None,
                       thinking_budget: int | None = None, response_schema: dict | None = None):
        reservation_tokens = min(max_output_tokens, 1024) if role.startswith(("teacher:", "gate:")) else \
            max_output_tokens
        estimate = ledger.reserve(model, prompt, reservation_tokens)
        try:
            if model.startswith("gpt-"):
                key = os.environ["OPENAI_API_KEY"]
                body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": max_output_tokens}
                if role == "author":
                    if response_schema:
                        body["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {"name": "authored_decision", "strict": True,
                                            "schema": response_schema},
                        }
                    else:
                        body["response_format"] = {"type": "json_object"}
                if model == "gpt-5.5":
                    body["reasoning_effort"] = "none"
                if reasoning_effort is not None:
                    body["reasoning_effort"] = reasoning_effort
                data = await self._post("https://api.openai.com/v1/chat/completions",
                                        {"Authorization": f"Bearer {key}"},
                                        body)
                usage = data.get("usage", {})
                result = data["choices"][0]["message"].get("content") or ""
                ledger.settle(estimate, model, usage, "openai", role, decision_id)
                return result, usage
            key = os.environ["ANTHROPIC_API_KEY"]
            body = {"model": model, "max_tokens": max_output_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
            if model == "claude-sonnet-5-5" and response_schema:
                body["thinking"] = {"type": "between_tools"}
            elif model == "claude-haiku-5-5" and role.startswith(("teacher:", "gate:")) \
                    and thinking_budget is not None and thinking_budget > 0:
                body["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget or 1024}
            else:
                body["thinking"] = {"type": "disabled"}
            if response_schema:
                body["tools"] = [{
                    "name": "submit_authored_decision",
                    "description": "Return the authored decision item matching the provided schema.",
                    "input_schema": response_schema,
                }]
                body["tool_choice"] = {"type": "auto"}
            if temperature is not None:
                body["temperature"] = temperature
            data = await self._post("https://api.anthropic.com/v1/messages",
                                    {"x-api-key": key, "anthropic-version": "2023-06-01"},
                                    body)
            usage = data.get("usage", {})
            tool_result = next((part.get("input") for part in data.get("content", [])
                                if part.get("type") == "tool_use"), None)
            result = json.dumps(tool_result) if tool_result is not None else "".join(
                part.get("text", "") for part in data.get("content", [])
            )
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

    async def sampled_label(self, model: str, state: str, question: dict, ledger: BudgetLedger,
                            decision_id: str | None = None, role: str | None = None) -> dict:
        if model in self.unavailable_models:
            return {"distribution": None, "samples": [], "valid_samples": 0, "majority": None,
                    "failures": [{"reason": "candidate_unavailable",
                                  "status_code": self.unavailable_models[model]["status_code"]}]}
        prompt, ids = render_question(state, question)
        rows = option_rows(question)
        output_cap = 1200 if model == "claude-haiku-5-5" else 4000
        effort = "low" if model in ("gpt-5.4-nano", "gpt-5.4-mini") else None
        max_tokens = 1200 if model == "claude-haiku-5-5" else output_cap
        sample_role = role or f"teacher:{model}"

        async def call(index: int):
            text, _ = await self.generate(
                model, LABEL_SYSTEM + "\n\n" + prompt, ledger, max_output_tokens=max_tokens,
                role=sample_role, decision_id=decision_id, temperature=1 if model == "claude-haiku-5-5" else None,
                reasoning_effort=effort, thinking_budget=0 if model == "claude-haiku-5-5" else None,
            )
            return index, text

        outputs = await asyncio.gather(*(call(i) for i in range(4)), return_exceptions=True)
        reverse = {option_id: key for option_id, key, _ in rows}
        answers = []
        failures = []
        for index, output in enumerate(outputs):
            if isinstance(output, Exception):
                if isinstance(output, BudgetExceeded):
                    raise output
                if isinstance(output, httpx.HTTPStatusError):
                    status = output.response.status_code
                    if 400 <= status < 500 and status not in (408, 429):
                        self.mark_unavailable(model, status)
                failures.append({"sample": index + 1, "reason": f"{type(output).__name__}: {output}"})
                continue
            _, visible = output
            option_id = first_option_id(visible, ids)
            if option_id is None:
                failures.append({"sample": index + 1, "reason": "no_valid_option_id"})
                continue
            answers.append(reverse[option_id])
        counts = Counter(answers)
        probabilities = {key: counts.get(key, 0) / len(answers) for _, key, _ in rows} if answers else None
        if probabilities is not None:
            from .build import floored
            probabilities = floored(probabilities)
        majority = None
        if answers:
            top_count = max(counts.values())
            leaders = [key for key, count in counts.items() if count == top_count]
            if len(leaders) == 1 and top_count > len(answers) / 2:
                majority = leaders[0]
        return {
            "distribution": probabilities,
            "samples": answers,
            "valid_samples": len(answers),
            "majority": majority,
            "failures": failures,
        }

    async def classic_label(self, model: str, state: str, question: dict, ledger: BudgetLedger,
                            decision_id: str | None = None) -> dict | None:
        if model in self.unavailable_models:
            return None
        prompt, ids = render_question(state, question)
        rows = option_rows(question)
        if model.startswith("gpt-"):
            estimate = ledger.reserve(model, LABEL_SYSTEM + prompt, 1)
            try:
                key = os.environ["OPENAI_API_KEY"]
                data = await self._post(
                    "https://api.openai.com/v1/chat/completions",
                    {"Authorization": f"Bearer {key}"},
                    {"model": model, "messages": [{"role": "system", "content": LABEL_SYSTEM},
                     {"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 1,
                     "logprobs": True, "top_logprobs": 20},
                )
                choice = data["choices"][0]
                ledger.settle(estimate, model, data.get("usage", {}), "openai",
                             f"teacher:{model}", decision_id)
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
            return answer_distribution(probabilities, ids, rows)

        outputs = await asyncio.gather(*[
            self.generate(model, LABEL_SYSTEM + "\n\n" + prompt, ledger, max_output_tokens=4,
                          role=f"teacher:{model}", decision_id=decision_id, temperature=1)
            for _ in range(3)
        ], return_exceptions=True)
        error = next((output for output in outputs if isinstance(output, Exception)), None)
        if error:
            raise error
        counts = Counter()
        for text, _ in outputs:
            option_id = first_option_id(text, ids)
            if option_id is not None:
                counts[option_id] += 1
        total = sum(counts.values())
        probabilities = {key: counts.get(key, 0) / total for key in ids} if total else None
        return answer_distribution(probabilities, ids, rows)

    async def label(self, model: str, state: str, question: dict, ledger: BudgetLedger,
                    decision_id: str | None = None) -> dict | None:
        if model in ("gpt-5.4-nano", "gpt-5.4-mini", "claude-haiku-5-5"):
            result = await self.sampled_label(model, state, question, ledger, decision_id)
            return result["distribution"]
        return await self.classic_label(model, state, question, ledger, decision_id)


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
                if model in ("gpt-5.4-nano", "gpt-5.4-mini", "claude-haiku-5-5"):
                    sampled = await client.sampled_label(
                        model, item["state"], question, ledger,
                        decision_id=f"{item['id']}:{qid}",
                    )
                    distribution = sampled["distribution"]
                    item.setdefault("teacher_samples", {}).setdefault(qid, {})[model] = {
                        "samples": sampled["samples"],
                        "valid_samples": sampled["valid_samples"],
                        "majority": sampled["majority"],
                    }
                    failures.extend({
                        "id": item["id"], "qid": qid, "model": model,
                        "sample": failure.get("sample"), "reason": failure["reason"],
                    } for failure in sampled["failures"])
                else:
                    distribution = await client.classic_label(
                        model, item["state"], question, ledger,
                        decision_id=f"{item['id']}:{qid}",
                    )
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
