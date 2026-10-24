import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Tests for the HobbyLM-parity batch: media keys in `keys`, set_brightness
// delta, Calculator keystroke typing, the timers RPCs, truthful launches,
// open_folder view, the screen-locked input guard and the display-asleep
// screen union. Hermetic: no real key / media events, no launches, no
// AppleScript, no files outside temp dirs.

private func catalog() -> [String: SkillDef] { try! Catalog.load() }

private func el(_ role: String, _ title: String? = nil, x: CGFloat = 10, y: CGFloat = 10,
                w: CGFloat = 80, h: CGFloat = 24, _ kids: [MockElement] = []) -> MockElement {
    MockElement(role: role, title: title, x: x, y: y, w: w, h: h, children: kids)
}

private func observeMock(_ h: Hands, _ root: Element, pid: pid_t = 4242) -> Observation {
    h.processObservation(roots: [root], app: "Mock", window: "W", pid: pid, maxNodes: 150, diff: true,
                         deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
}

// MARK: - 1. media keys

final class MediaKeyTests: XCTestCase {
    func testNamesAndCodes() {
        let want: [String: Int32] = [
            "volume_up": 0, "volume_down": 1, "brightness_up": 2, "brightness_down": 3,
            "mute": 7, "play_pause": 16, "next_track": 17, "previous_track": 18,
        ]
        for (n, c) in want { XCTAssertEqual(MediaKey.parse(n)?.code, c, n) }
        XCTAssertEqual(MediaKey.parse(" Volume-Up ")?.name, "volume_up")
        XCTAssertNil(MediaKey.parse("cmd+shift+n"))
        XCTAssertNil(MediaKey.parse("return"))
        XCTAssertEqual(MediaKey.parse("mute")?.kind, .volume)
        XCTAssertEqual(MediaKey.parse("brightness_up")?.kind, .brightness)
        XCTAssertEqual(MediaKey.parse("next_track")?.kind, .playback)
        XCTAssertEqual(MediaKey.forMediaAction("pause")?.code, 16)
        XCTAssertEqual(MediaKey.forMediaAction("previous")?.code, 18)
        XCTAssertNil(MediaKey.forMediaAction("rewind"))
    }

    /// The event shape the hardware keys produce: NX_SYSDEFINED, subtype 8,
    /// data1 = key << 16 | state << 8 (0xA down, 0xB up), tagged as ours.
    func testSystemDefinedEventEncodingAndTag() throws {
        for (name, code) in [("volume_up", Int32(0)), ("brightness_down", 3), ("mute", 7), ("play_pause", 16)] {
            for down in [true, false] {
                let cg = try XCTUnwrap(MediaKey.event(code: code, down: down), name)   // built, never posted
                XCTAssertTrue(SyntheticEvent.isTagged(cg), name)                       // push-to-talk ignores it
                XCTAssertEqual(cg.type.rawValue, 14, name)                              // NX_SYSDEFINED
                let ns = try XCTUnwrap(NSEvent(cgEvent: cg))
                XCTAssertEqual(ns.type, .systemDefined)
                XCTAssertEqual(ns.subtype.rawValue, 8)                                  // aux control buttons
                XCTAssertEqual(ns.data1, (Int(code) << 16) | ((down ? 0xA : 0xB) << 8), name)
                XCTAssertEqual(ns.data1 >> 16, Int(code))
                XCTAssertEqual((ns.data1 >> 8) & 0xFF, down ? 0xA : 0xB)
                XCTAssertEqual(ns.data2, -1)
            }
        }
        XCTAssertEqual(MediaKey.data1(code: 2, down: true), 0x20A00)
        XCTAssertEqual(MediaKey.data1(code: 2, down: false), 0x20B00)
    }

    private func hands(_ apps: MockApps) -> (Hands, Int) {
        let h = Hands()
        h.apps = apps
        let w = el("AXWindow", "W", x: 0, y: 0, w: 400, h: 300, [el("AXButton", "OK")])
        w.stableIdOverride = 77_001
        let o = observeMock(h, w)
        h.observeOverride = { observeMock(h, w) }
        return (h, o.elements[0].ref)
    }

    func testKeysPostsMediaKeyWithoutFocusGuardOrSettle() {
        // Another app is frontmost and the observed one can't be activated:
        // an ordinary combo is refused, a media key still goes out.
        let apps = MockApps(frontmost: 999, activateSucceeds: false)
        let (h, _) = hands(apps)
        var posted: [String] = []
        var settles = 0
        var reads = 0
        h.mediaKeyPostOverride = { posted.append($0.name) }
        h.settleOverride = { _ in settles += 1; return 0 }
        h.mediaLevelOverride = { kind in
            XCTAssertEqual(kind, .volume)
            reads += 1
            return reads == 1 ? ["level": 50, "muted": false] : ["level": 56, "muted": false]
        }
        let r = h.act(["op": "keys", "combo": "volume_up"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(posted, ["volume_up"])
        XCTAssertTrue(apps.activated.isEmpty)                 // no focus guard
        XCTAssertEqual(settles, 0)                             // no settle / re-observation
        XCTAssertNil(r["diff_text"])
        XCTAssertEqual(r["media_key"] as? String, "volume_up")
        XCTAssertEqual(r["level_before"] as? Int, 50)
        XCTAssertEqual(r["level"] as? Int, 56)
        XCTAssertEqual(r["muted"] as? Bool, false)
        XCTAssertEqual(r["changed"] as? Bool, true)
        XCTAssertTrue(JSONSerialization.isValidJSONObject(r))

        let combo = h.act(["op": "keys", "combo": "cmd+shift+n"])
        XCTAssertTrue((combo["error"] as? String ?? "").hasPrefix("focus_changed"), "\(combo)")
    }

    func testBrightnessReadBackSettlesAndUnchangedReportsFalse() {
        let (h, _) = hands(MockApps(frontmost: 4242))
        h.mediaKeyPostOverride = { _ in }
        var seq = [50, 47, 44, 44]                             // a ramp, then steady
        h.mediaLevelOverride = { _ in ["level": seq.count > 1 ? seq.removeFirst() : seq[0]] }
        let r = h.act(["op": "keys", "combo": "brightness_down"])
        XCTAssertEqual(r["level_before"] as? Int, 50)
        XCTAssertEqual(r["level"] as? Int, 44)                 // the settled value, not the ramp
        XCTAssertEqual(r["changed"] as? Bool, true)
        // At the limit nothing changes: changed=false after the bounded wait.
        h.mediaLevelOverride = { _ in ["level": 100] }
        h.mediaReadBackTimeout = 0.12
        let t0 = Date()
        let u = h.act(["op": "keys", "combo": "brightness_up"])
        XCTAssertEqual(u["changed"] as? Bool, false)
        XCTAssertEqual(u["level"] as? Int, 100)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.5)
        // Playback keys: no read-back.
        h.mediaLevelOverride = { _ in XCTFail("no read-back for playback keys"); return nil }
        let p = h.act(["op": "keys", "combo": "play_pause"])
        XCTAssertEqual(p["ok"] as? Bool, true)
        XCTAssertNil(p["changed"])
    }

    func testMediaKeyWithExpectStillVerifies() {
        let (h, _) = hands(MockApps(frontmost: 4242))
        h.mediaKeyPostOverride = { _ in }
        h.mediaLevelOverride = { _ in nil }
        var settles = 0
        h.settleOverride = { _ in settles += 1; return 0 }
        let r = h.act(["op": "keys", "combo": "mute", "expect": "title~\"W\""])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["expect_ok"] as? Bool, true)
        XCTAssertEqual(settles, 1)
    }

    func testLockedScreenAllowsMediaKeysOnly() {
        let apps = MockApps(frontmost: 4242)
        apps.locked = true
        let (h, ref) = hands(apps)
        var posted: [String] = []
        h.mediaKeyPostOverride = { posted.append($0.name) }
        h.mediaLevelOverride = { _ in nil }
        h.settleOverride = { _ in 0 }
        var typed: [String] = []
        h.typeTextOverride = { typed.append($0) }
        XCTAssertEqual(h.act(["op": "keys", "combo": "volume_down"])["ok"] as? Bool, true)
        XCTAssertEqual(posted, ["volume_down"])
        for p: [String: Any] in [["op": "keys", "combo": "return"],
                                 ["op": "type", "ref": ref, "text": "secret"],
                                 ["op": "click", "x": 20, "y": 20]] {
            let r = h.act(p)
            XCTAssertEqual(r["ok"] as? Bool, false, "\(p)")
            XCTAssertEqual(r["error"] as? String, "screen_locked", "\(p)")
            XCTAssertNotNil(r["observed"])
        }
        XCTAssertTrue(typed.isEmpty)
    }

    func testDSLAndMediaControl() throws {
        XCTAssertEqual(try DSLLine.parse("keys volume_up", epoch: 1)["combo"] as? String, "volume_up")
        XCTAssertEqual(try DSLLine.parse("keys brightness-down", epoch: 1)["op"] as? String, "keys")
        XCTAssertThrowsError(try DSLLine.parse("keys volume_upp", epoch: 1))
        let poster = MockPoster()
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster, apps: MockApps(), hooks: .inert)
        XCTAssertEqual(s.execute(name: "media_control", args: ["action": "next"])["ok"] as? Bool, true)
        XCTAssertEqual(s.execute(name: "media_control", args: ["action": "pause"])["ok"] as? Bool, true)
        XCTAssertEqual(s.execute(name: "media_control", args: ["action": "rewind"])["ok"] as? Bool, false)
        XCTAssertEqual(poster.mediaKeys, ["next_track", "play_pause"])
    }
}

