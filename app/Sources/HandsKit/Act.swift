import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import OSAKit

public enum HandsError: Error, CustomStringConvertible {
    case staleRef(Int)
    case invalidParams(String)
    case permission(String)
    case notImplemented(String)
    case needsConfirmation
    case skillFailed(String)
    /// The frontmost app is not the observed/target app and could not be
    /// re-activated: never type into the wrong app.
    case focusChanged(expected: String, frontmost: String)
    case `internal`(String)
    public var description: String {
        switch self {
        case .staleRef(let r): return "stale_ref #\(r)"
        case .invalidParams(let s): return "invalid params: \(s)"
        case .permission(let s): return "permission: \(s)"
        case .notImplemented(let s): return "not_implemented: \(s)"
        case .needsConfirmation: return "needs_confirmation"
        case .skillFailed(let s): return s
        case .focusChanged(let want, let got):
            return "focus_changed: frontmost is \(got), expected \(want)"
        case .internal(let s): return s
        }
    }
    public var code: String {
        switch self {
        case .staleRef: return "stale_ref"
        case .needsConfirmation: return "needs_confirmation"
        case .notImplemented: return "not_implemented"
        case .focusChanged: return "focus_changed"
        default: return "error"
        }
    }
}

/// App-side hooks (ghost cursor, skill HUD, timer bubble). Implemented by
/// the menu-bar app; the headless CLI leaves it nil so no flight time is
/// added. All methods are called off the main thread.
public protocol HandsDelegate: AnyObject {
    /// Called on the hands queue right before an action touches the UI.
    /// frame: global top-left points (nil for untargeted ops). Return the
    /// seconds to wait before executing (ghost-cursor flight time).
    func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval
    /// Called after the action and settle complete.
    func handsDidAct(op: String, frame: CGRect?, ok: Bool)
    /// Called after a `skill` RPC finished. `result` is the full skill
    /// response `{ok, result?, error?, ms}`; read-back values live in
    /// `result["result"]` (e.g. `{level, muted}` for volume skills).
    func handsDidRunSkill(name: String, args: [String: Any], result: [String: Any])
    /// A `start_timer` timer fired (on the timer queue).
    func handsTimerFired(label: String?)
}

public extension HandsDelegate {
    func handsDidRunSkill(name: String, args: [String: Any], result: [String: Any]) {}
    func handsTimerFired(label: String?) {}
}

// MARK: - CGEvent helpers

/// All posts go through `SyntheticEvent.post` (tagged with eventSourceUserData).
enum Events {
    static func click(at p: CGPoint, button: CGMouseButton = .left, clicks: Int = 1) {
        let downType: CGEventType = button == .left ? .leftMouseDown : .rightMouseDown
        let upType: CGEventType = button == .left ? .leftMouseUp : .rightMouseUp
        for i in 1...max(1, clicks) {
            if let d = CGEvent(mouseEventSource: nil, mouseType: downType,
                               mouseCursorPosition: p, mouseButton: button) {
                if i > 1 { d.setIntegerValueField(.mouseEventClickState, value: Int64(i)) }
                SyntheticEvent.post(d)
            }
            if let u = CGEvent(mouseEventSource: nil, mouseType: upType,
                               mouseCursorPosition: p, mouseButton: button) {
                if i > 1 { u.setIntegerValueField(.mouseEventClickState, value: Int64(i)) }
                SyntheticEvent.post(u)
            }
            if clicks > 1 { usleep(50_000) }
        }
    }

