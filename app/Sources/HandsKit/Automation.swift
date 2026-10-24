import AppKit
import CoreServices
import Foundation

/// macOS Automation (Apple Events) consent per target app. Skill
/// AppleScripts to Notes / Calendar / ... block behind the system consent
/// prompt the first time; onboarding asks up front instead.
///
/// Status reads use `AEDeterminePermissionToAutomateTarget` with
/// askUserIfNeeded=false (never prompts). It needs the target running
/// (else procNotFound -> `notRunning`, status unknown). `request` launches
/// the target hidden if needed, then asks (shows the prompt once; a denied
/// target only changes in System Settings > Privacy & Security > Automation).
public enum Automation {
    public struct Target: Hashable, Identifiable {
        public let name: String
        public let bundleId: String
        public var id: String { bundleId }
        /// Launched on demand by the system and left running (never quit by us).
        public var persistent: Bool { bundleId == "com.apple.finder" || bundleId == "com.apple.systemevents" }
        public init(name: String, bundleId: String) {
            self.name = name
            self.bundleId = bundleId
        }
    }

    public static let targets: [Target] = [
        Target(name: "Notes", bundleId: "com.apple.Notes"),
        Target(name: "Calendar", bundleId: "com.apple.iCal"),
        Target(name: "Reminders", bundleId: "com.apple.reminders"),
        Target(name: "Numbers", bundleId: "com.apple.iWork.Numbers"),
        Target(name: "Finder", bundleId: "com.apple.finder"),
        Target(name: "System Events", bundleId: "com.apple.systemevents"),
    ]

    public enum Status: Equatable, CustomStringConvertible {
        case granted, denied, notDetermined, notRunning, notInstalled
        case unknown(OSStatus)
        public var description: String {
            switch self {
            case .granted: return "granted"
            case .denied: return "denied"
            case .notDetermined: return "not_determined"
            case .notRunning: return "not_running"
            case .notInstalled: return "not_installed"
            case .unknown(let s): return "unknown(\(s))"
            }
        }
    }

    public static let settingsURL =
        URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation")!

    /// OSStatus of AEDeterminePermissionToAutomateTarget -> Status.
    public static func status(from s: OSStatus) -> Status {
        switch s {
        case noErr: return .granted
        case OSStatus(errAEEventNotPermitted): return .denied                // -1743
        case OSStatus(errAEEventWouldRequireUserConsent): return .notDetermined  // -1744
        case OSStatus(procNotFound): return .notRunning                      // -600
        default: return .unknown(s)
        }
    }

    static func appURL(_ t: Target) -> URL? {
        NSWorkspace.shared.urlForApplication(withBundleIdentifier: t.bundleId)
    }

    static func running(_ t: Target) -> NSRunningApplication? {
        NSRunningApplication.runningApplications(withBundleIdentifier: t.bundleId)
            .first { !$0.isTerminated }
    }

    /// Raw AEDeterminePermissionToAutomateTarget for `bundleId` (any event).
    static func determine(_ bundleId: String, ask: Bool) -> OSStatus {
        let desc = NSAppleEventDescriptor(bundleIdentifier: bundleId)
        guard let ae = desc.aeDesc else { return OSStatus(procNotFound) }
        return AEDeterminePermissionToAutomateTarget(ae, AEEventClass(typeWildCard),
                                                     AEEventID(typeWildCard), ask)
    }

    /// Current status; never prompts, never launches anything.
    public static func status(of t: Target) -> Status {
        guard appURL(t) != nil else { return .notInstalled }
        guard running(t) != nil else { return .notRunning }
        return status(from: determine(t.bundleId, ask: false))
    }

    public static func statuses() -> [(Target, Status)] {
        targets.map { ($0, status(of: $0)) }
    }

    /// One log line: `Notes=granted Calendar=not_running ...`.
    public static func summaryLine(_ s: [(Target, Status)]) -> String {
        s.map { "\($0.0.name.replacingOccurrences(of: " ", with: ""))=\($0.1)" }.joined(separator: " ")
    }

    private static let queue = DispatchQueue(label: "hands.automation", qos: .userInitiated)

    /// Ask for consent (shows the system prompt if not determined yet).
    /// Launches the target hidden first when it isn't running and quits it
    /// afterwards (unless Finder / System Events). Runs on a background
    /// queue (the call blocks until the user answers); `completion` on main.
    public static func request(_ t: Target, completion: @escaping (Status) -> Void) {
        queue.async {
            let result = requestSync(t)
            DispatchQueue.main.async { completion(result) }
        }
    }

    static func requestSync(_ t: Target) -> Status {
        guard let url = appURL(t) else { return .notInstalled }
        var launched: NSRunningApplication?
        if running(t) == nil {
            let cfg = NSWorkspace.OpenConfiguration()
            cfg.activates = false
            cfg.hides = true
            cfg.addsToRecentItems = false
            let sem = DispatchSemaphore(value: 0)
            NSWorkspace.shared.openApplication(at: url, configuration: cfg) { app, _ in
                launched = app
                sem.signal()
            }
            _ = sem.wait(timeout: .now() + 10)
            let end = Date().addingTimeInterval(10)
            while Date() < end, running(t).map({ !$0.isFinishedLaunching }) ?? true { usleep(100_000) }
        }
        // A freshly launched app may not take Apple Events for a moment.
        var st = status(from: determine(t.bundleId, ask: true))
        var tries = 0
        while st == .notRunning && tries < 20 {
            usleep(150_000)
            tries += 1
            st = status(from: determine(t.bundleId, ask: true))
        }
        if let app = launched, !t.persistent { app.terminate() }
        return st
    }
}