// MARK: - 2. set_brightness delta

final class BrightnessDeltaTests: XCTestCase {
    private func run(current: Float?, args: [String: Any]) -> (r: [String: Any], set: Float?) {
        var set: Float?
        var level = current
        var h = SystemHooks.inert
        h.brightnessGet = { level }
        h.brightnessSet = { set = $0; level = $0; return true }
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(), apps: MockApps(), hooks: h)
        return (s.execute(name: "set_brightness", args: args), set)
    }

    func testArithmetic() {
        XCTAssertEqual(Skills.brightnessTarget(current: 50, delta: -20), 30)
        XCTAssertEqual(Skills.brightnessTarget(current: 95, delta: 20), 100)
        XCTAssertEqual(Skills.brightnessTarget(current: 3, delta: -10), 0)
        XCTAssertEqual(Skills.brightnessTarget(current: 40, delta: 0), 40)
    }

    func testDeltaReadsSetsAndReadsBack() {
        let (r, set) = run(current: 0.5, args: ["delta": -20])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(set ?? -1, 0.30, accuracy: 0.0001)
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["level"] as? Int, 30)              // read back
        XCTAssertEqual(res?["previous"] as? Int, 50)
        XCTAssertEqual(res?["delta"] as? Int, -20)
        XCTAssertEqual(SkillFeedback.from(name: "set_brightness", response: r),
                       .level(kind: .brightness, level: 30, muted: false))
    }

    func testClampsAndSignedStrings() {
        XCTAssertEqual(run(current: 0.95, args: ["delta": 20]).set ?? -1, 1.0, accuracy: 0.0001)
        XCTAssertEqual(run(current: 0.03, args: ["delta": -10]).set ?? -1, 0.0, accuracy: 0.0001)
        let plus = run(current: 0.4375, args: ["delta": "+10"])   // 43.75 -> 44, + 10
        XCTAssertEqual((plus.r["result"] as? [String: Any])?["level"] as? Int, 54)
    }

    func testLevelWinsAndErrors() {
        let both = run(current: 0.5, args: ["level": 70, "delta": -20])
        XCTAssertEqual(both.set ?? -1, 0.70, accuracy: 0.0001)
        XCTAssertNil((both.r["result"] as? [String: Any])?["delta"])
        let none = run(current: 0.5, args: [:])
        XCTAssertEqual(none.r["ok"] as? Bool, false)
        XCTAssertTrue((none.r["error"] as? String ?? "").contains("missing arg level"), "\(none.r)")
        XCTAssertNil(none.set)
        let blind = run(current: nil, args: ["delta": 10])
        XCTAssertEqual(blind.r["ok"] as? Bool, false)
        XCTAssertTrue((blind.r["error"] as? String ?? "").contains("unreadable"), "\(blind.r)")
        XCTAssertNil(blind.set)
        XCTAssertEqual(SkillTargets.label(skill: "set_brightness", args: ["delta": -10]), "-10")
        XCTAssertEqual(SkillTargets.label(skill: "set_brightness", args: ["delta": 10]), "+10")
        XCTAssertEqual(SkillTargets.label(skill: "set_brightness", args: ["delta": "+10"]), "+10")
        XCTAssertEqual(SkillTargets.label(skill: "set_brightness", args: ["level": 70]), "70%")
    }
}

