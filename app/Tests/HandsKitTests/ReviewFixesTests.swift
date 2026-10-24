import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Tests for the hands review fixes (hands-1..8), new skills, HUD feedback,
// OCR, ctx capture and the confirm parser. Everything here is hermetic:
// no real key/mouse events, no Bluetooth/lock/trash side effects.

// MARK: - Mocks

final class MockPoster: EventPosting {
    var posted: [String] = []
    var typed: [String] = []
    /// Keystroke-app typing (Calculator) and media keys, recorded only.
    var keystrokes: [String] = []
    var mediaKeys: [String] = []
    func post(_ combo: KeyCombo) { posted.append(Combo.describe(combo)) }
    func typeText(_ text: String) { typed.append(text) }
    func typeKeystrokes(_ text: String) { keystrokes.append(text) }
    func postMediaKey(_ key: MediaKey) { mediaKeys.append(key.name) }
}

final class MockApps: AppControlling {
    var frontmost: pid_t
    var activateSucceeds: Bool
    var activated: [pid_t] = []
    var running: [RunningAppInfo]
    /// Lock screen up (screen_locked guard).
    var locked = false

    init(frontmost: pid_t = 1, activateSucceeds: Bool = true, running: [RunningAppInfo] = []) {
        self.frontmost = frontmost
        self.activateSucceeds = activateSucceeds
        self.running = running
    }

    func screenLocked() -> Bool { locked }
    func frontmostPid() -> pid_t { frontmost }
    func activate(pid: pid_t) -> Bool {
        activated.append(pid)
        if activateSucceeds { frontmost = pid }
        return activateSucceeds
    }
    func app(pid: pid_t) -> RunningAppInfo? { running.first { $0.pid == pid } }
    func runningApp(bundlePrefix: String) -> RunningAppInfo? {
        running.first { $0.bundleId.hasPrefix(bundlePrefix) }
    }
}

final class SpyDelegate: HandsDelegate {
    var skills: [(String, [String: Any])] = []
    var timerLabels: [String?] = []
    var onTimer: (() -> Void)?
    func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval { 0 }
    func handsDidAct(op: String, frame: CGRect?, ok: Bool) {}
    func handsDidRunSkill(name: String, args: [String: Any], result: [String: Any]) {
        skills.append((name, result))
    }
    func handsTimerFired(label: String?) {
        timerLabels.append(label)
        onTimer?()
    }
}

/// Script runner answering the volume read-back script.
final class VolumeSpy: ScriptRunning {
    var ran: [String] = []
    var state = "35,false"
    func run(_ source: String) throws -> String {
        ran.append(source)
        if source.contains("get volume settings") && source.contains("output muted") { return state }
        if source.hasPrefix("output volume of") { return "40" }
        return ""
    }
    /// The volume handlers read the state back (what macOS reports).
    func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String {
        ran.append("\(script.name).\(handler)(\(args.map { "\($0)" }.joined(separator: ",")))")
        return script.name == "volume" ? state : ""
    }
}

private func window(_ id: Int, _ titles: [String]) -> MockElement {
    let w = MockElement(role: "AXWindow", title: "W", x: 0, y: 0, w: 800, h: 600,
                        children: titles.enumerated().map { i, t in
                            MockElement(role: "AXButton", title: t, x: 10, y: CGFloat(10 + 30 * i))
                        })
    w.stableIdOverride = id
    return w
}

