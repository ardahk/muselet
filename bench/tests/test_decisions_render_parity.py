import pytest

from bench.systemone.schema import parse_request
from bench.systemone.server import server_questions
from brain.generic_decide import GenericRenderer
from training.decisions.render import render_question


@pytest.fixture(scope="module")
def renderer():
    return GenericRenderer("Qwen/Qwen3.5-4B")


@pytest.mark.parametrize("kind,count", [
    ("choice", 2), ("choice", 7), ("choice", 12), ("choice", 26),
    ("noul", 2), ("score", 2), ("score", 7), ("score", 10),
])
def test_training_datum_matches_systemone_renderer(renderer, kind, count):
    if kind == "choice":
        criteria = {f"key_{i}": f"Description for option {i}." for i in range(count)}
        target = {"key_0": 0.4, **{f"key_{i}": 0.6 / (count - 1) for i in range(1, count)}}
    elif kind == "noul":
        criteria, target = {"false": "Condition is not met.", "true": "Condition is met."}, {"true": 1.0}
    else:
        criteria = [f"Level {i} description." for i in range(count)]
        target = {str(count - 1): 1.0}
    payload = {"state": "A synthetic state containing the facts for this parity check.",
               "questions": {"q": {"type": kind, "instructions": "Which outcome applies?", "criteria": criteria}}}
    request = parse_request(payload)
    server_question = server_questions(request)["q"]
    plans, decisions = renderer.prepare(str(request.state), {"q": server_question})
    assert len(plans["q"]["keys"]) == 1
    expected = renderer.render_decisions(decisions)[plans["q"]["keys"][0]]
    datum, actual = render_question(renderer, str(request.state), payload["questions"]["q"], target)
    chunks = datum.model_input.chunks
    actual_tokens = list(chunks[0].tokens)
    assert actual_tokens == expected.tokens[:expected.choice_pos]
    assert actual.label_tokens == expected.label_tokens
    assert len(actual_tokens) == expected.choice_pos
