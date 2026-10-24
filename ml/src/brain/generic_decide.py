"""Generic System One decisions using the local Qwen/MLX renderer."""

from __future__ import annotations

import copy
import json
from typing import Any

from brain.decision import AlphaChoiceRenderer, split_model
from brain.vendor.tinker_decisions import Decision, DecisionRenderer


class TooManyOptionsError(ValueError):
    code = "invalid_request"

    def __init__(self, field: str, count: int, maximum: int):
        super().__init__(f"too_many_options: {count} options exceed the renderer limit of {maximum}")
        self.field = field


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=False)


def _choices(question: dict) -> list[tuple[str, str]]:
    kind = question["type"]
    if kind == "choice":
        return [
            (option, _text(question.get("descriptions", {}).get(option, "")))
            for option in question["options"]
        ]
    if kind == "score":
        return [(option, _text(question.get("descriptions", {}).get(option, ""))) for option in question["options"]]
    criteria = question.get("criteria")
    if isinstance(criteria, dict) and set(criteria) == {"false", "true"}:
        return [(key, _text(criteria[key])) for key in criteria]
    return [("true", "Yes"), ("false", "No")]


def _decision(state: str, question: dict) -> Decision:
    instructions = _text(question["instructions"])
    text = f"State:\n{state}\n\nQuestion:\n{instructions}"
    return Decision(text=text, choices=_choices(question))


def _find_subsequence(tokens: list[int], needle: list[int]) -> int:
    size = len(needle)
    for index in range(len(tokens) - size + 1):
        if tokens[index:index + size] == needle:
            return index
    raise RuntimeError("could not locate static-prefix sentinel in rendered prompt")


def _common_prefix(renderings: list[Any]) -> int:
    if not renderings:
        return 0
    limit = min(rendering.choice_pos for rendering in renderings)
    common = 0
    while common < limit:
        token = renderings[0].tokens[common]
        if any(rendering.tokens[common] != token for rendering in renderings[1:]):
            break
        common += 1
    return common


class GenericMLXDecider:
    """Cache the renderer's static prefix and score each question's choice tokens."""

    def __init__(self, model_path: str):
        import mlx.core as mx
        import mlx_lm
        from tinker_cookbook import model_info, renderers, tokenizer_utils
        from mlx_lm.models.cache import make_prompt_cache

        self.mx = mx
        self.model, _ = mlx_lm.load(model_path)
        self.body, self.lm_head = split_model(self.model)
        renderer_name = model_info.get_recommended_renderer_name("Qwen/Qwen3.5-4B")
        renderer = renderers.get_renderer(
            renderer_name, tokenizer_utils.get_tokenizer(model_path)
        )
        self.tokenizer = renderer.tokenizer
        self.choice_renderer = AlphaChoiceRenderer(renderer)
        self.renderer = DecisionRenderer(renderer, choice_renderer=self.choice_renderer)
        self._make_prompt_cache = make_prompt_cache
        self._static_tokens = self._render_static_prefix()
        self._static_cache = self._prefill(self._static_tokens)

    def _render_static_prefix(self) -> list[int]:
        marker = "MUSELET_STATIC_PREFIX_SENTINEL"
        probe = self.renderer.render(Decision(
            text=marker,
            choices=[("true", "Yes"), ("false", "No")],
        ))
        marker_tokens = self.tokenizer.encode(marker, add_special_tokens=False)
        return probe.tokens[:_find_subsequence(probe.tokens, marker_tokens)]

    def _prefill(self, tokens: list[int]):
        cache = self._make_prompt_cache(self.model)
        if tokens:
            self.body(self.mx.array([tokens]), cache=cache)
        return cache

    def _feed(self, cache, tokens: list[int]):
        if not tokens:
            raise RuntimeError("rendered decision has no tokens before its answer position")
        output = self.body(self.mx.array([tokens]), cache=cache)
        return self.lm_head(output[:, -1:, :]).astype(self.mx.float32)[0, 0]

    def decide(self, state: str, question: dict) -> dict[str, float]:
        return self.decide_many(state, {"decision": question})["decision"]

    def decide_many(self, state: str, questions: dict[str, dict]) -> dict[str, dict[str, float]]:
        decisions = {qid: _decision(state, question) for qid, question in questions.items()}
        maximum = len(self.choice_renderer.usable_ids)
        for qid, decision in decisions.items():
            if len(decision.choices) > maximum:
                raise TooManyOptionsError(f"questions.{qid}.criteria", len(decision.choices), maximum)

        renderings = {qid: self.renderer.render(decision) for qid, decision in decisions.items()}
        shared_len = _common_prefix(list(renderings.values()))
        static_len = len(self._static_tokens)
        if shared_len < static_len:
            raise RuntimeError("decision rendering diverged from the cached static prefix")

        shared_cache = copy.deepcopy(self._static_cache)
        first = next(iter(renderings.values()), None)
        if first is not None and shared_len > static_len:
            self._feed(shared_cache, first.tokens[static_len:shared_len])

        results: dict[str, dict[str, float]] = {}
        for qid, rendering in renderings.items():
            cache = copy.deepcopy(shared_cache)
            logits = self._feed(cache, rendering.tokens[shared_len:rendering.choice_pos])
            labels = decisions[qid].labels
            token_ids = [rendering.label_tokens[label] for label in labels]
            probabilities = self.mx.softmax(logits[self.mx.array(token_ids)], axis=0).tolist()
            results[qid] = dict(zip(labels, (float(value) for value in probabilities), strict=True))
        return results


__all__ = ["GenericMLXDecider", "TooManyOptionsError", "_decision"]