private func mockObserve(_ h: Hands, _ root: Element, window: String = "W", pid: pid_t = 1,
                     maxNodes: Int = 150) -> Observation {
    h.processObservation(roots: [root], app: "Mock", window: window, pid: pid,
                         maxNodes: maxNodes, diff: true,
                         deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
}

private func catalog() -> [String: SkillDef] { try! Catalog.load() }

// MARK: - hands-1: refs never reused; epoch checked

final class StaleRefAcrossWindowsTests: XCTestCase {
    func testW1RefInW2IsStale() {
        let h = Hands()
        let o1 = mockObserve(h, window(101, ["Save", "Cancel", "Name"]), window: "W1")
        let w1Ref = o1.elements.first { $0.label == "Cancel" }!.ref
        let o2 = mockObserve(h, window(202, ["A", "B", "C", "D", "E"]), window: "W2")
        XCTAssertTrue(o2.full)
        XCTAssertFalse(o2.elements.contains { $0.ref == w1Ref })   // never re-minted

        // act with a W1 ref (and its epoch) -> stale_ref, nothing executed
        let r = h.act(["op": "press", "ref": w1Ref, "epoch": o1.epoch])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("stale_ref"), "\(r)")
        // even without an epoch
        XCTAssertThrowsError(try h.element(ref: w1Ref))
        // a W2 ref with a pre-session epoch is stale too
        let w2Ref = o2.elements[0].ref
        XCTAssertThrowsError(try h.element(ref: w2Ref, epoch: o1.epoch))
        XCTAssertNoThrow(try h.element(ref: w2Ref, epoch: o2.epoch))
        XCTAssertNoThrow(try h.element(ref: w2Ref))
    }

    func testReturningToWindowResumesItsRefs() {
        let h = Hands()
        let w1 = window(111, ["Save", "Cancel"])
        let o1 = mockObserve(h, w1, window: "Doc")
        let cancel = o1.elements.first { $0.label == "Cancel" }!.ref
        let o2 = mockObserve(h, window(222, ["Open", "Close"]), window: "Open dialog")
        let w2Ref = o2.elements[0].ref
        XCTAssertThrowsError(try h.element(ref: cancel))
        // dialog closed, back to the same window element: same refs again
        let o3 = mockObserve(h, w1, window: "Doc")
        XCTAssertTrue(o3.full)
        XCTAssertEqual(o3.elements.first { $0.label == "Cancel" }?.ref, cancel)
        XCTAssertNoThrow(try h.element(ref: cancel, epoch: o2.epoch))
        XCTAssertThrowsError(try h.element(ref: w2Ref))       // dialog refs are stale now
    }

    func testSameWindowOlderEpochStillValid() {
        let h = Hands()
        let w = window(303, ["Save", "Cancel"])
        let o1 = mockObserve(h, w)
        _ = mockObserve(h, w)                                         // epoch advances
        let ref = o1.elements[0].ref
        XCTAssertNoThrow(try h.element(ref: ref, epoch: o1.epoch))  // same session
    }
}

// MARK: - hands-2: confirm parser

final class YesNoTests: XCTestCase {
    func testRefusals() {
        for s in ["not right now", "okay cancel that", "that's not correct", "no", "nope",
                  "Don't do it", "not sure", "never mind", "hold on", "stop", "wait",
                  "No.", "nah", "please don't send it", "that\u{2019}s not right"] {
            XCTAssertEqual(YesNo.parse(s), false, s)
        }
    }

    func testAmbiguousIsNotYes() {
        let r = YesNo.parse("yes no wait")
        XCTAssertTrue(r == nil || r == false)
        XCTAssertNotEqual(YesNo.parse("yes, don't"), true)
    }

    func testYes() {
        for s in ["yes", "Yes.", "yeah do it", "go ahead", "sure", "okay", "yep, send it",
                  "Sure, go ahead!", "absolutely", "yes please", "sure no problem"] {
            XCTAssertEqual(YesNo.parse(s), true, s)
        }
    }

    func testRightCorrectNoLongerYes() {
        XCTAssertNil(YesNo.parse("right"))
        XCTAssertNil(YesNo.parse("correct"))
        XCTAssertNil(YesNo.parse("hmm"))
        XCTAssertNil(YesNo.parse(""))
    }
}

// MARK: - hands-3: synthetic event tag

final class SyntheticEventTests: XCTestCase {
    func testTagRoundTrip() throws {
        let e = try XCTUnwrap(CGEvent(keyboardEventSource: nil, virtualKey: 53, keyDown: true))
        XCTAssertFalse(SyntheticEvent.isTagged(e))
        SyntheticEvent.tag(e)                       // tag only; never posted
        XCTAssertTrue(SyntheticEvent.isTagged(e))
        XCTAssertEqual(e.getIntegerValueField(.eventSourceUserData), 0x4D55534C)
    }

    func testComboDescribe() throws {
        XCTAssertEqual(Combo.describe(try Combo.parse("cmd+shift+n")), "shift+cmd+n")
        XCTAssertEqual(Combo.describe(try Combo.parse("ctrl+cmd+q")), "ctrl+cmd+q")
        XCTAssertEqual(Combo.describe(try Combo.parse("space")), "space")
    }
}

// MARK: - hands-4: expect polling

