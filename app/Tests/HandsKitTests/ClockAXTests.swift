import ApplicationServices
import CoreFoundation
import Foundation
import XCTest
@testable import HandsKit

// Timers: start_timer through Clock AX (fake Clock app tree) or Muselet's
// own timer, the timers / timers_cancel / timer_backend RPCs and the
// cross-process snapshot. Hermetic: fake AX elements, mock hooks and
// launcher; snapshots only in temp dirs.

// MARK: - Clock AX fake app

private enum StartEffect {
    case running
    case none
    case removeStart
    case pauseAndCancel
}

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
    let launcher: MockLauncher
    let apps: MockApps
    let skills: Skills
    let tab: ClockAXFakeElement
    let start: ClockAXFakeElement
    let pickerCancel: ClockAXFakeElement
    let wheels: [ClockAXFakeElement]
    let label: ClockAXFakeElement

    init(axReady: Bool = true, selected: Bool = true, settableWheels: Bool = false,
         stuckWheel: Int? = nil, startEffect: StartEffect = .running, withPicker: Bool = true,
         initialRunning: Bool = false) {
        let window = ClockAXFakeElement("AXWindow", "Clock", x: 0, y: 0, w: 400, h: 600)
        let app = ClockAXFakeElement("AXApplication")
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
        // Strong capture: nothing else retains the group until Start adds it.
        start.onAction = { [weak window, weak start, weak pickerCancel, runningGroup] action in
            guard action == (kAXPressAction as String) else { return false }
            switch startEffect {
            case .running:
                guard let window else { return false }
                window.attrs.children.append(runningGroup)
            case .none:
                break
            case .removeStart:
                if let window, let start {
                    window.attrs.children.removeAll { $0 === start }
                }
            case .pauseAndCancel:
                start?.attrs.title = "Pause"
                pickerCancel?.attrs.enabled = true
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
        hooks.clockAXReady = { axReady }
        self.window = window
        self.app = app
        self.launcher = launcher
        self.apps = apps
        self.tab = tab
        self.start = start
        self.pickerCancel = pickerCancel
        self.wheels = wheels
        self.label = label
        let skills = Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(),
                            apps: apps, hooks: hooks, launcher: launcher)
        self.skills = skills
        skills.axApp = { [weak app] _ in app ?? ClockAXFakeElement("AXApplication") }
        skills.clockAXTimeout = 0.02
        skills.clockAXSettle = 0.02
        skills.clockAXPoll = 0.001
        skills.clockAXStepWait = 0.01
        skills.clockAXVerify = 0.02
    }
}

