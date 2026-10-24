import ApplicationServices
import CoreFoundation
import Foundation
import XCTest
@testable import HandsKit

private func clockCatalog() -> [String: SkillDef] { try! Catalog.load() }

final class ClockAXFakeElement: Element {
    var attrs = ElAttrs()
    var singles: [String: Any] = [:]
    var settable: Set<String> = []
    var offeredActions: [String] = []
    var actions: [String] = []
    var onAction: ((String) -> Bool)?
    var onSet: ((String, Any?) -> Bool)?

    init(_ role: String, _ title: String? = nil, x: CGFloat = 0, y: CGFloat = 0,
         w: CGFloat = 80, h: CGFloat = 24, value: Any? = nil,
         enabled: Bool = true, children: [ClockAXFakeElement] = []) {
        attrs.role = role
        attrs.title = title
        attrs.position = CGPoint(x: x, y: y)
        attrs.size = CGSize(width: w, height: h)
        attrs.value = value
        attrs.enabled = enabled
        attrs.children = children
    }

    func copyAttrs() -> ElAttrs { attrs }
    func copySingleAttr(_ name: String) -> Any? { singles[name] }
    func isSettable(_ name: String) -> Bool { settable.contains(name) }
    func actionNames() -> [String] { offeredActions }
    func performAction(_ name: String) -> Bool {
        actions.append(name)
        return onAction?(name) ?? true
    }
    func setAttr(_ name: String, _ value: Any?) -> Bool {
        guard settable.contains(name) else { return false }
        if let onSet, !onSet(name, value) { return false }
        if name == (kAXValueAttribute as String) { attrs.value = value }
        if name == (kAXSelectedAttribute as String) { attrs.selected = value as? Bool }
        return true
    }
}

private final class ClockAXFixture {
    let window: ClockAXFakeElement
    let app: ClockAXFakeElement
    let shortcuts: FakeShortcuts
    let launcher: MockLauncher
    let apps: MockApps
    let skills: Skills
    let tab: ClockAXFakeElement
    let start: ClockAXFakeElement
    let pickerCancel: ClockAXFakeElement
    let wheels: [ClockAXFakeElement]
    let label: ClockAXFakeElement