final class ExpectPollingTests: XCTestCase {
    func testPollsUntilTitlePasses() {
        let h = Hands()
        let w = window(404, ["Reload"])
        _ = mockObserve(h, w, window: "Loading…")
        var calls = 0
        h.settleOverride = { _ in 5 }
        h.observeOverride = {
            calls += 1
            return mockObserve(h, w, window: calls >= 3 ? "GitHub · Build software" : "Loading…")
        }
        let t0 = Date()
        let r = h.act(["op": "wait", "ms": 0, "expect": "title~\"GitHub\""])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["expect_ok"] as? Bool, true)
        XCTAssertGreaterThanOrEqual(r["expect_polls"] as? Int ?? 0, 2)
        let settle = r["settle_ms"] as? Double ?? 0
        XCTAssertGreaterThan(settle, 120)              // ~2 polls of 80 ms
        XCTAssertLessThan(Date().timeIntervalSince(t0), 1.0)
    }

    func testTimesOutWithExpectFailed() {
        let h = Hands()
        let w = window(405, ["Reload"])
        _ = mockObserve(h, w, window: "Loading…")
        h.settleOverride = { _ in 0 }
        h.observeOverride = { mockObserve(h, w, window: "Loading…") }
        let t0 = Date()
        let r = h.act(["op": "wait", "ms": 0, "expect": "title~\"GitHub\"",
                       "expect_timeout_ms": 250])
        let dt = Date().timeIntervalSince(t0)
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("expect_failed"), "\(r)")
        XCTAssertGreaterThanOrEqual(dt, 0.24)
        XCTAssertLessThan(dt, 1.0)
    }

    func testImmediatePassNoPolling() {
        let h = Hands()
        let w = window(406, ["OK"])
        _ = mockObserve(h, w, window: "Done")
        h.settleOverride = { _ in 12.5 }
        h.observeOverride = { mockObserve(h, w, window: "Done") }
        let r = h.act(["op": "wait", "ms": 0, "expect": "title~\"Done\""])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertNil(r["expect_polls"])
        XCTAssertEqual(r["settle_ms"] as? Double, 12.5)
    }

    func testBadPredicateFailsBeforeActing() {
        let h = Hands()
        let r = h.act(["op": "wait", "ms": 0, "expect": "nonsense"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertNil(r["settle_ms"])                    // never acted/settled
    }
}

// MARK: - hands-6: appears/gone beyond the node cap

final class ExpectBeyondCapTests: XCTestCase {
    func testTruncatedFlag() {
        let h = Hands()
        let o = mockObserve(h, window(501, ["A", "B", "C"]), maxNodes: 2)
        XCTAssertTrue(o.truncated)
        XCTAssertEqual(o.elements.count, 2)
        let o2 = mockObserve(h, window(502, ["A", "B"]), maxNodes: 150)
        XCTAssertFalse(o2.truncated)
    }

    func testAppearsFallsBackToTargetedSearch() {
        let h = Hands()
        let o = mockObserve(h, window(503, ["Open"]))
        var searched: [String] = []
        h.labelSearchOverride = { label, _ in searched.append(label); return label == "Export…" }
        XCTAssertTrue(h.evalExpect(.appears("Open"), o).0)
        XCTAssertTrue(searched.isEmpty)                 // cheap path hit first
        XCTAssertTrue(h.evalExpect(.appears("Export…"), o).0)
        XCTAssertFalse(h.evalExpect(.appears("Nope"), o).0)
        XCTAssertEqual(searched, ["Export…", "Nope"])
    }

    func testGoneUsesLiveness() {
        let h = Hands()
        let w = window(504, ["Keep", "Close"])
        let o = mockObserve(h, w)
        let ref = o.elements.first { $0.label == "Close" }!.ref
        // Observation that lacks the ref (e.g. past the cap) but the element lives.
        var capped = o
        capped.elements.removeAll { $0.ref == ref }
        capped.truncated = true
        XCTAssertFalse(h.evalExpect(.gone(ref), capped).0)
        // Element destroyed -> gone, even from a truncated walk.
        (w.attrs.children[1] as! MockElement).alive = false
        XCTAssertTrue(h.evalExpect(.gone(ref), capped).0)
        // Unknown ref: never gone from a truncated walk; gone from a complete one.
        XCTAssertFalse(h.evalExpect(.gone(999_999_999), capped).0)
        var complete = capped
        complete.truncated = false
        XCTAssertTrue(h.evalExpect(.gone(999_999_999), complete).0)
        // Present in the list -> not gone.
        XCTAssertFalse(h.evalExpect(.gone(o.elements[0].ref), o).0)
    }
}

// MARK: - hands-8: input bound to the observed app

final class FocusGuardTests: XCTestCase {
    private func setup(apps: MockApps) -> (Hands, MockElement, Int) {
        let h = Hands()
        h.apps = apps
        let field = MockElement(role: "AXTextField", title: "Name", x: 10, y: 10)
        field.settable = ["AXFocused", "AXValue"]          // AX path: no synthetic typing
        let w = MockElement(role: "AXWindow", title: "W", x: 0, y: 0, w: 800, h: 600,
                            children: [field])
        w.stableIdOverride = 601
        let o = mockObserve(h, w, pid: 4242)
        h.settleOverride = { _ in 0 }
        h.observeOverride = { mockObserve(h, w, pid: 4242) }
        return (h, field, o.elements[0].ref)
    }

    func testFocusChangedWhenTargetCannotBeActivated() {
        let apps = MockApps(frontmost: 999, activateSucceeds: false)
        let (h, field, ref) = setup(apps: apps)
        let t0 = Date()
        let r = h.act(["op": "type", "ref": ref, "text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("focus_changed"), "\(r)")
        XCTAssertEqual(apps.activated, [4242])
        XCTAssertNil(field.store["AXValue"] ?? nil)        // never typed
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.6)   // <= ~300 ms wait
    }

    func testReactivatesTargetThenTypes() {
        let apps = MockApps(frontmost: 999, activateSucceeds: true)
        let (h, field, ref) = setup(apps: apps)
        let r = h.act(["op": "type", "ref": ref, "text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(apps.activated, [4242])
        XCTAssertEqual(field.store["AXValue"] as? String, "hello")
    }

    func testNoActivationWhenAlreadyFrontmost() {
        let apps = MockApps(frontmost: 4242)
        let (h, _, ref) = setup(apps: apps)
        let r = h.act(["op": "type", "ref": ref, "text": "x"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertTrue(apps.activated.isEmpty)
    }

    func testSkillAppSwitchRebindsToFrontmost() {
        let apps = MockApps(frontmost: 999, activateSucceeds: false)
        let (h, field, ref) = setup(apps: apps)
        h.noteExternalFocusChange()                        // e.g. skill open_app ran
        let r = h.act(["op": "type", "ref": ref, "text": "hi"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertTrue(apps.activated.isEmpty)
        XCTAssertEqual(field.store["AXValue"] as? String, "hi")
    }
}

// MARK: - hands-5: screenshot geometry helpers

final class ScreenshotHelperTests: XCTestCase {
    private func win(_ pid: Int32, _ num: UInt32, _ r: CGRect, layer: Int = 0) -> [String: Any] {
        [kCGWindowOwnerPID as String: NSNumber(value: pid),
         kCGWindowNumber as String: NSNumber(value: num),
         kCGWindowLayer as String: NSNumber(value: layer),
         kCGWindowAlpha as String: NSNumber(value: 1.0),
         kCGWindowBounds as String: r.dictionaryRepresentation as NSDictionary]
    }

    func testPickWindowPrefersAXFocusedFrame() {
        let list = [
            win(7, 11, CGRect(x: 0, y: 0, width: 300, height: 20), layer: 25),  // palette/menu
            win(7, 12, CGRect(x: 50, y: 50, width: 200, height: 100)),          // tooltip-ish
            win(7, 13, CGRect(x: 100, y: 80, width: 1200, height: 800)),        // focused doc
            win(8, 14, CGRect(x: 0, y: 0, width: 1500, height: 900)),           // other app
        ]
        XCTAssertEqual(Screenshot.pickWindow(cgList: list, pid: 7,
                                             axFrame: CGRect(x: 101, y: 80, width: 1200, height: 799)), 13)
        // No AX frame: frontmost (list order) layer-0 window of the pid.
        XCTAssertEqual(Screenshot.pickWindow(cgList: list, pid: 7, axFrame: nil), 12)
        XCTAssertNil(Screenshot.pickWindow(cgList: list, pid: 9, axFrame: nil))
    }

    func testDisplayContaining() {
        let a = Screenshot.DisplayInfo(id: 1, frame: CGRect(x: 0, y: 0, width: 1512, height: 982), backing: 2)
        let b = Screenshot.DisplayInfo(id: 2, frame: CGRect(x: 1512, y: -200, width: 2560, height: 1440), backing: 1)
        XCTAssertEqual(Screenshot.display(containing: CGPoint(x: 2000, y: 100), in: [a, b])?.id, 2)
        XCTAssertEqual(Screenshot.display(containing: CGPoint(x: 10, y: 10), in: [a, b])?.id, 1)
        XCTAssertEqual(Screenshot.display(containing: CGPoint(x: 5000, y: 0), in: [a, b])?.id, 2)  // nearest
    }

    func testPixelSizeUsesBackingAndCap() {
        // 300x200 pt region at 2x -> 600x400 px (under the cap)
        let (w, h) = Screenshot.pixelSize(source: CGRect(x: 0, y: 0, width: 300, height: 200),
                                          backing: 2, maxPixels: 1_000_000)
        XCTAssertEqual(w, 600); XCTAssertEqual(h, 400)
        // full 1512x982 display at 2x capped to ~1 MP, aspect kept
        let (w2, h2) = Screenshot.pixelSize(source: CGRect(x: 0, y: 0, width: 1512, height: 982),
                                            backing: 2, maxPixels: 1_000_000)
        XCTAssertLessThanOrEqual(w2 * h2, 1_000_000 + 2_000)
        XCTAssertEqual(Double(w2) / Double(h2), 1512.0 / 982.0, accuracy: 0.01)
    }

    func testRectParam() {
        XCTAssertEqual(rectParam(["region": [1, 2, 3, 4]], "region"), CGRect(x: 1, y: 2, width: 3, height: 4))
        XCTAssertNil(rectParam(["region": [1, 2, 3]], "region"))
        XCTAssertNil(rectParam([:], "region"))
    }
}

// MARK: - premiere_command

final class PremiereCommandTests: XCTestCase {
    private let premiere = RunningAppInfo(pid: 777, name: "Adobe Premiere Pro 2026",
                                          bundleId: "com.adobe.PremierePro.26")

    func testMappingSendsShortcutsToPremiere() {
        let expected: [String: String] = [
            "razor_at_playhead": "cmd+k", "add_marker": "m", "play_toggle": "space",
            "undo": "cmd+z", "go_to_start": "home", "go_to_end": "end", "export": "cmd+m",
        ]
        for (cmd, keys) in expected {
            let poster = MockPoster()
            let apps = MockApps(frontmost: 1, running: [premiere])
            let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster,
                           apps: apps, hooks: .inert)
            let r = s.execute(name: "premiere_command", args: ["command": cmd])
            XCTAssertEqual(r["ok"] as? Bool, true, "\(cmd): \(r)")
            XCTAssertEqual(poster.posted, [Combo.describe(try! Combo.parse(keys))], cmd)
            XCTAssertEqual(apps.activated, [777], cmd)
            XCTAssertEqual((r["result"] as? [String: Any])?["keys"] as? String, keys)
        }
    }

    func testNotRunning() {
        let poster = MockPoster()
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster,
                       apps: MockApps(), hooks: .inert)
        let r = s.execute(name: "premiere_command", args: ["command": "undo"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "Premiere Pro isn't open")
        XCTAssertTrue(poster.posted.isEmpty)
    }

    func testNeverSendsToAnotherApp() {
        let poster = MockPoster()
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [premiere])
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster,
                       apps: apps, hooks: .inert)
        let r = s.execute(name: "premiere_command", args: ["command": "razor_at_playhead"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("focus_changed"))
        XCTAssertTrue(poster.posted.isEmpty)
    }

    func testUnknownCommand() {
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(),
                       apps: MockApps(running: [premiere]), hooks: .inert)
        XCTAssertEqual(s.execute(name: "premiere_command", args: ["command": "fly"])["ok"] as? Bool, false)
    }
}

// MARK: - start_timer

final class TimerTests: XCTestCase {
    func testTimerFiresThroughMocks() {
        var sounds: [String] = []
        var notes: [(String, String)] = []
        var hooks = SystemHooks.inert
        let lock = NSLock()
        hooks.playSound = { n in lock.lock(); sounds.append(n); lock.unlock() }
        hooks.notify = { t, b in lock.lock(); notes.append((t, b)); lock.unlock() }
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(),
                       apps: MockApps(), hooks: hooks)
        let d = SpyDelegate()
        s.delegate = d
        let fired = expectation(description: "timer fired")
        d.onTimer = { fired.fulfill() }

        let t0 = Date()
        let r = s.execute(name: "start_timer", args: ["duration": 0.15, "label": "Tea"])
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.1)          // returns immediately
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertNotNil(r["fires_at"] as? String)
        XCTAssertEqual(s.pendingTimers, 1)
        wait(for: [fired], timeout: 2)
        XCTAssertGreaterThanOrEqual(Date().timeIntervalSince(t0), 0.14)
        lock.lock()
        XCTAssertEqual(sounds, ["Glass"])
        XCTAssertEqual(notes.first?.0, "Timer done")
        XCTAssertEqual(notes.first?.1, "Tea")
        lock.unlock()
        XCTAssertEqual(d.timerLabels, ["Tea"])
        let gone = expectation(description: "cleaned up")
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.1) { gone.fulfill() }
        wait(for: [gone], timeout: 1)
        XCTAssertEqual(s.pendingTimers, 0)
    }

    func testRejectsBadDuration() {
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(),
                       apps: MockApps(), hooks: .inert)
        XCTAssertEqual(s.execute(name: "start_timer", args: ["duration": 0])["ok"] as? Bool, false)
        XCTAssertEqual(s.execute(name: "start_timer", args: ["duration": "soon"])["ok"] as? Bool, false)
        XCTAssertEqual(s.pendingTimers, 0)
    }

    func testParseDuration() {
        XCTAssertEqual(Skills.parseDuration(90), 90)
        XCTAssertEqual(Skills.parseDuration(1.5), 1.5)
        XCTAssertEqual(Skills.parseDuration("90"), 90)
        XCTAssertEqual(Skills.parseDuration("90s"), 90)
        XCTAssertEqual(Skills.parseDuration("10 minutes"), 600)
        XCTAssertEqual(Skills.parseDuration("1h 30m"), 5400)
        XCTAssertEqual(Skills.parseDuration("1h30m"), 5400)
        XCTAssertEqual(Skills.parseDuration("2 hrs"), 7200)
        XCTAssertEqual(Skills.parseDuration("1:30"), 90)
        XCTAssertEqual(Skills.parseDuration("PT10M"), 600)
        XCTAssertNil(Skills.parseDuration("soon"))
        XCTAssertNil(Skills.parseDuration(nil))
    }
}

// MARK: - bluetooth / lock_screen / empty_trash (mocks only)

final class SystemSkillTests: XCTestCase {
    private func skills(_ hooks: SystemHooks, poster: MockPoster = MockPoster(),
                        scripts: ScriptRunning = SpyRunner()) -> Skills {
        Skills(catalog: catalog(), scripts: scripts, events: poster, apps: MockApps(), hooks: hooks)
    }

    func testBluetoothViaIOBluetooth() {
        var state = true
        var ccCalls = 0
        var h = SystemHooks.inert
        h.bluetoothGet = { state }
        h.bluetoothSet = { state = $0; return true }
        h.bluetoothControlCenter = { _ in ccCalls += 1; return state }
        let r = skills(h).execute(name: "bluetooth", args: ["on": false])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["on"] as? Bool, false)
        XCTAssertEqual(res?["method"] as? String, "iobluetooth")
        XCTAssertEqual(ccCalls, 0)
    }

    func testBluetoothFallsBackWhenSymbolMissing() {
        var state = false
        var h = SystemHooks.inert
        h.bluetoothGet = { nil }
        h.bluetoothSet = { _ in false }
        h.bluetoothControlCenter = { on in state = on; return on }
        let r = skills(h).execute(name: "bluetooth", args: ["on": true])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["method"] as? String, "control_center")
        XCTAssertTrue(state)
    }

    func testBluetoothFallsBackWhenStateDoesNotChange() {
        var ccCalls = 0
        var h = SystemHooks.inert
        h.bluetoothGet = { ccCalls > 0 }          // only the CC toggle "works"
        h.bluetoothSet = { _ in true }            // setter resolves but is ineffective
        h.bluetoothControlCenter = { _ in ccCalls += 1; return true }
        let t0 = Date()
        let r = skills(h).execute(name: "bluetooth", args: ["on": true])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["method"] as? String, "control_center")
        XCTAssertEqual(ccCalls, 1)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 1.6)   // <= 1 s verify window
    }

    func testBluetoothNoOpWhenAlreadyInState() {
        var sets = 0
        var h = SystemHooks.inert
        h.bluetoothGet = { true }
        h.bluetoothSet = { _ in sets += 1; return true }
        let r = skills(h).execute(name: "bluetooth", args: ["on": true])
        XCTAssertEqual((r["result"] as? [String: Any])?["changed"] as? Bool, false)
        XCTAssertEqual(sets, 0)
    }

    func testLockScreenPrivateThenFallback() {
        let poster = MockPoster()
        var h = SystemHooks.inert
        h.lockScreenPrivate = { false }           // symbol missing -> ctrl+cmd+q
        let r = skills(h, poster: poster).execute(name: "lock_screen", args: [:])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(poster.posted, ["ctrl+cmd+q"])
        XCTAssertEqual((r["result"] as? [String: Any])?["method"] as? String, "ctrl+cmd+q")

        let poster2 = MockPoster()
        var called = 0
        var h2 = SystemHooks.inert
        h2.lockScreenPrivate = { called += 1; return true }
        let r2 = skills(h2, poster: poster2).execute(name: "lock_screen", args: [:])
        XCTAssertEqual(called, 1)
        XCTAssertTrue(poster2.posted.isEmpty)
        XCTAssertEqual((r2["result"] as? [String: Any])?["method"] as? String, "SACLockScreenImmediate")
    }

    func testEmptyTrashGateAndScript() {
        let spy = SpyRunner()
        let s = skills(.inert, scripts: spy)
        let r = s.execute(name: "empty_trash", args: [:])
        XCTAssertEqual(r["error"] as? String, "needs_confirmation")
        XCTAssertTrue(spy.ran.isEmpty)
        let r2 = s.execute(name: "empty_trash", args: ["confirmed": true])
        XCTAssertEqual(r2["ok"] as? Bool, true)
        XCTAssertEqual(spy.ran, ["tell application \"Finder\" to empty trash"])
    }
}

