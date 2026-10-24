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
    /// Nothing that accepts text has the keyboard focus (`observed` says
    /// which app/window/element is focused); nothing was typed.
    case noTextTarget(observed: String)
    /// The screen is locked (the lock screen has the keyboard): synthetic
    /// keys, typing and clicks would land in it, so none are posted.
    case screenLocked
    /// The action ran but its read-back says it didn't take effect: `code`
    /// is the error (e.g. `not_frontmost`), `result` what was observed
    /// (still returned with ok=false).
    case verifyFailed(code: String, observed: String, result: [String: Any])
    case `internal`(String)
    /// Extra `observed` hint for the response, if any.
    public var observed: String? {
        switch self {
        case .noTextTarget(let o): return o
        case .screenLocked: return "the screen is locked"
        case .verifyFailed(_, let o, _): return o
        default: return nil
        }
    }
    /// Result payload to return with ok=false, if any.
    public var result: [String: Any]? {
        if case .verifyFailed(_, _, let r) = self { return r }
        return nil
    }
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
        case .noTextTarget: return "no_text_target"
        case .screenLocked: return "screen_locked"
        case .verifyFailed(let c, _, _): return c
        case .internal(let s): return s
        }
    }
    public var code: String {
        switch self {
        case .staleRef: return "stale_ref"
        case .needsConfirmation: return "needs_confirmation"
        case .notImplemented: return "not_implemented"
        case .focusChanged: return "focus_changed"
        case .noTextTarget: return "no_text_target"
        case .screenLocked: return "screen_locked"
        case .verifyFailed(let c, _, _): return c
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

    /// Keystroke-driven apps (Calculator, `TextTarget.keystrokeApps`): each
    /// character as its US-ANSI virtual key (+ shift) with the unicode
    /// string set too, so an app that reads the key code and one that reads
    /// the characters both get it. Unmapped characters go as unicode only.
    static func typeKeystrokes(_ s: String) {
        let src = CGEventSource(stateID: .hidSystemState)
        for ch in s {
            let (code, shift) = keystroke(for: ch) ?? (0, false)
            var utf16 = Array((ch == "\n" ? "\r" : String(ch)).utf16)
            let flags: CGEventFlags = shift ? .maskShift : []
            for down in [true, false] {
                guard let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down) else { continue }
                e.flags = flags
                e.keyboardSetUnicodeString(stringLength: utf16.count, unicodeString: &utf16)
                SyntheticEvent.post(e)
            }
            usleep(4_000)
        }
    }

    /// US-ANSI virtual key (and shift) for a character a calculator takes:
    /// digits, letters, `+ - * / = . , % ( ) ^`, space, tab, return.
    static func keystroke(for ch: Character) -> (CGKeyCode, Bool)? {
        let shifted: [Character: CGKeyCode] = [
            "+": 24, "*": 28, "(": 25, ")": 29, "%": 23, "^": 22, "!": 18, "_": 27,
        ]
        if let c = shifted[ch] { return (c, true) }
        switch ch {
        case "\n", "\r": return (36, false)
        case "\t": return (48, false)
        case " ": return (49, false)
        default: break
        }
        let s = String(ch)
        if let c = Combo.keyCodes[s], s.count == 1 { return (c, false) }
        let lower = s.lowercased()
        if lower != s, let c = Combo.keyCodes[lower], lower.count == 1 { return (c, true) }
        return nil
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
    ///
    /// `keys` also takes the media keys `volume_up | volume_down | mute |
    /// brightness_up | brightness_down | play_pause | next_track |
    /// previous_track` (`MediaKey`): system-defined events like the hardware
    /// keys, tagged as Muselet input. They are global, so there is no focus
    /// guard and (without `expect`) no settle / re-observation; the result
    /// carries `media_key` and, for volume / brightness keys, the read-back
    /// `level_before`, `level` (0-100), `changed` (+ `muted` for volume).
    ///
    /// `type` into a keystroke-driven app (`TextTarget.keystrokeApps`:
    /// Calculator) posts the characters as key presses (`target:
    /// "keystroke_app"`); the ref need not be a text field.
    ///
    /// `type` / `keys` / `click` fail with `screen_locked` while the lock
    /// screen is up (nothing is posted).
    public func act(_ params: [String: Any]) -> [String: Any] {
        let t0 = Date()
        var out: [String: Any] = [:]
        do {
            guard let op = params["op"] as? String else {
                throw HandsError.invalidParams("missing op")
            }
            // Media keys are global: no focus guard, no app settle.
            let mediaKey = op == "keys" ? (params["combo"] as? String).flatMap(MediaKey.parse) : nil
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
            if ["type", "keys", "click"].contains(op) && mediaKey == nil { try ensureTargetFocus() }

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
                // A keystroke app (Calculator) takes key presses, not AX
                // values or focus changes on its buttons.
                let keystrokeApp = TextTarget.isKeystrokeApp(apps.app(pid: targetPid())?.bundleId)
                if !keystrokeApp {
                    _ = rec.element.setAttr(kAXFocusedAttribute, true)
                    usleep(30_000)
                }
                // Never type into nothing: a non-text ref (button, row, ...)
                // is fine only if it or the focus it left accepts text
                // (spreadsheet cell, web editable) or the app is a keystroke app.
                let via = try requireTextTarget(rec)
                let typeText = typeTextOverride ?? Events.typeText
                if via == TextTarget.keystrokeVia {
                    (typeKeystrokesOverride ?? Events.typeKeystrokes)(TextTarget.keystrokeText(text))
                    out["target"] = TextTarget.keystrokeVia
                } else if rec.inWebArea {
                    // React-style inputs ignore AXValue: select-all + type.
                    Combo.post(try Combo.parse("cmd+a"))
                    typeText(text)
                } else if rec.element.isSettable(kAXValueAttribute) {
                    _ = rec.element.setAttr(kAXValueAttribute, text)
                } else {
                    typeText(text)
                }
                if params["enter"] as? Bool == true { Events.key(36) }
            case "keys":
                guard let c = params["combo"] as? String else {
                    throw HandsError.invalidParams("keys needs combo")
                }
                if let mk = mediaKey {
                    for (k, v) in pressMediaKey(mk) { out[k] = v }
                } else {
                    Combo.post(try Combo.parse(c))
                }
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
            // A media key changes nothing in the observed app: skip the
            // settle + re-observation (no diff_text, so the brain re-observes
            // if it plans further), unless an expect needs checking.
            if mediaKey != nil && pred == nil {
                out["settle_ms"] = 0.0
                out["epoch"] = currentEpoch
                out["ok"] = true
                delegate?.handsDidAct(op: op, frame: targetFrame, ok: true)
                return out
            }
            // A shell script that exits non-zero (or times out) failed
            // (planner-11): ok=false with exit_code/stdout/stderr.
            var scriptError: String?
            if let sr = scriptResult {
                for (k, v) in sr { out[k] = v }
                let code = sr["exit_code"] as? Int ?? 0
                if sr["timed_out"] as? Bool == true {
                    scriptError = "script_failed: timed out after \(Int(Self.shellTimeout)) s"
                } else if code != 0 {
                    let err = (sr["stderr"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                    scriptError = "script_failed: exit \(code)" + (err.isEmpty ? "" : ": \(err.prefix(300))")
                }
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
                // hands-13: the re-observation hit the node cap, so a `- #ref`
                // may only mean "pushed past the cap"; consumers must not
                // apply diff_text as a complete view.
                if post.truncated { out["truncated"] = true }
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
            if let scriptError { out["error"] = scriptError }
            let ok = expectOK && scriptError == nil
            out["ok"] = ok
            delegate?.handsDidAct(op: op, frame: targetFrame, ok: ok)
            return out
        } catch let e as HandsError {
            out["ok"] = false
            out["error"] = e.description
            if let o = e.observed { out["observed"] = o }
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

    static let shellTimeout: TimeInterval = 10
    /// Max chars of stdout/stderr returned per stream.
    static let shellOutputCap = 100_000

    /// /bin/zsh -c with a timeout. Always returns {stdout, stderr, output,
    /// exit_code, timed_out?}; act() turns a non-zero exit into ok=false.
    /// Pipes are drained while the process runs (a >64 KB output must not
    /// block the child until the timeout).
    func runShell(_ code: String, timeout: TimeInterval = Hands.shellTimeout) throws -> [String: Any] {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-c", code]
        let outP = Pipe(), errP = Pipe()
        p.standardOutput = outP
        p.standardError = errP
        p.standardInput = FileHandle.nullDevice
        let buf = ShellOutput()
        outP.fileHandleForReading.readabilityHandler = { h in buf.append(h.availableData, err: false) }
        errP.fileHandleForReading.readabilityHandler = { h in buf.append(h.availableData, err: true) }
        let done = DispatchSemaphore(value: 0)
        p.terminationHandler = { _ in done.signal() }
        do { try p.run() } catch {
            outP.fileHandleForReading.readabilityHandler = nil
            errP.fileHandleForReading.readabilityHandler = nil
            throw HandsError.skillFailed("shell: \(error.localizedDescription)")
        }
        var timedOut = false
        if done.wait(timeout: .now() + timeout) == .timedOut {
            timedOut = true
            p.terminate()
            if done.wait(timeout: .now() + 1) == .timedOut {
                kill(p.processIdentifier, SIGKILL)
                _ = done.wait(timeout: .now() + 1)
            }
        }
        // EOF arrives once every writer closed; a backgrounded child may
        // keep the pipe open, so wait only briefly.
        buf.waitForEOF(timeout: 0.2)
        outP.fileHandleForReading.readabilityHandler = nil
        errP.fileHandleForReading.readabilityHandler = nil
        let (outS, errS) = buf.strings(cap: Self.shellOutputCap)
        let rc = Int(p.isRunning ? -1 : p.terminationStatus)
        var r: [String: Any] = ["stdout": outS, "stderr": errS, "exit_code": rc, "output": outS]
        if timedOut { r["timed_out"] = true }
        return r
    }

    private func lastObservedPid() -> pid_t {
        lastPid != 0 ? lastPid : apps.frontmostPid()
    }

    /// App an input act goes to: the observed app, else the frontmost one.
    func targetPid() -> pid_t {
        lastPid != 0 && !focusRebindPending ? lastPid : apps.frontmostPid()
    }

    // MARK: media keys

    /// Post `key` (down + up). Volume / brightness keys read the level
    /// before and after (polled <= 400 ms until it changed and held for two
    /// reads): {media_key, level_before?, level?, changed?, muted?}.
    func pressMediaKey(_ key: MediaKey) -> [String: Any] {
        var r: [String: Any] = ["media_key": key.name]
        let kind = key.kind
        let before = kind == .playback ? nil : readMediaLevel(kind)
        (mediaKeyPostOverride ?? { $0.post() })(key)
        guard kind != .playback else { return r }
        var after = before
        var last: [String: AnyHashable]?
        let end = Date().addingTimeInterval(mediaReadBackTimeout)
        while Date() < end {
            Hands.pollWait(0.04)
            let cur = readMediaLevel(kind)
            if cur != before {
                if cur == last { after = cur; break }   // changed and settled
                last = cur
                after = cur
            }
        }
        // .base: plain Int / Bool for JSON.
        if let b = before?["level"] { r["level_before"] = b.base }
        if let a = after?["level"] { r["level"] = a.base }
        if let m = after?["muted"] { r["muted"] = m.base }
        r["changed"] = after != before
        return r
    }

    /// Current volume {level, muted} or brightness {level} (0-100), nil if unreadable.
    func readMediaLevel(_ kind: MediaKey.Kind) -> [String: AnyHashable]? {
        if let o = mediaLevelOverride { return o(kind) }
        switch kind {
        case .volume:
            let st = Skills.parseVolumeState((try? scripts.run(Skills.volumeStateScript)) ?? "")
            var d: [String: AnyHashable] = [:]
            if let l = st.level { d["level"] = l }
            if let m = st.muted { d["muted"] = m }
            return d.isEmpty ? nil : d
        case .brightness:
            return PrivateSymbols.brightness().map { ["level": Int(($0 * 100).rounded())] }
        case .playback:
            return nil
        }
    }

    /// Short role names whose elements take typed text as such.
    static let textRecordRoles: Set<String> = ["textfield", "textarea", "combobox"]

    /// `type #ref`: the ref (already focused) must accept text, or the
    /// keyboard focus it left must (Numbers cell, web editable inside a
    /// group), or the app must be a keystroke app (Calculator). Else
    /// no_text_target and nothing is typed. Returns how the text gets in:
    /// "text_role" | "accepts" | "focused" | "keystroke_app".
    @discardableResult
    func requireTextTarget(_ rec: ElementRecord) throws -> String {
        if Self.textRecordRoles.contains(rec.role) { return "text_role" }
        let pid = lastPid != 0 ? lastPid : apps.frontmostPid()
        let info = apps.app(pid: pid)
        if TextTarget.acceptsText(rec.element, rec.element.copyAttrs(), bundleId: info?.bundleId) {
            return "accepts"
        }
        let app = axAppOverride?(pid) ?? {
            let n = AXNode(AXUIElementCreateApplication(pid))
            n.setMessagingTimeout(0.25)
            return n
        }()
        let chk = TextTarget.check(app: app, appName: info?.name ?? apps.name(pid: pid),
                                   bundleId: info?.bundleId, windowFallback: false)
        if chk.ok { return chk.via ?? "focused" }
        throw HandsError.noTextTarget(
            observed: "#\(rec.ref) \(rec.role) \"\(String(rec.label.prefix(40)))\" takes no text; " + chk.observed)
    }

    /// hands-8: synthesized keys/typing/clicks must go to the observed app.
    /// If another app is frontmost, activate the target and wait <= 300 ms;
    /// still wrong -> focus_changed (never type into the wrong app).
    /// After a skill switched apps on purpose (`focusRebindPending`), or
    /// with no observation yet, the current frontmost app is the target.
    /// Never while the screen is locked (screen_locked).
    func ensureTargetFocus() throws {
        if apps.screenLocked() { throw HandsError.screenLocked }
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
            Hands.pollWait(0.02)
        }
        return apps.frontmostPid() == pid
    }

    func waitRunning(bundleId: String, timeout: TimeInterval) -> RunningAppInfo? {
        let end = Date().addingTimeInterval(timeout)
        while Date() < end {
            if let a = apps.runningApp(bundlePrefix: bundleId) { return a }
            Hands.pollWait(0.05)
        }
        return nil
    }

    /// Sleep one poll interval. On the main thread of a process without an
    /// NSApplication (the `hands` CLI) the run loop runs instead, because
    /// NSWorkspace / NSRunningApplication state (frontmost app, launches)
    /// only refreshes when the main run loop runs.
    static func pollWait(_ seconds: TimeInterval) {
        guard seconds > 0 else { return }
        if Thread.isMainThread && NSApp == nil {
            let t0 = Date()
            let r = CFRunLoopRunInMode(.defaultMode, seconds, false)
            let left = seconds - Date().timeIntervalSince(t0)
            if r == .finished, left > 0 { usleep(UInt32(left * 1_000_000)) }  // no sources yet
        } else {
            usleep(UInt32(seconds * 1_000_000))
        }
    }
}

/// Thread-safe stdout/stderr accumulator for `runShell`.
final class ShellOutput {
    private let lock = NSLock()
    private var out = Data(), err = Data()
    private var outEOF = false, errEOF = false, signaled = false
    private let eof = DispatchSemaphore(value: 0)

    func append(_ d: Data, err isErr: Bool) {
        lock.lock()
        if d.isEmpty {        // EOF (the handler may fire again with empty data)
            if isErr { errEOF = true } else { outEOF = true }
            let fire = outEOF && errEOF && !signaled
            if fire { signaled = true }
            lock.unlock()
            if fire { eof.signal() }
            return
        }
        if isErr { err.append(d) } else { out.append(d) }
        lock.unlock()
    }

    func waitForEOF(timeout: TimeInterval) { _ = eof.wait(timeout: .now() + timeout) }

    func strings(cap: Int) -> (String, String) {
        lock.lock(); defer { lock.unlock() }
        func s(_ d: Data) -> String {
            let str = String(decoding: d, as: UTF8.self)
            return str.count > cap ? String(str.prefix(cap)) + "…[truncated]" : str
        }
        return (s(out), s(err))
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
