import ApplicationServices
import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Skills: catalog + gating, system skills (bluetooth / lock_screen /
// empty_trash / set_brightness), volume / brightness / dark mode read-backs,
// HUD feedback, premiere_command, OCR, skill ghost targets, type_text text
// targets (keystroke apps, blind windows), skill AppleScripts compiled once
// as handlers, Automation status mapping, Control Center lookups. Hermetic:
// mock hooks, script runners and AX trees; no real key/mouse events, no
// Bluetooth/lock/trash side effects; the one real NSAppleScript test
// targets no app.

// MARK: - Catalog + skills gating

final class CatalogTests: XCTestCase {
    func testLoadsRepoCatalog() throws {
        let cat = try Catalog.load()   // walks up to repo skills/catalog.json
        XCTAssertGreaterThan(cat.count, 25)
        XCTAssertEqual(cat["set_volume"]?.risk, "safe")
        XCTAssertEqual(cat["send_message"]?.risk, "confirm")
        XCTAssertEqual(cat["quit_app"]?.risk, "confirm_if_unsaved")
        XCTAssertTrue(cat["set_volume"]?.args.first?.required ?? false)
    }
}

final class SkillGatingTests: XCTestCase {
    func skills() -> Skills {
        Skills(catalog: (try! Catalog.load()), scripts: SpyRunner(),
               events: MockPoster(), apps: MockApps(), hooks: .inert)
    }

    func testConfirmRiskRefusesWithoutConfirmed() {
        let r = skills().execute(name: "send_message",
                                 args: ["to": "mom", "body": "hi"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "needs_confirmation")
        XCTAssertNotNil(r["ms"])
    }

    func testMoveToTrashGate() {
        let r = skills().execute(name: "move_to_trash", args: ["path": "/tmp/x"])
        XCTAssertEqual(r["error"] as? String, "needs_confirmation")
    }

    func testMoveToTrashConfirmed() throws {
        let f = NSTemporaryDirectory() + "hands-test-\(UUID().uuidString)"
        try "x".write(toFile: f, atomically: true, encoding: .utf8)
        let r = skills().execute(name: "move_to_trash",
                                 args: ["path": f, "confirmed": true])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertFalse(FileManager.default.fileExists(atPath: f))
    }

    func testUnimplementedSkill() {
        // executor=brain skills are not implemented by HandsKit
        let r = skills().execute(name: "finance_review", args: [:])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String)?.contains("not_implemented") ?? false)
    }

    func testMissingRequiredArg() {
        let r = skills().execute(name: "set_volume", args: [:])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String)?.contains("missing arg") ?? false)
    }

    func testPathAliases() {
        XCTAssertEqual(PathAlias.resolve("downloads"),
                       NSHomeDirectory() + "/Downloads")
        XCTAssertEqual(PathAlias.resolve("Desktop"),
                       NSHomeDirectory() + "/Desktop")
        XCTAssertEqual(PathAlias.resolve("/tmp"), "/tmp")
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

// MARK: - set_brightness delta

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

// MARK: - read-backs + HUD feedback

final class ReadBackTests: XCTestCase {
    private func skills(_ spy: VolumeSpy, hooks: SystemHooks = .inert) -> Skills {
        Skills(catalog: catalog(), scripts: spy, events: MockPoster(), apps: MockApps(), hooks: hooks)
    }

    func testVolumeReadBack() {
        let spy = VolumeSpy()
        let r = skills(spy).execute(name: "set_volume", args: ["level": 30])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertNotNil(r["ms"])
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

    func testDarkModeReadBack() {
        // macOS reports the opposite of what was asked: the result must be
        // the read-back, not an echo of the argument.
        final class DarkSpy: ScriptRunning {
            func run(_ s: String) throws -> String { s.hasSuffix("get dark mode") ? "false" : "" }
            func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String {
                handler == "set_dark" ? "false" : ""
            }
        }
        let s = Skills(catalog: catalog(), scripts: DarkSpy(), events: MockPoster(),
                       apps: MockApps(), hooks: .inert)
        let r = s.execute(name: "dark_mode", args: ["on": true])
        XCTAssertEqual((r["result"] as? [String: Any])?["on"] as? Bool, false)
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

// MARK: - premiere_command

final class PremiereCommandTests: XCTestCase {
    private let premiere = RunningAppInfo(pid: 777, name: "Adobe Premiere Pro 2026",
                                          bundleId: "com.adobe.PremierePro.26")

    private final class PressElement: Element {
        let base: MockElement
        var succeeds = true
        var onPress: (() -> Void)?
        init(_ base: MockElement) { self.base = base }
        func copyAttrs() -> ElAttrs { base.copyAttrs() }
        func performAction(_ name: String) -> Bool {
            base.actions.append(name)
            onPress?()
            return succeeds
        }
        func setAttr(_ name: String, _ value: Any?) -> Bool { false }
        func isSettable(_ name: String) -> Bool { false }
    }

    private func timelineMenu() -> (MockElement, PressElement, PressElement) {
        let timeline = PressElement(MockElement(role: "AXMenuItem", title: "Timeline"))
        let menu = MockElement(role: "AXMenu")
        menu.attrs.children = [timeline]
        let window = PressElement(MockElement(role: "AXMenuBarItem", title: "Window", children: [menu]))
        let bar = MockElement(role: "AXMenuBar")
        bar.attrs.children = [window]
        let app = MockElement(role: "AXApplication")
        app.singles["AXMenuBar"] = bar
        return (app, window, timeline)
    }

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
            let (root, window, timeline) = timelineMenu()
            s.axApp = { _ in root }
            timeline.onPress = { XCTAssertTrue(poster.posted.isEmpty) }
            let r = s.execute(name: "premiere_command", args: ["command": cmd])
            XCTAssertEqual(r["ok"] as? Bool, true, "\(cmd): \(r)")
            XCTAssertEqual(window.base.actions, ["AXPress"], cmd)
            XCTAssertEqual(timeline.base.actions, ["AXPress"], cmd)
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

    func testTimelineMenuFailuresNeverSendKeys() {
        for failure in ["missing bar", "missing window", "disabled window", "failed window",
                        "missing timeline", "disabled timeline", "failed timeline", "submenu",
                        "ambiguous timeline", "focus changed"] {
            let poster = MockPoster()
            let apps = MockApps(running: [premiere])
            let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster,
                           apps: apps, hooks: .inert)
            let (root, window, timeline) = timelineMenu()
            switch failure {
            case "missing bar": root.singles.removeValue(forKey: "AXMenuBar")
            case "missing window": window.base.attrs.title = "Other"
            case "disabled window": window.base.attrs.enabled = false
            case "failed window": window.succeeds = false
            case "missing timeline": timeline.base.attrs.title = "Other"
            case "disabled timeline": timeline.base.attrs.enabled = false
            case "failed timeline": timeline.succeeds = false
            case "submenu": timeline.base.attrs.children = [MockElement(role: "AXMenu")]
            case "ambiguous timeline":
                (window.base.attrs.children[0] as! MockElement).attrs.children.append(
                    MockElement(role: "AXMenuItem", title: "Timeline"))
            case "focus changed": timeline.onPress = { apps.frontmost = 999 }
            default: XCTFail(failure)
            }
            s.axApp = { _ in root }
            let r = s.execute(name: "premiere_command", args: ["command": "undo"])
            XCTAssertEqual(r["ok"] as? Bool, false, "\(failure): \(r)")
            XCTAssertTrue(poster.posted.isEmpty, failure)
        }
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

// MARK: - ux-4: skill ghost targets

final class SkillTargetTests: XCTestCase {
    private let screen = CGRect(x: 0, y: 0, width: 1800, height: 1169)

    private final class Counter { var n = 0 }

    private func targets(dockY: CGFloat = 1080, extras: [SkillTargets.MenuExtra]? = nil,
                         reads: Counter? = nil) -> SkillTargets {
        let t = SkillTargets()
        let y = dockY
        t.readDock = {
            reads?.n += 1
            return [
                .init(title: "Finder", path: "/System/Library/CoreServices/Finder.app",
                      frame: CGRect(x: 112, y: y, width: 77, height: 93)),
                .init(title: "Zen", path: "/Applications/Zen.app", frame: CGRect(x: 420, y: y, width: 77, height: 93)),
                .init(title: "Safari", path: "/System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app",
                      frame: CGRect(x: 1190, y: y, width: 77, height: 93)),
                .init(title: "Numbers", path: "/Applications/Numbers Creator Studio.app",
                      frame: CGRect(x: 1344, y: y, width: 77, height: 93)),
            ]
        }
        t.readExtras = {
            extras ?? [
                .init(ident: "com.apple.menuextra.wifi", frame: CGRect(x: 1614, y: 8, width: 22, height: 24)),
                .init(ident: "com.apple.menuextra.controlcenter", frame: CGRect(x: 1652, y: 8, width: 26, height: 24)),
            ]
        }
        t.screens = { [screen] in screen }
        t.appPath = { name in name == "Safari" ? "/Applications/Safari.app" : nil }
        t.browserPath = { "/Applications/Zen.app" }
        return t
    }

    func testAppSkillsTargetTheDockIcon() {
        let t = targets()
        let s = t.target(skill: "open_app", args: ["app": "Safari"])
        XCTAssertEqual(s?.frame.minX, 1190)                   // matched by bundle name across paths
        XCTAssertEqual(s?.label, "Safari")
        XCTAssertEqual(t.target(skill: "quit_app", args: ["app": "Numbers"])?.frame.minX, 1344)  // title prefix
        XCTAssertEqual(t.target(skill: "hide_app", args: ["app": "zen"])?.frame.minX, 420)
        XCTAssertNil(t.target(skill: "open_app", args: ["app": "Xcode"]))   // not in the Dock
    }

    func testFinderAndBrowserSkills() {
        let t = targets()
        XCTAssertEqual(t.target(skill: "open_folder", args: ["path": "~/Downloads"])?.frame.minX, 112)
        XCTAssertEqual(t.target(skill: "open_folder", args: ["path": "~/Downloads"])?.label, "Downloads")
        XCTAssertEqual(t.target(skill: "find_file", args: ["query": "tax"])?.frame.minX, 112)
        XCTAssertEqual(t.target(skill: "new_folder", args: ["parent": "~", "name": "X"])?.frame.minX, 112)
        XCTAssertEqual(t.target(skill: "web_search", args: ["query": "flights"])?.frame.minX, 420)
        XCTAssertEqual(t.target(skill: "open_url", args: ["url": "github.com/x"])?.label, "github.com")
    }

    func testMenuExtrasWithControlCenterFallback() {
        let t = targets()
        XCTAssertEqual(t.target(skill: "wifi", args: ["on": false])?.frame.minX, 1614)
        XCTAssertEqual(t.target(skill: "wifi", args: ["on": false])?.label, "Off")
        XCTAssertEqual(t.target(skill: "set_volume", args: ["level": 30])?.frame.minX, 1652)  // no Sound extra
        XCTAssertEqual(t.target(skill: "set_volume", args: ["level": 30])?.label, "30%")
        for s in ["mute", "set_brightness", "dark_mode", "bluetooth", "change_volume"] {
            XCTAssertEqual(t.target(skill: s, args: [:])?.frame.minX, 1652, s)
        }
        let withSound = targets(extras: [
            .init(ident: "com.apple.menuextra.sound", frame: CGRect(x: 1500, y: 8, width: 22, height: 24)),
            .init(ident: "com.apple.menuextra.controlcenter", frame: CGRect(x: 1652, y: 8, width: 26, height: 24)),
        ])
        XCTAssertEqual(withSound.target(skill: "mute", args: ["on": true])?.frame.minX, 1500)
    }

    func testHiddenDockAndUntargetedSkills() {
        let hidden = targets(dockY: 1174)                     // auto-hidden Dock parks icons below the edge
        XCTAssertNil(hidden.target(skill: "open_app", args: ["app": "Safari"]))
        XCTAssertNil(hidden.target(skill: "open_folder", args: ["path": "~"]))
        XCTAssertFalse(SkillTargets.hasTarget("start_timer"))
        XCTAssertNil(targets().target(skill: "start_timer", args: ["duration": 60]))
        XCTAssertNil(targets(extras: []).target(skill: "wifi", args: ["on": true]))
    }

    func testFramesAreCachedForFiveSeconds() {
        let reads = Counter()
        var clock = Date(timeIntervalSince1970: 0)
        let t = targets(reads: reads)
        t.now = { clock }
        _ = t.target(skill: "open_app", args: ["app": "Safari"])
        _ = t.target(skill: "open_folder", args: ["path": "~"])
        clock = clock.addingTimeInterval(4.9)
        _ = t.target(skill: "open_app", args: ["app": "Zen"])
        XCTAssertEqual(reads.n, 1)
        clock = clock.addingTimeInterval(0.2)
        _ = t.target(skill: "open_app", args: ["app": "Zen"])
        XCTAssertEqual(reads.n, 2)
    }

    func testRPCSkillFliesGhostWithinLead() {
        final class GhostSpy: HandsDelegate {
            var frames: [CGRect?] = []
            var labels: [String?] = []
            func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval {
                frames.append(frame); labels.append(label)
                return 1.0                                     // a slow flight must not delay the skill > 120 ms
            }
            func handsDidAct(op: String, frame: CGRect?, ok: Bool) {}
        }
        let skills = Skills(catalog: try! Catalog.load(), scripts: VolumeSpy(), events: MockPoster(),
                            apps: MockApps(), hooks: .inert)
        let rpc = RPCHandler(skills: skills, skillTargets: targets(), warmUp: false)
        let spy = GhostSpy()
        rpc.delegate = spy
        let t0 = Date()
        let (ok, _, _) = rpc.handle(method: "skill", params: ["name": "set_volume", "args": ["level": 30]])
        XCTAssertTrue(ok)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.4)
        XCTAssertEqual(spy.frames.first??.minX, 1652)
        XCTAssertEqual(spy.labels.first ?? nil, "30%")
        // Skills without a natural target: no frame (ghost stays put, no wait).
        let t1 = Date()
        _ = rpc.handle(method: "skill", params: ["name": "battery_status", "args": [:]])
        XCTAssertEqual(spy.frames.count, 2)
        XCTAssertNil(spy.frames.last ?? nil)
        XCTAssertLessThan(Date().timeIntervalSince(t1), 0.2)
    }
}

// MARK: - no_text_target: type_text

final class NoTextTargetTests: XCTestCase {
    private let textEdit = RunningAppInfo(pid: 77, name: "TextEdit", bundleId: "com.apple.TextEdit")

    private func skills(app: MockElement, poster: MockPoster,
                        info: RunningAppInfo? = nil) -> Skills {
        let apps = MockApps(frontmost: (info ?? textEdit).pid, running: [info ?? textEdit])
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster, apps: apps, hooks: .inert)
        s.axApp = { _ in app }
        return s
    }

    private func window(_ kids: [MockElement]) -> MockElement {
        el("AXWindow", "Untitled", x: 100, y: 100, w: 600, h: 400, kids)
    }

    func testTypesIntoAFocusedTextField() {
        let field = el("AXTextField", "To", x: 120, y: 120)
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = field
        app.singles[kAXFocusedWindowAttribute as String] = window([field])
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(poster.typed, ["hello"])
        XCTAssertEqual((r["result"] as? [String: Any])?["target"] as? String, "focused")
    }

    func testNoTextTargetWhenNothingTakesText() {
        let bold = el("AXCheckBox", "bold", x: 120, y: 110)
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = bold
        app.singles[kAXFocusedWindowAttribute as String] = window([bold])
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "no_text_target")
        let observed = r["observed"] as? String ?? ""
        XCTAssertTrue(observed.contains("TextEdit"), observed)
        XCTAssertTrue(observed.contains("window \"Untitled\""), observed)
        XCTAssertTrue(observed.contains("checkbox \"bold\""), observed)
        XCTAssertTrue(poster.typed.isEmpty)                       // never typed
    }

    func testNoWindowNoFocusIsNoTextTarget() {
        // The live E2E: TextEdit with no window / nothing focused.
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "hi"])
        XCTAssertEqual(r["error"] as? String, "no_text_target")
        XCTAssertEqual(r["observed"] as? String, "app \"TextEdit\" window none focused none")
        XCTAssertTrue(poster.typed.isEmpty)
    }

    func testWindowTextAreaFallbackFocusesItFirst() {
        // Focus on the window itself (clicked the chrome): the document's
        // text area takes the text, focused first.
        let area = el("AXTextArea", x: 110, y: 140, w: 560, h: 340)
        area.settable = ["AXFocused"]
        let small = el("AXTextArea", x: 110, y: 110, w: 100, h: 20)
        let win = window([el("AXScrollArea", x: 100, y: 130, w: 600, h: 360, [area]), small])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = win
        app.singles[kAXFocusedWindowAttribute as String] = win
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "notes"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["target"] as? String, "window_textarea")
        XCTAssertEqual(area.store["AXFocused"] as? Bool, true)    // the larger one
        XCTAssertEqual(poster.typed, ["notes"])
    }

    func testWebEditableAndSpreadsheetCellsAccept() {
        let group = el("AXGroup", x: 120, y: 120)
        group.singles["AXEditableAncestor"] = el("AXTextArea")   // contenteditable
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = group
        let poster = MockPoster()
        XCTAssertEqual(skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "a"])["ok"] as? Bool, true)

        let table = el("AXTable", x: 100, y: 100, w: 500, h: 300)
        let numbers = RunningAppInfo(pid: 88, name: "Numbers", bundleId: "com.apple.iWork.Numbers")
        let app2 = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app2.singles[kAXFocusedUIElementAttribute as String] = table
        XCTAssertEqual(skills(app: app2, poster: poster, info: numbers)
            .execute(name: "type_text", args: ["text": "42"])["ok"] as? Bool, true)
        // A table elsewhere (Finder list) is not a text target.
        let finder = RunningAppInfo(pid: 89, name: "Finder", bundleId: "com.apple.finder")
        XCTAssertEqual(skills(app: app2, poster: poster, info: finder)
            .execute(name: "type_text", args: ["text": "42"])["error"] as? String, "no_text_target")
        XCTAssertEqual(poster.typed, ["a", "42"])
    }
}

