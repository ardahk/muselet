#!/usr/bin/env bash
# Stage the Henderson advisor demo on the demo Mac (run by the lead, not in CI).
#
#   evals/fixtures/advisor/setup_mac.sh [setup] [--dry-run|--apply]   stage files, calendar event, prior note
#   evals/fixtures/advisor/setup_mac.sh teardown [--dry-run|--apply]  remove exactly what setup created
#   evals/fixtures/advisor/setup_mac.sh reset [--dry-run|--apply]     between takes: delete the agent's prep
#                                                                       note and restore the client files
# --dry-run is the default. Every step is printed before anything runs. Idempotent: things that already
# exist are left alone and are not recorded, so teardown never removes anything setup did not create.
# Created items are recorded in $MUSELET_STATE_DIR/advisor_setup.state (default ~/.muselet).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/henderson"
CLIENTS_DIR="${MUSELET_CLIENTS_DIR:-$HOME/Documents/Clients}"
DEST="$CLIENTS_DIR/Henderson"
STATE_DIR="${MUSELET_STATE_DIR:-$HOME/.muselet}"
STATE="$STATE_DIR/advisor_setup.state"
FILES=(portfolio.xlsx portfolio.csv targets.json activity_last_60d.csv profile.json last_meeting_notes.txt annual_review.ics)
CAL_NAME="${MUSELET_CALENDAR:-Clients}"
EVENT_SUMMARY="Henderson annual review"
NOTES_FOLDER="Clients"
PRIOR_TITLE="Henderson - meeting notes - 2026-07-23"   # first line of last_meeting_notes.txt
PREP_TITLE="Henderson — annual review prep (Muselet)"           # written by the agent during the demo

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

if [[ "$MODE" == "apply" && "$(uname -s)" != "Darwin" ]]; then
  echo "--apply needs macOS (Calendar/Notes via osascript)" >&2
  exit 1
fi

record() { mkdir -p "$STATE_DIR"; printf '%s\t%s\n' "$1" "$2" >> "$STATE"; }
recorded() { [[ -f "$STATE" ]] && grep -qxF "$(printf '%s\t%s' "$1" "$2")" "$STATE"; }

# --- AppleScript helpers (values are passed as argv, never spliced into source) ----------------------
DATE_HANDLER='
on mk(y, m, d, secs)
  set dt to current date
  set day of dt to 1
  set year of dt to y
  set month of dt to m
  set day of dt to d
  set time of dt to secs
  return dt
end mk'

calendar_add() {  # prints "calendar=<created|existed> event=<created|existed>"
  osascript - "$CAL_NAME" "$EVENT_SUMMARY" "$DEST" <<OSA
on run argv
  set calName to item 1 of argv
  set summ to item 2 of argv
  set folderPath to item 3 of argv
  set d0 to my mk(2026, 10, 26, 10 * hours)
  set d1 to my mk(2026, 10, 26, 11 * hours)
  tell application id "com.apple.iCal"
    set calState to "existed"
    if not (exists calendar calName) then
      make new calendar with properties {name:calName}
      set calState to "created"
    end if
    set evState to "existed"
    tell calendar calName
      if (count of (every event whose summary is summ and start date is d0)) is 0 then
        make new event with properties {summary:summ, start date:d0, end date:d1, location:"Office", description:"Annual review with Mark and Elena Henderson. Client folder: " & folderPath}
        set evState to "created"
      end if
    end tell
  end tell
  return "calendar=" & calState & " event=" & evState
end run
$DATE_HANDLER
OSA
}

calendar_remove() {  # $1 = remove event (yes/no), $2 = remove calendar (yes/no)
  osascript - "$CAL_NAME" "$EVENT_SUMMARY" "$1" "$2" <<OSA
on run argv
  set calName to item 1 of argv
  set summ to item 2 of argv
  set d0 to my mk(2026, 10, 26, 10 * hours)
  tell application id "com.apple.iCal"
    if not (exists calendar calName) then return "calendar missing"
    if item 3 of argv is "yes" then
      tell calendar calName
        repeat with e in (get every event whose summary is summ and start date is d0)
          delete e
        end repeat
      end tell
    end if
    if item 4 of argv is "yes" then delete calendar calName
  end tell
  return "ok"
end run
$DATE_HANDLER
OSA
}

notes_html() {  # plain text file -> Notes HTML (one <div> per line)
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g' \
      -e 's|^$|<br>|' -e 's|.*|<div>&</div>|' "$1" | tr -d '\n'
}

notes_add_prior() {  # prints "folder=<created|existed> note=<created|existed>"
  osascript - "$NOTES_FOLDER" "$PRIOR_TITLE" "$(notes_html "$SRC/last_meeting_notes.txt")" <<'OSA'
on run argv
  set folderName to item 1 of argv
  set noteTitle to item 2 of argv
  tell application id "com.apple.Notes"
    set acct to default account
    set folderState to "existed"
    if not (exists folder folderName of acct) then
      make new folder at acct with properties {name:folderName}
      set folderState to "created"
    end if
    set f to folder folderName of acct
    set noteState to "existed"
    if (count of (every note of f whose name is noteTitle)) is 0 then
      make new note at f with properties {name:noteTitle, body:item 3 of argv}
      set noteState to "created"
    end if
  end tell
  return "folder=" & folderState & " note=" & noteState
end run
OSA
}

notes_delete() {  # $1 = note title, $2 = also delete the folder if empty (yes/no)
  osascript - "$NOTES_FOLDER" "$1" "$2" <<'OSA'
on run argv
  set folderName to item 1 of argv
  tell application id "com.apple.Notes"
    set acct to default account
    if not (exists folder folderName of acct) then return "folder missing"
    set f to folder folderName of acct
    repeat with n in (get every note of f whose name is (item 2 of argv))
      delete n
    end repeat
    if item 3 of argv is "yes" and (count of notes of f) is 0 then delete f
  end tell
  return "ok"
end run
OSA
}

