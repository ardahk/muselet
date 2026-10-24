import re, ast, sys
src=open('brain/orchestrator.py').read()
start=src.index('    _SCRIPT_BLOCK = re.compile('); end=src.index('    @staticmethod\n    def _read_sysctl')
ns={'re':re}
exec("class P:\n"+src[start:end], ns)
p=ns['P']()
cases={
 'sysevents_shutdown':'tell application "System Events"\n get name of every process\n shut down\nend tell',
 'sysevents_restart':'tell application "System Events" to restart -- get',
 'sysevents_logout':'tell application "System Events"\n get name of current user\n log out\nend tell',
 'finder_empty':'tell application "Finder"\n empty\n get name of window 1\nend tell',
 'numbers_plus_abbrev':'tell application "Numbers"\n get name of document 1\nend tell\ntell app "Terminal" to activate',
 'finder_eject':'tell application "Finder"\n eject every disk\n count windows\nend tell',
 'safari_closeall_ctrl':'tell application "Safari" to get URL of tab 1 of window 1',
}
for k,v in cases.items(): print(k, 'confirm' if p.script_needs_confirm('applescript',v) else 'NO CONFIRM')