// MARK: - read-backs + HUD feedback

final class ReadBackTests: XCTestCase {
    private func skills(_ spy: VolumeSpy, hooks: SystemHooks = .inert) -> Skills {
        Skills(catalog: catalog(), scripts: spy, events: MockPoster(), apps: MockApps(), hooks: hooks)
    }

    func testVolumeReadBack() {
        let spy = VolumeSpy()
        let r = skills(spy).execute(name: "set_volume", args: ["level": 30])
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["level"] as? Int, 35)          // what macOS actually reports
        XCTAssertEqual(res?["muted"] as? Bool, false)
        spy.state = "35,true"
        let m = skills(spy).execute(name: "mute", args: ["on": true])
        XCTAssertEqual((m["result"] as? [String: Any])?["muted"] as? Bool, true)
        XCTAssertEqual((m["result"] as? [String: Any])?["level"] as? Int, 35)
        spy.state = "50,false"
        let c = skills(spy).execute(name: "change_volume", args: ["delta": 10])
        XCTAssertTrue(spy.ran.contains("volume.set_level(50)"), "\(spy.ran)")
        XCTAssertEqual((c["result"] as? [String: Any])?["level"] as? Int, 50)
    }

    func testParseVolumeState() {
        XCTAssertEqual(Skills.parseVolumeState("44,false").level, 44)
        XCTAssertEqual(Skills.parseVolumeState("44,false").muted, false)
        XCTAssertNil(Skills.parseVolumeState("missing value,true").level)
        XCTAssertEqual(Skills.parseVolumeState("missing value,true").muted, true)
        XCTAssertNil(Skills.parseVolumeState("").muted)
    }

    func testBrightnessReadBack() {
        var h = SystemHooks.inert
        var set: Float = -1
        h.brightnessSet = { set = $0; return true }
        h.brightnessGet = { 0.7 }
        let r = skills(VolumeSpy(), hooks: h).execute(name: "set_brightness", args: ["level": 70])
        XCTAssertEqual(set, 0.7, accuracy: 0.001)
        XCTAssertEqual((r["result"] as? [String: Any])?["level"] as? Int, 70)
    }

    func testDarkModeReadBack() {
        final class DarkSpy: ScriptRunning {
            func run(_ s: String) throws -> String { s.hasSuffix("get dark mode") ? "true" : "" }
            func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String {
                handler == "set_dark" ? "true" : ""
            }
        }
        let s = Skills(catalog: catalog(), scripts: DarkSpy(), events: MockPoster(),
                       apps: MockApps(), hooks: .inert)
        let r = s.execute(name: "dark_mode", args: ["on": true])
        XCTAssertEqual((r["result"] as? [String: Any])?["on"] as? Bool, true)
    }

    func testFeedbackMapping() {
        func ok(_ r: [String: Any]) -> [String: Any] { ["ok": true, "result": r] }
        XCTAssertEqual(SkillFeedback.from(name: "set_volume", response: ok(["level": 30, "muted": false])),
                       .level(kind: .volume, level: 30, muted: false))
        XCTAssertEqual(SkillFeedback.from(name: "mute", response: ok(["level": 30, "muted": true])),
                       .level(kind: .volume, level: 30, muted: true))
        XCTAssertEqual(SkillFeedback.from(name: "set_brightness", response: ok(["level": 140])),
                       .level(kind: .brightness, level: 100, muted: false))
        XCTAssertEqual(SkillFeedback.from(name: "dark_mode", response: ok(["on": false])),
                       .toggle(kind: .darkMode, on: false))
        XCTAssertEqual(SkillFeedback.from(name: "wifi", response: ok(["on": true])),
                       .toggle(kind: .wifi, on: true))
        XCTAssertEqual(SkillFeedback.from(name: "bluetooth", response: ok(["on": true])),
                       .toggle(kind: .bluetooth, on: true))
        XCTAssertNil(SkillFeedback.from(name: "set_volume", response: ["ok": false, "error": "x"]))
        XCTAssertNil(SkillFeedback.from(name: "open_app", response: ok(["app": "Notes"])))
    }

    func testRPCSkillCallsDelegateAndMarksFocus() {
        let spy = VolumeSpy()
        let rpc = RPCHandler(skills: skills(spy), warmUp: false)
        let d = SpyDelegate()
        rpc.delegate = d
        let (ok, _, _) = rpc.handle(method: "skill", params: ["name": "set_volume", "args": ["level": 35]])
        XCTAssertTrue(ok)
        XCTAssertEqual(d.skills.first?.0, "set_volume")
        XCTAssertEqual((d.skills.first?.1["result"] as? [String: Any])?["level"] as? Int, 35)
        XCTAssertFalse(rpc.hands.focusRebindPending)       // volume doesn't switch apps
    }
}