// MARK: - keystroke apps (Calculator)

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

// MARK: - blind windows: keystroke fallback

final class BlindTypingTests: XCTestCase {
    private func fakeApp(window: ClockAXFakeElement) -> ClockAXFakeElement {
        let app = ClockAXFakeElement("AXApplication")
        app.singles[kAXFocusedWindowAttribute as String] = window
        return app
    }

    private func chromeWindow() -> ClockAXFakeElement {
        ClockAXFakeElement("AXWindow", "Spotify", children: [
            ClockAXFakeElement("AXButton", "Close"),
            ClockAXFakeElement("AXButton", "Minimize"),
            ClockAXFakeElement("AXButton", "this button also has an action to zoom the window"),
        ])
    }

    func testBlindTreeIsChromeOnly() {
        XCTAssertTrue(TextTarget.blindTree(chromeWindow()))
    }

    func testBlindTreeEmptyWindowIsBlind() {
        XCTAssertTrue(TextTarget.blindTree(
            ClockAXFakeElement("AXWindow", "Empty", children: [])))
    }

    func testBlindTreeRejectsContent() {
        let win = ClockAXFakeElement("AXWindow", "Notes", children: [
            ClockAXFakeElement("AXButton", "Close"),
            ClockAXFakeElement("AXTextArea", "Note body"),
        ])
        XCTAssertFalse(TextTarget.blindTree(win))
    }

