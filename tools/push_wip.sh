#!/usr/bin/env bash
# Snapshot the working tree (tracked + untracked, honoring .gitignore) to origin/wip/local so cloud
# reviewers can see in-progress local work. Never touches HEAD, the index or the working tree; the
# branch only fast-forwards (each snapshot's first parent is the previous snapshot).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
idx=$(mktemp)
trap 'rm -f "$idx"' EXIT
cp .git/index "$idx"
GIT_INDEX_FILE="$idx" git add -A
tree=$(GIT_INDEX_FILE="$idx" git write-tree)

if git grep -I -l -E '(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|hf_[A-Za-z0-9]{20,}|cog_[A-Za-z0-9]{10,}|apk_[A-Za-z0-9_]{10,}|BEGIN [A-Z ]*PRIVATE KEY)' \
    "$tree" -- ':!tools/push_wip.sh' ; then
  echo "refusing to push: secret-like strings found in the files above" >&2
  exit 1
fi

git fetch -q origin wip/local 2>/dev/null || true
head=$(git rev-parse HEAD)
parent=$(git rev-parse -q --verify refs/remotes/origin/wip/local || echo "$head")
if [ "$(git rev-parse "$parent^{tree}")" = "$tree" ]; then
  echo "wip/local unchanged ($(git rev-parse --short "$parent"))"
  exit 0
fi
parents=(-p "$parent")
[ "$parent" != "$head" ] && parents+=(-p "$head")
commit=$(git commit-tree "$tree" "${parents[@]}" -m "wip snapshot $(date -u +%FT%TZ) on main@$(git rev-parse --short HEAD)")
git push -q origin "$commit:refs/heads/wip/local"
echo "wip/local -> $(git rev-parse --short "$commit")"
