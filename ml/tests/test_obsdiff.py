"""apply_diff over the AGENTS.md observation/diff formats (task 2)."""

from brain.obsdiff import apply_diff, elements, parse_line, render_line

OBS = '''app: Finder | window: "Recents" | focused: #4
#1 button "Back"
#4 textfield "Search" value=""
#7 row "Downloads" selected
#9 checkbox "Show hidden" unchecked'''


def body(text):
    return text.split("\n")[1:]


def test_add_appends_line():
    out = apply_diff(OBS, '+ #31 button "Export"')
    assert out.split("\n")[-1] == '#31 button "Export"'
    assert out.startswith('app: Finder | window: "Recents" | focused: #4\n')


def test_remove_drops_line():
    out = apply_diff(OBS, "- #7")
    assert "#7" not in out and len(body(out)) == 3


def test_change_value():
    out = apply_diff(OBS, '~ #4 value="hel"')
    assert '#4 textfield "Search" value="hel"' in out


def test_change_flags():
    out = apply_diff(OBS, "~ #7 unselected\n~ #9 checked\n~ #1 disabled")
    assert '#7 row "Downloads"' in body(out)
    assert '#9 checkbox "Show hidden" checked' in body(out)
    assert '#1 button "Back" disabled' in body(out)
    assert '#1 button "Back"' in body(apply_diff(out, "~ #1 enabled"))


def test_combined_diff_keeps_order():
    out = apply_diff(OBS, '- #1\n+ #31 button "Export"\n~ #4 value="hi"')
    assert body(out) == ['#4 textfield "Search" value="hi"',
                         '#7 row "Downloads" selected',
                         '#9 checkbox "Show hidden" unchecked',
                         '#31 button "Export"']


def test_empty_diff_is_identity():
    assert apply_diff(OBS, "") == OBS
    assert apply_diff(OBS, None) == OBS


def test_absent_refs_are_ignored():
    assert apply_diff(OBS, '- #99\n~ #42 value="x"') == OBS


def test_add_existing_ref_replaces():
    out = apply_diff(OBS, '+ #7 row "Documents"')
    assert '#7 row "Documents"' in body(out) and "Downloads" not in out


def test_removed_focused_ref_drops_from_header():
    out = apply_diff(OBS, "- #4")
    assert out.split("\n")[0] == 'app: Finder | window: "Recents"'


def test_header_line_in_diff_replaces_header():
    hdr = 'app: Finder | window: "Downloads" | focused: #31'
    out = apply_diff(OBS, f'{hdr}\n+ #31 button "Export"')
    assert out.split("\n")[0] == hdr


def test_header_only_observation():
    out = apply_diff('app: Notes | window: "Notes"', '+ #2 textarea "Body" value=""')
    assert out == 'app: Notes | window: "Notes"\n#2 textarea "Body" value=""'


def test_no_header_observation():
    assert apply_diff('#1 button "Back"', "- #1") == ""


def test_quoted_labels_with_escapes_roundtrip():
    line = r'#5 button "Say \"hi\"" disabled'
    e = parse_line(line)
    assert e["label"] == 'Say "hi"' and e["enabled"] is False
    assert render_line(e) == line
    out = apply_diff(OBS, f"+ {line}")
    assert out.split("\n")[-1] == line


def test_value_with_spaces_and_quotes():
    out = apply_diff(OBS, r'~ #4 value="say \"x\" now"')
    assert r'#4 textfield "Search" value="say \"x\" now"' in out


def test_value_change_on_non_text_role_not_rendered():
    # Serializer.line only prints value= for text roles
    assert apply_diff(OBS, '~ #7 value="3"') == OBS


def test_unknown_lines_kept():
    obs = OBS + "\n(12 more)"
    assert "(12 more)" in apply_diff(obs, "- #1")


def test_matches_fresh_observation_after_chained_diffs():
    a = apply_diff(OBS, '~ #4 value="h"')
    b = apply_diff(a, '~ #4 value="hello"\n+ #12 row "hello.txt"')
    fresh = OBS.replace('value=""', 'value="hello"') + '\n#12 row "hello.txt"'
    assert b == fresh


def test_elements_carry_frames():
    prev = [{"ref": 4, "frame": [1, 2, 3, 4]}]
    els = elements(apply_diff(OBS, '+ #31 button "Export"'), prev)
    by = {e["ref"]: e for e in els}
    assert by[4]["frame"] == [1, 2, 3, 4] and by[4]["value"] == ""
    assert "frame" not in by[31] and by[31]["label"] == "Export"
    assert by[7]["selected"] is True and by[9]["checked"] is False


OBS_DIALOG = '''app: Adobe Premiere | window: "Clip speed / duration" | focused: #2
#1 button "clipSpeed" value="100"
#2 button "UI_HotTextNumberT" value="5"
#3 slider "Volume" value="0.5"
#4 stepper "Copies" value="1"
#5 incrementor "Rate" value="60"
#6 picker "Presets" value="Default"
#7 button "OK"'''


def test_numeric_obs_empty_diff_is_identity():
    assert apply_diff(OBS_DIALOG, "") == OBS_DIALOG
    assert apply_diff(OBS_DIALOG, None) == OBS_DIALOG


def test_numeric_and_hottext_value_changes_render():
    out = apply_diff(OBS_DIALOG, '~ #1 value="200"\n~ #2 value="8"\n'
                                 '~ #3 value="0.8"\n~ #4 value="2"\n'
                                 '~ #5 value="75"\n~ #6 value="Custom"')
    for line in ('#1 button "clipSpeed" value="200"',
                 '#2 button "UI_HotTextNumberT" value="8"',
                 '#3 slider "Volume" value="0.8"',
                 '#4 stepper "Copies" value="2"',
                 '#5 incrementor "Rate" value="75"',
                 '#6 picker "Presets" value="Custom"'):
        assert line in body(out)


def test_empty_numeric_value_not_rendered():
    out = apply_diff(OBS_DIALOG, '~ #3 value=""')
    assert '#3 slider "Volume"' in body(out)
    assert not any(l.startswith('#3 slider') and 'value=' in l
                   for l in body(out))


def test_ordinary_button_value_not_rendered():
    out = apply_diff(OBS_DIALOG, '~ #7 value="x"')
    assert '#7 button "OK"' in body(out) and 'value="x"' not in out


def test_hottext_match_is_case_sensitive():
    obs = 'app: X | window: "w"\n#1 button "hottext" value="1"'
    out = apply_diff(obs, '~ #1 value="9"')
    assert '#1 button "hottext"' in body(out) and 'value=' not in out


def test_elements_retain_numeric_value_strings():
    out = apply_diff(OBS_DIALOG, '~ #1 value="200"\n~ #3 value="0.8"')
    els = {e["ref"]: e for e in elements(out)}
    assert els[1]["value"] == "200"
    assert els[2]["value"] == "5"
    assert els[3]["value"] == "0.8"


def test_chained_numeric_diffs_match_fresh():
    a = apply_diff(OBS_DIALOG, '~ #1 value="200"')
    b = apply_diff(a, '~ #1 value="250"\n'
                      '+ #9 button "UI_HotTextNumberT" value="10"')
    fresh = OBS_DIALOG.replace('value="100"', 'value="250"') + \
        '\n#9 button "UI_HotTextNumberT" value="10"'
    assert b == fresh
