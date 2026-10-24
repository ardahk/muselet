"""Export a Tinker decisions adapter to a calibrated MLX 4-bit model."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_MODEL = "Qwen/Qwen3.5-4B"
NAME = "dec-full-lr2e4"
CALIBRATION = ROOT / "training/decisions/reports/snapshots/dec-full-lr2e4.calibration.json"
UNEMBED_PREFIX = "base_model.model.model.unembed_tokens."
EMBED_KEY = "model.language_model.embed_tokens.weight"


def _export_dir(name: str) -> Path:
    return ROOT / "runs" / "decisions" / "export" / name


def _load_key(directory: str | Path, key: str):
    from safetensors.torch import load_file

    path = Path(directory)
    index = path / "model.safetensors.index.json"
    shard = (
        json.loads(index.read_text())["weight_map"][key]
        if index.exists()
        else "model.safetensors"
    )
    return shard, load_file(str(path / shard))


def untie_lm_head(base_model: str, adapter_dir: str | Path, hf_dir: str | Path) -> dict:
    """Restore the input embeddings and write the trained output head separately."""
    import torch
    from huggingface_hub import snapshot_download
    from safetensors.torch import load_file, save_file

    adapter_dir = Path(adapter_dir)
    hf_dir = Path(hf_dir)
    adapter_config = json.loads((adapter_dir / "adapter_config.json").read_text())
    adapter = load_file(str(adapter_dir / "adapter_model.safetensors"))

    pairs = []
    for key in adapter:
        if key.endswith("lora_A.weight"):
            prefix = key.removesuffix("lora_A.weight")
            if "unembed_tokens." in prefix and prefix + "lora_B.weight" in adapter:
                pairs.append(prefix)
    if UNEMBED_PREFIX in pairs:
        unembed_prefix = UNEMBED_PREFIX
    elif len(pairs) == 1:
        unembed_prefix = pairs[0]
    elif len(pairs) > 1:
        raise ValueError(f"multiple unembed_tokens LoRA pairs found: {pairs}")
    elif any("unembed_tokens" in key for key in adapter):
        raise ValueError("unembed_tokens adapter keys exist without a matching LoRA A/B pair")
    else:
        unembed_prefix = None

    base_dir = snapshot_download(base_model, allow_patterns=["*.safetensors", "*.json"])
    _, base_tensors = _load_key(base_dir, EMBED_KEY)
    base = base_tensors[EMBED_KEY]
    shard, merged = _load_key(hf_dir, EMBED_KEY)
    if unembed_prefix is None:
        delta = torch.zeros_like(base, dtype=torch.float32)
        folded_delta_max_err = (merged[EMBED_KEY].float() - base.float()).abs().max().item()
    else:
        rank = adapter_config["r"]
        scale = adapter_config["lora_alpha"] / rank
        delta = (
            adapter[unembed_prefix + "lora_B.weight"].float()
            @ adapter[unembed_prefix + "lora_A.weight"].float()
        ) * scale
        if delta.shape != base.shape:
            raise ValueError(
                f"unembed_tokens LoRA delta shape {tuple(delta.shape)} does not match "
                f"base embedding shape {tuple(base.shape)}"
            )
        folded_delta_max_err = (
            merged[EMBED_KEY].float() - base.float() - delta
        ).abs().max().item()

    merged[EMBED_KEY] = base
    merged["lm_head.weight"] = (base.float() + delta).to(base.dtype)
    save_file(merged, str(hf_dir / shard), metadata={"format": "pt"})

    index = hf_dir / "model.safetensors.index.json"
    if index.exists():
        metadata = json.loads(index.read_text())
        metadata["weight_map"]["lm_head.weight"] = shard
        index.write_text(json.dumps(metadata, indent=2) + "\n")

    config_path = hf_dir / "config.json"
    config = json.loads(config_path.read_text())
    config["tie_word_embeddings"] = False
    if "text_config" in config:
        config["text_config"]["tie_word_embeddings"] = False
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    base_norm = base.float().norm().item()
    stats = {
        "folded_delta_max_err": folded_delta_max_err,
        "delta_absmax": delta.abs().max().item(),
        "delta_rel_norm": delta.norm().item() / base_norm,
    }
    if unembed_prefix is None:
        stats.update({"unembed_lora_found": False, "unembed_lora_prefix": None})
    else:
        stats.update({"unembed_lora_found": True, "unembed_lora_prefix": unembed_prefix})
    return stats


def download(tinker_path: str, name: str = NAME) -> Path:
    from tinker_cookbook import weights

    adapter_dir = _export_dir(name) / "adapter"
    weights.download(tinker_path=tinker_path, output_dir=str(adapter_dir))
    return adapter_dir


def merge(name: str = NAME) -> dict:
    from tinker_cookbook import weights

    output_dir = _export_dir(name)
    adapter_dir = output_dir / "adapter"
    hf_dir = output_dir / "hf"
    weights.build_hf_model(
        base_model=BASE_MODEL,
        adapter_path=str(adapter_dir),
        output_path=str(hf_dir),
        trust_remote_code=True,
    )
    return untie_lm_head(BASE_MODEL, adapter_dir, hf_dir)


def _validate_mlx_export(mlx_dir: Path) -> dict:
    config = json.loads((mlx_dir / "config.json").read_text())
    architecture = "Qwen3_5ForConditionalGeneration"
    if architecture not in config.get("architectures", []):
        raise ValueError(f"MLX config is missing expected architecture {architecture}")
    if config.get("tie_word_embeddings") is not False:
        raise ValueError("MLX config must set tie_word_embeddings=false")
    if "text_config" in config and config["text_config"].get("tie_word_embeddings") is not False:
        raise ValueError("MLX text_config must set tie_word_embeddings=false")

    expected_quantization = {"group_size": 64, "bits": 4, "mode": "affine"}
    quantization = config.get("quantization")
    if quantization is None:
        quantization = config.get("quantization_config")
    if quantization != expected_quantization:
        raise ValueError(f"unexpected MLX quantization config: {quantization}")

    index = mlx_dir / "model.safetensors.index.json"
    if not index.exists():
        raise ValueError("MLX conversion did not produce model.safetensors.index.json")
    weight_map = json.loads(index.read_text())["weight_map"]
    lm_head_weight = next(
        (key for key in weight_map if key == "lm_head.weight" or key.endswith(".lm_head.weight")),
        None,
    )
    if lm_head_weight is None:
        raise ValueError("MLX safetensors index is missing lm_head.weight")
    lm_head_prefix = lm_head_weight.removesuffix(".weight")
    quantized_keys = (f"{lm_head_prefix}.scales", f"{lm_head_prefix}.biases")
    present_quantized_keys = [key for key in quantized_keys if key in weight_map]
    missing = []
    if present_quantized_keys and len(present_quantized_keys) != len(quantized_keys):
        missing.extend(key for key in quantized_keys if key not in weight_map)
    if missing:
        raise ValueError(f"MLX safetensors index is missing lm_head keys: {missing}")
    return {
        "architecture": architecture,
        "quantization": quantization,
        "lm_head_keys": [lm_head_weight, *present_quantized_keys],
    }


def convert(name: str = NAME, mlx_python: str = sys.executable) -> dict:
    output_dir = _export_dir(name)
    hf_dir = output_dir / "hf"
    mlx_dir = output_dir / "mlx4"
    subprocess.run(
        [
            mlx_python,
            "-m",
            "mlx_lm",
            "convert",
            "--hf-path",
            str(hf_dir),
            "--mlx-path",
            str(mlx_dir),
            "--quantize",
            "--q-bits",
            "4",
            "--q-group-size",
            "64",
            "--q-mode",
            "affine",
        ],
        check=True,
    )
    validation = _validate_mlx_export(mlx_dir)
    shutil.copyfile(CALIBRATION, mlx_dir / "calibration.json")
    return {
        "mlx_dir": str(mlx_dir),
        "calibration": str(mlx_dir / "calibration.json"),
        **validation,
    }


def upload(directory: str | Path, repo: str) -> dict:
    if not repo.startswith("jonsnov/"):
        raise ValueError("uploads go to private jonsnov/ repos")

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id=repo, private=True, exist_ok=True)
    info = api.upload_folder(
        folder_path=str(directory),
        repo_id=repo,
        commit_message="Export calibrated decisions model",
    )
    return {"repo": repo, "revision": info.oid}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("download", "merge", "convert", "upload"))
    parser.add_argument("--name", default=NAME)
    parser.add_argument("--tinker-path")
    parser.add_argument("--mlx-python", default=sys.executable)
    parser.add_argument("--dir")
    parser.add_argument("--repo")
    args = parser.parse_args(argv)

    if args.command == "download":
        if not args.tinker_path:
            parser.error("--tinker-path is required for download")
        result = {"adapter_dir": str(download(args.tinker_path, args.name))}
    elif args.command == "merge":
        result = merge(args.name)
    elif args.command == "convert":
        result = convert(args.name, args.mlx_python)
    else:
        if not args.dir or not args.repo:
            parser.error("--dir and --repo are required for upload")
        try:
            result = upload(args.dir, args.repo)
        except ValueError as exc:
            parser.error(str(exc))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
