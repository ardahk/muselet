# Lane: fix-email-reply — reply to the email that is on screen, like a person would

User test: Zen showing a Google Workspace Gmail message (window title "... - hoke@berkeley.edu - UC Berkeley Mail",
URL mail.google.com). "Reply to this email that I can be there in ten minutes" -> draft_email reply path decided it was
the Mail app ("Couldn't open a reply in Mail"); with "on gmail" it opened the Gmail inbox in a new tab and lost the
email. Branch `cloud/fix-email-reply`, one PR, tests with fake observations.
- Detect the on-screen email from live context, not the title: ctx `url` (mail.google.com / outlook.office.com /
  outlook.live.com / app.fastmail.com ...) or the browser AX tree (message header, Reply button), else the Mail app
  when Mail is frontmost.
- Reply in place: press the page's Reply control (AX, by label "Reply"), wait for the reply editor, read the email
  being replied to (AX text, OCR fallback) and compose the body with the planner model (short, in the user's words,
  using the email's context), type it into the reply editor, leave it as a draft and say "Draft ready. Say send to
  send it". Sending stays behind the existing explicit confirm.
- Never navigate away from an open email to start a reply. If no email is on screen, ask which email.
- Same for "reply saying X", "respond to this", "answer this email". Keep new-email drafting as today.
