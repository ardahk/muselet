#!/usr/bin/env bash
# Drive muselet's UI for demos/screenshots (no OS actions are executed).
#   debug_ui.sh say "Volume set to 30"
#   debug_ui.sh ui thinking|acting|success|confused|sleeping|idle|listening ["bubble text"]
#   debug_ui.sh confirm "Send the message to Mom?"
#   debug_ui.sh confirm-cancel [id]                    # brain's confirm_cancel (no id = pending one)
#   debug_ui.sh latency 212 ["Opened Safari"]          # ui {mascot:success, bubble?, ms} -> latency chip
#   debug_ui.sh skill-ghost open_app app=Safari        # ghost flight to a skill's target (no skill runs)
#   debug_ui.sh ghost X Y W H "Label" [ok|fail]      # CG global top-left points
#   debug_ui.sh ghost-ax ["label substring"]          # preview a press on a real AX element
#   debug_ui.sh status                                 # writes a status line to the log
#   debug_ui.sh hud volume 40 | hud mute | hud brightness 70      # skill HUD preview
#   debug_ui.sh hud dark on|off | hud wifi on|off | hud bluetooth on|off
#   HUD_STYLE=vibrancy debug_ui.sh hud volume 40       # glass (default) | vibrancy
#   debug_ui.sh timer ["Tea"]                          # "Timer done" bubble (no timer runs)
set -euo pipefail
cmd="${1:?cmd}"; shift || true
json() { python3 -c 'import json,sys; print(json.dumps(dict(zip(sys.argv[1::2], sys.argv[2::2]))))' "$@"; }
case "$cmd" in
  say)      info=$(json cmd say text "${1:-Hello!}") ;;
  ui)       info=$(json cmd ui mascot "${1:-idle}" bubble "${2:-}") ;;
  confirm)  info=$(json cmd confirm summary "${1:-Send the message to Mom?}") ;;
  confirm-cancel) info=$(json cmd confirm_cancel id "${1:-}") ;;
  latency)  info=$(json cmd latency ms "${1:-212}" bubble "${2:-}") ;;
  skill-ghost)
    name="${1:?skill name}"; shift || true
    kv=(cmd skill_ghost name "$name")
    for a in "$@"; do kv+=("arg.${a%%=*}" "${a#*=}"); done
    info=$(json "${kv[@]}") ;;
  ghost)    info=$(json cmd ghost x "$1" y "$2" w "$3" h "$4" label "${5:-}" ok "$([ "${6:-ok}" = fail ] && echo false || echo true)") ;;
  ghost-ax) info=$(json cmd ghost-ax label "${1:-}") ;;
  status)   info=$(json cmd status) ;;
  hud)
    kind="${1:-volume}"; arg="${2:-}"
    case "$kind" in
      volume|mute|brightness) info=$(json cmd hud kind "$kind" level "${arg:-50}" style "${HUD_STYLE:-}") ;;
      *) info=$(json cmd hud kind "$kind" on "${arg:-on}" style "${HUD_STYLE:-}") ;;
    esac ;;
  timer)    info=$(json cmd timer label "${1:-}") ;;
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
