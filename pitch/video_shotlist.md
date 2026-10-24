# Demo video shot list (3:00, 1080p, record at 2x)

Always visible: mascot + bubble (bottom-right default), ghost cursor, menu bar (Wi-Fi icon), latency readout
(panel, top-right). Record the full display with ScreenCaptureKit / QuickTime; crop in edit, never in capture.
Captions: white on 70% black, bottom-center, <= 8 words. Numbers only from `claims.md`.

| # | Time | Region | Must be visible | Caption |
|---|---|---|---|---|
| 1 | 0:00-0:06 | Full screen | Mascot idle, panel, menu bar Wi-Fi on | "Fully on-device. Apple Silicon." |
| 2 | 0:06-0:20 | Full + zoom on panel | Volume HUD, dark-mode flip, latency readout with `{{route_ms_p50}}` | "`{{route_ms_p50}}` ms to decide" |
| 3 | 0:20-0:50 | Chrome window | Ghost cursor to address bar, typing, results, mascot bubble | "Reads the accessibility tree" |
| 4 | 0:50-0:56 | Menu bar zoom (right third) | Wi-Fi icon turning off | "Wi-Fi off" |
| 5 | 0:56-1:34 | Full screen | Calendar -> Finder -> Numbers (BND/VNQ green, VXUS amber) -> Notes brief; Wi-Fi icon off | "Client data never leaves the Mac" |
| 6 | 1:34-2:00 | Numbers window | Receipt rows flagged (mismatch, no match); Wi-Fi icon off | "6 matched · 1 swapped digits · 1 missing" |
| 7 | 2:00-2:30 | Premiere timeline + program monitor | Cut at playhead, marker, Export dialog; ghost cursor | "Cut · marker · export by voice" |
| 8 | inserts | Terminal, small | `lsof` showing only 127.0.0.1 sockets (`{{outbound_conns}}`) | "Loopback only" |
| 9 | 2:30-2:45 | Slide | Table: Muselet vs HobbyLM vs DeskMind, same Mac, strict pass + latency, sample sizes, source URLs | "Same Mac. Their harnesses." |
| 10 | 2:45-3:00 | Full screen | Mascot "success", Wi-Fi icon off | "Hold a key. Say it. Done." |

B-roll / backups: one clean rehearsal take of shots 3, 5, 6 for the live-demo fallbacks. Keep the trace JSONL of
every take used (`runs/traces/`) so each on-screen number can be traced to a run.