// MARK: - 3. keystroke apps (Calculator)

final class KeystrokeAppTests: XCTestCase {
    private let calc = RunningAppInfo(pid: 91, name: "Calculator", bundleId: "com.apple.calculator")

    /// Calculator-like AX: a window with the display and digit buttons; the
    /// keyboard focus on a button (nothing takes text).
    private func calculatorApp(window: Bool = true, focused: MockElement? = nil) -> (app: MockElement, win: MockElement) {
        let display = el("AXStaticText", x: 20, y: 40)
        display.attrs.value = "0"
        let seven = el("AXButton", "7", x: 20, y: 120)
        let win = el("AXWindow", "Calculator", x: 0, y: 0, w: 240, h: 400, [display, seven])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0, window ? [win] : [])
        if window { app.singles[kAXFocusedWindowAttribute as String] = win }
        if let f = focused ?? (window ? seven : nil) { app.singles[kAXFocusedUIElementAttribute as String] = f }
        return (app, win)
    }

    func testCalculatorIsAKeystrokeTarget() {
        let app = calculatorApp().app
        let chk = TextTarget.check(app: app, appName: "Calculator", bundleId: "com.apple.calculator")
        XCTAssertTrue(chk.ok)
        XCTAssertEqual(chk.via, "keystroke_app")
        XCTAssertNil(chk.focusTarget)
        // The same UI in another app: nothing takes text.
        XCTAssertFalse(TextTarget.check(app: app, appName: "Other", bundleId: "com.example.other").ok)
        // No window: the keys would land nowhere.
        XCTAssertFalse(TextTarget.check(app: calculatorApp(window: false).app, appName: "Calculator",
                                        bundleId: "com.apple.calculator").ok)
        // A real text field focused in Calculator takes text the normal way.
        let field = el("AXTextField", "Search")
        XCTAssertEqual(TextTarget.check(app: calculatorApp(focused: field).app, appName: "Calculator",
                                        bundleId: "com.apple.calculator").via, "focused")
        XCTAssertTrue(TextTarget.isKeystrokeApp("com.apple.Calculator"))
        XCTAssertFalse(TextTarget.isKeystrokeApp("com.apple.TextEdit"))
        XCTAssertFalse(TextTarget.isKeystrokeApp(nil))
    }

    func testTypeTextPostsKeystrokes() {
        let poster = MockPoster()
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster,
                       apps: MockApps(frontmost: calc.pid, running: [calc]), hooks: .inert)
        let app = calculatorApp().app
        s.axApp = { _ in app }
        let r = s.execute(name: "type_text", args: ["text": "11+4="])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["target"] as? String, "keystroke_app")
        XCTAssertEqual(poster.keystrokes, ["11+4="])
        XCTAssertTrue(poster.typed.isEmpty)
        _ = s.execute(name: "type_text", args: ["text": "6×7−2÷1="])
        XCTAssertEqual(poster.keystrokes.last, "6*7-2/1=")
    }

    func testTypeTextRefusesWhileLocked() {
        let poster = MockPoster()
        let apps = MockApps(frontmost: calc.pid, running: [calc])
        apps.locked = true
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster, apps: apps, hooks: .inert)
        let app = calculatorApp().app
        s.axApp = { _ in app }
        let r = s.execute(name: "type_text", args: ["text": "1"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "screen_locked")
        XCTAssertTrue(poster.keystrokes.isEmpty && poster.typed.isEmpty)
    }

    func testTypeOpOnACalculatorButtonPostsKeys() {
        let h = Hands()
        h.apps = MockApps(frontmost: calc.pid, running: [calc])
        let (app, win) = calculatorApp()
        win.stableIdOverride = 77_201
        let seven = win.attrs.children[1] as! MockElement
        seven.settable = ["AXFocused", "AXValue"]              // even a settable value is not used
        let pid = calc.pid
        let o = observeMock(h, win, pid: pid)
        h.settleOverride = { _ in 0 }
        h.observeOverride = { observeMock(h, win, pid: pid) }
        h.axAppOverride = { _ in app }
        var keys: [String] = []
        var typed: [String] = []
        h.typeKeystrokesOverride = { keys.append($0) }
        h.typeTextOverride = { typed.append($0) }
        let ref = o.elements.first { $0.label == "7" }!.ref
        let r = h.act(["op": "type", "ref": ref, "text": "11+4="])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["target"] as? String, "keystroke_app")
        XCTAssertEqual(keys, ["11+4="])
        XCTAssertTrue(typed.isEmpty)
        XCTAssertNil(seven.store["AXValue"] ?? nil)
        XCTAssertNil(seven.store["AXFocused"] ?? nil)          // buttons are not focused first
    }

    func testKeystrokeMapping() {
        XCTAssertEqual(Events.keystroke(for: "1")?.0, 18)
        XCTAssertEqual(Events.keystroke(for: "1")?.1, false)
        XCTAssertEqual(Events.keystroke(for: "+")?.0, 24)
        XCTAssertEqual(Events.keystroke(for: "+")?.1, true)
        XCTAssertEqual(Events.keystroke(for: "=")?.0, 24)
        XCTAssertEqual(Events.keystroke(for: "=")?.1, false)
        XCTAssertEqual(Events.keystroke(for: "*")?.0, 28)
        XCTAssertEqual(Events.keystroke(for: "/")?.0, 44)
        XCTAssertEqual(Events.keystroke(for: ".")?.0, 47)
        XCTAssertEqual(Events.keystroke(for: "\n")?.0, 36)
        XCTAssertEqual(Events.keystroke(for: "C")?.0, 8)
        XCTAssertEqual(Events.keystroke(for: "C")?.1, true)
        XCTAssertNil(Events.keystroke(for: "é"))
        XCTAssertEqual(TextTarget.keystrokeText("2×3÷4−1"), "2*3/4-1")
    }
}