    func testCheckFallsBackToKeystrokeOnBlindWindow() {
        // no focused element, no text area, blind tree -> keystroke_app
        let app = fakeApp(window: chromeWindow())
        let chk = TextTarget.check(app: app, appName: "Spotify",
                                   bundleId: "com.spotify.client",
                                   windowFallback: false)
        XCTAssertTrue(chk.ok)
        XCTAssertEqual(chk.via, TextTarget.keystrokeVia)
    }

    func testCheckNeverKeystrokesIntoMuselet() {
        let app = fakeApp(window: chromeWindow())
        let chk = TextTarget.check(app: app, appName: "Muselet",
                                   bundleId: "com.muselet.app",
                                   windowFallback: false)
        XCTAssertFalse(chk.ok)
    }

    func testCheckNormalTreeStillNoTextTarget() {
        let win = ClockAXFakeElement("AXWindow", "Notes", children: [
            ClockAXFakeElement("AXGroup", children: [
                ClockAXFakeElement("AXStaticText", "Hello"),
            ]),
        ])
        let app = fakeApp(window: win)
        let chk = TextTarget.check(app: app, appName: "Notes",
                                   bundleId: "com.apple.Notes",
                                   windowFallback: false)
        XCTAssertFalse(chk.ok)
        XCTAssertNil(chk.via)
    }
}

