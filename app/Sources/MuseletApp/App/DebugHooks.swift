import AppKit
import HandsKit

/// Local demo/debug hooks over DistributedNotificationCenter ("ai.muselet.debug").
/// They only drive the UI (mascot, bubble, ghost-cursor preview, skill HUD,
/// timer-done bubble) — no OS actions are executed. See app/scripts/debug_ui.sh.
final class DebugHooks {
    private var observer: NSObjectProtocol?

    init(model: AppModel, ghost: GhostCursor, mascot: MascotController, brain: BrainConnection,
         rpc: RPCHandler, hud: SkillHUD, bridge: HandsBridge) {
        observer = DistributedNotificationCenter.default().addObserver(
            forName: Notification.Name("ai.muselet.debug"), object: nil, queue: .main) { n in
            let info = n.userInfo ?? [:]
            let cmd = info["cmd"] as? String ?? ""
            func num(_ k: String) -> CGFloat? {
                if let d = info[k] as? NSNumber { return CGFloat(d.doubleValue) }
                if let s = info[k] as? String, let d = Double(s) { return CGFloat(d) }
                return nil
            }
            FileLog.shared.raw("debug hook: \(cmd)")
            switch cmd {
            case "ghost":
                // Fly to an explicit CG rect (global, top-left points).
                guard let x = num("x"), let y = num("y") else { return }
                let rect = CGRect(x: x, y: y, width: num("w") ?? 1, height: num("h") ?? 1)
                let label = info["label"] as? String
                let op = info["op"] as? String ?? "press"
                let ok = (info["ok"] as? String).map { $0 != "false" } ?? true
                Self.preview(ghost: ghost, op: op, frame: rect, label: label, ok: ok)
            case "ghost-ax":
                // Observe the frontmost window via HandsKit and preview a press
                // on the element whose label contains `label` (or the first button).
                let want = (info["label"] as? String)?.lowercased()
                DispatchQueue.global(qos: .userInitiated).async {
                    let (ok, result, err) = rpc.handle(method: "observe",
                                                       params: ["scope": "focused_window", "max_nodes": 150])
                    guard ok, let r = result as? [String: Any],
                          let els = r["elements"] as? [[String: Any]] else {
                        FileLog.shared.raw("debug ghost-ax observe failed: \(err ?? "?")")
                        return
                    }
                    let pick = els.first { e in
                        guard let l = (e["label"] as? String)?.lowercased(), !l.isEmpty else { return false }
                        if let w = want { return l.contains(w) }
                        return (e["role"] as? String) == "button"
                    }
                    guard let e = pick, let f = e["frame"] as? [Double], f.count == 4 else {
                        FileLog.shared.raw("debug ghost-ax: no matching element")
                        return
                    }
                    Self.preview(ghost: ghost, op: "press",
                                 frame: CGRect(x: f[0], y: f[1], width: f[2], height: f[3]),
                                 label: e["label"] as? String, ok: true)
                }
            case "say":
                brain.onSay?(info["text"] as? String ?? "Hello!")
            case "ui":
                brain.onUI?(info["mascot"] as? String, info["bubble"] as? String,
                            num("ms").map(Double.init))
            case "latency":
                // Latency chip preview: same path as a final ui message with ms.
                brain.onUI?(info["mascot"] as? String ?? "success", info["bubble"] as? String,
                            Double(num("ms") ?? 212))
            case "confirm":
                brain.onConfirm?("debug-\(Int(Date().timeIntervalSince1970))",
                                 info["summary"] as? String ?? "Send the message to Mom?")
            case "confirm_cancel":
                brain.onConfirmCancel?((info["id"] as? String).flatMap { $0.isEmpty ? nil : $0 })
            case "skill_ghost":
                // Ghost flight to a skill's natural target (Dock icon / menu
                // extra) without running the skill: arg.<k>=<v> become args.
                let name = info["name"] as? String ?? "open_app"
                var args: [String: Any] = [:]
                for (k, v) in info {
                    if let key = k as? String, key.hasPrefix("arg.") { args[String(key.dropFirst(4))] = v }
                }
                DispatchQueue.global(qos: .userInitiated).async {
                    guard let t = rpc.skillTargets.target(skill: name, args: args) else {
                        FileLog.shared.raw("debug skill_ghost \(name): no visible target")
                        return
                    }
                    Self.preview(ghost: ghost, op: name, frame: t.frame, label: t.label, ok: true)
                }
            case "hud":
                // Preview the skill HUD without running the skill:
                //   kind=volume|mute|brightness|dark|wifi|bluetooth level=0..100 on=true|false
                //   style=glass|vibrancy (sticks for later HUDs)
                if let s = (info["style"] as? String).flatMap(SkillHUD.Style.init(rawValue:)) {
                    SkillHUD.style = s
                }
                let level = Int(num("level") ?? 50)
                let on = (info["on"] as? String).map { ["1", "true", "on", "yes"].contains($0.lowercased()) } ?? true
                let fb: SkillFeedback
                switch info["kind"] as? String ?? "volume" {
                case "mute": fb = .level(kind: .volume, level: level, muted: true)
                case "brightness": fb = .level(kind: .brightness, level: level, muted: false)
                case "dark", "dark_mode": fb = .toggle(kind: .darkMode, on: on)
                case "wifi": fb = .toggle(kind: .wifi, on: on)
                case "bluetooth": fb = .toggle(kind: .bluetooth, on: on)
                default: fb = .level(kind: .volume, level: level, muted: false)
                }
                hud.show(fb)
            case "timer":
                // Same path as a fired start_timer (bubble + success mood).
                let label = (info["label"] as? String).flatMap { $0.isEmpty ? nil : $0 }
                bridge.handsTimerFired(label: label)
            case "automation_status":
                // Automation consent per target, read without prompting
                // (targets that aren't running read not_running = unknown).
                DispatchQueue.global(qos: .utility).async {
                    FileLog.shared.raw("automation " + Automation.summaryLine(Automation.statuses()))
                }
            case "status":
                let p = Permissions.snapshot()
                FileLog.shared.raw("status brain=\(model.brainStatus) stt=\(model.sttState) ptt=\(model.pushToTalkActive) "
                    + "ax=\(p.accessibility) screen=\(p.screenRecording) mic=\(p.microphone) input=\(p.inputMonitoring) "
                    + "mascot=\(mascot.anchorCG())")
            default:
                break
            }
        }
    }

    /// Same call sequence HandsKit uses around an act: willAct -> wait -> didAct.
    static func preview(ghost: GhostCursor, op: String, frame: CGRect, label: String?, ok: Bool) {
        DispatchQueue.global(qos: .userInitiated).async {
            let lead = ghost.handsWillAct(op: op, frame: frame, label: label)
            usleep(UInt32(lead * 1_000_000))
            usleep(180_000)   // stand-in for act + settle
            ghost.handsDidAct(op: op, frame: frame, ok: ok)
        }
    }
}