    init(shortcuts: [String] = [ClockShortcut.start, ClockShortcut.cancel],
         axReady: Bool = true, selected: Bool = true, settableWheels: Bool = false,
         stuckWheel: Int? = nil, addRunningOnStart: Bool = true, withPicker: Bool = true,
         initialRunning: Bool = false) {
        let window = ClockAXFakeElement("AXWindow", "Clock", x: 0, y: 0, w: 400, h: 600)
        let app = ClockAXFakeElement("AXApplication")
        let shortcutsRunner = FakeShortcuts(installed: shortcuts)
        let launcher = MockLauncher()
        launcher.apps["clock"] = (500, false)
        let apps = MockApps(frontmost: 500, running: [
            RunningAppInfo(pid: 500, name: "Clock", bundleId: ClockAX.bundleId),
        ])
        app.singles[kAXFocusedWindowAttribute as String] = window
        window.singles[kAXTitleAttribute as String] = "Clock"

        let tab = ClockAXFakeElement("AXRadioButton", "Timers", x: 15, y: 20,
                                     value: NSNumber(value: selected))
        tab.attrs.selected = selected
        tab.offeredActions = [kAXPressAction as String]
        tab.onAction = { [weak tab] action in
            guard action == (kAXPressAction as String) else { return false }
            tab?.attrs.value = NSNumber(value: true)
            tab?.attrs.selected = true
            return true
        }
        let label = ClockAXFakeElement("AXTextField", "Timer", x: 20, y: 80, value: "")
        label.settable = [kAXValueAttribute as String, kAXFocusedAttribute as String]
        let start = ClockAXFakeElement("AXButton", "Start", x: 240, y: 80, enabled: true)
        start.offeredActions = [kAXPressAction as String]
        let pickerCancel = ClockAXFakeElement("AXButton", "Cancel", x: 170, y: 80, enabled: false)
        pickerCancel.offeredActions = [kAXPressAction as String]
        let wheelValues = [0, 0, 0]
        let wheels = [
            ClockAXFakeElement("AXSlider", x: 250, y: 200, value: NSNumber(value: wheelValues[2])),
            ClockAXFakeElement("AXSlider", x: 100, y: 200, value: NSNumber(value: wheelValues[0])),
            ClockAXFakeElement("AXSlider", x: 175, y: 200, value: NSNumber(value: wheelValues[1])),
        ]
        for (i, wheel) in wheels.enumerated() {
            wheel.offeredActions = [kAXIncrementAction as String, kAXDecrementAction as String]
            if settableWheels { wheel.settable.insert(kAXValueAttribute as String) }
            wheel.onAction = { [weak wheel] action in
                guard i != stuckWheel, let wheel else { return i != stuckWheel }
                let current = ClockAX.wheelValue(wheel.attrs.value) ?? 0
                if action == (kAXIncrementAction as String) { wheel.attrs.value = NSNumber(value: current + 1) }
                if action == (kAXDecrementAction as String) { wheel.attrs.value = NSNumber(value: max(0, current - 1)) }
                return true
            }
        }
        let offscreen = ClockAXFakeElement("AXSlider", x: 90, y: 500, value: NSNumber(value: 0))

        let runningGroup = ClockAXFakeElement("AXGroup", x: 20, y: 300, w: 300, h: 100)
        let countdown = ClockAXFakeElement("AXStaticText", x: 30, y: 310, value: "1:30")
        let timerLabel = ClockAXFakeElement("AXStaticText", x: 30, y: 340, value: "Tea")
        let runningCancel = ClockAXFakeElement("AXButton", "Cancel", x: 40, y: 370)
        let pause = ClockAXFakeElement("AXButton", "Pause", x: 110, y: 370)
        runningGroup.attrs.children = [countdown, timerLabel, runningCancel, pause]
        runningCancel.onAction = { [weak window, weak runningGroup] action in
            guard action == (kAXPressAction as String), let window, let runningGroup else { return false }
            window.attrs.children.removeAll { $0 === runningGroup }
            return true
        }
        start.onAction = { [weak window, weak runningGroup] action in
            guard action == (kAXPressAction as String) else { return false }
            if addRunningOnStart, let window, let runningGroup {
                window.attrs.children.append(runningGroup)
            }
            return true
        }
        var controls: [ClockAXFakeElement] = [tab]
        if withPicker {
            controls += [label, pickerCancel, start] + wheels + [offscreen]
        }
        if initialRunning { controls.append(runningGroup) }
        window.attrs.children = controls

        var hooks = SystemHooks.inert
        hooks.shortcuts = shortcutsRunner
        hooks.clockAXReady = { axReady }
        self.window = window
        self.app = app
        self.shortcuts = shortcutsRunner
        self.launcher = launcher
        self.apps = apps
        self.tab = tab
        self.start = start
        self.pickerCancel = pickerCancel
        self.wheels = wheels
        self.label = label
        let skills = Skills(catalog: clockCatalog(), scripts: SpyRunner(), events: MockPoster(),
                            apps: apps, hooks: hooks, launcher: launcher)
        self.skills = skills
        skills.axApp = { [weak app] _ in app ?? ClockAXFakeElement("AXApplication") }
        skills.clockAXTimeout = 0.02
        skills.clockAXSettle = 0.02
        skills.clockAXPoll = 0.001
        skills.clockAXStepWait = 0.001
    }
}

final class ClockAXPureTests: XCTestCase {
    func testWheelValueDurationAndCountdownParsing() {
        XCTAssertEqual(ClockAX.wheelValue(NSNumber(value: 10.4)), 10)
        XCTAssertEqual(ClockAX.wheelValue("10 minutes"), 10)
        XCTAssertNil(ClockAX.wheelValue(NSNumber(value: true)))
        XCTAssertEqual(ClockAX.hms(90), [0, 1, 30])
        XCTAssertNil(ClockAX.hms(86_400))
        XCTAssertEqual(ClockAX.countdown(" 9:58 "), 598)
        XCTAssertEqual(ClockAX.countdown("1:02:03"), 3723)
        XCTAssertNil(ClockAX.countdown("1:2"))
        XCTAssertNil(ClockAX.countdown("99:99:99:99"))
    }

    func testParserGroupsThreeWheelsAndFindsRunningControls() {
        let tab = ClockAXFakeElement("AXRadioButton", "Timers", value: NSNumber(value: true))
        let field = ClockAXFakeElement("AXTextField", "Timer")
        let start = ClockAXFakeElement("AXButton", "Start", x: 200, y: 100)
        let cancel = ClockAXFakeElement("AXButton", "Cancel", x: 180, y: 100)
        let wheels = [
            ClockAXFakeElement("AXSlider", x: 300, y: 120),
            ClockAXFakeElement("AXSlider", x: 100, y: 121),
            ClockAXFakeElement("AXSlider", x: 200, y: 119),
            ClockAXFakeElement("AXSlider", x: 400, y: 500),
        ]
        let group = ClockAXFakeElement("AXGroup")
        group.attrs.children = [
            ClockAXFakeElement("AXStaticText", value: "1:20"),
            ClockAXFakeElement("AXStaticText", value: "Tea"),
            ClockAXFakeElement("AXButton", "Stop"),
            ClockAXFakeElement("AXButton", "Pause"),
        ]
        let root = ClockAXFakeElement("AXWindow", children: [tab, field, start, cancel] + wheels + [group])
        let nodes = ClockAX.collect(root).nodes
        let parsed = ClockAX.parse(nodes)
        XCTAssertTrue(parsed.tabSelected)
        XCTAssertEqual(parsed.wheels.count, 3)
        XCTAssertEqual(parsed.wheels.map { nodes[$0].a.frame.minX }, [100, 200, 300])
        XCTAssertEqual(nodes[parsed.labelField ?? 0].a.role, "AXTextField")
        XCTAssertEqual(nodes[parsed.start ?? 0].a.title, "Start")
        XCTAssertEqual(nodes[parsed.cancel ?? 0].a.title, "Cancel")
        XCTAssertEqual(parsed.running.count, 1)
        XCTAssertEqual(parsed.running.first?.leftS, 80)
        XCTAssertEqual(parsed.running.first?.label, "Tea")
        XCTAssertNotNil(parsed.running.first?.cancelButton)
        XCTAssertNotNil(parsed.running.first?.pauseButton)
    }