// MARK: - 4. timers RPCs

final class TimersRPCTests: XCTestCase {
    private func skills(_ hooks: SystemHooks = .inert) -> Skills {
        Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(), apps: MockApps(), hooks: hooks)
    }

    func testListShapeAndOrder() {
        let s = skills()
        defer { _ = s.cancelTimers(id: nil) }
        _ = s.execute(name: "start_timer", args: ["duration": 600, "label": "Tea"])
        _ = s.execute(name: "start_timer", args: ["duration": "90s"])
        let list = s.timerList()
        XCTAssertEqual(list.count, 2)
        XCTAssertEqual(list.map { $0["total_s"] as? Double }, [90, 600])         // soonest first
        let tea = list[1]
        XCTAssertEqual(tea["label"] as? String, "Tea")
        XCTAssertNil(list[0]["label"])
        XCTAssertTrue((tea["id"] as? String ?? "").hasPrefix("timer-"))
        XCTAssertEqual(tea["minutes"] as? Int, 10)
        XCTAssertEqual(tea["left_s"] as? Double ?? 0, 600, accuracy: 1)
        XCTAssertNotNil(tea["fires_at"] as? String)
        XCTAssertTrue(JSONSerialization.isValidJSONObject(["timers": list]))
    }

    func testMinutesLeftRoundUp() {
        let t0 = Date(timeIntervalSince1970: 1_000_000)
        let i = TimerRegistry.Info(id: "timer-x", label: nil, total: 600, startedAt: t0,
                                   firesAt: t0.addingTimeInterval(600))
        XCTAssertEqual(TimerRegistry.dict(i, now: t0.addingTimeInterval(230))["minutes"] as? Int, 7)  // 6:10 left
        XCTAssertEqual(TimerRegistry.dict(i, now: t0.addingTimeInterval(580))["minutes"] as? Int, 1)  // 0:20 left
        XCTAssertEqual(TimerRegistry.dict(i, now: t0.addingTimeInterval(700))["left_s"] as? Double, 0)
        XCTAssertEqual(TimerRegistry.dict(i, now: t0.addingTimeInterval(700))["minutes"] as? Int, 0)
        XCTAssertEqual(TimerRegistry.dict(i, now: t0)["total_s"] as? Double, 600)
    }

    func testRPCCancelOneUnknownAndAll() {
        let s = skills()
        let rpc = RPCHandler(skills: s, warmUp: false)
        let a = s.execute(name: "start_timer", args: ["duration": 300, "label": "Pasta"])
        _ = s.execute(name: "start_timer", args: ["duration": 120])
        _ = s.execute(name: "start_timer", args: ["duration": 60])
        let id = (a["result"] as? [String: Any])?["timer_id"] as? String
        XCTAssertNotNil(id)

        let (ok0, r0, _) = rpc.handle(method: "timers", params: [:])
        XCTAssertTrue(ok0)
        XCTAssertEqual(((r0 as? [String: Any])?["timers"] as? [[String: Any]])?.count, 3)

        let (ok1, r1, e1) = rpc.handle(method: "timers_cancel", params: ["id": id ?? ""])
        XCTAssertTrue(ok1, e1 ?? "")
        let d1 = r1 as? [String: Any]
        XCTAssertEqual((d1?["cancelled"] as? [[String: Any]])?.first?["label"] as? String, "Pasta")
        XCTAssertEqual((d1?["timers"] as? [[String: Any]])?.count, 2)

        let (ok2, r2, e2) = rpc.handle(method: "timers_cancel", params: ["id": "timer-nope"])
        XCTAssertFalse(ok2)
        XCTAssertEqual(e2, "unknown_timer: timer-nope")
        XCTAssertEqual(((r2 as? [String: Any])?["timers"] as? [[String: Any]])?.count, 2)

        let (ok3, _, e3) = rpc.handle(method: "timers_cancel", params: ["id": ""])
        XCTAssertFalse(ok3)
        XCTAssertTrue((e3 ?? "").hasPrefix("invalid params"), e3 ?? "")
        XCTAssertEqual(s.pendingTimers, 2)

        let (ok4, r4, _) = rpc.handle(method: "timers_cancel", params: [:])
        XCTAssertTrue(ok4)
        XCTAssertEqual(((r4 as? [String: Any])?["cancelled"] as? [[String: Any]])?.count, 2)
        XCTAssertEqual(s.pendingTimers, 0)
        // Nothing left: cancelling all again is fine.
        let (ok5, r5, _) = rpc.handle(method: "timers_cancel", params: [:])
        XCTAssertTrue(ok5)
        XCTAssertEqual(((r5 as? [String: Any])?["cancelled"] as? [[String: Any]])?.count, 0)
    }

    func testCancelledTimerNeverFires() {
        var sounds = 0
        let lock = NSLock()
        var h = SystemHooks.inert
        h.playSound = { _ in lock.lock(); sounds += 1; lock.unlock() }
        let s = skills(h)
        let d = SpyDelegate()
        s.delegate = d
        let r = s.execute(name: "start_timer", args: ["duration": 0.2])
        let id = (r["result"] as? [String: Any])?["timer_id"] as? String
        XCTAssertEqual(s.cancelTimers(id: id).count, 1)
        let e = expectation(description: "past due")
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.45) { e.fulfill() }
        wait(for: [e], timeout: 2)
        lock.lock(); XCTAssertEqual(sounds, 0); lock.unlock()
        XCTAssertTrue(d.timerLabels.isEmpty)
        XCTAssertEqual(s.pendingTimers, 0)
    }

    func testChangesReachTheHook() {
        var seen: [Int] = []
        let lock = NSLock()
        var h = SystemHooks.inert
        h.timersChanged = { infos in lock.lock(); seen.append(infos.count); lock.unlock() }
        let s = skills(h)
        _ = s.execute(name: "start_timer", args: ["duration": 600])
        _ = s.execute(name: "start_timer", args: ["duration": 900])
        _ = s.cancelTimers(id: nil)
        lock.lock(); XCTAssertEqual(seen, [1, 2, 0]); lock.unlock()
    }

    func testSnapshotRoundTripSkipsDeadProcessesAndPastTimers() {
        let dir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("hands-timers-test-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let now = Date()
        let live = TimerRegistry.Info(id: "timer-live", label: "Tea", total: 600,
                                      startedAt: now.addingTimeInterval(-60), firesAt: now.addingTimeInterval(540))
        let past = TimerRegistry.Info(id: "timer-past", label: nil, total: 60,
                                      startedAt: now.addingTimeInterval(-120), firesAt: now.addingTimeInterval(-60))
        TimerSnapshot.write([live, past], pid: 111, process: "Muselet", directory: dir, gc: false)
        TimerSnapshot.write([live], pid: 222, process: "hands", directory: dir, gc: false)
        TimerSnapshot.flush()
        let got = TimerSnapshot.read(directory: dir, now: now, isAlive: { $0 == 111 })
        XCTAssertEqual(got.count, 1)                               // 222 is dead, timer-past is due
        XCTAssertEqual(got.first?["id"] as? String, "timer-live")
        XCTAssertEqual(got.first?["label"] as? String, "Tea")
        XCTAssertEqual(got.first?["process"] as? String, "Muselet")
        XCTAssertEqual(got.first?["pid"] as? Int, 111)
        XCTAssertEqual(got.first?["minutes"] as? Int, 9)
        // No timers left in 111: its file goes away.
        TimerSnapshot.write([], pid: 111, directory: dir, gc: false)
        TimerSnapshot.flush()
        XCTAssertFalse(FileManager.default.fileExists(atPath: dir.appendingPathComponent("111.json").path))
        XCTAssertEqual(TimerSnapshot.read(directory: dir, now: now, isAlive: { _ in true }).map { $0["pid"] as? Int },
                       [222])
        // A writer garbage-collects the files of processes that are gone.
        var dead: pid_t = 99_999
        while TimerSnapshot.processAlive(dead) { dead += 1 }
        TimerSnapshot.write([live], pid: dead, directory: dir, gc: false)
        TimerSnapshot.write([live], pid: getpid(), directory: dir)
        TimerSnapshot.flush()
        XCTAssertFalse(FileManager.default.fileExists(atPath: dir.appendingPathComponent("\(dead).json").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: dir.appendingPathComponent("\(getpid()).json").path))
    }
}

