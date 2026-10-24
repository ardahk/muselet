# hands — digest (pass 34)

Open findings were re-verified on main 2920225 in pass 15: hands-1 to 9 and 11 to 14 are resolved, and hands-15 is superseded.
Pass 21 checks:
- main d514300 merged HandsKit batch 5, already reviewed on wip/local 630d661/4350185. The only later Swift delta is precompiling the volume-state script and an always-present `label` in timers. The AGENTS.md batch-5 contract matches the code.
- wip/local b63699f is identical to main.
- cloud/brain-5 b752261 handles `not_frontmost` by reading the failure `result`. That works: RPC.swift returns r with r["error"], BrainConnection always sends `result`, and server.rpc returns it with ok=false.
No new defects.
Pass 34: open 0 P0, 2 P1, 2 P2.
- NEW P1 hands-17: cloud/app-ui and cloud/brain-7 each add `config`/`config_ack`, with incompatible acks (`ok` vs `loaded`). A successful brain-7 load shows "Not available" in the app. app-ui's server awaits config inline, which would block the receive loop during brain-7's 35B load. The two branches conflict in server.py and cli.py. LEAD DECISION: pick one schema and one semantics.
- NEW P1 hands-18 (medium confidence): panel example prompts run with the MenuBarExtra window possibly frontmost/key. Observe has no own-pid fallback (Observe.swift:440), so the agent may act on Muselet itself. The pill typed path is correct.
- cloud/app-ui afb2688 otherwise: HandsKit unchanged; mic-pill toggle reuses pressBegan ctx capture; typed requests keep the cancelled-confirm yes/no guard (handleFinal).
- cloud/brain-7 13432fe: new RPCs are only `act url` (sites.fix_url) and the brain-side compose_text skill; nothing new is needed from HandsKit.
- cloud/data-pipeline 6c1e565, cloud/decisions 184c80f, cloud/native-research fa88c22 and cloud/report dffa733: no app/ or protocol changes in my lane.
- hands-10 (Act.swift:348) and hands-16 (orchestrator.py:988) are unchanged on main c949565.
Pass 33: main c949565 adds two builder briefs only (cloud/builder_appui.md, cloud/builder_comms.md); there is no code yet. wip/local 4ec066f is identical to main. cloud/decisions e125c13 only touches training data. `app/` and the protocol are unchanged, and hands-10 and hands-16 are still open at the same lines.
Things to check when these briefs land (not findings, because nothing is built yet):
(a) The app-UI brief adds a new `config`/`config_ack` frame that is not yet in AGENTS.md, protocol.py or server.py. Check that both sides agree.
(b) The typed-request path (the pill's keyboard button) must capture utterance ctx before the Muselet text field takes focus, or ctx.app becomes Muselet (this would undo hands-9/11). The pill and panel must not activate Muselet over the target app (hands-8 focus).
(c) The comms brief adds a `contacts_search` RPC that HandsKit doesn't implement yet. Check that the Swift side returns `result` on errors.
Pass 32: main 5292608 changes only one AGENTS.md line (benchmark overlap note). wip/local a02959b is identical to main. `app/` and the protocol are unchanged, and hands-10 and hands-16 are still open at the same lines.
Pass 31: main 82d94d9 merged cloud/brain-6 (#21); orchestrator.py is identical to 780f49d, which I reviewed in pass 30. The new sendgate.py only adds browser names (Zen etc.) and makes no RPC/app changes; `app/` is unchanged. wip/local 5b3d695 is identical to main. hands-16 is now at orchestrator.py:988, and hands-10 is still at Act.swift:348.
Pass 30: cloud/brain-6 780f49d adds send and grounded-click confirmation gates and an OCR probe. The probe sends `ocr {region:[x,y,w,h]}`, which matches RPC.swift:152-160. No defects. hands-10 and hands-16 are still open on main b625ceb.
Pass 29: main b625ceb (spend guard, pitch-4 merge), wip/local 49f808f and cloud/data-pipeline 512cce0 have no app/ or protocol changes. hands-10 and hands-16 are still open on main.
Pass 28: main fbd5aa0, wip/local 2f26223, cloud/data-pipeline 735686f and cloud/pitch-4 6393857 have no app/ or protocol changes (AGENTS.md benchmark policy, evalcheck, pitch). hands-10 and hands-16 are still open on main.
Pass 27: main d7c192f, wip/local 367d450 and cloud/data-pipeline 0ce9ea6 have no app/ or protocol changes (serving config, AGENTS.md serving notes, training). hands-10 and hands-16 were re-checked on main and are still open.
Pass 26: main 04c3930 merged grounder-wire (PR #19; orchestrator and grounder identical to afb12a6, reviewed in pass 25) and pitch-3, and added `click "<description>"` to the planner prompt. There are no app/ changes. wip/local aec8fbf is identical to main. hands-16 has moved to orchestrator.py:981.
Pass 25: cloud/grounder-wire afb12a6 adds `click "<target>"`: window screenshot, then the Grounder with a native zoom region, then `act click {x,y}`. I checked it against HandsKit. The screenshot result keys path/width/height/origin/scale match RPC.swift:149-150. to_global = origin + px/scale matches Screenshot.swift:26 (pixels per point). act click takes global points (Act.swift:406-416) and runs the focus guard. Dangerous labels need confirmation, and screenshots are deleted after use. No defects. main 7147694, wip/local 5764a0d, pitch-3 and data-pipeline have no lane changes.
Pass 24: wip/local 0db1681 and cloud/data-pipeline 0c1ca3d have no app/ or protocol changes. hands-10 (Act.swift:348) and hands-16 (orchestrator.py:958) were re-checked and are still open on main d502b78.
Pass 23: main d502b78 merged cloud/hobby-gaps (PR #16). Its orchestrator is identical to hobby-gaps 156556e (calculator, volume and brightness routing reviewed in passes 17-18), so hands-16 is now on main. There are no app/ changes. wip/local c7c04ce is identical to main.
Pass 22: main 26ff05b merged cloud/brain-5 (its orchestrator is identical to b752261, reviewed in pass 21) plus argfix and the route parity reference. There are no app/ changes. wip/local 2c79363 is identical to main. hobby-gaps 861b991 only merges main; its app/ is identical to d514300. cloud/decisions and cloud/data-pipeline are outside the lane.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-16 (P2, now on main 04c3930:981): the calculator path should use one `type` act (keystroke_app is on main) instead of one `keys` act per character, which costs at least 120 ms of settle per character.
- hands-10 (P2): cap the act ghost-cursor lead at Act.swift:348 (main 26ff05b) with `min(lead, cursor_lead_ms/1000)`.
- Not filed: `appears` still matches substrings and counts other already-open windows of the same app.
