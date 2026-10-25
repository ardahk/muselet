from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml" / "src"))

from brain.decision_chunking import combine_chunked
from brain.generic_decide import GenericRenderer
from bench.systemone.tinker_backend import TinkerDecider


class FakeRendering:
    def __init__(self, choices: list[tuple[str, str]]):
        self.labels = [label for label, _description in choices]
        self.label_tokens = {
            label: (
                int(label.removeprefix("option-")) + 1
                if label.startswith("option-")
                else {"left": 50, "right": 51, "0": 60, "1": 61, "2": 62,
                      "false": 70, "true": 71, "only": 80, "yes": 90, "no": 91}[label]
            )
            for label in self.labels
        }
        self.choice_pos = 2
        self.tokens = [101, 102, 103]


class FakeRenderer:
    prepare = GenericRenderer.prepare
    render_decisions = GenericRenderer.render_decisions

    def __init__(self, maximum: int = 58):
        self.maximum = maximum

    def render(self, decision):
        return FakeRendering(list(decision.choices))


class FakeModelInput:
    def __init__(self, tokens):
        self.tokens = list(tokens)

    @classmethod
    def from_ints(cls, tokens):
        return cls(tokens)


class FakeTensorData:
    @staticmethod
    def from_torch_sparse(tensor, pad_value):
        if pad_value != -1:
            raise AssertionError("expected sparse target padding of -1")
        return tensor


class FakeTinker:
    ModelInput = FakeModelInput
    TensorData = FakeTensorData

    class SamplingParams:
        def __init__(self, max_tokens):
            self.max_tokens = max_tokens


class FakeLogprobs:
    def __init__(self, tensor):
        self.tensor = tensor

    def to_torch(self):
        return self.tensor


class FakeSamplingClient:
    def __init__(self):
        self.calls = []
        self.failures_remaining = 0

    async def sample_async(
        self,
        *,
        prompt,
        num_samples,
        sampling_params,
        target_prompt_logprobs,
    ):
        if self.failures_remaining:
            self.failures_remaining -= 1
            error = RuntimeError("temporary service issue")
            error.status_code = 429
            raise error
        if num_samples != 1 or sampling_params.max_tokens != 1:
            raise AssertionError("sampler settings differ from the proven scoring path")
        targets = target_prompt_logprobs
        active_rows = torch.any(targets != -1, dim=1).nonzero().flatten().tolist()
        if active_rows != [1]:
            raise AssertionError(f"expected target logprobs at choice_pos - 1, got {active_rows}")
        token_ids = targets[1].tolist()
        if prompt.tokens != [101, 102, 103]:
            raise AssertionError(f"unexpected prompt tokens: {prompt.tokens}")
        self.calls.append(token_ids)
        result = torch.zeros_like(targets, dtype=torch.float32)
        result[1] = torch.tensor([token_id * 0.1 for token_id in token_ids])
        return types.SimpleNamespace(target_prompt_logprobs=FakeLogprobs(result))


def make_decider(maximum: int = 58) -> TinkerDecider:
    decider = TinkerDecider.__new__(TinkerDecider)
    decider.renderer = FakeRenderer(maximum)
    decider._combine_chunked = combine_chunked
    decider._tinker = FakeTinker
    decider._torch = torch
    decider.client = FakeSamplingClient()
    decider._loop = asyncio.new_event_loop()
    decider.last_input_tokens = None
    decider.temperature_probs = 1.0
    decider.temperature_conf = 1.0
    return decider


