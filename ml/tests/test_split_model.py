"""split_model must use an untied lm_head when the model has one (Qwen3.5-9B, Qwen3.6-35B-A3B keep it at
model.language_model.lm_head) and fall back to the tied embedding only when there is none (Qwen3.5-4B)."""

from types import SimpleNamespace

from brain.decision import split_model


def _wrapper(lm_head):
    embed = SimpleNamespace(as_linear="tied-embedding")
    body = SimpleNamespace(embed_tokens=embed)
    lm = SimpleNamespace(model=body, lm_head=lm_head) if lm_head else SimpleNamespace(model=body)
    return SimpleNamespace(model=body, language_model=lm), body


def test_untied_head_on_language_model_is_used():
    model, body = _wrapper("untied-head")
    inner, head = split_model(model)
    assert inner is body
    assert head == "untied-head"


def test_tied_model_falls_back_to_embedding():
    model, body = _wrapper(None)
    inner, head = split_model(model)
    assert inner is body
    assert head == "tied-embedding"
