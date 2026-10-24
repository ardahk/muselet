"""SPEC 1.7 export: Tinker sampler checkpoint -> merged bf16 HF model, parity.jsonl, private HF uploads.

  python -m muselet_train.export download --tinker-path tinker://.../sampler_weights/... --name v1
  python -m muselet_train.export merge --name v1
  python -m muselet_train.export parity --tinker-path ... --name v1 [--n 300]
  python -m muselet_train.export upload --dir /data/export/v1/hf --repo jonsnov/muselet-route-4b-v1
MLX conversion + CPU parity: training/scripts/mlx_parity.py (separate env).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from pathlib import Path

import tinker
from huggingface_hub import HfApi
from tinker_cookbook import weights

from muselet_train.catalog import REPO_ROOT
from muselet_train.gen import _load
from muselet_train.route_render import STUDENT_MODEL, RouteContext, render_route
from muselet_train.teacher import chunked_decision

OUT = Path("/data/export")
SAMPLES = REPO_ROOT / "training" / "artifacts" / "route_render_samples.jsonl"


def check_render_samples() -> int:
    """Training renderer must reproduce route_render_samples.jsonl token-for-token (the Mac contract)."""
    rows = [json.loads(x) for x in SAMPLES.read_text().splitlines()[1:] if x.strip()]
    for r in rows:
        got = render_route(RouteContext(**r["context"]), r["utterance"])
        assert got.tokens == r["tokens"] and got.choice_pos == r["choice_pos"], r["utterance"]
    return len(rows)


async def parity(tinker_path: str, name: str, run: str, n: int, seed: int) -> Path:
    print(json.dumps({"render_samples_ok": check_render_samples()}), flush=True)
    val = [r for r in _load(run, "route_dedup.jsonl") if r.get("split") == "val"]
    val = random.Random(seed).sample(val, min(n, len(val)))
    client = tinker.ServiceClient().create_sampling_client(model_path=tinker_path)
    sem = asyncio.Semaphore(32)

    async def one(r):
        rend = render_route(RouteContext(**r["context"]), r["utterance"])
        async with sem:
            probs = await chunked_decision(client, rend)
        return {"utterance": r["utterance"], "label": r["label"], "context": r["context"],
                "tokens": rend.tokens, "choice_pos": rend.choice_pos,
                "label_tokens": dict(rend.label_tokens), "probs": probs}

    rows = await asyncio.gather(*(one(r) for r in val))
    p = OUT / name / "parity.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    return p


def upload(path: str, repo: str) -> str:
    api = HfApi()
    api.create_repo(repo, private=True, exist_ok=True)
    info = api.upload_folder(folder_path=path, repo_id=repo, commit_message="muselet route export")
    return info.oid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["download", "merge", "parity", "upload", "check"])
    ap.add_argument("--tinker-path")
    ap.add_argument("--name", default="v1")
    ap.add_argument("--run", default="v2all")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dir")
    ap.add_argument("--repo")
    a = ap.parse_args()
    d = OUT / a.name
    if a.cmd == "check":
        print(check_render_samples())
    elif a.cmd == "download":
        print(weights.download(tinker_path=a.tinker_path, output_dir=str(d / "adapter")))
    elif a.cmd == "merge":
        weights.build_hf_model(base_model=STUDENT_MODEL, adapter_path=str(d / "adapter"),
                               output_path=str(d / "hf"), trust_remote_code=True)
        print(d / "hf")
    elif a.cmd == "parity":
        print(asyncio.run(parity(a.tinker_path, a.name, a.run, a.n, a.seed)))
    else:
        assert a.repo.startswith("jonsnov/"), "uploads go to private jonsnov/ repos"
        print(json.dumps({"repo": a.repo, "revision": upload(a.dir, a.repo)}))


if __name__ == "__main__":
    main()