    static func move(to p: CGPoint) {
        if let e = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved,
                           mouseCursorPosition: p, mouseButton: .left) {
            SyntheticEvent.post(e)
        }
    }

    static func cursorPosition() -> CGPoint {
        CGEvent(source: nil)?.location ?? .zero
    }

    static func scroll(at p: CGPoint, direction: String, units: Int) {
        var w1: Int32 = 0, w2: Int32 = 0
        let amt = Int32(max(1, units))
        switch direction.lowercased() {
        case "up": w1 = amt
        case "down": w1 = -amt
        case "left": w2 = amt
        case "right": w2 = -amt
        default: w1 = -amt
        }
        if let e = CGEvent(scrollWheelEvent2Source: nil, units: .line,
                           wheelCount: 2, wheel1: w1, wheel2: w2, wheel3: 0) {
            e.location = p
            SyntheticEvent.post(e)
        }
    }

    static func typeText(_ s: String) {
        let src = CGEventSource(stateID: .hidSystemState)
        for ch in s {
            var utf16 = Array(String(ch).utf16)
            if let d = CGEvent(keyboardEventSource: src, virtualKey: 0, keyDown: true) {
                d.flags = []
                d.keyboardSetUnicodeString(stringLength: utf16.count,
                                           unicodeString: &utf16)
                SyntheticEvent.post(d)
            }
            if let u = CGEvent(keyboardEventSource: src, virtualKey: 0, keyDown: false) {
                SyntheticEvent.post(u)
            }
            usleep(2_000)
        }
    }

    static func key(_ code: CGKeyCode, flags: CGEventFlags = []) {
        let src = CGEventSource(stateID: .hidSystemState)
        if let d = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true) {
            d.flags = flags; SyntheticEvent.post(d)
        }
        if let u = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false) {
            u.flags = flags; SyntheticEvent.post(u)
        }
    }
}

// MARK: - UI settle watcher

private final class SettleState {
    var lastEvent = Date.distantPast
    var count = 0
}

private let kSettleNotifications = [
    kAXFocusedUIElementChangedNotification, kAXValueChangedNotification,
    kAXTitleChangedNotification, kAXWindowCreatedNotification,
    kAXUIElementDestroyedNotification, kAXLayoutChangedNotification,
]

private func settleCallback(_ observer: AXObserver, _ element: AXUIElement,
                            _ name: CFString, _ refcon: UnsafeMutableRawPointer?) {
    guard let r = refcon else { return }
    let s = Unmanaged<SettleState>.fromOpaque(r).takeUnretainedValue()
    s.lastEvent = Date()
    s.count += 1
}

extension Hands {
    /// Wait for the app UI to settle: 120 ms of AX-notification quiet, or two
    /// identical consecutive snapshot hashes. Hard timeout 1.5 s.
    func waitForSettle(pid: pid_t, timeout: TimeInterval = 1.5,
                       quiet: TimeInterval = 0.12) -> Double {
        let start = Date()
        let state = SettleState()
        var observer: AXObserver?
        if AXObserverCreate(pid, settleCallback, &observer) == .success, let obs = observer {
            let appEl = AXUIElementCreateApplication(pid)
            for n in kSettleNotifications {
                AXObserverAddNotification(obs, appEl, n as CFString,
                                          Unmanaged.passUnretained(state).toOpaque())
            }
            CFRunLoopAddSource(CFRunLoopGetCurrent(),
                               AXObserverGetRunLoopSource(obs), .defaultMode)
        }
        defer {
            if let obs = observer {
                CFRunLoopRemoveSource(CFRunLoopGetCurrent(),
                                      AXObserverGetRunLoopSource(obs), .defaultMode)
            }
        }
        var lastHash = ""
        var stable = 0
        while Date().timeIntervalSince(start) < timeout {
            CFRunLoopRunInMode(.defaultMode, 0.03, false)
            if state.count > 0 && Date().timeIntervalSince(state.lastEvent) >= quiet { break }
            let h = snapshotHash()
            if h == lastHash { stable += 1 } else { stable = 0; lastHash = h }
            if stable >= 2 && Date().timeIntervalSince(start) >= 0.12 { break }
        }
        return Date().timeIntervalSince(start) * 1000
    }

