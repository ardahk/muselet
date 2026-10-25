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
            case "pill_hover":
                mascot.pill.mascotHover(info["on"] as? String != "false")
            case "pill_typing":
                // state=close: the Esc / X-button path (PillController.cancelTyping).
                if (info["state"] as? String ?? "open") == "close" {
                    mascot.pill.cancelTyping()
                } else {
                    mascot.pill.beginTyping(prefill: info["text"] as? String ?? "")
                }
            case "pill_slow":
                PillView.slowMotion = info["on"] as? String != "false"
            case "panel":
                // state=close hides it; appearance=light|dark|system first (screenshots).
                if let a = info["appearance"] as? String {
                    NSApp.appearance = a == "dark" ? NSAppearance(named: .darkAqua)
                        : a == "light" ? NSAppearance(named: .aqua) : nil
                }
                if info["state"] as? String == "close" { Self.closePanel() } else { Self.openPanel() }
            case "perm_fake":
                // Show a permission as missing in the panel (kind=microphone|...|none).
                let kind = info["kind"] as? String ?? "none"
                PanelView.debugMissing = Set(PermissionKind(rawValue: kind).map { [$0] } ?? [])
                model.objectWillChange.send()
            case "mascot_edge":
                // Same clamp as a live drag, pushed past an edge: left|right|top|bottom.
                mascot.debugDrag(toward: info["edge"] as? String ?? "left")
            case "icon_png":
                Self.writeIcon(to: info["dir"] as? String ?? NSTemporaryDirectory(),
                               recording: info["recording"] as? String == "true")
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

    /// Opens the MenuBarExtra panel. SwiftUI keeps its window after the first close
    /// (isVisible can stay true while it is hidden), so "open" means drawn on screen, and
    /// a stale window is presented directly rather than toggled through the status item.
    static func openPanel() {
        let windows = panelWindows()
        FileLog.shared.raw("debug panel: " + (windows.isEmpty ? "no window" : windows.map(describe).joined(separator: "; ")))
        if windows.contains(where: isOnScreen) { return }
        guard let button = statusButton() else {
            FileLog.shared.raw("debug panel: status bar button not found")
            return
        }
        if let w = windows.first { present(w, under: button); return }
        button.performClick(nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            let after = panelWindows()
            if after.contains(where: isOnScreen) { FileLog.shared.raw("debug panel: opened via click"); return }
            if let w = after.first { present(w, under: button) }
            else { FileLog.shared.raw("debug panel: no window after click") }
        }
    }

    static func closePanel() {
        panelWindows().filter(isOnScreen).forEach { $0.orderOut(nil) }
    }

    private static func panelWindows() -> [NSWindow] {
        NSApp.windows.filter { $0.className.contains("MenuBarExtraWindow") }
    }

    private static func statusButton() -> NSStatusBarButton? {
        NSApp.windows.filter { $0.className.contains("NSStatusBarWindow") }
            .compactMap { statusBarButton(in: $0.contentView) }.first
    }

    static func isOnScreen(_ w: NSWindow) -> Bool {
        w.isVisible && w.alphaValue > 0.01 && w.occlusionState.contains(.visible)
            && w.frame.width > 1 && NSScreen.screens.contains { $0.frame.intersects(w.frame) }
    }

    private static func describe(_ w: NSWindow) -> String {
        "visible=\(w.isVisible) alpha=\(w.alphaValue) occluded=\(!w.occlusionState.contains(.visible)) "
            + "key=\(w.isKeyWindow) frame=\(NSStringFromRect(w.frame))"
    }

    /// Top-centred under the status item (clamped to the screen), then key + front.
    private static func present(_ w: NSWindow, under button: NSStatusBarButton) {
        if let bw = button.window {
            let item = bw.convertToScreen(button.convert(button.bounds, to: nil))
            var x = item.midX - w.frame.width / 2
            if let vf = (bw.screen ?? NSScreen.main)?.visibleFrame {
                x = min(max(x, vf.minX + 8), vf.maxX - w.frame.width - 8)
            }
            w.setFrameTopLeftPoint(NSPoint(x: x, y: item.minY - 1))
        }
        w.alphaValue = 1
        NSApp.activate()
        w.makeKeyAndOrderFront(nil)
        FileLog.shared.raw("debug panel: presented directly " + describe(w))
    }

    /// The menu-bar glyph as PNGs at @1x and @2x (`<dir>/menubar-icon@{1,2}x.png`).
    static func writeIcon(to dir: String, recording: Bool) {
        let pt = MenuBarIcon.pointSize
        for scale in [1, 2] {
            let px = Int(pt) * scale
            guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px,
                                             bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                             isPlanar: false, colorSpaceName: .deviceRGB,
                                             bytesPerRow: 0, bitsPerPixel: 0) else { continue }
            rep.size = NSSize(width: pt, height: pt)
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
            MenuBarIcon.make(recording: recording).draw(in: NSRect(x: 0, y: 0, width: pt, height: pt))
            NSGraphicsContext.restoreGraphicsState()
            let url = URL(fileURLWithPath: dir).appendingPathComponent("menubar-icon@\(scale)x.png")
            try? rep.representation(using: .png, properties: [:])?.write(to: url)
            FileLog.shared.raw("debug icon: wrote \(url.path)")
        }
    }

    private static func statusBarButton(in view: NSView?) -> NSStatusBarButton? {
        guard let view else { return nil }
        if let button = view as? NSStatusBarButton { return button }
        for subview in view.subviews {
            if let button = statusBarButton(in: subview) { return button }
        }
        return nil
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
