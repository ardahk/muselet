import asyncio
import math

import httpx
import pytest

from training.decisions.build import CODE_TEACHERS, _select_code_teacher, _teacher_distribution_stats
from training.decisions.label import ApiClient, BudgetLedger, label_item


def test_permanent_4xx_disables_candidate_but_keeps_other_teachers(monkeypatch, tmp_path):
    client = ApiClient()
    calls = []

    async def fake_label(model, _state, _question, _ledger, decision_id=None):
        calls.append((model, decision_id))
        if model == "gpt-4.1-mini":
            request = httpx.Request("POST", "https://api.example.test")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)
        return {"yes": 0.8, "no": 0.2}

    monkeypatch.setattr(client, "label", fake_label)
    question = {
        "type": "choice",
        "instructions": "Choose.",
        "criteria": {"yes": "Yes.", "no": "No."},
    }
    item = {"id": "sample", "state": "state", "questions": {"q1": question, "q2": question}}
    ledger = BudgetLedger(5.0, tmp_path / "cost.jsonl", "test")

    teacher, failures = asyncio.run(label_item(item, list(CODE_TEACHERS), client, ledger))

    assert teacher["q1"]["gpt-4.1-mini"] is None
    assert teacher["q1"]["gpt-4.1"] == {"yes": 0.8, "no": 0.2}
    assert teacher["q2"]["gpt-4.1-mini"] is None
    assert client.unavailable_models["gpt-4.1-mini"]["status_code"] == 404
    assert calls == [
        ("gpt-4.1-mini", "sample:q1"),
        ("gpt-4.1", "sample:q1"),
        ("claude-haiku-5-5", "sample:q1"),
        ("gpt-4.1", "sample:q2"),
        ("claude-haiku-5-5", "sample:q2"),
    ]
    assert [failure["reason"] for failure in failures] == [
        "permanent_http_4xx",
        "candidate_unavailable",
    ]


def test_failed_predictions_are_excluded_from_teacher_agreement():
    records = [{
        "id": "sample",
        "family": "numeric",
        "state": "state",
        "questions": {"q1": {"type": "choice", "instructions": "Choose.", "criteria": {"A": "A", "B": "B"}}},
        "gold": {"q1": "A"},
        "teacher": {"q1": {
            "gpt-4.1-mini": {"A": 0.99, "B": 0.01},
            "gpt-4.1": None,
            "claude-haiku-5-5": {"A": 0.1, "B": 0.9},
        }},
    }]

    selected, report, disagreements = _select_code_teacher(
        records, {"gpt-4.1": {"status_code": 404}}
    )

    assert selected == "gpt-4.1-mini"
    assert report["numeric"]["gpt-4.1-mini"]["agreement"] == 1.0
    assert report["_overall"]["gpt-4.1"]["total"] == 0
    assert report["_overall"]["gpt-4.1"]["failed_calls"] == 1
    assert report["_overall"]["gpt-4.1"]["unavailable"] is True
    assert [row["model"] for row in disagreements] == ["claude-haiku-5-5"]


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


def test_claude_label_request_disables_thinking_for_short_answer(monkeypatch, tmp_path):
    client = ApiClient()
    ledger = BudgetLedger(5.0, tmp_path / "cost.jsonl", "test")
    captured = {}

    async def fake_post(_url, _headers, body):
        captured.update(body)
        return {"content": [{"type": "text", "text": "A"}],
                "usage": {"input_tokens": 10, "output_tokens": 1}}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setattr(client, "_post", fake_post)
    text, usage = asyncio.run(client.generate(
        "claude-haiku-5-5", "prompt", ledger, max_output_tokens=4,
        role="teacher:claude-haiku-5-5", decision_id="sample:q1", temperature=1,
    ))

    assert text == "A"
    assert usage["output_tokens"] == 1
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == 4


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
