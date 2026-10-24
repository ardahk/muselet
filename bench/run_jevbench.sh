#!/usr/bin/env bash
set -euo pipefail

PIN=609a664e81f46e03731600bd7bd9f1b7a61257c5
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-ml/.venv/bin/python}"
if [[ "$PY" == */* && "$PY" != /* ]]; then
  PY="$ROOT/$PY"
elif [[ "$PY" != */* ]]; then
  resolved_py="$(command -v "$PY" || true)"
  if [[ -n "$resolved_py" ]]; then PY="$resolved_py"; fi
fi
if [[ ! -x "$PY" ]]; then
  echo "$PY not found; run: uv sync --project ml (or set PY=...)" >&2
  exit 2
fi
URL=""
MODEL=muselet
LIMIT=""
START_SHIM=0
BACKEND=fake
MODEL_PATH=""
OUT_ROOT="$ROOT/runs/bench/jevbench"

usage() {
  echo "Usage: $0 [--url URL | --start-shim] [--backend fake|mlx] [--model-path PATH] [--model NAME] [--limit N] [--out-root DIR]"
}

while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --url) URL="$2"; shift 2 ;;
    --start-shim) START_SHIM=1; shift ;;
    --backend) BACKEND="$2"; shift 2 ;;
    --model-path) MODEL_PATH="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --out-root) OUT_ROOT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
if ((START_SHIM)) && [[ -n "$URL" ]]; then echo "Use either --url or --start-shim" >&2; exit 2; fi
if ((!START_SHIM)) && [[ -z "$URL" ]]; then echo "Pass --url or --start-shim" >&2; exit 2; fi

if [[ -n "${JEVBENCH_DIR:-}" ]]; then
  JEV="$JEVBENCH_DIR"
  [[ "$(git -C "$JEV" rev-parse HEAD)" == "$PIN" ]] || { echo "JEVBENCH_DIR must be at $PIN" >&2; exit 2; }
else
  SRC="$ROOT/runs/bench/_src/jevbench"
  mkdir -p "$(dirname "$SRC")"
  if [[ ! -d "$SRC/.git" ]]; then
    git clone --no-checkout https://github.com/fstandhartinger/jevbench.git "$SRC"
  fi
  git -C "$SRC" fetch --quiet origin "$PIN"
  git -C "$SRC" checkout --quiet "$PIN"
  JEV="$SRC"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$OUT_ROOT/$STAMP"
mkdir -p "$RUN"
SHIM_PID=""
cleanup() {
  if [[ -n "$SHIM_PID" ]]; then kill "$SHIM_PID" 2>/dev/null || true; wait "$SHIM_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
if ((START_SHIM)); then
  shim_args=(--host 127.0.0.1 --port 8793 --backend "$BACKEND" --model-name "$MODEL")
  if [[ -n "$MODEL_PATH" ]]; then shim_args+=(--model-path "$MODEL_PATH"); fi
  PYTHONPATH="$ROOT:$ROOT/ml/src${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m bench.systemone.cli "${shim_args[@]}" >"$RUN/shim.log" 2>&1 &
  SHIM_PID=$!
  URL=http://127.0.0.1:8793
  for _ in $(seq 1 100); do
    if "$PY" - "$URL/v1/models" <<'PY'
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1], timeout=1).read()
except Exception:
    raise SystemExit(1)
PY
    then break; fi
    kill -0 "$SHIM_PID" || { echo "shim exited; see $RUN/shim.log" >&2; exit 1; }
    sleep 0.1
  done
fi
printf '%q ' "$0" "$@" >"$RUN/command.txt"
printf '\nPython: %s\nJevBench commit: %s\nURL: %s\nModel: %s\n' "$PY" "$PIN" "$URL" "$MODEL" >>"$RUN/command.txt"
for split in original easy hard; do
  dir="$RUN/$split"
  mkdir -p "$dir/raw"
  args=(run --tasks "$JEV/datasets/public/$split.jsonl" --adapter typesafe --endpoint "$URL"
    --key-env "" --model "$MODEL" --cost-basis local_on_device --reserve-usd 0
    --results "$dir/results.jsonl" --raw-dir "$dir/raw" --ledger "$dir/ledger.jsonl"
    --manifest "$dir/manifest.json")
  if [[ -n "$LIMIT" ]]; then args+=(--limit "$LIMIT"); fi
  PYTHONPATH="$JEV" python3 -m jevbench.cli "${args[@]}"
  PYTHONPATH="$JEV" python3 -m jevbench.cli summarize --tasks "$JEV/datasets/public/$split.jsonl" \
    --results "$dir/results.jsonl" --ledger "$dir/ledger.jsonl" >"$dir/jevbench-summary.txt"
done
python3 "$ROOT/bench/jevbench_summary.py" --jevbench-dir "$JEV" --run-dir "$RUN"
echo "$RUN"
