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
