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
#   debug_ui.sh automation-status                      # Automation consent per app -> log (never prompts)
#   debug_ui.sh hud volume 40 | hud mute | hud brightness 70      # skill HUD preview
#   debug_ui.sh hud dark on|off | hud wifi on|off | hud bluetooth on|off
#   HUD_STYLE=vibrancy debug_ui.sh hud volume 40       # glass (default) | vibrancy
#   debug_ui.sh timer ["Tea"]                          # "Timer done" bubble (no timer runs)
#   debug_ui.sh pill-hover [on|off]
#   debug_ui.sh pill-typing open ["draft"] | close
#   debug_ui.sh panel [open|close] [light|dark|system]  # menu-bar panel (Settings)
#   debug_ui.sh perm-fake microphone|...|none          # show a permission as missing in the panel
#   debug_ui.sh mascot-edge left|right|top|bottom      # drag the kitten past an edge (clamped)
#   debug_ui.sh pill-slow on|off                       # 2 s typing open/close (mid-animation shots)
#   debug_ui.sh icon-png DIR [recording]               # DIR/menubar-icon@1x.png, @2x.png
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
  automation-status) info=$(json cmd automation_status) ;;
  hud)
    kind="${1:-volume}"; arg="${2:-}"
    case "$kind" in
      volume|mute|brightness) info=$(json cmd hud kind "$kind" level "${arg:-50}" style "${HUD_STYLE:-}") ;;
      *) info=$(json cmd hud kind "$kind" on "${arg:-on}" style "${HUD_STYLE:-}") ;;
    esac ;;
  timer)    info=$(json cmd timer label "${1:-}") ;;
  pill-hover)
    state="${1:-on}"
    case "$state" in
      on)  info=$(json cmd pill_hover on true) ;;
      off) info=$(json cmd pill_hover on false) ;;
      *) echo "usage: debug_ui.sh pill-hover [on|off]" >&2; exit 2 ;;
    esac ;;
  pill-typing)
    state="${1:-open}"
    case "$state" in
      open)  info=$(json cmd pill_typing state open text "${2:-}") ;;
      close) info=$(json cmd pill_typing state close) ;;
      *) echo "usage: debug_ui.sh pill-typing open [draft] | close" >&2; exit 2 ;;
    esac ;;
  panel)
    state="${1:-open}"
    case "$state" in
      open|close) info=$(json cmd panel state "$state" appearance "${2:-}") ;;
      *) echo "usage: debug_ui.sh panel [open|close] [light|dark|system]" >&2; exit 2 ;;
    esac ;;
  perm-fake)   info=$(json cmd perm_fake kind "${1:-none}") ;;
  mascot-edge) info=$(json cmd mascot_edge edge "${1:-left}") ;;
  pill-slow)   info=$(json cmd pill_slow on "$([ "${1:-on}" = off ] && echo false || echo true)") ;;
  icon-png)    info=$(json cmd icon_png dir "${1:?dir}" recording "$([ "${2:-}" = recording ] && echo true || echo false)") ;;
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
