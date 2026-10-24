#!/usr/bin/env bash
# Stage the October finance demo on the demo Mac (run by the lead, not in CI).
#
#   evals/fixtures/finance/setup_mac.sh [setup] [--dry-run|--apply]   copy statement, budget, receipts
#   evals/fixtures/finance/setup_mac.sh teardown [--dry-run|--apply]  remove exactly what setup created
#   evals/fixtures/finance/setup_mac.sh reset [--dry-run|--apply]     between takes: close the demo documents in
#                                                                       Numbers without saving, restore the files
# --dry-run is the default. Every step is printed before anything runs. Opens nothing. Idempotent: identical
# files are left alone, and only files/dirs setup created are recorded, so teardown never removes anything else.
# Destination: $MUSELET_FINANCE_DIR (default ~/Documents/Finance; the finance_review tool reads the same path).
# Created items are recorded in $MUSELET_STATE_DIR/finance_setup.state (default ~/.muselet).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${MUSELET_FINANCE_DIR:-$HOME/Documents/Finance}"
RECEIPTS_DEST="$DEST/Receipts"
STATE_DIR="${MUSELET_STATE_DIR:-$HOME/.muselet}"
STATE="$STATE_DIR/finance_setup.state"
FILES=(bank_statement_oct2026.csv budget_oct2026.xlsx)
RECEIPTS=()
for f in "$HERE"/receipts/receipt_*.png; do RECEIPTS+=("$(basename "$f")"); done

CMD="setup"
MODE="dry-run"
for arg in "$@"; do
  case "$arg" in
    setup|teardown|reset) CMD="$arg" ;;
    --dry-run) MODE="dry-run" ;;
    --apply) MODE="apply" ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [[ "$MODE" == "apply" && "$CMD" == "reset" && "$(uname -s)" != "Darwin" ]]; then
  echo "reset --apply needs macOS (closes Numbers documents via osascript)" >&2
  exit 1
fi

record() { mkdir -p "$STATE_DIR"; printf '%s\t%s\n' "$1" "$2" >> "$STATE"; }
recorded() { [[ -f "$STATE" ]] && grep -qxF "$(printf '%s\t%s' "$1" "$2")" "$STATE"; }
say() { printf '  %s\n' "$*"; }

# pairs "src dest" for every file setup manages
pairs() {
  local f
  for f in "${FILES[@]}"; do printf '%s\t%s\n' "$HERE/$f" "$DEST/$f"; done
  for f in "${RECEIPTS[@]}"; do printf '%s\t%s\n' "$HERE/receipts/$f" "$RECEIPTS_DEST/$f"; done
}

# --- setup -------------------------------------------------------------------------------------------
plan_setup() {
  echo "Plan ($CMD, $MODE):"
  say "1. mkdir -p $DEST$([[ -d $DEST ]] && echo '  (exists)')"
  say "2. mkdir -p $RECEIPTS_DEST$([[ -d $RECEIPTS_DEST ]] && echo '  (exists)')"
  local src dst
  while IFS=$'\t' read -r src dst; do
    if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
      say "3. copy $(basename "$dst")  (identical copy exists, skip)"
    else
      say "3. copy $src -> $dst$([[ -f $dst ]] && echo '  (differs: overwrite)')"
    fi
  done < <(pairs)
  say "   opens nothing; state file: $STATE"
}

do_setup() {
  local d
  for d in "$DEST" "$RECEIPTS_DEST"; do
    [[ -d "$d" ]] || { mkdir -p "$d"; recorded dir "$d" || record dir "$d"; }
  done
  local src dst
  while IFS=$'\t' read -r src dst; do
    if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then continue; fi
    local existed=no
    [[ -f "$dst" ]] && existed=yes
    cp "$src" "$dst"
    [[ "$existed" == "no" ]] && ! recorded file "$dst" && record file "$dst"
    echo "copied $(basename "$dst")"
  done < <(pairs)
  echo "Done. Files in $DEST (receipts in $RECEIPTS_DEST)."
}

# --- teardown ----------------------------------------------------------------------------------------
plan_teardown() {
  echo "Plan ($CMD, $MODE):"
  if [[ ! -f "$STATE" ]]; then say "nothing recorded in $STATE; nothing to remove"; return; fi
  local kind value
  while IFS=$'\t' read -r kind value; do
    case "$kind" in
      file) say "rm $value" ;;
      dir) say "rmdir $value (only if empty)" ;;
    esac
  done < <(tail -r "$STATE" 2>/dev/null || tac "$STATE")
  say "rm $STATE"
}

do_teardown() {
  [[ -f "$STATE" ]] || return 0
  local kind value
  while IFS=$'\t' read -r kind value; do
    case "$kind" in
      file) rm -f "$value" && echo "removed $value" ;;
      dir) rmdir "$value" 2>/dev/null && echo "removed $value" || echo "kept $value (not empty)" ;;
    esac
  done < <(tail -r "$STATE" 2>/dev/null || tac "$STATE")
  rm -f "$STATE"
  echo "Teardown done."
}

# --- reset (between demo takes) ----------------------------------------------------------------------
plan_reset() {
  echo "Plan ($CMD, $MODE):"
  say "Numbers: close bank_statement_oct2026 and budget_oct2026 without saving if they are open"
  say "restore ${FILES[*]} and ${#RECEIPTS[@]} receipts in $DEST from the fixture (undo any saved edits)"
}

do_reset() {
  osascript -e 'tell application id "com.apple.Numbers" to if it is running then close (every document whose name starts with "bank_statement_oct2026" or name starts with "budget_oct2026") saving no' || true
  mkdir -p "$RECEIPTS_DEST"
  local src dst
  while IFS=$'\t' read -r src dst; do cp "$src" "$dst"; done < <(pairs)
  echo "Reset done."
}

"plan_$CMD"
if [[ "$MODE" == "apply" ]]; then
  echo "Applying..."
  "do_$CMD"
else
  echo "(dry run: nothing changed; re-run with --apply)"
fi
