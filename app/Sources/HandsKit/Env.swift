import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

// MARK: - Synthetic event tagging

/// Every CGEvent HandsKit synthesizes carries this `eventSourceUserData`
/// ("MUSL"), so the app's own listeners (push-to-talk tap) can tell agent
/// input from the user's: the agent's `keys esc` must not cancel its task.
public enum SyntheticEvent {
    public static let userData: Int64 = 0x4D55534C

    public static func tag(_ e: CGEvent) {
        e.setIntegerValueField(.eventSourceUserData, value: userData)
    }

    public static func isTagged(_ e: CGEvent) -> Bool {
        e.getIntegerValueField(.eventSourceUserData) == userData
    }

    /// Tag, then post at the HID tap.
    public static func post(_ e: CGEvent, tap: CGEventTapLocation = .cghidEventTap) {
        tag(e)
        e.post(tap: tap)
    }
}

// MARK: - Key posting (injectable for tests)

public protocol EventPosting: AnyObject {
    func post(_ combo: KeyCombo)
}

/// Live poster: tagged CGEvents at the HID tap.
public final class CGEventPoster: EventPosting {
    public init() {}
    public func post(_ combo: KeyCombo) { Combo.post(combo) }
}

// MARK: - App focus (injectable for tests)

public struct RunningAppInfo: Equatable {
    public var pid: pid_t
    public var name: String
    public var bundleId: String
    public init(pid: pid_t, name: String, bundleId: String) {
        self.pid = pid; self.name = name; self.bundleId = bundleId
    }
}

public protocol AppControlling: AnyObject {
    func frontmostPid() -> pid_t
    /// Ask `pid` to become frontmost. Returns false if the request failed outright.
    @discardableResult func activate(pid: pid_t) -> Bool
    func app(pid: pid_t) -> RunningAppInfo?
    func runningApp(bundlePrefix: String) -> RunningAppInfo?
}

public extension AppControlling {
    /// True when `pid` is frontmost, activating it and waiting up to
    /// `timeout` (polling every 15 ms) if it isn't.
    func ensureFrontmost(pid: pid_t, timeout: TimeInterval = 0.3) -> Bool {
        if frontmostPid() == pid { return true }
        activate(pid: pid)
        let end = Date().addingTimeInterval(timeout)
        while Date() < end {
            if frontmostPid() == pid { return true }
            usleep(15_000)
        }
        return frontmostPid() == pid
    }

    func name(pid: pid_t) -> String {
        app(pid: pid)?.name ?? (pid == 0 ? "none" : "pid \(pid)")
    }
}

/// Live implementation over NSWorkspace + AX.
public final class WorkspaceApps: AppControlling {
    public init() {}

    public func frontmostPid() -> pid_t {
        NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0
    }

    @discardableResult
    public func activate(pid: pid_t) -> Bool {
        // AXFrontmost works for trusted clients even under cooperative
        // activation (a background accessory app can't steal focus with
        // NSRunningApplication.activate alone on macOS 14+).
        let el = AXUIElementCreateApplication(pid)
        AXUIElementSetMessagingTimeout(el, 0.25)
        let axOK = AXUIElementSetAttributeValue(
            el, kAXFrontmostAttribute as CFString, kCFBooleanTrue) == .success
        let nsOK = NSRunningApplication(processIdentifier: pid)?
            .activate(options: [.activateAllWindows]) ?? false
        return axOK || nsOK
    }

    public func app(pid: pid_t) -> RunningAppInfo? {
        guard let a = NSRunningApplication(processIdentifier: pid) else { return nil }
        return RunningAppInfo(pid: pid, name: a.localizedName ?? "?",
                              bundleId: a.bundleIdentifier ?? "")
    }

    public func runningApp(bundlePrefix: String) -> RunningAppInfo? {
        guard let a = NSWorkspace.shared.runningApplications.first(where: {
            ($0.bundleIdentifier ?? "").hasPrefix(bundlePrefix) && !$0.isTerminated
        }) else { return nil }
        return RunningAppInfo(pid: a.processIdentifier, name: a.localizedName ?? "?",
                              bundleId: a.bundleIdentifier ?? "")
    }
}