    private func snapshotHash() -> String {
        var parts: [String] = [NSWorkspace.shared.frontmostApplication?.localizedName ?? ""]
        if let app = NSWorkspace.shared.frontmostApplication {
            let el = AXUIElementCreateApplication(app.processIdentifier)
            var v: CFTypeRef?
            var win: AXUIElement?
            if AXUIElementCopyAttributeValue(el, kAXFocusedWindowAttribute as CFString, &v) == .success,
               let w = v { win = (w as! AXUIElement) }
            if let win {
                var t: CFTypeRef?
                if AXUIElementCopyAttributeValue(win, kAXTitleAttribute as CFString, &t) == .success,
                   let s = t as? String { parts.append(s) }
                var kids: CFTypeRef?
                if AXUIElementCopyAttributeValue(win, kAXChildrenAttribute as CFString, &kids) == .success,
                   let arr = kids as? [Any] { parts.append("\(arr.count)") }
            }
            var fe: CFTypeRef?
            if AXUIElementCopyAttributeValue(el, kAXFocusedUIElementAttribute as CFString, &fe) == .success,
               let f = fe {
                let a = AXNode(f as! AXUIElement).copyAttrs()
                let valPrefix = String("\(a.value ?? "")".prefix(30))
                parts.append("\(a.role ?? "")|\(a.title ?? a.desc ?? "")|\(valPrefix)")
            }
        }
        return parts.joined(separator: "|")
    }
}

// MARK: - act dispatch