// MARK: - skill AppleScripts: handlers compiled once

final class MockCompiled: CompiledAppleScript {
    let source: String
    var executes = 0
    var calls: [(String, [Any])] = []
    init(_ source: String) { self.source = source }
    func execute() throws -> String { executes += 1; return "ok" }
    func callHandler(_ name: String, args: [Any]) throws -> String {
        calls.append((name, args))
        return name == "set_level" ? "\(args.first ?? 0),false" : "ok"
    }
}

final class MockCompiler {
    var compiled: [String: MockCompiled] = [:]
    var compiles: [String] = []
    func compile(_ s: String) throws -> CompiledAppleScript {
        compiles.append(s)
        let c = MockCompiled(s)
        compiled[s] = c
        return c
    }
}

final class AppleScriptHandlerTests: XCTestCase {
    func testHandlerCompiledOnceAcrossDifferentArgs() throws {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        _ = try r.call(SkillScripts.notes, "new_note", ["Groceries", "<h1>Groceries</h1>"])
        _ = try r.call(SkillScripts.notes, "new_note", ["Ideas", "<h1>Ideas</h1>"])
        XCTAssertEqual(mc.compiles, [SkillScripts.notes.source])        // ONE compile
        XCTAssertEqual(r.compileCount, 1)
        let calls = mc.compiled[SkillScripts.notes.source]!.calls
        XCTAssertEqual(calls.map(\.0), ["new_note", "new_note"])
        XCTAssertEqual(calls.map { $0.1.first as? String }, ["Groceries", "Ideas"])
    }

