import Foundation
import HandsKit

/// Settings › Timers: "Use the Clock app for timers" (persisted; default on)
/// and the optional shortcut backup setup steps (docs/CLOCK_TIMERS.md).
enum TimerSettings {
    static let key = "muselet.clockTimers"

    static var useClock: Bool {
        get { UserDefaults.standard.object(forKey: key) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static let shortcutsURL = URL(string: "shortcuts://")!

    /// Short form of docs/CLOCK_TIMERS.md for the panel.
    static let setupSteps = [
        "Muselet sets timers in Clock directly (needs Accessibility).",
        "Optional backup: Open Shortcuts and click + to make a new shortcut.",
        "Optional backup: Name it exactly “\(ClockShortcut.start)”.",
        "Optional backup: Add “Receive Text input” (shortcut input / details: Text).",
        "Optional backup: Add “Get Numbers from Input”.",
        "Optional backup: Add “Start Timer” and set its duration to the Numbers, in seconds.",
        "Optional backup: “\(ClockShortcut.cancel)” with “Cancel Timer”.",
        "Optional backup: “\(ClockShortcut.status)”: “Get Current Timer” → “Stop and Output”.",
        "Optional backup: Come back and click Check again.",
    ]
}

/// `timer_backend` RPC result, for the Settings row.
struct ClockTimerStatus: Equatable {
    var ready: Bool
    var axReady: Bool
    var shortcuts: [String]

    init(ready: Bool, axReady: Bool = false, shortcuts: [String]) {
        self.ready = ready
        self.axReady = axReady
        self.shortcuts = shortcuts
    }

    init?(_ d: Any?) {
        guard let d = d as? [String: Any], let ready = d["clock_ready"] as? Bool else { return nil }
        self.init(ready: ready, axReady: d["clock_ax_ready"] as? Bool ?? false,
                  shortcuts: d["shortcuts"] as? [String] ?? [])
    }
}