extension Hands {
    /// Execute one DSL op. params: {op, ref?, epoch?, text?, combo?, x?, y?,
    /// direction?, n?, right?, double?, name?, url?, ms?, expect?,
    /// expect_timeout_ms? (default 1500), cursor_lead_ms?}
    public func act(_ params: [String: Any]) -> [String: Any] {
        let t0 = Date()
        var out: [String: Any] = [:]
        do {
            guard let op = params["op"] as? String else {
                throw HandsError.invalidParams("missing op")
            }
            // Parse expect up front: a bad predicate must fail before acting.
            var pred: ExpectPredicate? = nil
            if let exp = params["expect"] {
                do { pred = try Expect.parse(json: exp) }
                catch { throw HandsError.invalidParams("\(error)") }
            }
            // Refs are valid only in the window session they were minted in;
            // an epoch older than the session start is stale_ref too.
            var refRec: ElementRecord? = nil
            if let r = intParam(params, "ref") {
                refRec = try element(ref: r, epoch: intParam(params, "epoch"))
            }
            // Ghost-cursor hook: the app may animate a cursor to the target
            // first; headless has no delegate so no delay is added.
            var targetFrame: CGRect? = refRec?.frame
            if op == "click",
               let x = doubleParam(params, "x"), let y = doubleParam(params, "y") {
                targetFrame = CGRect(x: x, y: y, width: 1, height: 1)
            }
            let lead = delegate?.handsWillAct(
                op: op, frame: targetFrame, label: refRec?.label) ?? 0
            if lead > 0 { usleep(UInt32(min(lead, 5.0) * 1_000_000)) }

            // Synthesized input must land in the observed app (hands-8).
            if ["type", "keys", "click"].contains(op) { try ensureTargetFocus() }

            let pidForSettle = lastObservedPid()
            var scriptResult: [String: Any]? = nil
            switch op {
            case "press":
                guard let rec = refRec else { throw HandsError.invalidParams("press needs ref") }
                if !rec.element.performAction(kAXPressAction)
                    && !rec.element.performAction("AXConfirm") {
                    try ensureTargetFocus()
                    Events.click(at: CGPoint(x: rec.frame.midX, y: rec.frame.midY))
                }
            case "type":
                guard let rec = refRec else { throw HandsError.invalidParams("type needs ref") }
                let text = params["text"] as? String ?? ""
                _ = rec.element.setAttr(kAXFocusedAttribute, true)
                usleep(30_000)
                if rec.inWebArea {
                    // React-style inputs ignore AXValue: select-all + type.
                    Combo.post(try Combo.parse("cmd+a"))
                    Events.typeText(text)
                } else if rec.element.isSettable(kAXValueAttribute) {
                    _ = rec.element.setAttr(kAXValueAttribute, text)
                } else {
                    Events.typeText(text)
                }
                if params["enter"] as? Bool == true { Events.key(36) }
            case "keys":
                guard let c = params["combo"] as? String else {
                    throw HandsError.invalidParams("keys needs combo")
                }
                Combo.post(try Combo.parse(c))
            case "scroll":
                guard let rec = refRec else { throw HandsError.invalidParams("scroll needs ref") }
                let dir = params["direction"] as? String ?? "down"
                let n = intParam(params, "n") ?? 3
                Events.scroll(at: CGPoint(x: rec.frame.midX, y: rec.frame.midY),
                              direction: dir, units: n)
            case "click":
                guard let x = doubleParam(params, "x"), let y = doubleParam(params, "y") else {
                    throw HandsError.invalidParams("click needs x,y")
                }
                let p = CGPoint(x: x, y: y)
                let orig = Events.cursorPosition()
                let right = params["right"] as? Bool ?? false
                let dbl = params["double"] as? Bool ?? false
                Events.move(to: p)
                Events.click(at: p, button: right ? .right : .left, clicks: dbl ? 2 : 1)
                Events.move(to: orig)
            case "open":
                guard let name = params["name"] as? String ?? params["app"] as? String else {
                    throw HandsError.invalidParams("open needs name")
                }
                let pid = try openAppNamed(name)
                // Let activation land before the fused re-observation, so
                // the session (and the focus guard) binds to the new app.
                if pid > 0 { _ = waitFrontmost(pid: pid, timeout: 2.0) }
            case "url":
                guard let s = params["url"] as? String, let u = URL(string: s) else {
                    throw HandsError.invalidParams("url needs url")
                }
                let handler = NSWorkspace.shared.urlForApplication(toOpen: u)
                    .flatMap { Bundle(url: $0)?.bundleIdentifier }
                NSWorkspace.shared.open(u)
                if let bid = handler,
                   let app = apps.runningApp(bundlePrefix: bid) ?? waitRunning(bundleId: bid, timeout: 2.0) {
                    _ = waitFrontmost(pid: app.pid, timeout: 1.5)
                }
            case "wait":
                let ms = intParam(params, "ms") ?? 500
                usleep(UInt32(min(ms, 60_000)) * 1000)
            case "script":
                guard let lang = params["lang"] as? String,
                      let code = params["code"] as? String else {
                    throw HandsError.invalidParams("script needs lang+code")
                }
                scriptResult = try runScript(lang: lang, code: code)
            default:
                throw HandsError.invalidParams("unknown op \(op)")
            }
            out["act_ms"] = (Date().timeIntervalSince(t0) * 1000).rounded(to: 2)
            if let sr = scriptResult {
                for (k, v) in sr { out[k] = v }
            }

            // Settle, then fused re-observation for diff_text + expect.
            let pid = pidForSettle != 0 ? pidForSettle : apps.frontmostPid()
            let baseline = previous             // pre-act records (cumulative diff)
            let settleStart = Date()
            let settleMs = settleOverride?(pid) ?? waitForSettle(pid: pid)
            out["settle_ms"] = settleMs.rounded(to: 2)
            let reobserve: () -> Observation? = { [unowned self] in
                if let o = self.observeOverride { return try? o() }
                return try? self.observe(scope: "focused_window", diff: true)
            }
            var post = reobserve()
            var sawFull = post?.full ?? false

            var expectOK = true
            if let pred {
                // Poll: a slow UI (page load, sheet, document open) may pass
                // later; re-observe ~every 80 ms until it passes or times out.
                let timeout = Double(max(0, intParam(params, "expect_timeout_ms") ?? 1500)) / 1000
                let deadline = Date().addingTimeInterval(timeout)
                var (ok, observed) = post.map { evalExpect(pred, $0, deadline: deadline) }
                    ?? (false, "no observation")
                var polls = 0
                while !ok && Date() < deadline {
                    let tick = Date()
                    let remaining = deadline.timeIntervalSince(tick)
                    usleep(UInt32(max(0, min(0.08, remaining)) * 1_000_000))
                    polls += 1
                    if let o = reobserve() {
                        post = o
                        sawFull = sawFull || o.full
                        (ok, observed) = evalExpect(pred, o, deadline: deadline)
                    }
                }
                if polls > 0 {
                    // Time from settle start until the predicate passed (or gave up).
                    out["settle_ms"] = (Date().timeIntervalSince(settleStart) * 1000).rounded(to: 2)
                    out["expect_polls"] = polls
                }
                out["expect_ok"] = ok
                out["observed"] = observed
                expectOK = ok
                if !ok { out["error"] = "expect_failed: \(observed)" }
            }
            out["epoch"] = currentEpoch
            if let post {
                if sawFull {
                    out["diff_text"] = ""
                    out["full"] = true
                } else {
                    // Cumulative diff vs the pre-act state (refs are unique,
                    // so a ref present in both is the same element).
                    let old = Set(baseline.map { $0.ref })
                    var matched: [Int: Int] = [:]
                    for e in post.elements where old.contains(e.ref) { matched[e.ref] = e.ref }
                    out["diff_text"] = Differ.diff(old: baseline, new: post.elements, matched: matched)
                }
            }
            out["ok"] = expectOK
            delegate?.handsDidAct(op: op, frame: targetFrame, ok: expectOK)
            return out
        } catch let e as HandsError {
            out["ok"] = false
            out["error"] = e.description
            out["act_ms"] = (Date().timeIntervalSince(t0) * 1000).rounded(to: 2)
            delegate?.handsDidAct(op: params["op"] as? String ?? "?",
                                  frame: nil, ok: false)
            return out
        } catch {
            out["ok"] = false
            out["error"] = "\(error)"
            out["act_ms"] = (Date().timeIntervalSince(t0) * 1000).rounded(to: 2)
            delegate?.handsDidAct(op: params["op"] as? String ?? "?",
                                  frame: nil, ok: false)
            return out
        }
    }