    func testWarmUpCompilesEverySkillScriptAndRunsNothing() {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        r.warmUp()
        let expected = SkillScripts.all.map(\.source) + SkillScripts.fixedSources
        XCTAssertEqual(mc.compiles, expected)
        XCTAssertTrue(mc.compiled.values.allSatisfy { $0.executes == 0 && $0.calls.isEmpty })
        for s in expected { XCTAssertTrue(r.isCompiled(s)) }
        // Real calls afterwards compile nothing new.
        _ = try? r.call(SkillScripts.volume, "set_level", [30])
        _ = try? r.run("output volume of (get volume settings)")
        XCTAssertEqual(mc.compiles.count, expected.count)
    }

    func testAdHocScriptsAreCachedBySourceInAnLRU() throws {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        _ = try r.run("return 1")
        _ = try r.run("return 1")
        XCTAssertEqual(mc.compiles, ["return 1"])
        for i in 0..<70 { _ = try r.run("return \(i + 2)") }        // evicts "return 1"
        _ = try r.run("return 1")
        XCTAssertEqual(mc.compiles.filter { $0 == "return 1" }.count, 2)
        // pinned skill scripts survive any number of ad-hoc scripts
        _ = try r.call(SkillScripts.volume, "set_level", [10])
        for i in 0..<70 { _ = try r.run("return \(i + 200)") }
        _ = try r.call(SkillScripts.volume, "set_level", [20])
        XCTAssertEqual(mc.compiles.filter { $0 == SkillScripts.volume.source }.count, 1)
    }

