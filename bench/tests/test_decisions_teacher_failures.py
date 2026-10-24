import asyncio
import math
import random

import httpx
import pytest

from training.decisions.build import CODE_FAMILIES, CODE_TEACHERS, _gate_subset, _teacher_distribution_stats
from training.decisions.families import GENERATORS
from training.decisions.label import ApiClient, BudgetLedger, label_item


def test_permanent_4xx_disables_candidate_but_keeps_other_teachers(monkeypatch, tmp_path):
    client = ApiClient()
    calls = []

    async def fake_label(model, _state, _question, _ledger, decision_id=None, role=None):
        calls.append((model, decision_id))
        if model == "gpt-5.4-nano":
            request = httpx.Request("POST", "https://api.example.test")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)
        return {"distribution": {"yes": 0.8, "no": 0.2}, "samples": ["yes"],
                "valid_samples": 1, "majority": "yes", "failures": []}

    monkeypatch.setattr(client, "sampled_label", fake_label)
    question = {
        "type": "choice",
        "instructions": "Choose.",
        "criteria": {"yes": "Yes.", "no": "No."},
    }
    item = {"id": "sample", "state": "state", "questions": {"q1": question, "q2": question}}
    ledger = BudgetLedger(5.0, tmp_path / "cost.jsonl", "test")

    teacher, failures = asyncio.run(label_item(item, list(CODE_TEACHERS), client, ledger))

    assert teacher["q1"]["gpt-5.4-nano"] is None
    assert teacher["q1"]["gpt-5.4-mini"] == {"yes": 0.8, "no": 0.2}
    assert teacher["q2"]["gpt-5.4-nano"] is None
    assert client.unavailable_models["gpt-5.4-nano"]["status_code"] == 404
    assert calls == [
        ("gpt-5.4-nano", "sample:q1"),
        ("gpt-5.4-mini", "sample:q1"),
        ("claude-haiku-5-5", "sample:q1"),
        ("gpt-5.4-mini", "sample:q2"),
        ("claude-haiku-5-5", "sample:q2"),
    ]
    assert [failure["reason"] for failure in failures] == [
        "permanent_http_4xx",
        "candidate_unavailable",
    ]


def test_gate_subset_has_25_per_family_and_50_per_type():
    records = [
        GENERATORS[family](random.Random(index * 100 + item), "mixed", 3, ["choice", "noul", "score"])
        for index, family in enumerate(CODE_FAMILIES)
        for item in range(25)
    ]
    rows = _gate_subset(records, 814)
    assert len(rows) == 150
    assert {family: sum(row["item"]["family"] == family for row in rows) for family in CODE_FAMILIES} == {
        family: 25 for family in CODE_FAMILIES
    }
    assert {kind: sum(row["type"] == kind for row in rows) for kind in ("choice", "noul", "score")} == {
        "choice": 50, "noul": 50, "score": 50
    }


def test_teacher_target_sharpness_uses_each_distribution():
    stats = _teacher_distribution_stats(
        [{"teacher": {"q1": {"teacher-a": {"yes": 0.75, "no": 0.25}}}}],
        ("teacher-a",),
    )

    assert stats["teacher-a"]["mean_max_probability"] == 0.75
    assert stats["teacher-a"]["mean_entropy_nats"] == pytest.approx(
        -(0.75 * math.log(0.75) + 0.25 * math.log(0.25))
    )


def test_permanent_4xx_releases_reserved_budget_and_marks_model(monkeypatch, tmp_path):
    client = ApiClient()
    ledger = BudgetLedger(5.0, tmp_path / "cost.jsonl", "test")
    question = {
        "type": "choice",
        "instructions": "Choose.",
        "criteria": {"yes": "Yes.", "no": "No."},
    }
    request = httpx.Request("POST", "https://api.example.test")
    response = httpx.Response(404, request=request)

    async def fail_post(*_args, **_kwargs):
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(client, "_post", fail_post)
    try:
        asyncio.run(client.label("gpt-4.1-mini", "state", question, ledger, "sample:q1"))
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("permanent 4xx was not propagated")

    assert ledger.reserved == 0
    assert ledger.spent == 0
    assert client.unavailable_models["gpt-4.1-mini"]["status_code"] == 404


def test_haiku_reasoning_label_uses_four_samples_and_extended_thinking(monkeypatch, tmp_path):
    client = ApiClient()
    ledger = BudgetLedger(5.0, tmp_path / "cost.jsonl", "test")
    captured = []

    async def fake_post(_url, _headers, body):
        captured.append(body.copy())
        return {"content": [{"type": "text", "text": "A"}],
                "usage": {"input_tokens": 10, "output_tokens": 1}}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr(client, "_post", fake_post)
    question = {"type": "choice", "instructions": "Choose.", "criteria": {"yes": "Yes.", "no": "No."}}
    result = asyncio.run(client.sampled_label("claude-haiku-5-5", "state", question, ledger, "sample:q1"))
    assert result["valid_samples"] == 4
    assert len(captured) == 4
    assert all(body["thinking"] == {"type": "enabled", "budget_tokens": 1024} for body in captured)
    assert all(body["temperature"] == 1 and body["max_tokens"] == 1200 for body in captured)


@pytest.mark.parametrize("model", ["gpt-5.4-nano", "gpt-5.4-mini"])
def test_gpt_reasoning_label_uses_low_effort_and_four_samples(model, monkeypatch, tmp_path):
    client = ApiClient()
    ledger = BudgetLedger(5.0, tmp_path / f"{model}.jsonl", "test")
    captured = []

    async def fake_post(_url, _headers, body):
        captured.append(body.copy())
        return {
            "choices": [{"message": {"content": "Answer: A"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(client, "_post", fake_post)
    question = {"type": "choice", "instructions": "Choose.", "criteria": {"yes": "Yes.", "no": "No."}}
    result = asyncio.run(client.sampled_label(model, "state", question, ledger, "sample:q1"))

    assert result["valid_samples"] == 4
    assert len(captured) == 4
    assert all(body["reasoning_effort"] == "low" for body in captured)
    assert all(body["max_completion_tokens"] == 4000 for body in captured)


def test_author_models_use_supported_low_cost_reasoning_modes(monkeypatch, tmp_path):
    client = ApiClient()
    ledger = BudgetLedger(5.0, tmp_path / "cost.jsonl", "test")
    captured = []

    async def fake_post(_url, _headers, body):
        captured.append(body)
        if body["model"] == "gpt-5.5":
            return {"choices": [{"message": {"content": '{"state":"x","questions":[]}'}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        return {"content": [{"type": "text", "text": '{"state":"x","questions":[]}'}],
                "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr(client, "_post", fake_post)
    asyncio.run(client.generate("gpt-5.5", "prompt", ledger, decision_id="gpt"))
    asyncio.run(client.generate("claude-sonnet-5-5", "prompt", ledger, decision_id="claude"))

    assert captured[0]["reasoning_effort"] == "none"
    assert captured[1]["thinking"] == {"type": "between_tools"}