// MARK: - 6/7. truthful launches + open_folder view

/// LaunchServices stand-in: records opens; tests move the "frontmost" app.
final class MockLauncher: Launching {
    var apps: [String: (pid: pid_t, launched: Bool)] = [:]
    /// URL scheme, file extension, or "folder" -> default app.
    var defaults: [String: LaunchTarget] = [:]
    var opened: [(url: URL, app: LaunchTarget?)] = []
    var openPid: pid_t = 0
    var onOpen: ((URL, LaunchTarget?) -> Void)?
    var onOpenApp: ((String) -> Void)?

    func openApp(named name: String) throws -> (pid: pid_t, launched: Bool) {
        guard let a = apps[name.lowercased()] else { throw HandsError.skillFailed("app not found: \(name)") }
        onOpenApp?(name)
        return a
    }

    func defaultApp(for url: URL) -> LaunchTarget? {
        if url.isFileURL { return defaults[url.pathExtension.isEmpty ? "folder" : url.pathExtension] }
        return defaults[url.scheme ?? ""]
    }

    func open(_ url: URL, with app: LaunchTarget?) throws -> pid_t {
        opened.append((url, app))
        onOpen?(url, app)
        return openPid
    }
}

/// App whose front window title comes from a closure (changes over time);
/// nil = no window.
final class TitledApp: Element {
    final class Window: Element {
        let title: () -> String?
        init(_ title: @escaping () -> String?) { self.title = title }
        func copyAttrs() -> ElAttrs {
            var a = ElAttrs()
            a.role = "AXWindow"
            a.title = title()
            a.size = CGSize(width: 800, height: 600)
            return a
        }
        func performAction(_ name: String) -> Bool { false }
        func setAttr(_ name: String, _ value: Any?) -> Bool { false }
        func isSettable(_ name: String) -> Bool { false }
        func copySingleAttr(_ name: String) -> Any? { name == kAXTitleAttribute as String ? title() : nil }
    }