// MARK: - OCR

final class OCRTests: XCTestCase {
    private func fixture(_ name: String) -> String {
        URL(fileURLWithPath: #filePath)                      // app/Tests/HandsKitTests/x.swift
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("evals/fixtures/finance/receipts/\(name)").path
    }

    func testReceiptFixture() throws {
        let path = fixture("receipt_08.png")
        try XCTSkipUnless(FileManager.default.fileExists(atPath: path), "fixture missing")
        let r = try OCR.run(path: path, region: nil, excludeBundleId: nil)
        let text = r["text"] as? String ?? ""
        XCTAssertTrue(text.contains("PHILZ COFFEE"), text)
        XCTAssertTrue(text.contains("TOTAL  10.58"), text)
        XCTAssertTrue(text.contains("10/30/2026"), text)
        let lines = r["lines"] as? [[String: Any]] ?? []
        XCTAssertFalse(lines.isEmpty)
        XCTAssertEqual((lines.first?["frame"] as? [Double])?.count, 4)
        XCTAssertEqual(r["coords"] as? String, "image_px")
        XCTAssertNotNil(r["ms"] as? Double)
    }

    func testRowJoin() {
        func l(_ t: String, _ x: CGFloat, _ y: CGFloat) -> OCR.Line {
            OCR.Line(text: t, frame: CGRect(x: x, y: y, width: 40, height: 20), confidence: 1)
        }
        let lines = [l("16.46", 300, 102), l("TOTAL", 20, 100), l("SUBTOTAL", 20, 60), l("14.93", 300, 61)]
        XCTAssertEqual(OCR.joinRows(lines), "SUBTOTAL  14.93\nTOTAL  16.46")
        XCTAssertEqual(OCR.sortReadingOrder(lines).map(\.text), ["SUBTOTAL", "14.93", "TOTAL", "16.46"])
    }

    func testBadInput() {
        XCTAssertThrowsError(try OCR.run(path: nil, region: nil, excludeBundleId: nil))
        XCTAssertThrowsError(try OCR.run(path: "/nonexistent.png", region: nil, excludeBundleId: nil))
    }
}

// MARK: - utterance ctx capture

final class PendingCtxTests: XCTestCase {
    func testDeliversValueWhenFast() {
        let p = PendingCtx(fallback: ["focused": "none"], queue: DispatchQueue.global()) {
            ["focused": "textarea \"Body\""]
        }
        let e = expectation(description: "ctx")
        p.whenReady(timeout: 0.2, queue: .global()) { v in
            XCTAssertEqual(v["focused"] as? String, "textarea \"Body\"")
            e.fulfill()
        }
        wait(for: [e], timeout: 1)
        XCTAssertNotNil(p.ready)
    }

