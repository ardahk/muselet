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

from muselet_train import datums as D
from muselet_train.catalog import REPO_ROOT
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


async def parity(tinker_path: str, run: str, teacher_files: tuple[str, ...], n: int, seed: int, out: Path) -> Path:
    """Held-out route items (final labels after the lead's A1 rules) with the trained Tinker sampler's
    distribution over the 41 choice ids, for the Mac (Metal) MLX parity test."""
    print(json.dumps({"render_samples_ok": check_render_samples()}), flush=True)
    val = [it for it in D.route_items(run, teacher_files) if it.split == "val"]
    val = random.Random(seed).sample(val, min(n, len(val)))
    client = tinker.ServiceClient().create_sampling_client(model_path=tinker_path)
    sem = asyncio.Semaphore(32)

    async def one(it):
        rend = render_route(RouteContext(**it.context), it.utterance)
        async with sem:
            probs = await chunked_decision(client, rend)
        return {"utterance": it.utterance, "label": it.label, "context": it.context,
                "tokens": rend.tokens, "choice_pos": rend.choice_pos,
                "choice_ids": dict(rend.label_tokens), "tinker_probs": probs}

    rows = await asyncio.gather(*(one(it) for it in val))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    return out


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
    ap.add_argument("--teacher-files", nargs="*", default=[])
    ap.add_argument("--out", default=str(REPO_ROOT / "training" / "artifacts" / "parity_300.jsonl"))
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
        print(asyncio.run(parity(a.tinker_path, a.run, tuple(a.teacher_files), a.n, a.seed, Path(a.out))))
    else:
        assert a.repo.startswith("jonsnov/"), "uploads go to private jonsnov/ repos"
        print(json.dumps({"repo": a.repo, "revision": upload(a.dir, a.repo)}))


if __name__ == "__main__":
    main()
