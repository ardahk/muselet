"""Tinker-backed System One decisions using the shared Qwen renderer."""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path
from typing import Any

_TARGET_IDS_PER_CALL = 18
_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 0.25


def _load_generic_renderer():
    repo = Path(__file__).resolve().parents[2]
    ml_src = str(repo / "ml" / "src")
    if ml_src not in sys.path:
        sys.path.insert(0, ml_src)
    from brain.generic_decide import GenericRenderer, combine_chunked

    return GenericRenderer, combine_chunked


def _is_transient_error(error: Exception) -> bool:
    if isinstance(error, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return True
    if any(term in type(error).__name__.lower() for term in ("timeout", "connection", "temporary")):
        return True
    if getattr(error, "retryable", False):
        return True
    response = getattr(error, "response", None)
    status = (
        getattr(error, "status_code", None)
        or getattr(error, "http_status_code", None)
        or getattr(response, "status_code", None)
    )
    return status in (408, 425, 429) or isinstance(status, int) and status >= 500


class DecisionDistributions(dict):
    def __init__(self, probabilities: dict, confidence_distributions: dict):
        super().__init__(probabilities)
        self.confidence_distributions = confidence_distributions


class TinkerDecider:
    """Score shared GenericRenderer tokens using Tinker's sampler logprobs."""

    def __init__(
        self,
        model_path: str,
        temperature_probs: float = 1.0,
        temperature_conf: float = 1.0,
    ):
        import tinker
        import torch

        if (
            not math.isfinite(temperature_probs) or not math.isfinite(temperature_conf)
            or temperature_probs <= 0 or temperature_conf <= 0
        ):
            raise ValueError("temperatures must be positive")
        service_client = tinker.ServiceClient()
        if model_path.startswith("tinker://"):
            self.client = service_client.create_sampling_client(model_path=model_path)
        else:
            self.client = service_client.create_sampling_client(base_model=model_path)
        renderer_type, self._combine_chunked = _load_generic_renderer()
        self.renderer = renderer_type("Qwen/Qwen3.5-4B")
        self._tinker = tinker
        self._torch = torch
        self.temperature_probs = float(temperature_probs)
        self.temperature_conf = float(temperature_conf)
        self._loop = asyncio.new_event_loop()
        self.last_input_tokens: int | None = None

    def decide(self, state: str, question: dict) -> dict[str, float]:
        return self.decide_many(state, {"decision": question})["decision"]

    async def _sample_chunk(self, rendering: Any, token_ids: list[int]) -> list[float]:
        torch = self._torch
        choice_row = rendering.choice_pos - 1
        if choice_row < 0 or choice_row >= len(rendering.tokens) - 1:
            raise RuntimeError("rendered decision has an invalid choice position")
        targets = torch.full(
            (len(rendering.tokens) - 1, len(token_ids)),
            -1,
            dtype=torch.int64,
        )
        targets[choice_row] = torch.tensor(token_ids, dtype=torch.int64)
        sparse_targets = self._tinker.TensorData.from_torch_sparse(targets, pad_value=-1)
        prompt = self._tinker.ModelInput.from_ints(rendering.tokens)
        sampling_params = self._tinker.SamplingParams(max_tokens=1)

        for attempt in range(_RETRY_ATTEMPTS):
            try:
                response = await self.client.sample_async(
                    prompt=prompt,
                    num_samples=1,
                    sampling_params=sampling_params,
                    target_prompt_logprobs=sparse_targets,
                )
                break
            except Exception as exc:
                if attempt + 1 == _RETRY_ATTEMPTS or not _is_transient_error(exc):
                    raise
                await asyncio.sleep(_RETRY_DELAY_SECONDS * (2 ** attempt))
        if response.target_prompt_logprobs is None:
            raise RuntimeError("target_prompt_logprobs not returned for this model")
        logprobs = response.target_prompt_logprobs.to_torch()[choice_row]
        return [float(value) for value in logprobs.tolist()]

    async def _score_rendering(
        self, rendering: Any
    ) -> tuple[dict[str, float], dict[str, float], int]:
        labels = list(rendering.labels)
        chunks = [
            labels[offset:offset + _TARGET_IDS_PER_CALL]
            for offset in range(0, len(labels), _TARGET_IDS_PER_CALL)
        ]

        async def score_part(part: list[str]) -> list[float]:
            token_ids = [rendering.label_tokens[label] for label in part]
            return await self._sample_chunk(rendering, token_ids)

        first_logprobs = await score_part(chunks[0])
        remaining = await asyncio.gather(*(score_part(part) for part in chunks[1:]))
        logprobs = first_logprobs + [value for part in remaining for value in part]
        logits = self._torch.tensor(logprobs, dtype=self._torch.float32)
        temperature_probs = getattr(self, "temperature_probs", 1.0)
        temperature_conf = getattr(self, "temperature_conf", 1.0)
        probabilities = self._torch.softmax(logits / temperature_probs, dim=0).tolist()
        confidence = self._torch.softmax(logits / temperature_conf, dim=0).tolist()
        return (
            dict(zip(labels, probabilities, strict=True)),
            dict(zip(labels, confidence, strict=True)),
            len(chunks) * len(rendering.tokens),
        )

    async def _score_renderings(self, renderings: dict) -> tuple[dict, dict, int]:
        if not renderings:
            return {}, {}, 0
        values = await asyncio.gather(*(
            self._score_rendering(rendering) for rendering in renderings.values()
        ))
        probabilities = {
            key: result[0] for key, result in zip(renderings, values, strict=True)
        }
        confidence = {
            key: result[1] for key, result in zip(renderings, values, strict=True)
        }
        return probabilities, confidence, sum(result[2] for result in values)

    async def _decide_many(self, state: str, questions: dict[str, dict]) -> DecisionDistributions:
        plans, decisions = self.renderer.prepare(state, questions)
        renderings = self.renderer.render_decisions(decisions)
        conditional, conditional_confidence, input_tokens = await self._score_renderings(renderings)

        results = {}
        confidence_results = {}
        stage_two = {}
        for qid, plan in plans.items():
            chunks = plan["chunks"]
            if not plan["keys"]:
                results[qid] = {plan["fixed"]: 1.0}
                confidence_results[qid] = {plan["fixed"]: 1.0}
                continue
            distributions = [conditional[key] for key in plan["keys"]]
            if len(chunks) == 1:
                results[qid] = distributions[0]
                confidence_results[qid] = conditional_confidence[plan["keys"][0]]
                continue
            winners = []
            for chunk, distribution in zip(chunks, distributions, strict=True):
                winners.append(max(chunk, key=lambda option: distribution[option[0]]))
            decision = plan["decision"]
            stage_two[qid] = type(decision)(text=decision.text, choices=winners)

        final_renderings = self.renderer.render_decisions(stage_two)
        final_distributions, final_confidence, final_tokens = await self._score_renderings(final_renderings)
        for qid in stage_two:
            plan = plans[qid]
            results[qid] = self._combine_chunked(
                plan["chunks"],
                [conditional[key] for key in plan["keys"]],
                final_distributions[qid],
            )
            confidence_results[qid] = self._combine_chunked(
                plan["chunks"],
                [conditional_confidence[key] for key in plan["keys"]],
                final_confidence[qid],
            )
        self.last_input_tokens = input_tokens + final_tokens
        return DecisionDistributions(results, confidence_results)

    def decide_many(self, state: str, questions: dict[str, dict]) -> dict[str, dict[str, float]]:
        return self._loop.run_until_complete(self._decide_many(state, questions))


__all__ = ["TinkerDecider"]
