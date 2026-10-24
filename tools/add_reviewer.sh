#!/usr/bin/env bash
# Launch one more continuous reviewer (Fusion, no secrets) and register it for review pulses.
#   tools/add_reviewer.sh <lane-id> <lane-brief.md> [acu-cap]
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
lane=$1; brief=$2; acu=${3:-150}
mkdir -p runs
[ -f runs/reviewers.json ] || echo "[]" > runs/reviewers.json
if python3 -c 'import json,sys; sys.exit(0 if any(r["lane"]==sys.argv[1] for r in json.load(open("runs/reviewers.json"))) else 1)' "$lane"; then
  echo "lane $lane already registered" >&2; exit 1
fi
prompt=$(mktemp)
trap 'rm -f "$prompt"' EXIT
{ printf 'Your lane id is `%s`; your output branch is `review/%s`.\n\n' "$lane" "$lane"; cat cloud/review/common.md "$brief"; } > "$prompt"
res=$(python3 tools/devin_cloud.py create --title "muselet review: $lane" --prompt-file "$prompt" \
      --repo ardahk/muselet --acu "$acu" --no-secrets --tag muselet-review)
python3 - "$res" "$lane" <<'EOF'
import json, sys
s = json.loads(sys.argv[1]); s["lane"] = sys.argv[2]
rs = json.load(open("runs/reviewers.json")); rs.append(s)
json.dump(rs, open("runs/reviewers.json", "w"), indent=1)
print(s["lane"], s["session_id"], s["url"])
EOF
