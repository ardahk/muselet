"""Token-level parity between planner LoRA samples and the brain prompt builder."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from brain.catalog import Catalog
from brain.decision import RouteRenderer
from brain.planner import FEWSHOT_PATH, Planner, history

SAMPLES = Path(__file__).resolve().parents[2] / \
    "training" / "artifacts" / "planner_lora_render_samples.jsonl"
MODEL = "mlx-community/Qwen3.5-4B-4bit"
LOGIN_RE = re.compile(
    r"\b(?:sign\s*in|sign-in|log\s*in|login|password)\b", re.IGNORECASE)


def _snapshot():
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(MODEL, local_files_only=True)
    except Exception:
        return None


_SNAP = _snapshot()
pytestmark = pytest.mark.skipif(
    _SNAP is None, reason="Qwen3.5-4B tokenizer not cached")


@pytest.fixture(scope="module")
def planners():
    catalog = Catalog.load()
    rr = RouteRenderer(_SNAP, catalog)
    engine = SimpleNamespace(
        model_path=_SNAP,
        model=None,
        tokenizer=rr.tokenizer,
        body=None,
        lm_head=None,
        rr=rr,
        catalog=catalog,
    )
    return (
        Planner(_SNAP, catalog, engine=engine, few_shot=None, retrieval_k=0),
        Planner(_SNAP, catalog, engine=engine, few_shot=FEWSHOT_PATH,
                retrieval_k=0),
    )


def _samples():
    rows = [json.loads(line) for line in SAMPLES.read_text().splitlines()
            if line.strip()]
    assert rows[0]["meta"] == {
        "demos": "jonsnov/muselet-planner-demos-v1@9453ff6",
        "tokenizer": MODEL,
        "few_shot": None,
        "retrieval_k": 0,
    }
    return rows[1:]


def _login_page(observation):
    window = re.match(
        r'^app: [^|]+ \| window: "((?:[^"\\]|\\.)*)"', observation)
    title = window[1] if window else ""
    return bool(LOGIN_RE.search(f"{title}\n{observation}"))


def test_sample_tokens_match_brain_planner(planners):
    planner, default_planner = planners
    rows = _samples()
    im_end_id = planner.tokenizer.convert_tokens_to_ids("<|im_end|>")

    for row in rows:
        state = row["state"]
        prompt = planner.prompt_tokens(
            state["goal"],
            state["observation"],
            history(state.get("last_batch"), "dsl"),
            None,
            state.get("script_output"),
            _login_page(state["observation"]),
        )

        assert row["n_prompt"] == len(prompt), row["id"]
        assert row["tokens"][:row["n_prompt"]] == prompt, row["id"]
        expected_completion = planner.tokenizer.encode(
            row["completion"], add_special_tokens=False) + [im_end_id]
        assert row["tokens"][row["n_prompt"]:] == expected_completion, row["id"]

        default_prompt = default_planner.prompt_tokens(
            state["goal"],
            state["observation"],
            history(state.get("last_batch"), "dsl"),
            None,
            state.get("script_output"),
            _login_page(state["observation"]),
        )
        assert len(default_prompt) > len(prompt), row["id"]
