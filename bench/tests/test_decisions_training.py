import random

from training.decisions.calibrate import fit_temperatures
from training.decisions.train import batches, datum_tokens, estimate, stratified_subset
from training.decisions.route.loader import RouteExport, sample_route_args


def test_trainer_batches_preserve_rows_and_cover_each_item_once():
    rows = [{"tokens": [index, index + 1], "family": f"f{index % 2}",
             "type": ("choice", "noul", "score")[index % 3]} for index in range(17)]
    result = batches(rows, 4, 12)
    assert [len(batch) for batch in result] == [4, 4, 4, 4, 1]
    assert {row["tokens"][0] for batch in result for row in batch} == set(range(17))
    assert sum(len(datum_tokens(row)) for batch in result for row in batch) == 34


def test_trainer_batches_mix_task_types_without_dropping_datums():
    rows = [
        {"kind": kind, "tokens": [index]}
        for kind in ("generic", "route", "args")
        for index in range(80)
    ]
    result = batches(rows, 24, 41)
    assert sum(len(batch) for batch in result) == len(rows)
    assert all({"generic", "route", "args"} <= {row["kind"] for row in batch}
               for batch in result[:-1])


def test_it2b_recipe_is_deterministic_and_uses_60_40_train_pools():
    export = RouteExport(
        route=[{"id": f"r{i}", "split": "train"} for i in range(20)]
        + [{"id": "r-val", "split": "val"}],
        args=[{"id": f"a{i}", "split": "train"} for i in range(20)]
        + [{"id": "a-val", "split": "val"}],
        meta={},
    )
    route, args = sample_route_args(export, 7)
    again_route, again_args = sample_route_args(export, 7)
    rng = random.Random(0)
    expected_route = rng.sample(export.route[:-1], 4)
    expected_args = rng.sample(export.args[:-1], 3)
    assert route == expected_route
    assert args == expected_args
    assert (route, args) == (again_route, again_args)


def test_trainer_subset_and_cost_estimate_are_stratified():
    rows = [{"tokens": [i], "family": f"f{i % 2}",
             "type": ("choice", "noul", "score")[i % 3]} for i in range(60)]
    selected = stratified_subset(rows, 12, 19)
    assert len(selected) == 12
    assert len({row["family"] for row in selected}) == 2
    assert len({row["type"] for row in selected}) == 3
    costs = estimate(selected, rows[:6], epochs=1, eval_every=50, batch_size=4)
    assert costs["train_tokens"] == 12
    assert costs["eval_tokens"] == 6
    assert costs["total_usd"] > 0


def test_calibration_fits_positive_dev_only_temperatures():
    rows = [
        {"logits": [5.0, 0.0], "target": [0.8, 0.2], "gold": 0},
        {"logits": [0.0, 5.0], "target": [0.2, 0.8], "gold": 1},
    ]
    fitted = fit_temperatures(rows)
    assert fitted["temperature_probs"] > 0
    assert fitted["temperature_conf"] > 0
    assert fit_temperatures(rows) == fitted
