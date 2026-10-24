import json
from pathlib import Path

from muselet_train.catalog import option_names
from muselet_train.route_render import RouteContext, render_route, route_renderer

SAMPLES = Path(__file__).resolve().parents[1] / "artifacts" / "route_render_samples.jsonl"


def test_id_alphabet_and_options():
    cr = route_renderer().choice_renderer
    assert len(cr.ids) >= 40
    assert option_names()[-4:] == ["MULTI_STEP", "ASK", "REFUSE", "ANSWER"]


def test_render_layout():
    r = render_route(RouteContext(app="Finder"), "mute")
    text = route_renderer().tokenizer.decode(r.tokens)
    assert text.endswith("choice#?")
    assert 'choice#A = "set_volume": ' in text.split("<|im_start|>user")[0]
    assert 'Request: "mute"' in text


def test_samples_reproduce():
    lines = [json.loads(x) for x in SAMPLES.read_text().splitlines()]
    for ex in (x for x in lines if x["kind"] == "route"):
        r = render_route(RouteContext(**ex["context"]), ex["utterance"])
        assert r.tokens == ex["tokens"] and r.choice_pos == ex["choice_pos"]


def test_args_datum_trains_answer_only_on_runtime_prompt():
    """Runtime (DecisionEngine.args) prefills the empty think block; the ARGS datum must weight only answer + im_end."""
    from muselet_train.catalog import skill_by_name
    from muselet_train.datums import args_datums
    from muselet_train.route_render import RouteContext, args_runtime_prompt, base_renderer

    ctx = {"app": "Safari", "focused": "none", "selection": False, "online": True, "last_action": "none"}
    r = {"skill": "change_volume", "context": ctx, "utterance": "turn it up by twenty", "target": "delta=20"}
    d = args_datums([r], "Qwen/Qwen3.5-4B")[0]
    rend = base_renderer("Qwen/Qwen3.5-4B")
    ids = d.model_input.to_ints()
    w = d.loss_fn_inputs["weights"].to_torch().tolist()
    tg = d.loss_fn_inputs["target_tokens"].to_torch().tolist()
    first = next(i for i, x in enumerate(w) if x > 0)
    prompt = args_runtime_prompt(rend, skill_by_name("change_volume"), RouteContext(**ctx), r["utterance"])
    assert ids[:first + 1] == prompt
    assert rend.tokenizer.decode([t for t, x in zip(tg, w) if x > 0]) == "delta=20<|im_end|>"
