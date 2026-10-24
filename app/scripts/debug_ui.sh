#!/usr/bin/env bash
# Drive muselet's UI for demos/screenshots (no OS actions are executed).
#   debug_ui.sh say "Volume set to 30"
#   debug_ui.sh ui thinking|acting|success|confused|sleeping|idle|listening ["bubble text"]
#   debug_ui.sh confirm "Send the message to Mom?"
#   debug_ui.sh ghost X Y W H "Label" [ok|fail]      # CG global top-left points
#   debug_ui.sh ghost-ax ["label substring"]          # preview a press on a real AX element
#   debug_ui.sh status                                 # writes a status line to the log
set -euo pipefail
cmd="${1:?cmd}"; shift || true
json() { python3 -c 'import json,sys; print(json.dumps(dict(zip(sys.argv[1::2], sys.argv[2::2]))))' "$@"; }
case "$cmd" in
  say)      info=$(json cmd say text "${1:-Hello!}") ;;
  ui)       info=$(json cmd ui mascot "${1:-idle}" bubble "${2:-}") ;;
  confirm)  info=$(json cmd confirm summary "${1:-Send the message to Mom?}") ;;
  ghost)    info=$(json cmd ghost x "$1" y "$2" w "$3" h "$4" label "${5:-}" ok "$([ "${6:-ok}" = fail ] && echo false || echo true)") ;;
  ghost-ax) info=$(json cmd ghost-ax label "${1:-}") ;;
  status)   info=$(json cmd status) ;;
  *) echo "unknown cmd $cmd" >&2; exit 2 ;;
esac
osascript -l JavaScript - "$info" <<'JXA'
ObjC.import('Foundation');
function run(argv) {
  const info = JSON.parse(argv[0]);
  const d = $.NSMutableDictionary.alloc.init;
  for (const k in info) { if (info[k] !== '') d.setObjectForKey($(String(info[k])), $(k)); }
  $.NSDistributedNotificationCenter.defaultCenter
    .postNotificationNameObjectUserInfoDeliverImmediately('ai.muselet.debug', $(), d, true);
}
JXA