    func testSkillsUseHandlersNotSplicedSource() {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        let s = Skills(catalog: catalog(), scripts: r, events: MockPoster(), apps: MockApps(), hooks: .inert)
        let a = s.execute(name: "new_note", args: ["title": "Q\"4\" <plan>", "body": "line 1\nline 2 & more"])
        let b = s.execute(name: "new_note", args: ["body": "buy oat milk"])
        XCTAssertEqual(a["ok"] as? Bool, true, "\(a)")
        XCTAssertEqual(b["ok"] as? Bool, true, "\(b)")
        XCTAssertEqual(mc.compiles, [SkillScripts.notes.source])
        let calls = mc.compiled[SkillScripts.notes.source]!.calls
        XCTAssertEqual(calls[0].1.first as? String, "Q\"4\" <plan>")        // verbatim name
        XCTAssertEqual(calls[0].1.last as? String,
                       "<h1>Q\"4\" &lt;plan&gt;</h1><br>line 1<br>line 2 &amp; more")
        let v = s.execute(name: "set_volume", args: ["level": 30])
        XCTAssertEqual((v["result"] as? [String: Any])?["level"] as? Int, 30)
        XCTAssertEqual(mc.compiles.count, 2)                              // + volume script
    }

    func testRealHandlerCallPassesParameters() throws {
        // Real NSAppleScript, no app targeted: verifies the subroutine-event
        // encoding (name, positional args, types) end to end.
        let script = SkillScript(name: "math", source: """
            on add_two(a, b)
                return (a + b) as text
            end add_two
            on greet(who, loud)
                if loud then return "HI " & who
                return "hi " & who
            end greet
            """)
        let r = AppleScriptRunner()
        XCTAssertEqual(try r.call(script, "add_two", [2, 3]), "5")
        XCTAssertEqual(try r.call(script, "add_two", [40, 2]), "42")
        XCTAssertEqual(try r.call(script, "greet", ["Ada \"Lovelace\"", true]), "HI Ada \"Lovelace\"")
        XCTAssertEqual(try r.call(script, "GREET", ["x", false]), "hi x")   // case-insensitive
        XCTAssertEqual(r.compileCount, 1)
        XCTAssertThrowsError(try r.call(script, "missing_handler", []))
    }