class TinkerDeciderTests(unittest.TestCase):
    def tearDown(self):
        for value in getattr(self, "_deciders", []):
            value._loop.close()

    def track(self, decider):
        if not hasattr(self, "_deciders"):
            self._deciders = []
        self._deciders.append(decider)
        return decider

    def test_sampling_chunks_at_18_ids_and_matches_one_softmax(self):
        decider = self.track(make_decider())
        labels = [f"option-{index}" for index in range(41)]
        rendering = FakeRendering([(label, "") for label in labels])

        probabilities, confidence, tokens = decider._loop.run_until_complete(
            decider._score_rendering(rendering)
        )

        self.assertEqual([len(call) for call in decider.client.calls], [18, 18, 5])
        self.assertEqual(decider.client.calls[0], list(range(1, 19)))
        logits = torch.tensor([token_id * 0.1 for token_id in range(1, 42)])
        expected = torch.softmax(logits, dim=0).tolist()
        for label, probability in zip(labels, expected, strict=True):
            self.assertAlmostEqual(probabilities[label], probability, places=7)
            self.assertAlmostEqual(confidence[label], probability, places=7)
        self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=6)
        self.assertEqual(tokens, 3 * len(rendering.tokens))

    def test_large_choice_uses_tournament_and_generic_chunk_combine(self):
        decider = self.track(make_decider(maximum=3))
        labels = [f"option-{index}" for index in range(8)]
        question = {
            "type": "choice",
            "instructions": "pick one",
            "options": labels,
            "descriptions": {label: label for label in labels},
        }

        result = decider.decide_many("state", {"choice": question})["choice"]

        chunks = [labels[:3], labels[3:6], labels[6:]]
        conditional = []
        winners = []
        for chunk in chunks:
            logits = torch.tensor([
                (labels.index(label) + 1) * 0.1 for label in chunk
            ])
            probabilities = torch.softmax(logits, dim=0).tolist()
            distribution = dict(zip(chunk, probabilities, strict=True))
            conditional.append(distribution)
            winners.append(max(chunk, key=distribution.__getitem__))
        winner_logits = torch.tensor([
            (labels.index(label) + 1) * 0.1 for label in winners
        ])
        winner_probs = torch.softmax(winner_logits, dim=0).tolist()
        expected = combine_chunked(
            [[(label, label) for label in chunk] for chunk in chunks],
            conditional,
            dict(zip(winners, winner_probs, strict=True)),
        )
        self.assertEqual(set(result), set(labels))
        self.assertAlmostEqual(sum(result.values()), 1.0, places=6)
        for label in labels:
            self.assertAlmostEqual(result[label], expected[label], places=7)
        self.assertGreater(len(decider.client.calls), len(chunks))

    def test_noul_score_choice_and_single_option_keys_match_shim(self):
        decider = self.track(make_decider())
        questions = {
            "choice": {
                "type": "choice",
                "instructions": "choose",
                "options": ["left", "right"],
                "descriptions": {"left": "Left", "right": "Right"},
            },
            "score": {
                "type": "score",
                "instructions": "rate",
                "options": ["0", "1", "2"],
                "descriptions": {"0": "low", "1": "mid", "2": "high"},
            },
            "noul": {
                "type": "noul",
                "instructions": "yes or no",
                "options": ["false", "true"],
                "descriptions": {"false": "No", "true": "Yes"},
            },
            "single": {
                "type": "choice",
                "instructions": "only choice",
                "options": ["only"],
                "descriptions": {"only": "Only"},
            },
        }

        results = decider.decide_many("state", questions)

        for qid, question in questions.items():
            self.assertEqual(set(results[qid]), set(question["options"]))
            self.assertAlmostEqual(sum(results[qid].values()), 1.0, places=6)
        self.assertEqual(results["single"], {"only": 1.0})

    def test_transient_sampler_errors_retry_with_backoff(self):
        decider = self.track(make_decider())
        decider.client.failures_remaining = 1
        rendering = FakeRendering([("yes", ""), ("no", "")])

        async def no_delay(_delay):
            return None

        with patch("bench.systemone.tinker_backend.asyncio.sleep", new=no_delay):
            result = decider._loop.run_until_complete(decider._score_rendering(rendering))

        self.assertEqual(len(decider.client.calls), 1)
        self.assertAlmostEqual(sum(result[0].values()), 1.0, places=6)

    def test_probability_and_confidence_temperatures_are_applied_separately(self):
        decider = self.track(make_decider())
        decider.temperature_probs = 0.5
        decider.temperature_conf = 2.0
        rendering = FakeRendering([("yes", ""), ("no", "")])

        probabilities, confidence, _tokens = decider._loop.run_until_complete(
            decider._score_rendering(rendering)
        )

        logits = torch.tensor([9.0, 9.1])
        expected_probs = torch.softmax(logits / 0.5, dim=0).tolist()
        expected_conf = torch.softmax(logits / 2.0, dim=0).tolist()
        self.assertAlmostEqual(probabilities["yes"], expected_probs[0], places=7)
        self.assertAlmostEqual(confidence["yes"], expected_conf[0], places=7)
        self.assertNotAlmostEqual(probabilities["yes"], confidence["yes"], places=5)


if __name__ == "__main__":
    unittest.main()
