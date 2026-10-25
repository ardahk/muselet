import AppKit
import ApplicationServices
import CoreFoundation
import Foundation

public enum ClockAX {
    public static let bundleId = "com.apple.clock"
    public static let appName = "Clock"

    public struct Node {
        public let el: Element
        public let a: ElAttrs
        public let parent: Int?
        public let depth: Int

        public var names: [String] {
            [a.title, a.desc, a.placeholder, a.help].compactMap {
                guard let value = $0?.trimmingCharacters(in: .whitespacesAndNewlines),
                      !value.isEmpty else { return nil }
                return value
            }
        }

        public var text: [String] {
            var values = names
            if let value = a.value as? String {
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty { values.append(trimmed) }
            }
            return values
        }
    }

    public struct Running {
        public var node: Int
        public var leftS: Double
        public var label: String?
        public var cancelButton: Int?
        public var pauseButton: Int?
    }

    public struct TimersUI {
        public var tab: Int?
        public var tabSelected = false
        public var wheels: [Int] = []
        public var labelField: Int?
        public var start: Int?
        public var cancel: Int?
        public var running: [Running] = []
    }

    public static func collect(_ root: Element, maxNodes: Int = 600, maxDepth: Int = 30)
        -> (nodes: [Node], truncated: Bool) {
        guard maxNodes > 0 else { return ([], true) }
        var nodes = [Node(el: root, a: root.copyAttrs(), parent: nil, depth: 0)]
        var index = 0
        var truncated = false
        while index < nodes.count {
            let parent = nodes[index]
            if parent.depth < maxDepth {
                for child in parent.a.children {
                    if nodes.count >= maxNodes {
                        truncated = true
                        break
                    }
                    nodes.append(Node(el: child, a: child.copyAttrs(),
                                      parent: index, depth: parent.depth + 1))
                }
            } else if !parent.a.children.isEmpty {
                truncated = true
            }
            if nodes.count >= maxNodes && index + 1 < nodes.count {
                truncated = true
            }
            index += 1
        }
        return (nodes, truncated)
    }

