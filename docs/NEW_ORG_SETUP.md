# Moving Muselet development to a new Devin org: setup steps for Arda

About 10 minutes of clicking. Nothing in the repo has to move: GitHub, HF and Tinker stay as they are. Only the
Devin org (cloud agents) and the local Devin login change.

## 0. Before you switch
- Leave the old org running until its credits run out. Every active cloud agent keeps a `## Handoff` section in its
  PR plus a `HANDOFF.md` on its branch, so the new org can pick up from GitHub at any time.
- The Mac keeps running: the Muselet app, its brain on `:8765`, and all models and data. Nothing to stop.

## 1. New org: GitHub
In the new org's web app go to **Settings → Integrations → GitHub**, install or authorize, and give it access to
**`ardahk/muselet`**. Cloud agents clone from here.

## 2. New org: a service user, for the lead's `tools/devin_cloud.py`
1. Go to **Settings → Service users → New**. Give it permissions to create and manage sessions and send messages.
   Optionally add `ViewOrgConsumption`, so the lead can read ACU usage through the API (it returned 0 in the old
   org).
2. Copy the token, which starts with `cog_`, and the org id, which starts with `org-` (it's in the URL or in
   Settings).

## 3. Mac: point the scripts at the new org
Edit `/Users/arda/cal13.0/.env`. The file is gitignored, so it's never committed. Change only these two lines and
keep everything else:
```
DEVIN_API_KEY=cog_...new...
DEVIN_ORG_ID=org-...new...
```
`TINKER_API_KEY`, `HF_TOKEN`, `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are already in that file.
`tools/devin_cloud.py` passes them to every new cloud session as secrets, so you don't need to add org secrets
by hand. If you prefer org-level secrets, add those same four names under **Settings → Secrets**.

Check it works (prints `{"session_id": ..., "status": ...}`):
```sh
cd /Users/arda/cal13.0
printf 'Reply with the word ready and stop. Do not change anything.\n' > /tmp/ping.md
python3 tools/devin_cloud.py create --title "muselet ping" --prompt-file /tmp/ping.md --no-secrets
```

## 4. Local Devin: log in to the new org and start the new lead
1. In the Devin desktop app (or CLI) on the Mac, sign out and sign in with the account of the new org. Open the
   folder `/Users/arda/cal13.0`.
2. Start a **new session**: Fusion mode, max thinking, the same as now.
3. Paste the whole of `docs/MASTER_PROMPT.md` as the first message, or type: *"Read docs/MASTER_PROMPT.md and
   follow it."*
   The new lead then:
   - re-reads the repo state;
   - re-creates the 10 reviewer lanes in the new org;
   - relaunches cloud builders for every unfinished lane from `cloud/handoff/*.md` plus each old PR's Handoff
     section;
   - continues the Mac-side work.

## 5. Mac permissions (only if prompted)
- Muselet itself needs:
  - **Accessibility, Screen Recording, Microphone, Contacts, Calendars**, all already granted;
  - **Automation** for System Events, Finder, Notes, Numbers, Messages, Music, Calendar and Reminders.
- If a prompt says **"Devin wants access to control Mail / Messages / Slack"**, click **Don't Allow**. The
  benchmark harness no longer needs it (it reads those apps through System Events now). If the new session runs
  under a different Devin app identity, macOS may ask again for Accessibility and Automation for that app; allow
  **Accessibility** for Devin, which the benchmark runners need.

## 6. When you're about to leave the Mac for benchmarks
Before you walk away:
- quit Mail, Messages, Notes, Reminders, Calculator, Numbers, TextEdit and Safari;
- close Finder windows;
- keep the default calendar set to **Muselet Bench**.
Then tell the lead "go". It runs the live suite and HobbyLM's 125 tasks with `caffeinate`, so the screen
doesn't lock.

## 7. After the switch
The old org's sessions stop on their own when its credits are gone. There's nothing to clean up. Their branches
and PRs stay on GitHub.
