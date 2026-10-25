import json
from pathlib import Path

import pytest

from training.decisions.route.catalog import options
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
    n_now = len(options())
    for sample in samples:
        n_sample = sum(
            line.startswith("choice#") and " = " in line
            for line in sample["text"].splitlines()
        )
        if n_sample != n_now:
            pytest.skip(
                f"route_render_samples.jsonl predates skills/catalog.json "
                f"({n_sample} vs {n_now} options); regenerate in the router lane"
            )
        rendering = render_route(RouteContext(**sample["context"]), sample["utterance"])
        assert rendering.tokens == sample["tokens"]
        assert rendering.choice_pos == sample["choice_pos"]
        assert rendering.label_tokens[sample["label"]] == sample["label_token"]
