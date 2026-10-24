import Foundation
import HandsKit

/// Settings › Timers: "Use the Clock app for timers" (persisted; default on,
/// effective only while `Muselet Start Timer` is installed) and the
/// one-time shortcut setup steps (docs/CLOCK_TIMERS.md).
enum TimerSettings {
    static let key = "muselet.clockTimers"

    static var useClock: Bool {
        get { UserDefaults.standard.object(forKey: key) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static let shortcutsURL = URL(string: "shortcuts://")!

    /// Short form of docs/CLOCK_TIMERS.md for the panel.
    static let setupSteps = [
        "Open Shortcuts and click + to make a new shortcut.",
        "Name it exactly “\(ClockShortcut.start)”.",
        "Add “Receive Text input” (shortcut input / details: Text).",
        "Add “Get Numbers from Input”.",
        "Add “Start Timer” and set its duration to the Numbers, in seconds.",
        "Optional: “\(ClockShortcut.cancel)” with “Cancel Timer”.",
        "Optional: “\(ClockShortcut.status)”: “Get Current Timer” → “Stop and Output”.",
        "Come back and click Check again.",
    ]
}

/// `timer_backend` RPC result, for the Settings row.
struct ClockTimerStatus: Equatable {
    var ready: Bool
    var shortcuts: [String]

    init(ready: Bool, shortcuts: [String]) {
        self.ready = ready
        self.shortcuts = shortcuts
    }

    init?(_ d: Any?) {
        guard let d = d as? [String: Any], let ready = d["clock_ready"] as? Bool else { return nil }
        self.init(ready: ready, shortcuts: d["shortcuts"] as? [String] ?? [])
    }
}