    public static func wheelValue(_ value: Any?) -> Int? {
        if let number = value as? NSNumber {
            guard CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
            let result = number.doubleValue.rounded()
            guard result.isFinite, result >= Double(Int.min), result <= Double(Int.max) else { return nil }
            return Int(result)
        }
        guard let string = value as? String,
              let range = string.range(of: #"\d+"#, options: .regularExpression) else { return nil }
        return Int(string[range])
    }

    public static func hms(_ seconds: Double) -> [Int]? {
        guard seconds.isFinite else { return nil }
        let rounded = seconds.rounded()
        guard rounded >= 1, rounded <= 86_399 else { return nil }
        let total = Int(rounded)
        return [total / 3600, (total % 3600) / 60, total % 60]
    }

    public static func countdown(_ source: String) -> Double? {
        let value = source.trimmingCharacters(in: .whitespacesAndNewlines)
        guard value.range(of: #"^\d{1,2}(:\d{2}){1,2}$"#, options: .regularExpression) != nil else {
            return nil
        }
        let parts = value.split(separator: ":").compactMap { Int($0) }
        guard parts.count == 2 || parts.count == 3 else { return nil }
        if parts.count == 2 { return Double(parts[0] * 60 + parts[1]) }
        return Double(parts[0] * 3600 + parts[1] * 60 + parts[2])
    }

    public static func parse(_ nodes: [Node]) -> TimersUI {
        var ui = TimersUI()
        ui.tab = nodes.firstIndex {
            $0.a.role == "AXRadioButton" && $0.names.contains {
                $0.caseInsensitiveCompare("Timers") == .orderedSame
            }
        }
        if let tab = ui.tab {
            let valueSelected = (nodes[tab].a.value as? NSNumber).map { $0.doubleValue != 0 } ?? false
            ui.tabSelected = valueSelected || nodes[tab].a.selected == true
        }

        ui.start = nodes.firstIndex {
            $0.a.role == "AXButton" && named($0, "Start")
        }
        let cancels = nodes.indices.filter {
            nodes[$0].a.role == "AXButton" && named(nodes[$0], "Cancel")
        }
        if let start = ui.start, let nearest = cancels.min(by: {
            distance(nodes[$0].a.frame, nodes[start].a.frame)
                < distance(nodes[$1].a.frame, nodes[start].a.frame)
        }) {
            ui.cancel = nearest
        } else {
            ui.cancel = cancels.first
        }

        let sliders = nodes.indices.filter { nodes[$0].a.role == "AXSlider" }
        var groups: [[Int]] = []
        for index in sliders {
            let y = nodes[index].a.frame.midY
            if let group = groups.firstIndex(where: { indices in
                guard let first = indices.first else { return false }
                return abs(nodes[first].a.frame.midY - y) <= 12
            }) {
                groups[group].append(index)
            } else {
                groups.append([index])
            }
        }
        let triples = groups.filter { $0.count == 3 }
        let selectedGroup: [Int]?
        if let start = ui.start {
            selectedGroup = triples.min {
                abs(groupMidY($0, nodes: nodes) - nodes[start].a.frame.midY)
                    < abs(groupMidY($1, nodes: nodes) - nodes[start].a.frame.midY)
            }
        } else {
            selectedGroup = triples.first
        }
        ui.wheels = (selectedGroup ?? []).sorted {
            nodes[$0].a.frame.minX < nodes[$1].a.frame.minX
        }

        let fields = nodes.indices.filter { nodes[$0].a.role == "AXTextField" }
        ui.labelField = fields.first { named(nodes[$0], "Timer") }
            ?? (fields.count == 1 ? fields[0] : nil)

        var found: [Int] = []
        for index in nodes.indices {
            let node = nodes[index]
            guard node.a.role != "AXSlider", node.a.role != "AXTextField",
                  !found.contains(where: { isDescendant(index, of: $0, nodes: nodes) }) else { continue }
            let text = [node.a.title, node.a.desc, node.a.value as? String].compactMap { $0 }
            guard let left = text.compactMap(countdown).first else { continue }
            found.append(index)
            var ancestor = node.parent
            var group: Int?
            for _ in 0..<4 {
                guard let current = ancestor else { break }
                let descendants = nodes.indices.filter { $0 == current || isDescendant($0, of: current, nodes: nodes) }
                let hasActionButton = descendants.contains {
                    nodes[$0].a.role == "AXButton" && $0 != ui.start && $0 != ui.cancel
                }
                if hasActionButton { group = current; break }
                ancestor = nodes[current].parent
            }
            var cancelButton: Int?
            var pauseButton: Int?
            var label: String?
            if let group {
                let descendants = nodes.indices.filter { $0 == group || isDescendant($0, of: group, nodes: nodes) }
                cancelButton = descendants.first {
                    nodes[$0].a.role == "AXButton" && $0 != ui.start && $0 != ui.cancel
                        && matches(nodes[$0], pattern: #"(?i)\b(cancel|stop|delete|remove|clear|close)\b|xmark"#)
                }
                pauseButton = descendants.first {
                    nodes[$0].a.role == "AXButton"
                        && matches(nodes[$0], pattern: #"(?i)pause|resume"#)
                }
                label = descendants.first {
                    guard nodes[$0].a.role == "AXStaticText" else { return false }
                    return nodes[$0].text.contains {
                        countdown($0) == nil && $0.caseInsensitiveCompare("Timer") != .orderedSame
                    }
                }.flatMap { nodes[$0].text.first {
                    countdown($0) == nil && $0.caseInsensitiveCompare("Timer") != .orderedSame
                } }
            }
            ui.running.append(Running(node: index, leftS: left, label: label,
                                      cancelButton: cancelButton, pauseButton: pauseButton))
        }
        return ui
    }

    public static func match(records: [[String: Any]], running: [Running], now: Date) -> [[String: Any]] {
        var available = Set(running.indices)
        return records.map { record in
            guard record["backend"] as? String == "clock_ax" else { return record }
            var result = record
            let label = record["label"] as? String
            let match: Int?
            if let label, !label.isEmpty {
                match = available.first { index in
                    running[index].label?.caseInsensitiveCompare(label) == .orderedSame
                }
            } else {
                match = nil
            }
            let selected: Int?
            if let match {
                selected = match
            } else {
                let left = (record["left_s"] as? NSNumber)?.doubleValue
                    ?? (record["fires_at"] as? String).flatMap(isoDate)
                        .map { $0.timeIntervalSince(now) }
                selected = left.flatMap { target in
                    available.min { abs(running[$0].leftS - target) < abs(running[$1].leftS - target) }
                        .flatMap { abs(running[$0].leftS - target) <= ClockAX.matchTolerance ? $0 : nil }
                }
            }
            if let selected {
                available.remove(selected)
                result["clock_seen"] = true
                result["clock_left_s"] = running[selected].leftS
            } else {
                result["clock_seen"] = false
            }
            return result
        }
    }

    /// Seconds of disagreement still counted as the same timer.
    public static let matchTolerance: Double = 5

    public static func backend(axReady: Bool) -> String {
        axReady ? "clock_ax" : "muselet"
    }

    public static func liveReady() -> Bool {
        AXIsProcessTrusted()
            && NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleId) != nil
    }

    private static func named(_ node: Node, _ name: String) -> Bool {
        node.names.contains { $0.caseInsensitiveCompare(name) == .orderedSame }
    }

    private static func distance(_ a: CGRect, _ b: CGRect) -> CGFloat {
        hypot(a.midX - b.midX, a.midY - b.midY)
    }

    private static func groupMidY(_ group: [Int], nodes: [Node]) -> CGFloat {
        guard !group.isEmpty else { return 0 }
        return group.map { nodes[$0].a.frame.midY }.reduce(0, +) / CGFloat(group.count)
    }

    private static func isDescendant(_ index: Int, of ancestor: Int, nodes: [Node]) -> Bool {
        var parent = nodes[index].parent
        while let current = parent {
            if current == ancestor { return true }
            parent = nodes[current].parent
        }
        return false
    }

    private static func matches(_ node: Node, pattern: String) -> Bool {
        node.names.contains { $0.range(of: pattern, options: .regularExpression) != nil }
    }

    private static func isoDate(_ source: String) -> Date? {
        ISO8601DateFormatter().date(from: source)
    }
}

private func recordClockAXStep(_ text: String, to steps: inout [String]) {
    guard steps.count < 24 else { return }
    steps.append(String(text.prefix(100)))
}

struct ClockAXAttempt {
    var reason: String?
    var pressed = false
    var steps: [String] = []
    var verified = false
    var signal: String?
    var ms: Double = 0
    var method: String?
    var labelSet: Bool?
}

extension Skills {
    func clockAXStart(seconds: Double, label: String?) -> ClockAXAttempt {
        let started = Date()
        var pressed = false
        var steps: [String] = []
        func finish(_ reason: String? = nil, verified: Bool = false, signal: String? = nil,
                    method: String? = nil, labelSet: Bool? = nil) -> ClockAXAttempt {
            ClockAXAttempt(reason: reason, pressed: pressed, steps: Array(steps.prefix(24)),
                           verified: verified, signal: signal,
                           ms: (Date().timeIntervalSince(started) * 1000).rounded(to: 2),
                           method: method, labelSet: labelSet)
        }
        guard hooks.clockAXReady() else {
            recordClockAXStep("AX unavailable", to: &steps)
            return finish("clock_ax_unavailable")
        }
        recordClockAXStep("AX ready", to: &steps)
        guard !apps.screenLocked() else {
            recordClockAXStep("screen locked", to: &steps)
            return finish("screen_locked")
        }
        guard let targets = ClockAX.hms(seconds) else {
            recordClockAXStep("duration out of range", to: &steps)
            return finish("duration_out_of_range")
        }
        recordClockAXStep("duration \(targets[0]):\(targets[1]):\(targets[2])", to: &steps)
        let opened: (pid: pid_t, launched: Bool)
        do {
            opened = try launcher.openApp(named: ClockAX.appName)
        } catch {
            recordClockAXStep("Clock launch failed", to: &steps)
            return finish("clock_launch_failed")
        }
        recordClockAXStep(opened.launched ? "Clock launched" : "Clock open", to: &steps)
        let foreground = waitForeground(pid: opened.pid, bundleId: ClockAX.bundleId,
                                        timeout: clockAXTimeout) { $0 != nil }
        guard foreground.front else {
            recordClockAXStep("Clock not frontmost", to: &steps)
            return finish("clock_not_frontmost")
        }
        recordClockAXStep("Clock frontmost", to: &steps)
        guard let window = Hands.pickWindow(app: axApp(foreground.pid))?.window else {
            recordClockAXStep("Clock window missing", to: &steps)
            return finish("clock_no_window")
        }
        var ui = ClockAX.parse(ClockAX.collect(window).nodes)
        guard let tab = ui.tab else {
            recordClockAXStep("Timers tab missing", to: &steps)
            return finish("timers_tab_missing")
        }
        if !ui.tabSelected {
            recordClockAXStep("Timers tab press", to: &steps)
            guard windowFromIndex(tab, window: window, ui: ui) else {
                recordClockAXStep("Timers tab press failed", to: &steps)
                return finish("timers_tab_failed")
            }
            let until = Date().addingTimeInterval(clockAXSettle)
            while Date() < until {
                Hands.pollWait(clockAXPoll)
                ui = ClockAX.parse(ClockAX.collect(window).nodes)
                if ui.tabSelected, ui.start != nil, ui.wheels.count == 3 { break }
            }
            guard ui.tabSelected else {
                recordClockAXStep("Timers tab failed", to: &steps)
                return finish("timers_tab_failed")
            }
        }
        recordClockAXStep("Timers tab selected", to: &steps)
        let pickerEnd = Date().addingTimeInterval(clockAXSettle)
        while (ui.start == nil || ui.wheels.count != 3) && Date() < pickerEnd {
            Hands.pollWait(clockAXPoll)
            ui = ClockAX.parse(ClockAX.collect(window).nodes)
        }
        guard ui.start != nil, ui.wheels.count == 3 else {
            recordClockAXStep("picker missing", to: &steps)
            return finish("picker_missing")
        }
        recordClockAXStep("picker ready", to: &steps)
        let labels = ["h", "m", "s"]
        var methods: [String] = []
        for index in 0..<3 {
            let currentNodes = ClockAX.collect(window).nodes
            let currentUI = ClockAX.parse(currentNodes)
            guard currentUI.wheels.count == 3, currentUI.wheels.indices.contains(index),
                  currentNodes.indices.contains(currentUI.wheels[index]) else {
                recordClockAXStep("picker changed", to: &steps)
                return finish("picker_missing")
            }
            let result = setClockWheel(currentNodes[currentUI.wheels[index]].el, target: targets[index],
                                       name: labels[index], steps: &steps)
            guard let method = result.method else {
                recordClockAXStep(result.reason ?? "wheel \(labels[index]) mismatch", to: &steps)
                return finish(result.reason ?? "wheel_\(labels[index])_mismatch",
                              method: summarizeWheelMethods(methods))
            }
            methods.append(method)
        }
        let wheelMethod = summarizeWheelMethods(methods)
        let labelSet = setClockLabel(window: window, label: label)
        if labelSet == true {
            recordClockAXStep("label set", to: &steps)
        } else if labelSet == false {
            recordClockAXStep("label failed", to: &steps)
        }
        Hands.pollWait(clockAXStepWait)
        let nodesBefore = ClockAX.collect(window).nodes
        let beforeUI = ClockAX.parse(nodesBefore)
        let actualValues: [Int?] = (0..<3).map { index in
            guard beforeUI.wheels.indices.contains(index),
                  nodesBefore.indices.contains(beforeUI.wheels[index]) else { return nil }
            return ClockAX.wheelValue(nodesBefore[beforeUI.wheels[index]].a.value)
        }
        func valueText(_ index: Int) -> String {
            guard actualValues.indices.contains(index), let value = actualValues[index] else { return "?" }
            return String(value)
        }
        recordClockAXStep("pre_start h=\(valueText(0)) m=\(valueText(1)) s=\(valueText(2))", to: &steps)
        guard let startIndex = beforeUI.start, nodesBefore.indices.contains(startIndex) else {
            recordClockAXStep("Start missing", to: &steps)
            return finish("start_missing", method: wheelMethod, labelSet: labelSet)
        }
        guard nodesBefore[startIndex].a.enabled else {
            recordClockAXStep("Start disabled", to: &steps)
            return finish("start_disabled", method: wheelMethod, labelSet: labelSet)
        }
        guard beforeUI.wheels.count == 3 else {
            recordClockAXStep("wheels changed", to: &steps)
            return finish("wheels_changed", method: wheelMethod, labelSet: labelSet)
        }
        for index in 0..<3 {
            guard actualValues[index] == targets[index] else {
                recordClockAXStep("wheels changed", to: &steps)
                return finish("wheels_changed", method: wheelMethod, labelSet: labelSet)
            }
        }
        let beforeCount = beforeUI.running.count
        let cancelWasEnabled = clockAXControlEnabled(beforeUI.cancel, nodes: nodesBefore)
        let beforePauseCount = clockAXPauseCount(nodesBefore)
        guard nodesBefore[startIndex].el.performAction(kAXPressAction as String) else {
            recordClockAXStep("start press failed", to: &steps)
            return finish("start_press_failed", method: wheelMethod, labelSet: labelSet)
        }
        pressed = true
        recordClockAXStep("start press ok", to: &steps)
        if let signal = clockAXVerifyStart(window: window, beforeCount: beforeCount,
                                           beforePauseCount: beforePauseCount,
                                           cancelWasEnabled: cancelWasEnabled) {
            recordClockAXStep("verified \(signal)", to: &steps)
            return finish(nil, verified: true, signal: signal,
                          method: wheelMethod, labelSet: labelSet)
        }
        let retryNodes = ClockAX.collect(window).nodes
        let retryUI = ClockAX.parse(retryNodes)
        let retryStartEnabled = retryUI.start.map {
            retryNodes.indices.contains($0) && retryNodes[$0].a.enabled
        } ?? false
        let retryCancelEnabled = clockAXControlEnabled(retryUI.cancel, nodes: retryNodes)
        let retryPauseCount = clockAXPauseCount(retryNodes)
        let startState = retryUI.start == nil ? "missing" : (retryStartEnabled ? "enabled" : "disabled")
        let cancelState = retryCancelEnabled ? "enabled" : "disabled"
        recordClockAXStep("verify timeout start=\(startState) cancel=\(cancelState) running=\(retryUI.running.count)",
                          to: &steps)
        let unchanged = retryUI.tab != nil && retryStartEnabled && !retryCancelEnabled
            && retryUI.running.count == beforeCount && retryPauseCount <= beforePauseCount
        if unchanged, let retryIndex = retryUI.start, retryNodes.indices.contains(retryIndex) {
            recordClockAXStep("start retry", to: &steps)
            if retryNodes[retryIndex].el.performAction(kAXPressAction as String) {
                recordClockAXStep("start retry press ok", to: &steps)
                if let signal = clockAXVerifyStart(window: window, beforeCount: beforeCount,
                                                   beforePauseCount: beforePauseCount,
                                                   cancelWasEnabled: cancelWasEnabled) {
                    recordClockAXStep("verified \(signal)", to: &steps)
                    return finish(nil, verified: true, signal: signal,
                                  method: wheelMethod, labelSet: labelSet)
                }
            } else {
                recordClockAXStep("start retry press failed", to: &steps)
            }
        } else {
            recordClockAXStep("start retry skipped", to: &steps)
        }
        return finish("start_unverified", method: wheelMethod, labelSet: labelSet)
    }

    func clockAXRead() -> (status: String, running: [ClockAX.Running]) {
        guard hooks.clockAXReady() else { return ("unavailable", []) }
        guard let app = apps.runningApp(bundlePrefix: ClockAX.bundleId) else { return ("not_running", []) }
        guard let window = Hands.pickWindow(app: axApp(app.pid))?.window else { return ("no_window", []) }
        let ui = ClockAX.parse(ClockAX.collect(window).nodes)
        guard ui.tabSelected else { return ("tab_hidden", []) }
        return ("read", ui.running)
    }

    func clockAXCancel(_ info: TimerRegistry.Info, now: Date) -> String? {
        guard hooks.clockAXReady() else { return "clock_ax_unavailable" }
        guard let app = apps.runningApp(bundlePrefix: ClockAX.bundleId) else { return "clock_not_running" }
        guard apps.ensureFrontmost(pid: app.pid, timeout: clockAXTimeout) else { return "clock_not_frontmost" }
        guard let window = Hands.pickWindow(app: axApp(app.pid))?.window else { return "clock_no_window" }
        var nodes = ClockAX.collect(window).nodes
        var ui = ClockAX.parse(nodes)
        if let tab = ui.tab, !ui.tabSelected {
            guard nodes[tab].el.performAction(kAXPressAction as String) else { return "timers_tab_failed" }
            let end = Date().addingTimeInterval(clockAXSettle)
            while Date() < end {
                Hands.pollWait(clockAXPoll)
                nodes = ClockAX.collect(window).nodes
                ui = ClockAX.parse(nodes)
                if ui.tabSelected { break }
            }
            guard ui.tabSelected else { return "timers_tab_failed" }
        }
        let candidates = ui.running.filter { $0.cancelButton != nil }
        let selected: ClockAX.Running?
        if let label = info.label, !label.isEmpty,
           let same = candidates.first(where: { $0.label?.caseInsensitiveCompare(label) == .orderedSame }) {
            selected = same
        } else {
            let target = info.firesAt.timeIntervalSince(now)
            selected = candidates.min { abs($0.leftS - target) < abs($1.leftS - target) }
                .flatMap { abs($0.leftS - target) <= ClockAX.matchTolerance ? $0 : nil }
        }
        guard let selected, let cancel = selected.cancelButton,
              nodes.indices.contains(cancel) else { return "clock_timer_not_found" }
        let beforeCount = ui.running.count
        guard nodes[cancel].el.performAction(kAXPressAction as String) else { return "clock_cancel_unverified" }
        let end = Date().addingTimeInterval(clockAXSettle)
        while Date() < end {
            Hands.pollWait(clockAXPoll)
            let after = ClockAX.parse(ClockAX.collect(window).nodes)
            if after.running.count < beforeCount { return nil }
        }
        return "clock_cancel_unverified"
    }

    private func setClockWheel(_ wheel: Element, target: Int, name: String, steps: inout [String])
        -> (method: String?, reason: String?) {
        let (method, reason) = setClockWheelAX(wheel, target: target, name: name, steps: &steps)
        if method != nil || reason == "wheel_\(name)_unreadable" {
            return (method, reason)
        }
        // AX set/step didn't stick: drive it like a user — click the wheel to
        // focus it, type the digits, then arrow-key step, re-reading after each.
        return setClockWheelKeys(wheel, target: target, name: name, steps: &steps)
    }

    private func setClockWheelAX(_ wheel: Element, target: Int, name: String, steps: inout [String])
        -> (method: String?, reason: String?) {
        let rawValue = wheel.copyAttrs().value
        let raw = String(describing: rawValue).prefix(40)
        recordClockAXStep("\(name) raw=\(raw) -> \(target)", to: &steps)
        guard let current = ClockAX.wheelValue(rawValue) else {
            recordClockAXStep("\(name) unreadable", to: &steps)
            return (nil, "wheel_\(name)_unreadable")
        }
        if current == target, stableClockWheel(wheel, target: target) {
            recordClockAXStep("\(name) \(current)->\(target) none", to: &steps)
            return ("none", nil)
        }
        let valueAttr = kAXValueAttribute as String
        if wheel.isSettable(valueAttr) {
            _ = wheel.setAttr(valueAttr, NSNumber(value: target))
            if stableClockWheel(wheel, target: target) {
                recordClockAXStep("\(name) set ok", to: &steps)
                return ("set", nil)
            }
        }
        var stepCount = 0
        let initial = ClockAX.wheelValue(wheel.copyAttrs().value) ?? current
        let budget = min(70, abs(target - initial) + 5)
        while stepCount < budget {
            guard let before = ClockAX.wheelValue(wheel.copyAttrs().value) else {
                recordClockAXStep("\(name) unreadable", to: &steps)
                return (nil, "wheel_\(name)_unreadable")
            }
            if before == target {
                if stableClockWheel(wheel, target: target) {
                    recordClockAXStep("\(name) \(initial)->\(target) step x\(stepCount)", to: &steps)
                    return ("step", nil)
                }
                recordClockAXStep("\(name) stuck at \(before)", to: &steps)
                return (nil, "wheel_\(name)_stuck")
            }
            let action = before < target ? kAXIncrementAction as String : kAXDecrementAction as String
            guard wheel.performAction(action) else {
                recordClockAXStep("\(name) stuck at \(before)", to: &steps)
                return (nil, "wheel_\(name)_stuck")
            }
            let end = Date().addingTimeInterval(clockAXStepWait)
            var changed = false
            var targetReads = 0
            while Date() < end {
                guard let after = ClockAX.wheelValue(wheel.copyAttrs().value) else {
                    recordClockAXStep("\(name) unreadable", to: &steps)
                    return (nil, "wheel_\(name)_unreadable")
                }
                if after == target {
                    targetReads += 1
                    if targetReads >= 2 {
                        stepCount += 1
                        recordClockAXStep("\(name) \(initial)->\(target) step x\(stepCount)", to: &steps)
                        return ("step", nil)
                    }
                } else {
                    targetReads = 0
                }
                if after != before {
                    changed = true
                    if after != target { break }
                }
                Hands.pollWait(clockAXPoll)
            }
            guard changed else {
                recordClockAXStep("\(name) stuck at \(before)", to: &steps)
                return (nil, "wheel_\(name)_stuck")
            }
            stepCount += 1
        }
        if stableClockWheel(wheel, target: target) {
            recordClockAXStep("\(name) \(initial)->\(target) step x\(stepCount)", to: &steps)
            return ("step", nil)
        }
        let actual = ClockAX.wheelValue(wheel.copyAttrs().value)
        recordClockAXStep("\(name) stuck at \(actual.map { String($0) } ?? "?")", to: &steps)
        return (nil, "wheel_\(name)_mismatch")
    }

    private func setClockWheelKeys(_ wheel: Element, target: Int, name: String, steps: inout [String])
        -> (method: String?, reason: String?) {
        guard let initial = ClockAX.wheelValue(wheel.copyAttrs().value) else {
            recordClockAXStep("\(name) unreadable", to: &steps)
            return (nil, "wheel_\(name)_unreadable")
        }
        if initial == target, stableClockWheel(wheel, target: target) {
            recordClockAXStep("\(name) \(initial)->\(target) none", to: &steps)
            return ("none", nil)
        }
        let frame = wheel.copyAttrs().frame
        Events.click(at: CGPoint(x: frame.midX, y: frame.midY))
        usleep(120_000)
        Events.typeKeystrokes(String(target))
        if stableClockWheel(wheel, target: target) {
            recordClockAXStep("\(name) \(initial)->\(target) type", to: &steps)
            return ("type", nil)
        }
        // Digits didn't take: arrow-key stepping on the focused wheel.
        var arrows = 0
        let arrowBudget = min(70, abs(target - initial) + 5)
        while arrows < arrowBudget {
            guard let before = ClockAX.wheelValue(wheel.copyAttrs().value) else {
                recordClockAXStep("\(name) unreadable", to: &steps)
                return (nil, "wheel_\(name)_unreadable")
            }
            if before == target {
                if stableClockWheel(wheel, target: target) {
                    recordClockAXStep("\(name) \(initial)->\(target) arrows x\(arrows)", to: &steps)
                    return ("arrows", nil)
                }
                recordClockAXStep("\(name) stuck at \(before)", to: &steps)
                return (nil, "wheel_\(name)_stuck")
            }
            postKey(before < target ? 126 : 125)  // up / down arrow
            let end = Date().addingTimeInterval(clockAXStepWait)
            var moved = false
            while Date() < end {
                if let after = ClockAX.wheelValue(wheel.copyAttrs().value), after != before {
                    moved = true
                    break
                }
                Hands.pollWait(clockAXPoll)
            }
            guard moved else {
                recordClockAXStep("\(name) arrows stuck at \(before)", to: &steps)
                return (nil, "wheel_\(name)_stuck")
            }
            arrows += 1
        }
        if stableClockWheel(wheel, target: target) {
            recordClockAXStep("\(name) \(initial)->\(target) arrows x\(arrows)", to: &steps)
            return ("arrows", nil)
        }
        let actual = ClockAX.wheelValue(wheel.copyAttrs().value)
        recordClockAXStep("\(name) stuck at \(actual.map { String($0) } ?? "?")", to: &steps)
        return (nil, "wheel_\(name)_mismatch")
    }

    /// Posts one virtual-key press to the focused app (Clock's wheel accepts
    /// up/down arrows once focused).
    private func postKey(_ code: CGKeyCode) {
        let src = CGEventSource(stateID: .hidSystemState)
        for down in [true, false] {
            if let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down) {
                SyntheticEvent.post(e)
            }
        }
        usleep(30_000)
    }

    private func stableClockWheel(_ wheel: Element, target: Int) -> Bool {
        let end = Date().addingTimeInterval(clockAXStepWait)
        var consecutive = 0
        while Date() < end {
            if ClockAX.wheelValue(wheel.copyAttrs().value) == target {
                consecutive += 1
                if consecutive == 2 { return true }
            } else {
                consecutive = 0
            }
            Hands.pollWait(clockAXPoll)
        }
        return false
    }

    private func clockAXVerifyStart(window: Element, beforeCount: Int, beforePauseCount: Int,
                                    cancelWasEnabled: Bool) -> String? {
        let end = Date().addingTimeInterval(clockAXVerify)
        while Date() < end {
            Hands.pollWait(clockAXPoll)
            let nodes = ClockAX.collect(window).nodes
            let ui = ClockAX.parse(nodes)
            guard ui.tab != nil else { continue }
            if ui.running.count > beforeCount { return "running_added" }
            let newPause = clockAXPauseCount(nodes) > beforePauseCount
            let cancelEnabled = clockAXControlEnabled(ui.cancel, nodes: nodes)
            if (newPause || ui.start == nil) && !cancelWasEnabled && cancelEnabled {
                return "pause_cancel"
            }
        }
        return nil
    }

    private func clockAXPauseCount(_ nodes: [ClockAX.Node]) -> Int {
        nodes.filter {
            $0.a.role == "AXButton"
                && $0.names.contains {
                    $0.range(of: #"(?i)pause|resume"#, options: .regularExpression) != nil
                }
        }.count
    }

    private func clockAXControlEnabled(_ index: Int?, nodes: [ClockAX.Node]) -> Bool {
        guard let index, nodes.indices.contains(index) else { return false }
        return nodes[index].a.enabled
    }

    private func setClockLabel(window: Element, label: String?) -> Bool? {
        guard let label else { return nil }
        let nodes = ClockAX.collect(window).nodes
        let ui = ClockAX.parse(nodes)
        guard let fieldIndex = ui.labelField, nodes.indices.contains(fieldIndex) else { return false }
        let field = nodes[fieldIndex].el
        if (nodes[fieldIndex].a.value as? String) == label { return true }
        let valueAttr = kAXValueAttribute as String
        guard field.isSettable(valueAttr) else { return false }
        _ = field.setAttr(kAXFocusedAttribute as String, true)
        _ = field.setAttr(valueAttr, label)
        let end = Date().addingTimeInterval(clockAXStepWait)
        while Date() < end {
            if (field.copyAttrs().value as? String) == label { return true }
            Hands.pollWait(clockAXPoll)
        }
        return (field.copyAttrs().value as? String) == label
    }

    private func summarizeWheelMethods(_ methods: [String]) -> String {
        let unique = Set(methods.filter { $0 != "none" })
        if unique.isEmpty { return "none" }
        return unique.count == 1 ? (unique.first ?? "none") : "mixed"
    }

    private func windowFromIndex(_ index: Int, window: Element, ui: ClockAX.TimersUI) -> Bool {
        let nodes = ClockAX.collect(window).nodes
        guard nodes.indices.contains(index), ui.tab != nil else { return false }
        return nodes[index].el.performAction(kAXPressAction as String)
    }
}

public enum ClockAXProbe {
    public static func run(open: Bool = false) -> [String: Any] {
        Permissions.requireAX()
        let started = Date()
        let apps = WorkspaceApps()
        let launcher = WorkspaceLauncher()
        var app = apps.runningApp(bundlePrefix: ClockAX.bundleId)
        if app == nil && !open {
            return ["running": false, "hint": "Run hands probe clock --open to open Clock.",
                    "ms": (Date().timeIntervalSince(started) * 1000).rounded(to: 1)]
        }
        if open {
            let pid: pid_t
            do {
                let opened = try launcher.openApp(named: ClockAX.appName)
                pid = opened.pid
            } catch {
                return ["running": app != nil, "error": "clock_launch_failed",
                        "ms": (Date().timeIntervalSince(started) * 1000).rounded(to: 1)]
            }
            if pid > 0 { _ = apps.ensureFrontmost(pid: pid, timeout: 3.0) }
            let end = Date().addingTimeInterval(3.0)
            while Date() < end {
                app = apps.runningApp(bundlePrefix: ClockAX.bundleId)
                if let app, Hands.pickWindow(app: AXNode(AXUIElementCreateApplication(app.pid))) != nil { break }
                Hands.pollWait(0.05)
            }
            if let app, let window = Hands.pickWindow(app: AXNode(AXUIElementCreateApplication(app.pid)))?.window {
                var nodes = ClockAX.collect(window).nodes
                var ui = ClockAX.parse(nodes)
                if let tab = ui.tab, !ui.tabSelected, nodes.indices.contains(tab) {
                    _ = nodes[tab].el.performAction(kAXPressAction as String)
                    Hands.pollWait(0.5)
                }
            } else {
                Hands.pollWait(0.5)
            }
        }
        guard let app else {
            return ["running": false, "hint": "Clock is not running.",
                    "ms": (Date().timeIntervalSince(started) * 1000).rounded(to: 1)]
        }
        let appElement = AXNode(AXUIElementCreateApplication(app.pid))
        appElement.setMessagingTimeout(0.5)
        let picked = Hands.pickWindow(app: appElement)
        guard let window = picked?.window else {
            return ["running": true, "pid": Int(app.pid),
                    "frontmost": apps.frontmostPid() == app.pid,
                    "window_title": NSNull(), "window_source": picked?.source ?? "none",
                    "node_count": 0, "truncated": false, "elements": [],
                    "parsed": ["tab": NSNull(), "tab_selected": false, "wheels": [],
                               "label_field": NSNull(), "start": NSNull(), "cancel": NSNull(), "running": []],
                    "ms": (Date().timeIntervalSince(started) * 1000).rounded(to: 1)]
        }
        let collected = ClockAX.collect(window)
        let nodes = collected.nodes
        let ui = ClockAX.parse(nodes)
        let elements: [[String: Any]] = nodes.enumerated().map { i, node in
            let value = node.a.value
            let valueType: String
            if let number = value as? NSNumber {
                valueType = CFGetTypeID(number) == CFBooleanGetTypeID() ? "bool" : "number"
            } else if value is String {
                valueType = "string"
            } else {
                valueType = value == nil ? "none" : "other"
            }
            let identifier = node.el.copySingleAttr(kAXIdentifierAttribute as String) as? String
            let selected: Any = node.a.selected.map { $0 as Any } ?? NSNull()
            return [
                "i": i, "parent": node.parent as Any? ?? NSNull(), "depth": node.depth,
                "role": node.a.role as Any? ?? NSNull(), "subrole": node.a.subrole as Any? ?? NSNull(),
                "title": node.a.title as Any? ?? NSNull(), "desc": node.a.desc as Any? ?? NSNull(),
                "value": value.map { String(describing: $0).prefix(120).description } as Any? ?? NSNull(),
                "value_type": valueType, "placeholder": node.a.placeholder as Any? ?? NSNull(),
                "help": node.a.help as Any? ?? NSNull(), "identifier": identifier as Any? ?? NSNull(),
                "enabled": node.a.enabled, "selected": selected,
                "frame": [Double(node.a.frame.minX), Double(node.a.frame.minY),
                          Double(node.a.frame.width), Double(node.a.frame.height)],
                "min": number(node.el.copySingleAttr(kAXMinValueAttribute as String)) as Any? ?? NSNull(),
                "max": number(node.el.copySingleAttr(kAXMaxValueAttribute as String)) as Any? ?? NSNull(),
                "settable": [kAXValueAttribute as String, kAXFocusedAttribute as String,
                             kAXSelectedAttribute as String].filter { node.el.isSettable($0) },
                "actions": node.el.actionNames(),
            ]
        }
        let wheels: [[String: Any]] = ui.wheels.compactMap { index in
            guard nodes.indices.contains(index) else { return nil }
            let node = nodes[index]
            return ["i": index, "value": node.a.value.map { String(describing: $0) } as Any? ?? NSNull(),
                    "parsed": ClockAX.wheelValue(node.a.value) as Any? ?? NSNull(),
                    "min": number(node.el.copySingleAttr(kAXMinValueAttribute as String)) as Any? ?? NSNull(),
                    "max": number(node.el.copySingleAttr(kAXMaxValueAttribute as String)) as Any? ?? NSNull(),
                    "value_settable": node.el.isSettable(kAXValueAttribute as String),
                    "actions": node.el.actionNames(),
                    "frame": [Double(node.a.frame.minX), Double(node.a.frame.minY),
                              Double(node.a.frame.width), Double(node.a.frame.height)]]
        }
        func control(_ index: Int?) -> Any {
            guard let index, nodes.indices.contains(index) else { return NSNull() }
            return ["i": index, "enabled": nodes[index].a.enabled]
        }
        let running = ui.running.map { timer -> [String: Any] in
            ["i": timer.node, "left_s": timer.leftS, "label": timer.label as Any? ?? NSNull(),
             "cancel_button": timer.cancelButton as Any? ?? NSNull(),
             "pause_button": timer.pauseButton as Any? ?? NSNull()]
        }
        return [
            "running": true, "pid": Int(app.pid), "frontmost": apps.frontmostPid() == app.pid,
            "window_title": Hands.windowTitle(window), "window_source": picked?.source ?? "none",
            "node_count": nodes.count, "truncated": collected.truncated,
            "elements": elements,
            "parsed": [
                "tab": ui.tab as Any? ?? NSNull(), "tab_selected": ui.tabSelected,
                "wheels": wheels, "label_field": ui.labelField as Any? ?? NSNull(),
                "start": control(ui.start), "cancel": control(ui.cancel), "running": running,
            ],
            "ms": (Date().timeIntervalSince(started) * 1000).rounded(to: 1),
        ]
    }

    private static func number(_ value: Any?) -> Double? {
        guard let number = value as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        return number.doubleValue.isFinite ? number.doubleValue : nil
    }
}
