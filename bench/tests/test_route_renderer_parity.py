import json
from pathlib import Path

from training.decisions.route.route_render import RouteContext, render_route


ROOT = Path(__file__).resolve().parents[2]


def test_route_renderer_matches_cloud_render_samples():
    samples_path = ROOT / "training/artifacts/route_render_samples.jsonl"
    samples = [
        json.loads(line)
        for line in samples_path.read_text().splitlines()
        if line.strip() and json.loads(line).get("kind") == "route"
    ]
    assert samples
    for sample in samples:
        rendering = render_route(RouteContext(**sample["context"]), sample["utterance"])
        assert rendering.tokens == sample["tokens"]
        assert rendering.choice_pos == sample["choice_pos"]
        assert rendering.label_tokens[sample["label"]] == sample["label_token"]
