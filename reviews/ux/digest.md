# ux digest — pass 33

Heads: main c949565 (unchanged), wip/local 4ec066f (= main), new cloud/app-ui afb2688, cloud/brain-7 13432fe,
cloud/native-research fa88c22 and cloud/report dffa733 (docs only), cloud/decisions 184c80f and cloud/data-pipeline
6c1e565 (no lane files).

Counts: 0 P0, 1 P1 (branch-only), 9 P2 (8 on main, 1 branch-only).

New
- ux-21 P1 (brain-7 x app-ui): the two branches use different config_ack shapes. brain-7 sends `{escalate_planner, loaded}`
  with no `ok`; app-ui's ConfigAck.parse falls back to ok=false, so a successful 35B load shows "Not available". Both
  branches also add a config handler to server.py and will conflict when merged. Pick one schema before merging either.
- ux-22 P2 (brain-7): the app sends the persisted toggle on every reconnect, and brain-7 then loads the 35B on the shared
  MLX worker, so the first planner requests after a brain restart queue behind the load with only "thinking" on screen
  (load time not measured).

Rechecks
- ux-12: brain-7 adds three sign-in-gate prompts that also set ui("listening") while the mic is off.
- ux-15: the app-ui tooltip is now honest, but the row still counts only granted apps and shows "Grant" for not-running ones.
- ux-14, ux-16, ux-17, ux-18, ux-19, ux-20: unchanged on main.

app-ui otherwise looks sound: typed and example requests reuse the utterance path with ctx captured before Muselet
takes focus (RequestCtx), the pill mic toggles pressBegan/pressEnded, and config is re-sent after hello on reconnect.
Swift was not compiled (Linux).