    func testAllSkillScriptsCompile() throws {
        // Compile only (nothing runs, no app is launched).
        let r = AppleScriptRunner()
        let res = r.precompile(SkillScripts.all.map(\.source) + SkillScripts.fixedSources)
        for x in res { XCTAssertTrue(x.ok, "failed to compile:\n\(x.source)") }
    }
}

// MARK: - Automation status mapping

final class AutomationTests: XCTestCase {
    func testStatusMapping() {
        XCTAssertEqual(Automation.status(from: 0), .granted)
        XCTAssertEqual(Automation.status(from: -1743), .denied)
        XCTAssertEqual(Automation.status(from: -1744), .notDetermined)
        XCTAssertEqual(Automation.status(from: -600), .notRunning)
        XCTAssertEqual(Automation.status(from: -50), .unknown(-50))
    }

    func testTargetsAndSummary() {
        func target(_ name: String) -> Automation.Target {
            Automation.targets.first { $0.name == name }!
        }
        let line = Automation.summaryLine([(target("Notes"), .granted),
                                           (target("System Events"), .notRunning)])
        XCTAssertEqual(line, "Notes=granted SystemEvents=not_running")
        XCTAssertTrue(target("Finder").persistent)               // Finder is never quit
        XCTAssertFalse(target("Numbers").persistent)             // Numbers launched hidden is quit
    }
}

