#!/usr/bin/env bash
# Waits for each model's HF download to finish, then runs bench/speed_lab.py on it.
# A repo counts as done when its snapshot has all weight files from
# model.safetensors.index.json (or a single model.safetensors) and no
# *.incomplete blobs remain.
set -u
ROOT=/Users/arda/cal13.0
PY="$ROOT/ml/.venv/bin/python"
RESULTS=runs/speedlab/results.jsonl
MODELS="Qwen3.5-0.8B-4bit Qwen3.5-4B-4bit Qwen3.5-2B-4bit Qwen3.5-0.8B-8bit Qwen3.5-9B-4bit Qwen3.6-35B-A3B-4bit"
mkdir -p "$ROOT/runs/speedlab"

is_done() {
  "$PY" - "$1" <<'EOF'
import glob, json, os, sys
d = os.path.expanduser(f"~/.cache/huggingface/hub/models--mlx-community--{sys.argv[1]}")
snaps = glob.glob(os.path.join(d, "snapshots", "*"))
if not snaps:
    sys.exit(1)
snap = snaps[0]
import time
if any(time.time() - os.path.getmtime(p) < 120 for p in glob.glob(os.path.join(d, "blobs", "*.incomplete"))):
    sys.exit(1)
idx = os.path.join(snap, "model.safetensors.index.json")
if os.path.exists(idx):
    files = set(json.load(open(idx))["weight_map"].values())
elif os.path.exists(os.path.join(snap, "model.safetensors")):
    files = {"model.safetensors"}
else:
    sys.exit(1)
for f in files:
    p = os.path.join(snap, f)
    if not (os.path.exists(p) and os.path.getsize(p) > 0):
        sys.exit(1)
sys.exit(0)
EOF
}

for name in $MODELS; do
  repo="mlx-community/$name"
  log="$ROOT/runs/speedlab/$name.log"
  echo "[watcher] waiting for $repo $(date)" | tee -a "$log"
  until is_done "$name"; do sleep 20; done
  echo "[watcher] $repo download complete, benchmarking $(date)" | tee -a "$log"
  (cd "$ROOT" && "$ROOT/ml/.venv/bin/python" bench/speed_lab.py \
      --models "$repo" --runs 7 --out "$RESULTS") >> "$log" 2>&1
  echo "[watcher] $repo bench rc=$? $(date)" | tee -a "$log"
done
echo "[watcher] ALL DONE $(date)"
