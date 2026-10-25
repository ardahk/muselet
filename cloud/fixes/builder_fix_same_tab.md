# Lane: fix-same-tab — keep browsing in the user's current tab

User: "navigate to wikipedia" then "search for history" opened the search in a NEW tab; "when I'm navigating in a tab
I want it on the same page; e.g. 'add some chicken to my cart' on Amazon should happen in the same tab". Branch
`cloud/fix-same-tab`, one PR; Swift (uncompiled, own commit, `## Mac requests`) + Python.
- HandsKit `open_url {url, browser?, same_tab?}`: when `same_tab` and the target browser is frontmost with a window,
  navigate the current tab (focus the address bar with cmd+L, type the URL, Return; verify the title/URL changed),
  else open as today. Report `same_tab_used`.
- Brain: memory follow-ups (site_search etc.) and "go to / navigate to / open <site>" while a browser is frontmost use
  `same_tab=true`; "new tab"/"open ... in a new tab" or no browser in front keep a new tab.
- On-page tasks ("add some chicken to my cart", "click the first result", "play the first video") while a site is in
  front go to the planner with the page observation (no new tab, no new search engine), acting in the page.
- Tests with fakes; AGENTS.md RPC line.
