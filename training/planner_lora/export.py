"""Export a Tinker planner checkpoint to a verified MLX 4-bit model."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_MODEL = "Qwen/Qwen3.5-4B"
DEMOS_REVISION = "jonsnov/muselet-planner-demos-v1@9453ff6"
UPLOAD_REPO = "jonsnov/muselet-planner-4b-lora-mlx4"
ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "training" / "reports" / "planner-lora-export.json"
SAMPLES = ROOT / "training" / "artifacts" / "planner_lora_render_samples.jsonl"
TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "chat_template.jinja",
    "generation_config.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
)
EMBEDDING_KEY = "model.language_model.embed_tokens.weight"
EMBEDDING_TOLERANCE = 0.05


def _load_key(d: str, key: str):
    from safetensors.torch import load_file
    idx = Path(d) / "model.safetensors.index.json"
    shard = json.loads(idx.read_text())["weight_map"][key] if idx.exists() else "model.safetensors"
    return shard, load_file(str(Path(d) / shard))


def untie_lm_head(base_model: str, adapter_dir: str, hf_dir: str) -> dict:
    """Qwen3.5-4B ties lm_head to embed_tokens. Tinker's unembed_tokens LoRA changes only the output head, but
    build_hf_model folds it into the tied embed_tokens, which also shifts every input embedding. Restore the
    base input embeddings and write the trained head as a separate lm_head.weight."""
    import torch
    from huggingface_hub import snapshot_download
    from safetensors.torch import load_file, save_file
    cfg = json.loads((Path(adapter_dir) / "adapter_config.json").read_text())
    ad = load_file(str(Path(adapter_dir) / "adapter_model.safetensors"))
    pre = "base_model.model.model.unembed_tokens."
    delta = (ad[pre + "lora_B.weight"].float() @ ad[pre + "lora_A.weight"].float()) * (cfg["lora_alpha"] / cfg["r"])
    key = "model.language_model.embed_tokens.weight"
    base = _load_key(snapshot_download(base_model, allow_patterns=["*.safetensors", "*.json"]), key)[1][key]
    shard, t = _load_key(hf_dir, key)
    err = (t[key].float() - base.float() - delta).abs().max().item()
    t[key] = base
    t["lm_head.weight"] = (base.float() + delta).to(base.dtype)
    save_file(t, str(Path(hf_dir) / shard), metadata={"format": "pt"})
    idx = Path(hf_dir) / "model.safetensors.index.json"
    if idx.exists():
        j = json.loads(idx.read_text())
        j["weight_map"]["lm_head.weight"] = shard
        idx.write_text(json.dumps(j, indent=2))
    c = json.loads((Path(hf_dir) / "config.json").read_text())
    c["tie_word_embeddings"] = False
    if "text_config" in c:
        c["text_config"]["tie_word_embeddings"] = False
    (Path(hf_dir) / "config.json").write_text(json.dumps(c, indent=2))
    return {"folded_delta_max_err": err, "delta_absmax": delta.abs().max().item(),
            "delta_rel_norm": (delta.norm() / base.float().norm()).item(), "dtype": str(base.dtype),
            "torch": torch.__version__}


def checkpoint_step(tinker_path: str, explicit_step: int | None = None) -> int | None:
    if explicit_step is not None:
        return explicit_step
    training_report = ROOT / "training" / "reports" / "planner-lora-v1.json"
    if training_report.exists():
        try:
            report = json.loads(training_report.read_text())
            for checkpoint in report.get("ckpts", []):
                if checkpoint.get("path") == tinker_path:
                    return checkpoint.get("step")
        except (OSError, json.JSONDecodeError):
            pass
    match = re.search(r"(?:step|[-_])(\d+)(?:/)?$", tinker_path)
    return int(match[1]) if match else None


def _weight_keys(directory: Path) -> list[str]:
    index = directory / "model.safetensors.index.json"
    if index.exists():
        return list(json.loads(index.read_text())["weight_map"])
    from safetensors import safe_open
    keys = []
    for path in sorted(directory.glob("*.safetensors")):
        with safe_open(str(path), framework="pt", device="cpu") as weights:
            keys.extend(weights.keys())
    return keys


def _tensor_file(directory: Path, key: str) -> Path:
    index = directory / "model.safetensors.index.json"
    if index.exists():
        return directory / json.loads(index.read_text())["weight_map"][key]
    from safetensors import safe_open
    for path in sorted(directory.glob("*.safetensors")):
        with safe_open(str(path), framework="pt", device="cpu") as weights:
            if key in weights.keys():
                return path
    raise KeyError(f"{key} not found in {directory}")


def compare_embeddings(base_dir: Path, mlx_dir: Path) -> dict:
    import mlx.core as mx
    import torch
    from safetensors import safe_open

    mlx_keys = [key for key in _weight_keys(mlx_dir)
                if key.endswith("embed_tokens.weight")]
    if len(mlx_keys) != 1:
        raise AssertionError(f"expected one MLX embed_tokens weight, found {mlx_keys}")
    mlx_key = mlx_keys[0]
    scales_key = mlx_key.removesuffix(".weight") + ".scales"
    biases_key = mlx_key.removesuffix(".weight") + ".biases"
    keys = set(_weight_keys(mlx_dir))
    quantized = scales_key in keys
    base_file = _tensor_file(base_dir, EMBEDDING_KEY)
    mlx_file = _tensor_file(mlx_dir, mlx_key)
    max_abs_error = 0.0
    elements = 0
    config = json.loads((mlx_dir / "config.json").read_text())
    quantization = config.get("quantization_config", {})
    group_size = quantization.get("group_size", 64)
    bits = quantization.get("bits", 4)
    mode = quantization.get("mode", "affine")
    with safe_open(str(base_file), framework="pt", device="cpu") as base_weights, \
            safe_open(str(mlx_file), framework="pt", device="cpu") as mlx_weights:
        base = base_weights.get_slice(EMBEDDING_KEY)
        mlx = mlx_weights.get_slice(mlx_key)
        scales = mlx_weights.get_slice(scales_key) if quantized else None
        biases = (mlx_weights.get_slice(biases_key)
                  if quantized and biases_key in keys else None)
        if not quantized and base.get_shape() != mlx.get_shape():
            raise AssertionError(
                f"embedding shape mismatch: {base.get_shape()} vs {mlx.get_shape()}")
        rows = base.get_shape()[0]
        for start in range(0, rows, 256):
            end = min(start + 256, rows)
            reference = mx.array(base[start:end].float().numpy())
            if quantized:
                dequantized = mx.dequantize(
                    mx.array(mlx[start:end].numpy()),
                    mx.array(scales[start:end].float().numpy()),
                    (mx.array(biases[start:end].float().numpy())
                     if biases is not None else None),
                    group_size=group_size,
                    bits=bits,
                    mode=mode,
                    dtype=mx.float32,
                )
            else:
                dequantized = mx.array(mlx[start:end].float().numpy())
            difference = mx.abs(reference - dequantized.astype(mx.float32))
            mx.eval(difference)
            max_abs_error = max(max_abs_error, difference.max().item())
            elements += difference.size
    return {
        "ok": max_abs_error <= EMBEDDING_TOLERANCE,
        "base_key": EMBEDDING_KEY,
        "mlx_key": mlx_key,
        "method": "dequantized" if quantized else "direct",
        "quantization": (
            {"group_size": group_size, "bits": bits, "mode": mode}
            if quantized else None),
        "max_abs_error": max_abs_error,
        "tolerance": EMBEDDING_TOLERANCE,
        "elements": elements,
        "torch": torch.__version__,
    }


def _config_checks(directory: Path) -> dict:
    config = json.loads((directory / "config.json").read_text())
    root_untied = config.get("tie_word_embeddings") is False
    text_config = config.get("text_config")
    text_untied = text_config is None or text_config.get("tie_word_embeddings") is False
    keys = _weight_keys(directory)
    head_keys = [key for key in keys if key.endswith("lm_head.weight")]
    return {
        "tie_word_embeddings_false": root_untied and text_untied,
        "root_tie_word_embeddings": config.get("tie_word_embeddings"),
        "text_config_tie_word_embeddings": (
            text_config.get("tie_word_embeddings") if text_config else None),
        "lm_head_present": bool(head_keys),
        "lm_head_keys": head_keys,
    }


def _copy_tokenizer_files(base_dir: Path, destinations: list[Path]) -> list[str]:
    copied = []
    for name in TOKENIZER_FILES:
        source = base_dir / name
        if not source.is_file():
            continue
        copied.append(name)
        for destination in destinations:
            shutil.copy2(source, destination / name)
    if "tokenizer.json" not in copied or "tokenizer_config.json" not in copied:
        raise FileNotFoundError("base model snapshot is missing tokenizer files")
    return copied


def smoke_decode(mlx_dir: Path) -> list[dict]:
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import generate_step

    model, tokenizer = load(str(mlx_dir))
    rows = [json.loads(line) for line in SAMPLES.read_text().splitlines()
            if line.strip()][1:3]
    stop_ids = {tokenizer.eos_token_id}
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    if im_end_id is not None:
        stop_ids.add(im_end_id)
    outputs = []
    for row in rows:
        prompt = mx.array(row["tokens"][:row["n_prompt"]], dtype=mx.int32)
        generated = []
        for token, _ in generate_step(prompt, model, max_tokens=40):
            token = int(token)
            generated.append(token)
            if token in stop_ids:
                break
        outputs.append({
            "id": row["id"],
            "completion": row["completion"],
            "mlx_greedy": tokenizer.decode(generated),
            "tokens_generated": len(generated),
        })
    return outputs


def upload(mlx_dir: Path, tinker_path: str, step: int | None) -> str:
    from huggingface_hub import HfApi

    repo = UPLOAD_REPO
    assert repo == "jonsnov/muselet-planner-4b-lora-mlx4"
    if step is None:
        raise ValueError("checkpoint step is required for the upload README")
    (mlx_dir / "README.md").write_text(
        f"# Muselet planner Qwen3.5-4B LoRA (MLX 4-bit)\n\n"
        f"- Base model: `{BASE_MODEL}`\n"
        f"- Training data: `{DEMOS_REVISION}`\n"
        f"- Tinker checkpoint: `{tinker_path}` (step {step})\n"
        f"- Training used no few-shot examples.\n"
        f"- `lm_head` is untied from the input embeddings.\n"
    )
    api = HfApi()
    api.create_repo("jonsnov/muselet-planner-4b-lora-mlx4", private=True, exist_ok=True)
    info = api.upload_folder(
        folder_path=str(mlx_dir),
        repo_id="jonsnov/muselet-planner-4b-lora-mlx4",
        commit_message="Export Muselet planner 4B LoRA as MLX 4-bit",
    )
    return info.oid


def export(tinker_path: str, out: Path, step: int | None = None,
           do_upload: bool = False) -> dict:
    from huggingface_hub import snapshot_download
    from tinker_cookbook import weights
    from mlx_lm import convert as mlx_convert

    out = out.expanduser().resolve()
    data_root = (Path.home() / "data").resolve()
    if not out.is_relative_to(data_root):
        raise ValueError(f"export output must be under {data_root}: {out}")
    adapter_dir = out / "adapter"
    hf_dir = out / "hf"
    mlx_dir = out / "mlx4"
    out.mkdir(parents=True, exist_ok=True)

    weights.download(tinker_path=tinker_path, output_dir=str(adapter_dir))
    weights.build_hf_model(
        base_model=BASE_MODEL,
        adapter_path=str(adapter_dir),
        output_path=str(hf_dir),
        trust_remote_code=True,
    )
    untie_checks = untie_lm_head(BASE_MODEL, str(adapter_dir), str(hf_dir))

    base_snapshot = Path(snapshot_download(
        BASE_MODEL,
        allow_patterns=["*.safetensors", "*.json", "*.jinja"],
    ))
    tokenizer_files = _copy_tokenizer_files(base_snapshot, [hf_dir])
    mlx_convert(
        str(hf_dir),
        mlx_path=str(mlx_dir),
        quantize=True,
        q_bits=4,
        q_group_size=64,
    )
    tokenizer_files = _copy_tokenizer_files(base_snapshot, [mlx_dir])

    hf_checks = _config_checks(hf_dir)
    mlx_checks = _config_checks(mlx_dir)
    if (not hf_checks["tie_word_embeddings_false"]
            or hf_checks["text_config_tie_word_embeddings"] is not False
            or not hf_checks["lm_head_present"]):
        raise AssertionError(f"HF untied-head check failed: {hf_checks}")
    if not mlx_checks["tie_word_embeddings_false"] or not mlx_checks["lm_head_present"]:
        raise AssertionError(f"MLX untied-head check failed: {mlx_checks}")
    embedding_check = compare_embeddings(base_snapshot, mlx_dir)
    if not embedding_check["ok"]:
        raise AssertionError(f"MLX input embeddings differ from base: {embedding_check}")

    smoke_outputs = smoke_decode(mlx_dir)
    hf_revision = upload(mlx_dir, tinker_path, step) if do_upload else None
    report = {
        "tinker_path": tinker_path,
        "step": step,
        "base_model": BASE_MODEL,
        "base_model_revision": base_snapshot.name,
        "paths": {
            "adapter": str(adapter_dir),
            "hf": str(hf_dir),
            "mlx4": str(mlx_dir),
        },
        "checks": {
            "untie": untie_checks,
            "hf": hf_checks,
            "mlx4": mlx_checks,
            "input_embeddings_equal_base": embedding_check,
            "tokenizer_files": tokenizer_files,
        },
        "smoke_outputs": smoke_outputs,
        "hf_smoke": {
            "status": "skipped",
            "reason": "4B PyTorch CPU greedy comparison is optional and may be slow",
        },
        "hf_revision": hf_revision,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if hf_revision:
        print(f"HF commit revision: {hf_revision}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tinker-path", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--step", type=int)
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    step = checkpoint_step(args.tinker_path, args.step)
    export(args.tinker_path, args.out, step=step, do_upload=args.upload)


if __name__ == "__main__":
    main()
