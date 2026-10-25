#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PY:-ml/.venv/bin/python}"
if [[ "$PY" == */* && "$PY" != /* ]]; then
  PY="$ROOT/$PY"
elif [[ "$PY" != */* ]]; then
  PY="$(command -v "$PY")"
fi
exec "$PY" -m bench.typed_decisions "$@"