// MARK: - Clock AX

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
        XCTAssertFalse((value["clock_ax_steps"] as? [String] ?? []).isEmpty)
        XCTAssertEqual(f.label.attrs.value as? String, "Tea")
        XCTAssertEqual(f.skills.timerList().first?["backend"] as? String, "clock_ax")
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

    func testWheelFailureFallsBackToMuseletSilently() {
        let f = ClockAXFixture(stuckWheel: 2)
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(result["ok"] as? Bool, true, "\(result)")
        XCTAssertEqual(value["backend"] as? String, "muselet")
        XCTAssertEqual(value["fallback_reason"] as? String, "wheel_m_stuck")
        XCTAssertEqual(value["clock_ax_reason"] as? String, "wheel_m_stuck")
        XCTAssertEqual(value["verified"] as? Bool, false)
        XCTAssertEqual(f.skills.timerList().first?["backend"] as? String, "muselet")
    }

    func testUnverifiedStartRetriesOnceThenFallsBackToMuselet() {
        let f = ClockAXFixture(startEffect: .none)
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(value["backend"] as? String, "muselet")
        XCTAssertEqual(value["verified"] as? Bool, false)
        XCTAssertEqual(value["fallback_reason"] as? String, "start_unverified")
        XCTAssertEqual(value["clock_ax_reason"] as? String, "start_unverified")
        XCTAssertEqual(f.start.actions, [kAXPressAction as String, kAXPressAction as String])
        XCTAssertTrue((value["clock_ax_steps"] as? [String] ?? []).contains("start retry"))
    }

    func testStartGoneWithoutCancelEnabledIsNotVerified() {
        let f = ClockAXFixture(startEffect: .removeStart)
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(value["backend"] as? String, "muselet")
        XCTAssertEqual(value["clock_ax_reason"] as? String, "start_unverified")
        XCTAssertEqual(f.start.actions, [kAXPressAction as String])
    }

    func testPauseAndEnabledCancelVerify() {
        let f = ClockAXFixture(startEffect: .pauseAndCancel)
        defer { _ = f.skills.timers.cancel(id: nil) }
        let result = f.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(value["backend"] as? String, "clock_ax")
        XCTAssertEqual(value["verified"] as? Bool, true)
        XCTAssertEqual(value["verify_signal"] as? String, "pause_cancel")
    }

    func testUnavailableAXDoesNotLaunchClock() {
        let unavailable = ClockAXFixture(axReady: false)
        var launches = 0
        unavailable.launcher.onOpenApp = { _ in launches += 1 }
        defer { _ = unavailable.skills.timers.cancel(id: nil) }
        let result = unavailable.skills.execute(name: "start_timer", args: ["duration": 90])
        let value = result["result"] as? [String: Any] ?? [:]
        XCTAssertEqual(value["backend"] as? String, "muselet")
        XCTAssertEqual(value["fallback_reason"] as? String, "clock_ax_unavailable")
        XCTAssertEqual(value["clock_ax_reason"] as? String, "clock_ax_unavailable")
        XCTAssertEqual(value["verified"] as? Bool, false)
        XCTAssertNotNil(value["clock_ax_steps"] as? [String])
        XCTAssertEqual(unavailable.skills.timerList().first?["backend"] as? String, "muselet")
        XCTAssertEqual(launches, 0)
    }

    func testClockAXCancelAndUnsupportedReason() {
        let f = ClockAXFixture(initialRunning: true)
        let record = f.skills.timers.start(seconds: 90, label: "Tea", backend: "clock_ax") { _ in }
        let cancelled = f.skills.cancelTimersDetailed(id: record.id)
        XCTAssertEqual(cancelled.cancelled.count, 1)
        XCTAssertEqual(f.skills.pendingTimers, 0)

        let noMatch = ClockAXFixture()
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
        XCTAssertEqual(Set(backend.keys), ["clock_ax_ready", "backend"])
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

// MARK: - timers RPCs

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
        XCTAssertTrue(list[0]["label"] is NSNull)                // always present; null without a label
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
        // Per-timer cancel (clock backend handling) reports the true
        // intermediate list: [1,2] starts, then 1 then 0 pending.
        lock.lock(); XCTAssertEqual(seen, [1, 2, 1, 0]); lock.unlock()
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

// MARK: - start_timer without Clock AX

/// Inert hooks (Accessibility not trusted): Muselet's own timer, silently
/// (docs/CLOCK_TIMERS.md).
final class TimerFallbackTests: XCTestCase {
    private func skills() -> Skills {
        Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(), hooks: .inert)
    }

    private func result(_ r: [String: Any]) -> [String: Any] { r["result"] as? [String: Any] ?? [:] }

    func testTimerBackendRPCHasNoShortcutFields() {
        let rpc = RPCHandler(skills: skills(), warmUp: false)
        let (ok, r, _) = rpc.handle(method: "timer_backend", params: ["refresh": true])
        XCTAssertTrue(ok)
        let d = r as? [String: Any] ?? [:]
        XCTAssertEqual(Set(d.keys), ["clock_ax_ready", "backend"])
        XCTAssertEqual(d["backend"] as? String, "muselet")
        XCTAssertEqual(d["clock_ax_ready"] as? Bool, false)
    }

    func testTimersReportMuseletTimer() {
        let s = skills()
        defer { _ = s.timers.cancel(id: nil) }
        let id = result(s.execute(name: "start_timer", args: ["duration": 60]))["timer_id"] as? String ?? ""
        let report = s.timersReport()
        XCTAssertNil(report["clock"])
        XCTAssertNil(report["clock_ax"])
        XCTAssertEqual((report["timers"] as? [[String: Any]])?.first?["id"] as? String, id)
    }

    func testSnapshotRoundTripKeepsBackend() {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("clock-snap-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let now = Date()
        let info = TimerRegistry.Info(id: "timer-c", label: "Tea", total: 600, startedAt: now,
                                      firesAt: now.addingTimeInterval(600), backend: "clock_ax")
        TimerSnapshot.write([info], pid: 111, process: "Muselet", directory: dir, gc: false)
        TimerSnapshot.flush()
        let got = TimerSnapshot.read(directory: dir, now: now, isAlive: { $0 == 111 })
        XCTAssertEqual(got.first?["backend"] as? String, "clock_ax")
        XCTAssertEqual(got.first?["label"] as? String, "Tea")
    }
}