    let window: Window
    init(_ title: @escaping () -> String?) { window = Window(title) }
    func copyAttrs() -> ElAttrs { var a = ElAttrs(); a.role = "AXApplication"; return a }
    func performAction(_ name: String) -> Bool { false }
    func setAttr(_ name: String, _ value: Any?) -> Bool { false }
    func isSettable(_ name: String) -> Bool { false }
    func copySingleAttr(_ name: String) -> Any? {
        name == kAXFocusedWindowAttribute as String && window.title() != nil ? window : nil
    }
}

final class TruthfulLaunchTests: XCTestCase {
    private let term = RunningAppInfo(pid: 1, name: "Terminal", bundleId: "com.apple.Terminal")
    private let safari = RunningAppInfo(pid: 600, name: "Safari", bundleId: "com.apple.Safari")
    private let zen = RunningAppInfo(pid: 700, name: "Zen", bundleId: "app.zen-browser.zen")
    private let finder = RunningAppInfo(pid: 800, name: "Finder", bundleId: "com.apple.finder")
    private let preview = RunningAppInfo(pid: 900, name: "Preview", bundleId: "com.apple.Preview")
    private var zenTarget: LaunchTarget {
        LaunchTarget(name: "Zen", bundleId: zen.bundleId, url: URL(fileURLWithPath: "/Applications/Zen.app"))
    }
    private var cleanup: [String] = []

    override func tearDown() {
        for p in cleanup { try? FileManager.default.removeItem(atPath: p) }
        cleanup = []
        super.tearDown()
    }

    private func tempDir(_ name: String) throws -> String {
        let root = NSTemporaryDirectory() + "hands-launch-\(UUID().uuidString)"
        let p = root + "/" + name
        try FileManager.default.createDirectory(atPath: p, withIntermediateDirectories: true)
        cleanup.append(root)
        return p
    }

    private func tempFile(_ name: String) throws -> String {
        let p = try tempDir("files") + "/" + name
        try "x".write(toFile: p, atomically: true, encoding: .utf8)
        return p
    }

    private func skills(_ apps: MockApps, _ launcher: MockLauncher, scripts: ScriptRunning = SpyRunner(),
                        poster: MockPoster = MockPoster(),
                        title: @escaping (pid_t) -> String?) -> Skills {
        let s = Skills(catalog: catalog(), scripts: scripts, events: poster, apps: apps, hooks: .inert,
                       launcher: launcher)
        s.axApp = { pid in TitledApp { title(pid) } }
        s.openAppTimeout = 0.3
        s.openTimeout = 0.4
        s.launchPollInterval = 0.01
        s.launchReactivateInterval = 0.05
        s.viewPollInterval = 0.01
        s.displayNameOverride = { ($0 as NSString).lastPathComponent }
        return s
    }

    // open_app

