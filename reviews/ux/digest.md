# ux digest — pass 38

Heads: main 026aff0 (adds the Contacts permission row and probe, and the contacts_search / messages_compose /
messages_send RPCs), wip/local 98d1401, new cloud/brain-8 4546d09 and cloud/planner-demos 84798ec (no lane files).

Counts: 0 P0, 0 P1, 10 P2. None new.

- ux-23: fixed on wip/local (no_text_target -> "Couldn't find the Messages text box", plus copy for
  recipient_unverified and bad_handle), but not yet on main.
- wip also sends panel example requests only after Muselet deactivates (sendFromPanel, 0.5 s deadline), so ctx never
  binds to Muselet itself. Good.
- main: the Contacts row follows the existing permission pattern (notDetermined -> requestAccess, denied -> Settings).
- brain-8: the permission-prompt gate ("A permission prompt is open. Please answer it, then say continue.", 11 words)
  and the web-answer fallback (10 words) stay within 12 words, and the web answer ends success/idle. The permission
  gate adds another ui("listening") while the mic is off (ux-12).
- ux-14, ux-15, ux-16, ux-17, ux-18, ux-19, ux-20, ux-22: unchanged on main.
