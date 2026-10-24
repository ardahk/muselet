"""Generic System One decisions using the local Qwen/MLX renderer."""

from __future__ import annotations

import copy
import json
from typing import Any

from brain.decision import AlphaChoiceRenderer, split_model
from brain.decision_chunking import chunk_options, combine_chunked
from brain.vendor.tinker_decisions import Decision, DecisionRenderer


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


class GenericRenderer:
    """Tokenizer-only rendering and common-prefix planning for System One decisions."""

    def __init__(self, tokenizer_path: str):
        from tinker_cookbook import model_info, renderers, tokenizer_utils

        renderer_name = model_info.get_recommended_renderer_name("Qwen/Qwen3.5-4B")
        renderer = renderers.get_renderer(renderer_name, tokenizer_utils.get_tokenizer(tokenizer_path))
        self.tokenizer = renderer.tokenizer
        self.choice_renderer = AlphaChoiceRenderer(renderer)
        self.choice_renderer.IDS = self.choice_renderer.usable_ids
        self.renderer = DecisionRenderer(renderer, choice_renderer=self.choice_renderer)
        self.maximum = len(self.choice_renderer.usable_ids)
        self.static_tokens = self._render_static_prefix()

    def _render_static_prefix(self) -> list[int]:
        marker = "MUSELET_STATIC_PREFIX_SENTINEL"
        probe = self.renderer.render(Decision(
            text=marker,
            choices=[("true", "Yes"), ("false", "No")],
        ))
        marker_tokens = self.tokenizer.encode(marker, add_special_tokens=False)
        return probe.tokens[:_find_subsequence(probe.tokens, marker_tokens)]

    def prepare(self, state: str, questions: dict[str, dict]):
        plans = {}
        decisions = {}
        for qid, question in questions.items():
            choices = _choices(question)
            if len(choices) == 1:
                plans[qid] = {
                    "decision": None,
                    "chunks": [choices],
                    "keys": [],
                    "fixed": choices[0][0],
                }
                continue
            decision = _decision(state, question)
            chunks = chunk_options(list(decision.choices), self.maximum)
            keys = []
            for index, chunk in enumerate(chunks):
                key = (qid, index)
                keys.append(key)
                decisions[key] = decision if len(chunks) == 1 else Decision(
                    text=decision.text, choices=chunk
                )
            plans[qid] = {"decision": decision, "chunks": chunks, "keys": keys}
        return plans, decisions

    def render(self, decision: Decision):
        return self.renderer.render(decision)

    def render_decisions(self, decisions: dict):
        return {key: self.render(decision) for key, decision in decisions.items()}

    @staticmethod
    def common_prefix(renderings: list[Any]) -> int:
        return _common_prefix(renderings)


class GenericMLXDecider:
    """Cache the renderer's static prefix and score choice tokens with MLX.

    All MLX work runs on one dedicated worker thread — MLX streams are
    thread-local, so a model loaded on thread A cannot be evaluated on
    thread B. The shim's ThreadingHTTPServer dispatches each request to a
    fresh handler thread; without a worker, _score_renderings dies with
    "no Stream(gpu, 1) in current thread".
    """

    def __init__(self, model_path: str):
        import queue
        import threading

        self._jobs: queue.Queue = queue.Queue()
        self._init_done: queue.Queue = queue.Queue()
        self._worker = threading.Thread(
            target=self._worker_main, args=(model_path,), daemon=True, name="mlx-decide"
        )
        self._worker.start()
        self.last_input_tokens: int | None = None
        err = self._init_done.get()  # init result
        if isinstance(err, Exception):
            raise err

    def _worker_main(self, model_path: str):
        try:
            import mlx.core as mx
            import mlx_lm
            from mlx_lm.models.cache import make_prompt_cache

            self.mx = mx
            self.model, _ = mlx_lm.load(model_path)
            self.body, self.lm_head = split_model(self.model)
            self.renderer = GenericRenderer(model_path)
            self._make_prompt_cache = make_prompt_cache
            self._static_cache = self._prefill(self.renderer.static_tokens)
            self._init_done.put(None)
        except Exception as e:  # report init failure to __init__
            self._init_done.put(e)
            return
        while True:
            job = self._jobs.get()
            if job is None:
                return
            fn, out = job
            try:
                out.put(fn())
            except Exception as e:
                out.put(e)

    def _submit(self, fn):
        import queue as _q

        out = _q.Queue()
        self._jobs.put((fn, out))
        result = out.get()
        if isinstance(result, Exception):
            raise result
        return result

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

    def _score_renderings(self, renderings: dict) -> tuple[dict, int]:
        if not renderings:
            return {}, 0
        shared_len = self.renderer.common_prefix(list(renderings.values()))
        static_len = len(self.renderer.static_tokens)
        if shared_len < static_len:
            raise RuntimeError("decision rendering diverged from the cached static prefix")

        shared_cache = copy.deepcopy(self._static_cache)
        input_tokens = 0
        shared_logits = None
        first = next(iter(renderings.values()), None)
        if first is not None and shared_len > static_len:
            shared_tokens = first.tokens[static_len:shared_len]
            shared_logits = self._feed(shared_cache, shared_tokens)
            input_tokens += len(shared_tokens)

        results = {}
        for qid, rendering in renderings.items():
            cache = copy.deepcopy(shared_cache)
            suffix = rendering.tokens[shared_len:rendering.choice_pos]
            if suffix:
                logits = self._feed(cache, suffix)
                input_tokens += len(suffix)
            elif shared_logits is not None:
                logits = shared_logits
            else:
                raise RuntimeError("rendered decision has no dynamic prompt tokens")
            labels = list(rendering.label_tokens)
            token_ids = [rendering.label_tokens[label] for label in labels]
            probabilities = self.mx.softmax(logits[self.mx.array(token_ids)], axis=0).tolist()
            results[qid] = dict(zip(labels, (float(value) for value in probabilities), strict=True))
        return results, input_tokens

    def decide_many(self, state: str, questions: dict[str, dict]) -> dict[str, dict[str, float]]:
        return self._submit(lambda: self._decide_many(state, questions))

    def _decide_many(self, state: str, questions: dict[str, dict]) -> dict[str, dict[str, float]]:
        plans, decisions = self.renderer.prepare(state, questions)
        renderings = self.renderer.render_decisions(decisions)
        conditional, input_tokens = self._score_renderings(renderings)

        results = {}
        stage_two = {}
        for qid, plan in plans.items():
            chunks = plan["chunks"]
            if not plan["keys"]:
                results[qid] = {plan["fixed"]: 1.0}
                continue
            distributions = [conditional[key] for key in plan["keys"]]
            if len(chunks) == 1:
                results[qid] = distributions[0]
                continue
            winners = []
            for chunk, distribution in zip(chunks, distributions, strict=True):
                winner = max(chunk, key=lambda option: distribution[option[0]])
                winners.append(winner)
            stage_two[qid] = Decision(text=plan["decision"].text, choices=winners)

        final_renderings = self.renderer.render_decisions(stage_two)
        final_distributions, final_tokens = self._score_renderings(final_renderings)
        for qid, decision in stage_two.items():
            plan = plans[qid]
            conditional_distributions = [
                conditional[key] for key in plan["keys"]
            ]
            results[qid] = combine_chunked(
                plan["chunks"], conditional_distributions, final_distributions[qid]
            )
        self.last_input_tokens = input_tokens + final_tokens
        return results


__all__ = [
    "GenericMLXDecider", "GenericRenderer", "chunk_options",
    "combine_chunked", "_decision",
]