    func testOpenAppReturnsOnceFrontmost() {
        let apps = MockApps(frontmost: 1, running: [term, safari])
        let launcher = MockLauncher()
        launcher.apps["safari"] = (600, true)
        launcher.onOpenApp = { _ in apps.frontmost = 600 }       // the launch brought it forward
        let s = skills(apps, launcher) { _ in "Start Page" }
        let r = s.execute(name: "open_app", args: ["app": "Safari"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["app"] as? String, "Safari")
        XCTAssertEqual(res?["frontmost"] as? String, "Safari")
        XCTAssertEqual(res?["launched"] as? Bool, true)
        XCTAssertEqual(res?["window_title"] as? String, "Start Page")
        XCTAssertTrue(apps.activated.isEmpty)
    }

    func testOpenAppReactivatesWhenTheLaunchDidNotComeForward() {
        let apps = MockApps(frontmost: 1, running: [term, safari])
        let launcher = MockLauncher()
        launcher.apps["safari"] = (600, false)
        let s = skills(apps, launcher) { _ in nil }
        let r = s.execute(name: "open_app", args: ["app": "safari"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(apps.activated.first, 600)
        XCTAssertEqual((r["result"] as? [String: Any])?["app"] as? String, "Safari")   // resolved name
        XCTAssertEqual((r["result"] as? [String: Any])?["launched"] as? Bool, false)
    }

    func testOpenAppNeverFrontmostIsNotFrontmostWithTheReadBack() {
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [term, safari])
        let launcher = MockLauncher()
        launcher.apps["safari"] = (600, true)
        let s = skills(apps, launcher) { _ in nil }
        let t0 = Date()
        let r = s.execute(name: "open_app", args: ["app": "Safari"])
        let dt = Date().timeIntervalSince(t0)
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "not_frontmost")
        XCTAssertTrue((r["observed"] as? String ?? "").contains("Terminal"), "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["frontmost"] as? String, "Terminal")
        XCTAssertGreaterThanOrEqual(dt, 0.28)                    // waited the whole bound
        XCTAssertLessThan(dt, 1.0)
        XCTAssertFalse(apps.activated.isEmpty)                   // and retried activation
        // Unknown app: the launcher's error, no wait.
        XCTAssertEqual(s.execute(name: "open_app", args: ["app": "Nope"])["error"] as? String,
                       "app not found: Nope")
    }

    // open_url / web_search

    func testOpenURLWaitsForTheBrowserAndANewTitle() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var openedAt: Date?
        launcher.onOpen = { _, _ in apps.frontmost = 700; openedAt = Date() }
        let s = skills(apps, launcher) { pid in
            guard pid == 700 else { return nil }
            // The old tab's title until the new page loads ~60 ms after the open.
            guard let t = openedAt, Date().timeIntervalSince(t) > 0.06 else { return "GitHub" }
            return "Example Domain — Zen Browser"
        }
        let r = s.execute(name: "open_url", args: ["url": "example.com"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["url"] as? String, "https://example.com")
        XCTAssertEqual(res?["browser"] as? String, "Zen")
        XCTAssertEqual(res?["frontmost"] as? String, "Zen")
        XCTAssertEqual(res?["window_title"] as? String, "Example Domain — Zen Browser")
        XCTAssertEqual(res?["title_changed"] as? Bool, true)
        XCTAssertEqual(launcher.opened.first?.url.absoluteString, "https://example.com")
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "app.zen-browser.zen")   // the default browser
    }

    func testOpenURLUnchangedTitleIsReported() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        launcher.onOpen = { _, _ in apps.frontmost = 700 }
        let s = skills(apps, launcher) { pid in pid == 700 ? "Example Domain" : nil }
        let r = s.execute(name: "open_url", args: ["url": "https://example.com"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")              // frontmost: it did open
        XCTAssertEqual((r["result"] as? [String: Any])?["title_changed"] as? Bool, false)
    }

    func testFreshBrowserLaunchWaitsPastPlaceholderTitles() {
        let apps = MockApps(frontmost: 1, running: [term])           // Zen not running yet
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var openedAt: Date?
        let zen = self.zen
        launcher.onOpen = { _, _ in apps.running.append(zen); apps.frontmost = 700; openedAt = Date() }
        let s = skills(apps, launcher) { pid in
            guard pid == 700, let t = openedAt else { return nil }
            return Date().timeIntervalSince(t) > 0.06 ? "Example Domain" : "New Tab"
        }
        let r = s.execute(name: "open_url", args: ["url": "https://example.com"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["window_title"] as? String, "Example Domain")
        XCTAssertEqual((r["result"] as? [String: Any])?["title_changed"] as? Bool, true)
    }

    func testOpenURLNeverFrontmostIsNotFrontmost() {
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        let s = skills(apps, launcher) { _ in "GitHub" }
        let r = s.execute(name: "open_url", args: ["url": "example.com"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "not_frontmost")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["browser"] as? String, "Zen")
        XCTAssertEqual(res?["frontmost"] as? String, "Terminal")
        XCTAssertEqual(res?["url"] as? String, "https://example.com")
    }

    func testWebSearchOpensTheEncodedQueryInTheBrowser() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var openedAt: Date?
        launcher.onOpen = { _, _ in apps.frontmost = 700; openedAt = Date() }
        let s = skills(apps, launcher) { _ in openedAt == nil ? "GitHub" : "AT&T c++ a=b - Google Search" }
        let r = s.execute(name: "web_search", args: ["query": "AT&T c++ a=b"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(launcher.opened.first?.url.absoluteString,
                       "https://www.google.com/search?q=AT%26T%20c%2B%2B%20a%3Db")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["query"] as? String, "AT&T c++ a=b")
        XCTAssertEqual(res?["window_title"] as? String, "AT&T c++ a=b - Google Search")
    }

    // open_folder (+ view) / open_file

    func testOpenFolderReadsTheWindowTitleAndAppliesTheView() throws {
        let dir = try tempDir("Reports")
        let apps = MockApps(frontmost: 1, running: [term, finder])
        let launcher = MockLauncher()
        launcher.openPid = 800
        launcher.onOpen = { _, _ in apps.frontmost = 800 }
        let spy = SpyRunner()
        spy.respond = "list view"
        let poster = MockPoster()
        let s = skills(apps, launcher, scripts: spy, poster: poster) { pid in pid == 800 ? "Reports" : nil }
        let r = s.execute(name: "open_folder", args: ["path": dir, "view": "list"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["app"] as? String, "Finder")
        XCTAssertEqual(res?["frontmost"] as? String, "Finder")
        XCTAssertEqual(res?["window_title"] as? String, "Reports")
        XCTAssertEqual(res?["title_matches"] as? Bool, true)
        XCTAssertEqual(poster.posted, ["cmd+2"])
        XCTAssertEqual(spy.ran, [FinderView.readScript])
        XCTAssertEqual(res?["view"] as? String, "list")
        XCTAssertEqual(res?["view_applied"] as? Bool, true)
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "com.apple.finder")
        XCTAssertEqual(launcher.opened.first?.url.path, dir)
    }

    func testOpenFolderViewValidatedFirstAndOnlyForTheVerifiedWindow() throws {
        let dir = try tempDir("Taxes")
        let apps = MockApps(frontmost: 1, running: [term, finder])
        let launcher = MockLauncher()
        launcher.openPid = 800
        launcher.onOpen = { _, _ in apps.frontmost = 800 }
        let spy = SpyRunner()
        let poster = MockPoster()
        let s = skills(apps, launcher, scripts: spy, poster: poster) { pid in pid == 800 ? "Downloads" : nil }
        let bad = s.execute(name: "open_folder", args: ["path": dir, "view": "huge"])
        XCTAssertEqual(bad["ok"] as? Bool, false)
        XCTAssertTrue((bad["error"] as? String ?? "").contains("view must be"), "\(bad)")
        XCTAssertTrue(launcher.opened.isEmpty)                   // nothing opened
        // Finder came forward but another folder's window is in front: no keys.
        let r = s.execute(name: "open_folder", args: ["path": dir, "view": "icons"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["title_matches"] as? Bool, false)
        XCTAssertEqual(res?["view_applied"] as? Bool, false)
        XCTAssertNotNil(res?["view_error"])
        XCTAssertTrue(poster.posted.isEmpty)
        XCTAssertTrue(spy.ran.isEmpty)
        // Missing folder: nothing opened.
        XCTAssertEqual(s.execute(name: "open_folder", args: ["path": dir + "/nope"])["ok"] as? Bool, false)
        XCTAssertEqual(launcher.opened.count, 1)
    }

    func testOpenFolderNotFrontmost() throws {
        let dir = try tempDir("Inbox")
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [term, finder])
        let launcher = MockLauncher()
        launcher.openPid = 800
        let s = skills(apps, launcher) { _ in "Inbox" }
        let r = s.execute(name: "open_folder", args: ["path": dir])
        XCTAssertEqual(r["error"] as? String, "not_frontmost")
        XCTAssertEqual((r["result"] as? [String: Any])?["path"] as? String, dir)
    }

    func testFinderViewMapping() {
        XCTAssertEqual(FinderView.parse("Columns"), .columns)
        XCTAssertEqual(FinderView.parse("icon"), .icons)
        XCTAssertEqual(FinderView.parse("gallery"), .gallery)
        XCTAssertNil(FinderView.parse("tiles"))
        XCTAssertEqual(FinderView.icons.combo, "cmd+1")
        XCTAssertEqual(FinderView.list.combo, "cmd+2")
        XCTAssertEqual(FinderView.columns.combo, "cmd+3")
        XCTAssertEqual(FinderView.gallery.combo, "cmd+4")
        XCTAssertEqual(FinderView.fromAppleScript("column view"), .columns)
        XCTAssertEqual(FinderView.fromAppleScript("flow view"), .gallery)
        XCTAssertEqual(FinderView.fromAppleScript("«constant ****lsvw»"), .list)
        XCTAssertEqual(FinderView.fromAppleScript("icon view"), .icons)
        XCTAssertNil(FinderView.fromAppleScript("group view"))
        XCTAssertTrue(SkillScripts.fixedSources.contains(FinderView.readScript))   // precompiled at warm-up
    }

    func testOpenFileWaitsForItsAppAndTitle() throws {
        let file = try tempFile("report.pdf")
        let apps = MockApps(frontmost: 1, running: [term, preview])
        let launcher = MockLauncher()
        launcher.defaults["pdf"] = LaunchTarget(name: "Preview", bundleId: preview.bundleId, url: nil)
        launcher.openPid = 900
        launcher.onOpen = { _, _ in apps.frontmost = 900 }
        let s = skills(apps, launcher) { pid in pid == 900 ? "report" : nil }   // extension hidden
        let r = s.execute(name: "open_file", args: ["path": file])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["app"] as? String, "Preview")
        XCTAssertEqual(res?["frontmost"] as? String, "Preview")
        XCTAssertEqual(res?["window_title"] as? String, "report")
        XCTAssertEqual(res?["title_matches"] as? Bool, true)
        let odd = try tempFile("data.xyz")
        XCTAssertEqual(s.execute(name: "open_file", args: ["path": odd])["error"] as? String,
                       "no app opens data.xyz")
    }
}

// MARK: - display asleep

final class ScreenUnionTests: XCTestCase {
    func testFallsBackToOnlineDisplaysWhileAsleep() throws {
        var online: UInt32 = 0
        CGGetOnlineDisplayList(0, nil, &online)
        try XCTSkipIf(online == 0, "no displays at all")
        let u = Walker.screenUnion()
        XCTAssertFalse(u.isNull)
        XCTAssertGreaterThan(u.width, 0)
    }
}
