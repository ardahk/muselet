"""Base screens for the v2 planner benchmark (labels as HandsKit reports them; see planner_v2_lib docstring)."""

from planner_v2_lib import CHROME, Screen

SIDEBAR = ['row "Recents"', 'row "Applications"', 'row "Desktop"', 'row "Documents"', 'row "Downloads"',
           'row "iCloud Drive"', 'row "AirDrop"']
FINDER_TB = ['button "Back"', 'button "Forward"', 'radio "Icons" unchecked', 'radio "List" unchecked',
             'radio "Columns" unchecked', 'radio "Gallery" unchecked', 'button "Group"', 'button "Share"',
             'button "Edit Tags"', 'popup "Action"', 'textfield "Search" value=""']


def finder(folder="Downloads", files=("report.pdf",), view="List", start=101, focus=None, search=""):
    tb = [x.replace(f'"{view}" unchecked', f'"{view}" checked') for x in FINDER_TB]
    tb = [x.replace('value=""', f'value="{search}"') if x.startswith("textfield") else x for x in tb]
    side = [x + (" selected" if x == f'row "{folder}"' else "") for x in SIDEBAR]
    if view == "List":
        body = ['button "Name"', 'button "Date Modified"', 'button "Size"', 'button "Kind"'] + \
               [f'row "{f}"' for f in files]
    else:
        body = [f'image "{f}"' for f in files]
    return Screen("Finder", folder, CHROME + tb + side + body, start=start, focus=focus)


def safari(title, url, body, start=201, focus=None, tabs=None, url_value=None):
    tabs = tabs or [title]
    items = CHROME + ['button "Show Sidebar"', 'button "Back"', 'button "Forward"', 'button "Privacy Report"',
                      f'textfield "Smart Search Field" value="{url_value if url_value is not None else url}"',
                      'button "Reload this page"', 'button "Share"', 'button "New Tab"', 'button "Show Tab Overview"']
    items += [f'radio "{t}" ' + ("checked" if t == title else "unchecked") for t in tabs]
    return Screen("Safari", title, items + list(body), start=start, focus=focus)


def chrome(title, url, body, start=301, focus=None, tabs=None):
    tabs = tabs or [title]
    items = CHROME + [f'radio "{t}" ' + ("checked" if t == title else "unchecked") for t in tabs]
    items += ['button "New Tab"', 'button "Back"', 'button "Forward"', 'button "Reload"', 'button "View site information"',
              f'textfield "Address and search bar" value="{url}"', 'button "Bookmark this tab"', 'button "You"',
              'popup "Chrome"']
    return Screen("Google Chrome", f"{title} - Google Chrome", items + list(body), start=start, focus=focus)


def zen(title, url, body, start=401, focus=None, tabs=None):
    tabs = tabs or [title]
    items = CHROME + ['button "Back"', 'button "Forward"', 'button "Reload"',
                      f'textfield "Search or enter address" value="{url}"', 'button "Bookmark this page"',
                      'button "Zen Sidebar"'] + \
        [f'radio "{t}" ' + ("checked" if t == title else "unchecked") for t in tabs]
    return Screen("Zen", f"{title} — Zen", items + list(body), start=start, focus=focus)


def mail_inbox(rows, start=501, focus=None, window="Inbox – iCloud", search=""):
    items = CHROME + ['button "Filter"', 'button "Compose new message"', 'button "Archive"',
                      'button "Move to Trash"', 'button "Move to Junk"', 'button "Reply"', 'button "Reply All"',
                      'button "Forward"', 'button "Flag"', f'textfield "Search" value="{search}"',
                      'row "Inbox" selected', 'row "Drafts"', 'row "Sent"', 'row "Junk"', 'row "Trash"', 'row "Archive"']
    items += [f'row "{r}"' for r in rows]
    return Screen("Mail", window, items, start=start, focus=focus)


