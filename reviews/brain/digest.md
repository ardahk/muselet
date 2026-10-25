# Brain lane digest — pass 76 (2026-10-25T06:55Z)

Open: **P0 0 / P1 13 / P2 20**. New: brain-59 (main), brain-60, brain-61 (agentic-evidence), brain-62 (browser-flow). Moved to main: brain-57, brain-58.

## Branches
- **main de1070d**: merged agentic-apps, f30bf1d auto-done (timer/cart progress evidence), cart re-add refusal, loading text markers; test double fixed.
- **wip/local 52e4b94**: snapshot on main; lane identical.
- **cloud/agentic-evidence c4703c4** (on main): one evidence() for done + auto-done, app kinds auto-finish -> brain-60, brain-61.
- **cloud/app-knowhow fc92f6b** (on dc40e17): route-hint tips; no finding.
- **cloud/browser-flow c0421e6** (on dc40e17): default browser, in-task same tab, compound fallback -> brain-62.

## New
- **brain-60 (P1)**: auto-done accepts done with no verification; email evidence with no body accepts a filled To: field.
- **brain-59 (P2)**: timer cancel/stop auto-done fires with no Clock on screen.
- **brain-61 (P2)**: user approves the send, brain stops and says "press Send".
- **brain-62 (P2, code reading)**: compound fallback replays the whole utterance after earlier steps ran.

## Tests (MLX stub, Linux)
- main/wip 18 MLX-only / 2396 passed; agentic-evidence 19 (+stale stub) / 2434; app-knowhow 18 / 2376; browser-flow 18 / 2363.
- Pass76 repros: main 2/2 timer fail; agentic-evidence 4/4 fail.
