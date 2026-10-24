from __future__ import annotations

import torch
import tinker

from brain.generic_decide import GenericRenderer
from brain.generic_decide import _decision


def _sparse(datum: tinker.Datum) -> tinker.Datum:
    if not datum.loss_fn_inputs:
        return datum
    return tinker.Datum(
        model_input=datum.model_input,
        loss_fn_inputs={key: tinker.TensorData.from_torch_sparse(value.to_torch())
                        for key, value in datum.loss_fn_inputs.items()},
    )


def render_question(renderer: GenericRenderer, state: str, question: dict, target: dict[str, float]):
    decision = _decision(state, question)
    labels = [label for label, _ in decision.choices]
    assert len(labels) <= 26, "decision generator exceeded the 26-option cap"
    distribution = {label: max(0.0, float(target.get(label, 0.0))) for label in labels}
    total = sum(distribution.values())
    if total <= 0:
        raise ValueError("target distribution has no mass over rendered labels")
    distribution = {label: value / total for label, value in distribution.items()}
    rendering = renderer.render(decision)
    if len(labels) > renderer.maximum:
        raise ValueError("26-option cap exceeds the renderer maximum; tournament targets are unsupported")
    n_positions = rendering.choice_pos
    target_tokens = torch.zeros((n_positions, len(labels)), dtype=torch.int64)
    target_tokens[-1] = torch.tensor([rendering.label_tokens[label] for label in labels], dtype=torch.int64)
    weights = torch.zeros((n_positions, len(labels)), dtype=torch.float32)
    weights[-1] = torch.tensor([distribution[label] for label in labels], dtype=torch.float32)
    datum = tinker.Datum(
        model_input=tinker.ModelInput.from_ints(rendering.tokens[:n_positions]),
        loss_fn_inputs={
            "target_tokens": tinker.TensorData.from_torch(target_tokens),
            "weights": tinker.TensorData.from_torch(weights),
        },
    )
    if len(labels) > 20:
        datum = _sparse(datum)
    return datum, rendering


def render_records(records: list[dict], model: str = "Qwen/Qwen3.5-4B"):
    renderer = GenericRenderer(model)
    output = []
    for item in records:
        for qid, question in item["questions"].items():
            target = item.get("target", {}).get(qid) or {item["gold"][qid]: 1.0}
            datum, rendering = render_question(renderer, item["state"], question, target)
            output.append({"record_id": item["id"], "qid": qid, "family": item["family"],
                           "datum": datum, "rendering": rendering, "target": target})
    return output