def mail_compose(to="", subject="", body="", start=601, focus=None, window="New Message"):
    items = CHROME + ['button "Send"', 'button "Header Fields"', 'button "Attach"', 'button "Format"',
                      f'textfield "To:" value="{to}"', f'textfield "Cc:" value=""', f'textfield "Subject:" value="{subject}"',
                      'popup "From:"', f'textarea "Message Body" value="{body}"']
    return Screen("Mail", window, items, start=start, focus=focus)


def messages(contact, history=(), rows=("Mom", "Alex", "Jordan"), start=701, draft="", focus="__composer__"):
    items = CHROME + ['button "Compose"', 'textfield "Search" value=""'] + \
        [f'row "{r}"' + (" selected" if r == contact else "") for r in rows] + \
        ['button "Apps"', f'textfield "iMessage" value="{draft}"', 'button "Record audio"', 'button "Emoji"'] + \
        [f'text "{h}"' for h in history]
    s = Screen("Messages", contact, items, start=start)
    return s.with_(focus="iMessage" if focus == "__composer__" else focus)


def notes(selected, note_rows, body, title_field=None, start=801, focus=None, folder="Notes"):
    items = CHROME + ['button "Show Folders"', 'button "List View"', 'button "Gallery View"', 'button "Delete"',
                      'button "New Note"', 'button "Format"', 'button "Checklist"', 'button "Table"',
                      'button "Attachments"', 'button "Share"', 'textfield "Search" value=""',
                      f'row "{folder}" selected'] + \
        [f'row "{r}"' + (" selected" if r == selected else "") for r in note_rows]
    items.append(f'textarea "{selected}" value="{body}"')
    return Screen("Notes", selected, items, start=start, focus=focus)


def numbers(doc, sheets=("Sheet 1",), active=None, cells=(), start=901, focus=None):
    active = active or sheets[0]
    items = CHROME + ['button "View"', 'button "Zoom"', 'button "Add Category"', 'button "Pivot Table"',
                      'button "Insert"', 'button "Table"', 'button "Chart"', 'button "Text"', 'button "Shape"',
                      'button "Media"', 'button "Comment"', 'button "Share"', 'button "Format"', 'button "Organize"',
                      'button "Add Sheet"'] + \
        [f'radio "{s}" ' + ("checked" if s == active else "unchecked") for s in sheets] + \
        [f'cell "{c}"' for c in cells]
    return Screen("Numbers", doc, items, start=start, focus=focus)


def calendar(view="Week", start=1001, focus=None, extra=()):
    items = CHROME + ['button "Calendars"', 'button "Add"', 'radio "Day" unchecked', 'radio "Week" unchecked',
                      'radio "Month" unchecked', 'radio "Year" unchecked', 'textfield "Search" value=""',
                      'button "Previous"', 'button "Today"', 'button "Next"']
    items = [x.replace(f'"{view}" unchecked', f'"{view}" checked') for x in items]
    return Screen("Calendar", "Calendar", items + list(extra), start=start, focus=focus)


def reminders(list_name, todos, lists=("Today", "Scheduled", "All", "Flagged", "Reminders", "Errands"), start=1101,
              focus=None, done=()):
    items = CHROME + ['button "Show Sidebar"', 'textfield "Search" value=""'] + \
        [f'row "{l}"' + (" selected" if l == list_name else "") for l in lists] + \
        ['button "Add"', 'button "Share"', 'button "Show Completed"'] + \
        [f'checkbox "{t}" ' + ("checked" if t in done else "unchecked") for t in todos] + \
        ['textfield "New Reminder" value=""']
    return Screen("Reminders", list_name, items, start=start, focus=focus)


SETTINGS_SIDEBAR = ['row "Wi‑Fi"', 'row "Bluetooth"', 'row "Network"', 'row "Battery"', 'row "General"',
                    'row "Accessibility"', 'row "Appearance"', 'row "Control Center"', 'row "Desktop & Dock"',
                    'row "Displays"', 'row "Focus"', 'row "Notifications"', 'row "Sound"', 'row "Lock Screen"',
                    'row "Privacy & Security"', 'row "Touch ID & Password"', 'row "Wallpaper"']