    func testMatchingUsesLabelFirstAndConsumesRunningTimersOnce() {
        let running = [
            ClockAX.Running(node: 1, leftS: 100, label: "Tea", cancelButton: nil, pauseButton: nil),
            ClockAX.Running(node: 2, leftS: 102, label: "Water", cancelButton: nil, pauseButton: nil),
        ]
        let records: [[String: Any]] = [
            ["id": "a", "backend": "clock_ax", "label": "tea", "left_s": 200],
            ["id": "b", "backend": "clock_ax", "left_s": 101],
            ["id": "c", "backend": "muselet", "left_s": 100],
        ]
        let matched = ClockAX.match(records: records, running: running, now: Date())
        XCTAssertEqual(matched[0]["clock_seen"] as? Bool, true)
        XCTAssertEqual(matched[0]["clock_left_s"] as? Double, 100)
        XCTAssertEqual(matched[1]["clock_seen"] as? Bool, true)
        XCTAssertNil(matched[2]["clock_seen"])
    }

    func testBackendSelection() {
        XCTAssertEqual(ClockAX.backend(enabled: false, axReady: true, shortcutReady: true), "muselet")
        XCTAssertEqual(ClockAX.backend(enabled: true, axReady: true, shortcutReady: true), "clock_ax")
        XCTAssertEqual(ClockAX.backend(enabled: true, axReady: false, shortcutReady: true), "clock")
        XCTAssertEqual(ClockAX.backend(enabled: true, axReady: false, shortcutReady: false), "muselet")
    }
}

