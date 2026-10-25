import json
import math
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml" / "src"))

from bench.systemone import cli
from bench.systemone.server import make_server
from brain.generic_decide import _tempered


def test_tempered_matches_softmax_and_sharpens_with_lower_temperature():
    logits = [0.0, 1.0, 2.0]
    weights = [math.exp(value) for value in logits]
    expected = [weight / sum(weights) for weight in weights]
    assert _tempered(logits, 1.0) == pytest.approx(expected)
    assert _tempered(logits, 0.5)[-1] > _tempered(logits, 1.0)[-1]


@pytest.mark.parametrize("backend", ["mlx", "tinker"])
def test_cli_loads_calibration_for_backend(tmp_path, monkeypatch, backend):
    calibration = tmp_path / "calibration.json"
    calibration.write_text(json.dumps({
        "temperature_probs": 0.9,
        "temperature_conf": 0.7,
    }))
    received = {}

    def decider(model_path, **kwargs):
        received.update({"model_path": model_path, **kwargs})
        return object()

    if backend == "mlx":
        from brain import generic_decide

        monkeypatch.setattr(generic_decide, "GenericMLXDecider", decider)
    else:
        from bench.systemone import tinker_backend

        monkeypatch.setattr(tinker_backend, "TinkerDecider", decider)
    monkeypatch.setattr(cli, "serve", lambda *args: None)

    assert cli.main([
        "--backend", backend,
        "--model-path", "model",
        "--calibration", str(calibration),
    ]) == 0
    assert received == {
        "model_path": "model",
        "temperature_probs": 0.9,
        "temperature_conf": 0.7,
    }


def test_cli_rejects_calibration_with_nondefault_temperature(tmp_path):
    calibration = tmp_path / "calibration.json"
    calibration.write_text(json.dumps({
        "temperature_probs": 0.9,
        "temperature_conf": 0.7,
    }))
    with pytest.raises(SystemExit) as error:
        cli.main([
            "--backend", "mlx",
            "--model-path", "model",
            "--calibration", str(calibration),
            "--temperature-probs", "0.8",
        ])
    assert error.value.code == 2


def test_server_uses_decider_confidence_distributions():
    class Distributions(dict):
        confidence_distributions = {"choice": {"a": 0.5, "b": 0.5}}

    class Decider:
        def decide_many(self, _state, _questions):
            return Distributions({"choice": {"a": 0.9, "b": 0.1}})

    server = make_server("127.0.0.1", 0, Decider())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/v1/systemone",
            data=json.dumps({
                "state": "state",
                "questions": {
                    "choice": {
                        "type": "choice",
                        "instructions": "pick",
                        "criteria": {"a": "A", "b": "B"},
                    },
                },
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = json.loads(urllib.request.urlopen(request, timeout=2).read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    answer = response["answers"]["choice"]
    assert answer["probabilities"] == {"a": 0.9, "b": 0.1}
    assert answer["confidence"] == 0.0