    func testFallbackAfterTimeoutWhenAppHangs() {
        let p = PendingCtx(fallback: ["app": "Hung", "focused": "none"], queue: DispatchQueue.global()) {
            usleep(800_000)                                  // a beachballing app
            return ["app": "Hung", "focused": "button \"x\""]
        }
        XCTAssertNil(p.ready)                                // partials omit ctx
        let t0 = Date()
        let e = expectation(description: "fallback")
        var calls = 0
        p.whenReady(timeout: 0.2, queue: .main) { v in
            calls += 1
            XCTAssertEqual(v["focused"] as? String, "none")
            XCTAssertEqual(v["app"] as? String, "Hung")
            e.fulfill()
        }
        wait(for: [e], timeout: 1)
        let dt = Date().timeIntervalSince(t0)
        XCTAssertGreaterThanOrEqual(dt, 0.19)
        XCTAssertLessThan(dt, 0.6)
        // the late real value must not trigger a second delivery
        let settle = expectation(description: "settle")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { settle.fulfill() }
        wait(for: [settle], timeout: 2)
        XCTAssertEqual(calls, 1)
    }

    func testBeginReturnsImmediately() {
        let t0 = Date()
        let p = UtteranceCtx.begin()
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.05)
        XCTAssertNotNil(p.fallback["app"])
        XCTAssertEqual(p.fallback["focused"] as? String, "none")
    }
}
