#!/usr/bin/env bash
set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  printf 'ffmpeg is required. Install it with: brew install ffmpeg\n' >&2
  exit 1
fi

FOOTAGE_DIR="${1:-$HOME/Desktop/Footage}"
PROJECT_DIR="${2:-$HOME/Movies/Muselet Demo}"
FONT="${MUSELET_DEMO_FONT:-/System/Library/Fonts/Supplemental/Arial.ttf}"

if [[ ! -f "$FONT" ]]; then
  printf 'Font not found: %s (set MUSELET_DEMO_FONT to a TTF file)\n' "$FONT" >&2
  exit 1
fi

mkdir -p "$FOOTAGE_DIR" "$PROJECT_DIR"

make_shot() {
  local number="$1"
  local output="$2"
  local source="$3"
  local frequency="$((220 + number * 55))"
  local drawtext
  drawtext="drawtext=fontfile='${FONT}':text='SHOT ${number}':fontcolor=white:fontsize=112:borderw=5:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2"

  ffmpeg -hide_banner -loglevel error -y \
    -f lavfi -i "$source" \
    -f lavfi -i "sine=frequency=${frequency}:sample_rate=48000:duration=10" \
    -t 10 -r 30 -vf "$drawtext" \
    -c:v libx264 -preset veryfast -crf 21 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -shortest "$output"
  printf 'Wrote %s\n' "$output"
}

make_shot 1 "$PROJECT_DIR/shot1.mp4" \
  "mandelbrot=size=1920x1080:rate=30"
make_shot 2 "$FOOTAGE_DIR/shot2.mp4" \
  "testsrc2=size=1920x1080:rate=30"
make_shot 3 "$FOOTAGE_DIR/shot3.mp4" \
  "life=size=1920x1080:rate=30:seed=23:life_color=0x70e0ff:death_color=0x101020"
make_shot 4 "$FOOTAGE_DIR/shot4.mp4" \
  "smptehdbars=size=1920x1080:rate=30"
