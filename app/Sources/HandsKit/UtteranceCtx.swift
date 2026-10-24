import AppKit
import ApplicationServices
import Network

/// Capture the context sent on an utterance frame (AGENTS.md):
/// frontmost app name, focused element as `<role> "<label>"` (HandsKit's
/// role map), selection (non-empty AXSelectedText), online (NWPathMonitor's
/// latest status — never a blocking probe).
public enum UtteranceCtx {
    private static var monitorStarted = false
    private static var lastOnline = true
    private static let monLock = NSLock()

    /// Latest NWPathMonitor status; starts the monitor lazily.
    public static func online() -> Bool {
        monLock.lock()
        defer { monLock.unlock() }
        if !monitorStarted {
            monitorStarted = true
            let m = NWPathMonitor()
            m.pathUpdateHandler = { p in
                monLock.lock()
                lastOnline = (p.status == .satisfied)
                monLock.unlock()
            }
            m.start(queue: DispatchQueue(label: "ctx.nwpath"))
        }
        return lastOnline
    }

    /// Focused element of `app` as `<role> "<label>"`, or "none".
    public static func focusedSummary(pid: pid_t) -> String {
        let appEl = AXUIElementCreateApplication(pid)
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            appEl, kAXFocusedUIElementAttribute as CFString, &v) == .success,
            let fe = v else { return "none" }
        let a = AXNode(fe as! AXUIElement).copyAttrs()
        guard let axRole = a.role, let role = kRoleMap[axRole] else {
            return "none"
        }
        let label = Walker.label(of: a, role: role)
        return "\(role) \"\(label)\""
    }

    /// Non-empty AXSelectedText on the focused element.
    public static func hasSelection(pid: pid_t) -> Bool {
        let appEl = AXUIElementCreateApplication(pid)
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            appEl, kAXFocusedUIElementAttribute as CFString, &v) == .success,
            let fe = v else { return false }
        var sel: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            fe as! AXUIElement, "AXSelectedText" as CFString, &sel) == .success,
            let s = sel as? String else { return false }
        return !s.isEmpty
    }

    /// The ctx dict to send on the utterance frame.
    public static func capture() -> [String: Any] {
        let app = NSWorkspace.shared.frontmostApplication
        let pid = app?.processIdentifier ?? 0
        return [
            "app": app?.localizedName ?? "none",
            "focused": pid != 0 ? focusedSummary(pid: pid) : "none",
            "selection": pid != 0 ? hasSelection(pid: pid) : false,
            "online": online(),
        ]
    }
}