final class ClockAXDriverTests: XCTestCase {
    func testStartUsesSteppingThenReportsVerifiedClockAXRecord() {
        let f = ClockAXFixture()
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90, "label": "Tea"])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(result["ok"] as? Bool, true, "\(result)")
        XCTAssertEqual(value["backend"] as? String, "clock_ax")
        XCTAssertEqual(value["verified"] as? Bool, true)
        XCTAssertEqual(value["verify_signal"] as? String, "running_added")
        XCTAssertEqual(value["wheel_method"] as? String, "step")
        XCTAssertEqual(value["label_set"] as? Bool, true)
        XCTAssertEqual(f.label.attrs.value as? String, "Tea")
        XCTAssertEqual(f.skills.timerList().first?["backend"] as? String, "clock_ax")
        XCTAssertTrue(f.shortcuts.runs.isEmpty)
        XCTAssertEqual(f.apps.frontmostPid(), 500)
    }

    func testStartUsesAXValueWhenWheelsAreSettable() {
        let f = ClockAXFixture(settableWheels: true)
        f.wheels.forEach { $0.attrs.value = NSNumber(value: 2) }
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(value["backend"] as? String, "clock_ax")
        XCTAssertEqual(value["wheel_method"] as? String, "set")
    }

    func testUnselectedTabIsPressedBeforePickerUse() {
        let f = ClockAXFixture(selected: false)
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        XCTAssertEqual((result["result"] as? [String: Any])?["backend"] as? String, "clock_ax")
        XCTAssertEqual(f.tab.actions, [kAXPressAction as String])
    }

    func testWheelFailureFallsBackToShortcutThenMuselet() {
        let withShortcut = ClockAXFixture(stuckWheel: 2)
        defer { _ = withShortcut.skills.timers.cancel(id: nil) }
        let first = withShortcut.skills.execute(name: "start_timer", args: ["duration": 90])
        let firstResult = first["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(firstResult["backend"] as? String, "clock")
        XCTAssertEqual(firstResult["clock_ax_reason"] as? String, "wheel_m_stuck")
        XCTAssertEqual(withShortcut.shortcuts.runs.map(\.name), [ClockShortcut.start])

        let noShortcut = ClockAXFixture(shortcuts: [], stuckWheel: 2)
        defer { _ = noShortcut.skills.timers.cancel(id: nil) }
        let second = noShortcut.skills.execute(name: "start_timer", args: ["duration": 90])
        let secondResult = second["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(secondResult["backend"] as? String, "muselet")
        XCTAssertEqual(secondResult["fallback_reason"] as? String, "shortcut_missing")
        XCTAssertEqual(secondResult["clock_ax_reason"] as? String, "wheel_m_stuck")
    }

    func testNoFallbackAfterStartPressEvenWhenUnverified() {
        let f = ClockAXFixture(addRunningOnStart: false)
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(value["backend"] as? String, "clock_ax")
        XCTAssertEqual(value["verified"] as? Bool, false)
        XCTAssertNil(value["clock_ax_reason"])
        XCTAssertEqual(f.start.actions, [kAXPressAction as String])
        XCTAssertTrue(f.shortcuts.runs.isEmpty)
    }

    func testReadinessAndToggleOffDoNotLaunchClock() {
        let unavailable = ClockAXFixture(axReady: false)
        var launches = 0
        unavailable.launcher.onOpenApp = { _ in launches += 1 }
        defer { _ = unavailable.skills.timers.cancel(id: nil) }
        let result = unavailable.skills.execute(name: "start_timer", args: ["duration": 90])
        XCTAssertEqual((result["result"] as? [String: Any])?["clock_ax_reason"] as? String,
                       "clock_ax_unavailable")
        XCTAssertEqual(launches, 0)

        let disabled = ClockAXFixture()
        disabled.skills.clock.enabled = false
        disabled.launcher.onOpenApp = { _ in launches += 1 }
        defer { _ = disabled.skills.timers.cancel(id: nil) }
        let off = disabled.skills.execute(name: "start_timer", args: ["duration": 90])
        XCTAssertEqual((off["result"] as? [String: Any])?["fallback_reason"] as? String, "clock_off")
        XCTAssertEqual(launches, 0)
    }

    func testClockAXCancelAndUnsupportedReason() {
        let f = ClockAXFixture(shortcuts: [], initialRunning: true)
        let record = f.skills.timers.start(seconds: 90, label: "Tea", backend: "clock_ax") { _ in }
        let cancelled = f.skills.cancelTimersDetailed(id: record.id)
        XCTAssertEqual(cancelled.cancelled.count, 1)
        XCTAssertEqual(f.skills.pendingTimers, 0)

        let noMatch = ClockAXFixture(shortcuts: [])
        let pending = noMatch.skills.timers.start(seconds: 90, label: "Missing", backend: "clock_ax") { _ in }
        let rpc = RPCHandler(skills: noMatch.skills, warmUp: false)
        let (ok, response, error) = rpc.handle(method: "timers_cancel", params: ["id": pending.id])
        XCTAssertFalse(ok)
        XCTAssertTrue(error?.hasPrefix("unsupported:") == true)
        let data = response as? [String: Any] ?? [:]
        XCTAssertEqual((data["clock_ax_reasons"] as? [[String: Any]])?.first?["reason"] as? String,
                       "clock_timer_not_found")
        XCTAssertEqual(noMatch.skills.pendingTimers, 1)
        _ = noMatch.skills.timers.cancel(id: pending.id)
    }

    func testTimersReportAndTimerBackendRPCIncludeClockAX() {
        let f = ClockAXFixture()
        defer { _ = f.skills.timers.cancel(id: nil) }
        let info = f.skills.timers.start(seconds: 90, label: "Tea", backend: "clock_ax") { _ in }
        let windowGroup = ClockAXFakeElement("AXGroup", x: 20, y: 300)
        windowGroup.attrs.children = [
            ClockAXFakeElement("AXStaticText", value: "1:30"),
            ClockAXFakeElement("AXStaticText", value: "Tea"),
            ClockAXFakeElement("AXButton", "Cancel"),
            ClockAXFakeElement("AXButton", "Pause"),
        ]
        f.window.attrs.children.append(windowGroup)
        let report = f.skills.timersReport(now: info.startedAt)
        XCTAssertEqual((report["clock_ax"] as? [String: Any])?["status"] as? String, "read")
        XCTAssertEqual(((report["timers"] as? [[String: Any]])?.first)?["clock_seen"] as? Bool, true)

        let rpc = RPCHandler(skills: f.skills, warmUp: false)
        let backend = rpc.handle(method: "timer_backend", params: [:]).1 as? [String: Any] ?? [:]
        XCTAssertEqual(backend["clock_ax_ready"] as? Bool, true)
        XCTAssertEqual(backend["backend"] as? String, "clock_ax")
        f.skills.clock.enabled = false
        let disabled = rpc.handle(method: "timer_backend", params: [:]).1 as? [String: Any] ?? [:]
        XCTAssertEqual(disabled["backend"] as? String, "muselet")
    }
}
