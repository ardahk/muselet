#!/usr/bin/env bash
# Hobby setup for Apple Silicon Macs. Downloads pinned model files, clones/builds the pinned macos-use server, builds Swift tools.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data models vendor
python3 -m venv .venv
.venv/bin/pip install -q "mlx==0.32.3" "mlx-lm==0.31.3" "transformers==5.17.0" "tokenizers==0.23.2" "huggingface-hub==1.33.0" \
  "numpy==2.5.3" "safetensors==0.8.0"
# FP32 Instruct weights (sha256 d0899e0a...); skipped if already present
[ -f models/hobbylm-1B-instruct/model.safetensors ] || .venv/bin/hf download harims95/hobbylm-1B-instruct \
  --revision 8a90f6eb6a3d7c7eb952fd01b512a406821366ab --local-dir models/hobbylm-1B-instruct
# MLX runtime (executed code) + tokenizer, pinned revision; the 3.7 GB MLX weights are skipped (Hobby runs FP32 + adapter)
[ -d models/hobbylm-1B-mlx/runtime ] || .venv/bin/hf download harims95/hobbylm-1B-mlx \
  --revision a2192174572dca075f8378db70cb3e8e70bfe521 --local-dir models/hobbylm-1B-mlx \
  --include 'runtime/*' --include '*.json' --include '*.txt'   # one --include per pattern; extra bare names would be read as files
[ -d models/hobbylm-1B-mlx/runtime/mlx_hobbylm ] || { echo "MLX runtime download failed (models/hobbylm-1B-mlx/runtime)" >&2; exit 1; }
# macos-use (Business Source License 1.1, see its LICENSE), pinned commit
[ -d vendor/mcp-server-macos-use ] || git clone https://github.com/mediar-ai/mcp-server-macos-use vendor/mcp-server-macos-use
git -C vendor/mcp-server-macos-use checkout -q 205c8880e8c06fa96a3e3a859e6edca728eb6c47
(cd vendor/mcp-server-macos-use && swift build -c release)
# small Swift tools: checkers and system controls
for t in calc_checker brightness media_key checker; do swiftc -O hobby/$t.swift -o data/$t; done
echo "Done. Grant Accessibility to your terminal app, then: .venv/bin/python hobby/hobby_demo.py r4"
