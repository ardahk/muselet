# Brain lane digest — pass 67 (2026-10-25T04:40Z)

Open: **P0 0 / P1 9 / P2 13**. New: brain-50. Moved to main: brain-49.

## Branches
- **main dc6f2f5** (from b340f24): merged cloud/fallback 36b421e, cloud/open-ended 0d687d2, cloud/fix-same-tab 0e38395, cloud/fix-pending 09dadc0, hands-clock-verify, design-polish, and premiere-demo (357660b: new tools/premiere_edit.py, OCR export polling).
  - fix-pending: server.py runs confirm-time utterances in `_interrupt_task`; receive loop not blocked; only recognized commands cancel the prompt.
  - fallback (default off): compose_text/draft_email pre-routes now wrapped in `_with_fallback`; send_message still excluded.
  - premiere_edit: every op confirmation-gated by default (`MUSELET_PREMIERE_CONFIRM=each`); export verified by a new Desktop .mp4. Routing is over-broad -> brain-50.
- **wip/local 6a1f942**: snapshot on main@dc6f2f5; lane matches main.
- **cloud/premiere-demo a1c0f04**: premiere_edit identical to main; branch is behind main otherwise.
- **cloud/fallback 36b421e**: in main. Branch-only suite has 3 stale CLI test fakes (main's merge fixed them).
- fix-pending / fix-same-tab / open-ended heads are all in main.

## New
- **brain-50 (P2, main)**: `premiere_edit.parse_request` matches any text containing "premiere" (any app), and export/render/marker/cut words when Premiere is front; `_engine_route` runs it before the router. "search google for premiere pro export settings" from Safari -> Premiere export confirm. Repro: tests/test_brain_pass67.py (4/4 fail on main).

## Rechecks
- brain-49 now on main (pass65 repro 3/3 fail on main).
- brain-47, brain-48 still fail on main. brain-22, brain-42, brain-43 unchanged.

## Tests (MLX stub, Linux)
- main: 18 failed (MLX-only), 2326 passed, 2 xfailed. Review repros: 29 failed (+3 brain-49) / 52 passed; pass67 4 failed.
- fallback 21 failed (18 MLX + 3 stale fakes); fix-pending, fix-same-tab, open-ended, premiere-demo: 18 MLX-only.