    /// script op: applescript via cached NSAppleScript, jxa via OSAKit,
    /// shell via /bin/zsh -c with a 10 s timeout.
    private func runScript(lang: String, code: String) throws -> [String: Any] {
        switch lang {
        case "applescript":
            let out = try scripts.run(code)
            return ["output": out]
        case "jxa":
            return ["output": try runJXA(code)]
        case "shell":
            return try runShell(code)
        default:
            throw HandsError.invalidParams("unknown script lang \(lang)")
        }
    }

    private func runJXA(_ code: String) throws -> String {
        guard let jxa = OSALanguage(forName: "JavaScript") else {
            throw HandsError.internal("JXA unavailable")
        }
        let script = OSAScript(source: code, language: jxa)
        var err: NSDictionary?
        let out = script.executeAndReturnError(&err)
        if let e = err {
            throw HandsError.skillFailed(
                "jxa: \((e["NSAppleScriptErrorMessage"] as? String) ?? "\(e)")")
        }
        return out?.stringValue ?? ""
    }

    private func runShell(_ code: String) throws -> [String: Any] {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-c", code]
        let outP = Pipe(), errP = Pipe()
        p.standardOutput = outP
        p.standardError = errP
        try p.run()
        let done = DispatchSemaphore(value: 0)
        DispatchQueue.global().async { p.waitUntilExit(); done.signal() }
        var rc = p.terminationStatus
        var timedOut = false
        if done.wait(timeout: .now() + 10) == .timedOut {
            p.terminate()
            timedOut = true
            _ = done.wait(timeout: .now() + 2)
        }
        rc = p.terminationStatus
        let outS = String(data: outP.fileHandleForReading.readDataToEndOfFile(),
                          encoding: .utf8) ?? ""
        let errS = String(data: errP.fileHandleForReading.readDataToEndOfFile(),
                          encoding: .utf8) ?? ""
        var r: [String: Any] = ["stdout": outS, "stderr": errS,
                                "exit_code": Int(rc), "output": outS]
        if timedOut {
            throw HandsError.skillFailed("shell timed out (10s): \(errS)")
        }
        if rc != 0 {
            r["exit_code"] = Int(rc)
            return r   // output still reported; caller decides
        }
        return r
    }

    private func lastObservedPid() -> pid_t {
        lastPid != 0 ? lastPid : apps.frontmostPid()
    }