// MARK: - Control Center via MenuBarAgent

final class ControlCenterLookupTests: XCTestCase {
    /// macOS 27 MenuBarAgent: AXExtrasMenuBar > AXHostingView groups > AXMenuExtra.
    private func menuBarAgent(withBluetooth: Bool) -> MockElement {
        func extra(_ ident: String, _ desc: String, x: CGFloat) -> MockElement {
            let e = el("AXMenuBarItem", x: x, y: 8, w: 26, h: 22)
            e.attrs.subrole = "AXMenuExtra"
            e.attrs.desc = desc
            e.singles["AXIdentifier"] = ident
            let host = el("AXGroup", x: x, y: 0, w: 26, h: 39, [e])
            host.attrs.subrole = "AXHostingView"
            return host
        }
        var hosts = [extra("com.apple.menuextra.wifi", "Wi‑Fi, connected", x: 1614),
                     extra("com.apple.menuextra.controlcenter", "Control Center", x: 1652)]
        if withBluetooth { hosts.insert(extra("com.apple.menuextra.bluetooth", "Bluetooth", x: 1580), at: 0) }
        let bar = el("AXMenuBar", x: 1420, y: 0, w: 359, h: 39, hosts)
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles["AXExtrasMenuBar"] = bar
        return app
    }

    func testExtrasInsideHostingGroups() {
        let items = ControlCenter.extras(in: menuBarAgent(withBluetooth: false))
        XCTAssertEqual(items.map(\.ident), ["com.apple.menuextra.wifi", "com.apple.menuextra.controlcenter"])
        XCTAssertEqual(items.last?.frame, CGRect(x: 1652, y: 8, width: 26, height: 22))
        XCTAssertTrue(ControlCenter.extras(in: el("AXApplication", x: 0, y: 0, w: 0, h: 0)).isEmpty)
    }

    func testOpenerPrefersTheModuleExtraElseControlCenter() {
        let own = ControlCenter.pickOpener(ControlCenter.extras(in: menuBarAgent(withBluetooth: true)),
                                           named: "Bluetooth")
        XCTAssertEqual(own?.ident, "com.apple.menuextra.bluetooth")
        let cc = ControlCenter.pickOpener(ControlCenter.extras(in: menuBarAgent(withBluetooth: false)),
                                          named: "Bluetooth")
        XCTAssertEqual(cc?.ident, "com.apple.menuextra.controlcenter")
        XCTAssertNil(ControlCenter.pickOpener([], named: "Bluetooth"))
    }

    func testFindToggleInPanelWindows() {
        let tile = el("AXCheckBox", x: 1500, y: 60, w: 150, h: 60)
        tile.attrs.desc = "Bluetooth"
        tile.attrs.value = NSNumber(value: 1)
        let wifi = el("AXCheckBox", x: 1340, y: 60, w: 150, h: 60)
        wifi.attrs.desc = "Wi‑Fi"
        let panel = el("AXWindow", x: 1330, y: 40, w: 340, h: 500,
                       [el("AXGroup", x: 1330, y: 40, w: 340, h: 500, [wifi, tile])])
        let found = ControlCenter.findToggle(in: [panel], named: "Bluetooth")
        XCTAssertTrue(found === tile)
        XCTAssertEqual(ControlCenter.value(of: tile), true)
        XCTAssertNil(ControlCenter.findToggle(in: [panel], named: "AirDrop"))
    }
}
