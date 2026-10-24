#!/usr/bin/env bash
# usage: post_it3.sh <tinker sampler path of the selected it3 checkpoint>
set -euo pipefail
cd ~/repos/muselet/training
UV=~/.local/bin/uv
export MUSELET_CATALOG=$PWD/artifacts/catalog_v3.json
NAME=it3
SP=$1
$UV run python -m muselet_train.export parity --tinker-path "$SP" --run v3m --n 300 --out artifacts/parity_300_it3.jsonl
$UV run python -m muselet_train.export download --name $NAME --tinker-path "$SP"
$UV run python -m muselet_train.export merge --name $NAME
$UV run --script scripts/mlx_parity.py convert --hf /data/export/$NAME/hf --out /data/export/$NAME/mlx-4bit --bits 4
$UV run python -m muselet_train.export check
echo POST_DONE
