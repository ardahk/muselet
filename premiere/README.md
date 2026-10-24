# Muselet Bridge — Premiere Pro UXP plugin

> **UNTESTED.** This plugin was written from the official UXP Premiere Pro docs
> (https://developer.adobe.com/premiere-pro/uxp/) and samples
> (https://github.com/AdobeDocs/uxp-premiere-pro-samples) without access to Premiere Pro. Only the
> command dispatch and websocket transport were exercised, under Node against a mocked `premierepro`
> module. Expect fixes on first load in Premiere Pro 26.x.

`muselet-bridge/` is a UXP **panel** plugin (manifest v5). UXP plugins can only be WebSocket *clients*,
so the panel connects **out** to the muselet brain at `ws://127.0.0.1:8766` (reconnects with backoff
from 0.5s up to 10s), sends a `{"t":"hello",...}` frame, then runs one command per frame:

```
-> {"id":"r1","cmd":"add_marker","args":{"name":"intro"}}
<- {"id":"r1","ok":true,"result":{"name":"intro","time":12.4}}
<- {"id":"r2","ok":false,"error":"not_supported","detail":"..."}
```

| cmd | args | Premiere API (docs page) |
|---|---|---|
| `sequence_info` | – | `Sequence.name/getEndTime/getPlayerPosition/getVideoTrack(Count)/getAudioTrack(Count)`, `VideoTrack.getTrackItems`, `VideoClipTrackItem.getName/getStartTime/getEndTime` |
| `add_marker` | `name?`, `comments?` | `Markers.getMarkers` + `Markers.createAddMarkerAction` at the playhead |
| `razor_at_playhead` | – | **not_supported**: no razor/split API is documented. Send `cmd+k` from the app instead. |
| `add_transition` | `index` (clip i on V1, 0-based), `track?`, `match_name?`, `duration?` (s) | `TransitionFactory` + `AddTransitionOptions` + `VideoClipTrackItem.createAddVideoTransitionAction` (end of clip i, double-sided; prefers "Cross Dissolve") |
| `move_playhead` | `seconds` | `Sequence.setPlayerPosition(TickTime.createWithSeconds)` |
| `export_sequence` | `preset_path` (.epr), `output_path`, `queue_to_ame?`, `full?` | `EncoderManager.getManager().exportSequence(seq, ExportType.IMMEDIATELY, out, preset, full)` |
| `undo` | – | **not_supported**: no undo API is documented. Send `cmd+z` from the app instead. |
| `ping` | – | – |

Every edit is wrapped in `project.lockedAccess(() => project.executeTransaction(...))`. Since 26.3,
actions must be created inside the lock, so each edit is a single undo step labelled `Muselet: ...`.

## Load the unsigned dev plugin (macOS)

1. Install **UXP Developer Tools** (UDT, v2.2 or later) from the Creative Cloud desktop app (All apps → "UXP Developer Tools").
   UDT needs admin rights.
2. Launch UDT and click **Enable** when it asks to turn on Developer Mode. If that fails, quit UDT, create
   `/Library/Application Support/Adobe/UXP/Developer/settings.json` containing `{"developer": true}`
   (needs `sudo`), then relaunch UDT.
3. Start **Premiere Pro 26.x** and open a project with an active sequence.
4. In UDT, click **Add Plugin** and select `premiere/muselet-bridge/manifest.json`.
5. On the plugin row, choose **••• → Load & Watch** (or **Load**). A green toast means it loaded. If it fails,
   open **Details** for the log.
6. In Premiere, open **Window → UXP Plugins → Muselet Bridge**. The panel must be open for the socket to run.
   It shows `connected`, or `disconnected, retry in Ns`.
7. Debug with the **`{}`** button in UDT, which opens Chrome DevTools (console logs are prefixed `[muselet]`).
   After editing `manifest.json`, **Unload** and then **Load** again; Watch does not pick up manifest changes.

## Manifest permissions

```json
"requiredPermissions": { "network": { "domains": ["ws://127.0.0.1:8766", "ws://localhost:8766"] } }
```
Without the `network` permission, all socket connections fail. The docs only show `https://` and `wss://`
domain examples, and they note that "macOS restricts `http://`". If Premiere blocks the plain `ws://`
loopback connection, try these in order:
1. Use `"domains": "all"`.
2. If that still fails, serve the brain endpoint over `wss://` with a locally trusted certificate.

Other gaps to check on first load:
- `host.minVersion` is `26.0.0`. The docs list the APIs used here as available since 25.6.
- No icons are bundled. Add `icons` entries if UDT warns about missing icons.

## Test with the tiny websocket server

```
uv run --project ml python premiere/test_server.py            # interactive: type `sequence_info` or `move_playhead {"seconds": 3}`
uv run --project ml python premiere/test_server.py --script   # smoke test: ping, sequence_info, move_playhead,
                                                              # add_marker, razor/undo (expect not_supported), unknown cmd
```
Start the server first, then open or reload the panel. Press **Reconnect** in the panel to retry right away.
The smoke script edits the open sequence: it moves the playhead and adds one marker (Cmd+Z removes the marker).
