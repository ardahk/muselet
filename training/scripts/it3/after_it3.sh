#!/usr/bin/env bash
set -uo pipefail
cd ~/repos/muselet/training
UV=~/.local/bin/uv
export MUSELET_CATALOG=$PWD/artifacts/catalog_v3.json
while [ ! -f /data/train/it3/checkpoints.json ]; do sleep 20; done
SP=$(python3 -c "import json;print([c['path'] for c in json.load(open('/data/train/it3/checkpoints.json')) if c['kind']=='sampler'][-1])")
echo "SP=$SP"
( for s in route_v2 route_v1; do $UV run python -m muselet_train.eval_route --tinker-path "$SP" --set $s --name it3; done
  $UV run python -m muselet_train.eval_route --tinker-path "$SP" --set items --items /data/gen/v3m/val_items.jsonl --tag val3 --name it3
  echo EVALS_DONE ) > /data/train/logs/eval_it3.log 2>&1 &
/data/train/post_it3.sh "$SP" > /data/train/logs/post_it3.log 2>&1
wait
echo AFTER_DONE