    /// hands-8: synthesized keys/typing/clicks must go to the observed app.
    /// If another app is frontmost, activate the target and wait <= 300 ms;
    /// still wrong -> focus_changed (never type into the wrong app).
    /// After a skill switched apps on purpose (`focusRebindPending`), or
    /// with no observation yet, the current frontmost app is the target.
    func ensureTargetFocus() throws {
        let target = lastPid
        guard target > 0, !focusRebindPending, target != getpid() else { return }
        if apps.frontmostPid() == target { return }
        if apps.ensureFrontmost(pid: target, timeout: 0.3) { return }
        throw HandsError.focusChanged(expected: apps.name(pid: target),
                                      frontmost: apps.name(pid: apps.frontmostPid()))
    }

    func waitFrontmost(pid: pid_t, timeout: TimeInterval) -> Bool {
        let end = Date().addingTimeInterval(timeout)
        while Date() < end {
            if apps.frontmostPid() == pid { return true }
            usleep(20_000)
        }
        return apps.frontmostPid() == pid
    }

    func waitRunning(bundleId: String, timeout: TimeInterval) -> RunningAppInfo? {
        let end = Date().addingTimeInterval(timeout)
        while Date() < end {
            if let a = apps.runningApp(bundlePrefix: bundleId) { return a }
            usleep(50_000)
        }
        return nil
    }
}

/// Launch or activate an app by name. Returns its pid (0 if unknown).
@discardableResult
func openAppNamed(_ name: String) throws -> pid_t {
    // Running first.
    if let running = NSWorkspace.shared.runningApplications.first(where: {
        ($0.localizedName ?? "").localizedCaseInsensitiveCompare(name) == .orderedSame
    }) {
        // AXFrontmost + activate (cooperative activation may ignore the latter).
        WorkspaceApps().activate(pid: running.processIdentifier)
        return running.processIdentifier
    }
    if let url = AppResolver.url(forAppNamed: name) {
        let cfg = NSWorkspace.OpenConfiguration()
        cfg.activates = true
        let sem = DispatchSemaphore(value: 0)
        var openErr: Error?
        var pid: pid_t = 0
        NSWorkspace.shared.openApplication(at: url, configuration: cfg) { app, err in
            openErr = err; pid = app?.processIdentifier ?? 0; sem.signal()
        }
        _ = sem.wait(timeout: .now() + 5)
        if let e = openErr { throw HandsError.skillFailed(e.localizedDescription) }
        return pid
    }
    throw HandsError.skillFailed("app not found: \(name)")
}

enum AppResolver {
    static func url(forAppNamed name: String) -> URL? {
        let fm = FileManager.default
        let dirs = ["/Applications", "/System/Applications",
                    NSHomeDirectory() + "/Applications"]
        let wanted = name.lowercased()
        for d in dirs {
            guard let items = try? fm.contentsOfDirectory(atPath: d) else { continue }
            for i in items where i.hasSuffix(".app") {
                let base = String(i.dropLast(4)).lowercased()
                if base == wanted { return URL(fileURLWithPath: d + "/" + i) }
            }
        }
        for d in dirs {
            guard let items = try? fm.contentsOfDirectory(atPath: d) else { continue }
            for i in items where i.hasSuffix(".app") {
                let base = String(i.dropLast(4)).lowercased()
                if base.contains(wanted) { return URL(fileURLWithPath: d + "/" + i) }
            }
        }
        return nil
    }
}

func intParam(_ p: [String: Any], _ k: String) -> Int? {
    if let i = p[k] as? Int { return i }
    if let n = p[k] as? NSNumber { return n.intValue }
    if let s = p[k] as? String { return Int(s) }
    return nil
}

func doubleParam(_ p: [String: Any], _ k: String) -> Double? {
    if let i = p[k] as? Double { return i }
    if let n = p[k] as? NSNumber { return n.doubleValue }
    if let s = p[k] as? String { return Double(s) }
    return nil
}

public extension Double {
    func rounded(to places: Int) -> Double {
        let m = pow(10.0, Double(places))
        return (self * m).rounded() / m
    }
}
