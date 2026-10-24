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
    ]
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
    ]
])
def test_script_read_only_and_numbers_exemption(lang, code):
    orch = Orchestrator.__new__(Orchestrator)
    assert not orch.script_needs_confirm(lang, code)