say() { printf '  %s\n' "$*"; }

# --- setup -------------------------------------------------------------------------------------------
plan_setup() {
  echo "Plan ($CMD, $MODE):"
  say "1. mkdir -p $DEST$([[ -d $DEST ]] && echo '  (exists)')"
  local f
  for f in "${FILES[@]}"; do
    if [[ -f "$DEST/$f" ]] && cmp -s "$SRC/$f" "$DEST/$f"; then
      say "2. copy $f  (identical copy exists, skip)"
    else
      say "2. copy $SRC/$f -> $DEST/$f$([[ -f $DEST/$f ]] && echo '  (differs: overwrite)')"
    fi
  done
  say "3. Calendar: ensure calendar \"$CAL_NAME\"; add \"$EVENT_SUMMARY\" 2026-10-26 10:00-11:00 (from annual_review.ics) unless present"
  say "4. Notes: ensure folder \"$NOTES_FOLDER\"; add note \"$PRIOR_TITLE\" from last_meeting_notes.txt unless present"
  say "   state file: $STATE"
}

do_setup() {
  [[ -d "$CLIENTS_DIR" ]] || { mkdir -p "$CLIENTS_DIR"; record dir "$CLIENTS_DIR"; }
  [[ -d "$DEST" ]] || { mkdir -p "$DEST"; record dir "$DEST"; }
  local f
  for f in "${FILES[@]}"; do
    if [[ -f "$DEST/$f" ]] && cmp -s "$SRC/$f" "$DEST/$f"; then continue; fi
    local existed=no
    [[ -f "$DEST/$f" ]] && existed=yes
    cp "$SRC/$f" "$DEST/$f"
    [[ "$existed" == "no" ]] && ! recorded file "$DEST/$f" && record file "$DEST/$f"
    echo "copied $f"
  done
  local out
  out="$(calendar_add)"
  echo "Calendar: $out"
  [[ "$out" == *"calendar=created"* ]] && record calendar "$CAL_NAME"
  [[ "$out" == *"event=created"* ]] && record event "$EVENT_SUMMARY"
  out="$(notes_add_prior)"
  echo "Notes: $out"
  [[ "$out" == *"folder=created"* ]] && record notes_folder "$NOTES_FOLDER"
  [[ "$out" == *"note=created"* ]] && record note "$PRIOR_TITLE"
  echo "Done. Check: open \"$DEST\"; Calendar on 2026-10-26; Notes folder \"$NOTES_FOLDER\"."
}

# --- teardown ----------------------------------------------------------------------------------------
plan_teardown() {
  echo "Plan ($CMD, $MODE):"
  if [[ ! -f "$STATE" ]]; then say "nothing recorded in $STATE; nothing to remove"; return; fi
  local kind value
  while IFS=$'\t' read -r kind value; do
    case "$kind" in
      note) say "Notes: delete note \"$value\"" ;;
      notes_folder) say "Notes: delete folder \"$value\" if empty" ;;
      event) say "Calendar: delete \"$value\" on 2026-10-26 10:00" ;;
      calendar) say "Calendar: delete calendar \"$value\"" ;;
      file) say "rm $value" ;;
      dir) say "rmdir $value (only if empty)" ;;
    esac
  done < <(tail -r "$STATE" 2>/dev/null || tac "$STATE")
  say "rm $STATE"
}

do_teardown() {
  [[ -f "$STATE" ]] || return 0
  local del_note=no del_folder=no del_event=no del_cal=no kind value
  recorded note "$PRIOR_TITLE" && del_note=yes
  recorded notes_folder "$NOTES_FOLDER" && del_folder=yes
  recorded event "$EVENT_SUMMARY" && del_event=yes
  recorded calendar "$CAL_NAME" && del_cal=yes
  if [[ "$del_note" == yes || "$del_folder" == yes ]]; then
    if [[ "$del_note" == yes ]]; then echo "Notes: $(notes_delete "$PRIOR_TITLE" "$del_folder")"
    else echo "Notes: $(notes_delete "__none__" "$del_folder")"; fi
  fi
  if [[ "$del_event" == yes || "$del_cal" == yes ]]; then echo "Calendar: $(calendar_remove "$del_event" "$del_cal")"; fi
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
  say "Notes: delete \"$PREP_TITLE\" in folder \"$NOTES_FOLDER\" (the agent's output)"
  say "restore ${FILES[*]} in $DEST from the fixture (undo any saved edits)"
  say "Numbers: close $DEST/portfolio.xlsx without saving if it is open (matched by file path)"
}

do_reset() {
  echo "Notes: $(notes_delete "$PREP_TITLE" no)"
  # close only the demo workbook (by file path), never another client's portfolio
  osascript - "$DEST/portfolio.xlsx" <<'OSA' || true
on run argv
  set p to item 1 of argv
  tell application id "com.apple.Numbers"
    if it is running then
      repeat with d in (get every document)
        try
          if POSIX path of ((file of d) as alias) is p then close d saving no
        end try
      end repeat
    end if
  end tell
end run
OSA
  local f
  for f in "${FILES[@]}"; do cp "$SRC/$f" "$DEST/$f"; done
  echo "Reset done."
}

"plan_$CMD"
if [[ "$MODE" == "apply" ]]; then
  echo "Applying..."
  "do_$CMD"
else
  echo "(dry run: nothing changed; re-run with --apply)"
fi