def settings(pane, controls, start=1201, focus=None, search=""):
    side = [x + (" selected" if x == f'row "{pane}"' else "") for x in SETTINGS_SIDEBAR]
    items = CHROME + ['button "Back"', 'button "Forward"', f'textfield "Search" value="{search}"'] + side + list(controls)
    return Screen("System Settings", pane, items, start=start, focus=focus)


def preview(doc, start=1301, extra=(), focus=None):
    items = CHROME + ['popup "View Menu"', 'button "Zoom Out"', 'button "Zoom In"', 'button "Share"',
                      'button "Highlight"', 'button "Rotate"', 'button "Markup"', 'button "Show Markup Toolbar"',
                      'textfield "Search" value=""'] + list(extra)
    return Screen("Preview", doc, items, start=start, focus=focus)


IWORK_TB = ['button "View"', 'button "Zoom"', 'button "Insert"', 'button "Table"', 'button "Chart"', 'button "Text"',
            'button "Shape"', 'button "Media"', 'button "Comment"', 'button "Collaborate"', 'button "Format"']


def pages(doc, body="", start=1401, focus=None, extra=()):
    items = CHROME + IWORK_TB[:2] + ['button "Add Page"'] + IWORK_TB[2:] + ['button "Document"',
                                                                            f'textarea "Body" value="{body}"']
    return Screen("Pages", doc, items + list(extra), start=start, focus=focus)


def keynote(doc, slides=("Slide 1",), start=1501, focus=None, extra=()):
    items = CHROME + IWORK_TB[:2] + ['button "Play"', 'button "Add Slide"'] + IWORK_TB[2:] + ['button "Animate"',
                                                                                              'button "Document"'] + \
        [f'row "{s}"' for s in slides]
    return Screen("Keynote", doc, items + list(extra), start=start, focus=focus)


def slack(channel, msgs=(), channels=("general", "random", "design", "eng-deploys"), dms=("Dana Lee", "Sam Ortiz"),
          start=1601, draft="", focus="__composer__"):
    items = ['button "Back"', 'button "Forward"', 'button "History"', 'textfield "Search Acme" value=""',
             'button "Home"', 'button "DMs"', 'button "Activity"', 'button "More"'] + \
        [f'row "{c}"' + (" selected" if c == channel else "") for c in channels] + [f'row "{d}"' for d in dms] + \
        ['button "Add canvas"', f'textarea "Message #{channel}" value="{draft}"', 'button "Attach"',
         'button "Emoji"', 'button "Send now"'] + [f'text "{m}"' for m in msgs]
    s = Screen("Slack", f"{channel} (Channel) - Acme - Slack", items, start=start)
    return s.with_(focus=f"Message #{channel}" if focus == "__composer__" else focus)


def premiere(project="Wedding Edit", start=1701):
    return Screen("Adobe Premiere Pro 2026", f"/Users/arda/Movies/{project}.prproj", CHROME, start=start, blind=True)


def textedit_doc(body="", window="Untitled", start=1801, focus="__body__"):
    items = CHROME + ['popup "Paragraph Styles"', 'combobox "Font Size" value="12"', 'checkbox "Bold" unchecked',
                      'checkbox "Italic" unchecked', 'checkbox "Underline" unchecked', 'popup "Lists"',
                      f'textarea "Text" value="{body}"']
    s = Screen("TextEdit", window, items, start=start)
    return s.with_(focus="Text" if focus == "__body__" else focus)


def music(rows=("Recently Added", "Artists", "Albums", "Songs", "Running", "Chill"), start=1901, extra=()):
    items = CHROME + ['textfield "Search" value=""', 'button "Previous"', 'button "Play"', 'button "Next"',
                      'button "Shuffle"', 'button "Repeat"', 'slider "Volume"'] + [f'row "{r}"' for r in rows]
    return Screen("Music", "Music", items + list(extra), start=start)
