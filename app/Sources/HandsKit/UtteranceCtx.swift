import AppKit
import ApplicationServices
import Network

/// Capture the context sent on an utterance frame (AGENTS.md):
/// frontmost app name, focused element as `<role> "<label>"` (HandsKit's
/// role map), selection (non-empty selected text), online (NWPathMonitor's
/// latest status — never a blocking probe).
///
/// AX calls use a 0.15 s messaging timeout (a hung frontmost app must not
/// stall push-to-talk). The app captures asynchronously via `begin()`.
public enum UtteranceCtx {
    public static let axTimeout: Float = 0.15

    private static var monitorStarted = false
    private static var lastOnline = true
    private static let monLock = NSLock()
    private static let queue = DispatchQueue(label: "ctx.capture", qos: .userInitiated)

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

    /// Focused element of `pid` as (`<role> "<label>"` or "none", has
    /// selection). One kAXFocusedUIElement fetch, reused for both; every
    /// element gets the short messaging timeout.
    public static func focusedInfo(pid: pid_t) -> (focused: String, selection: Bool) {
        guard pid > 0 else { return ("none", false) }
        let appEl = AXUIElementCreateApplication(pid)
        AXUIElementSetMessagingTimeout(appEl, axTimeout)
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            appEl, kAXFocusedUIElementAttribute as CFString, &v) == .success,
            let fe = v, CFGetTypeID(fe) == AXUIElementGetTypeID() else { return ("none", false) }
        let fel = fe as! AXUIElement
        AXUIElementSetMessagingTimeout(fel, axTimeout)
        let node = AXNode(fel)
        node.setMessagingTimeout(axTimeout)
        let a = node.copyAttrs()
        var focused = "none"
        if let axRole = a.role, let role = kRoleMap[axRole] {
            focused = "\(role) \"\(Walker.label(of: a, role: role))\""
        }
        return (focused, hasSelection(fel))
    }

    /// Selection: AXSelectedTextRange length > 0 (cheap), else non-empty
    /// AXSelectedText (web areas often lack the range).
    private static func hasSelection(_ el: AXUIElement) -> Bool {
        var r: CFTypeRef?
        if AXUIElementCopyAttributeValue(el, kAXSelectedTextRangeAttribute as CFString, &r) == .success,
           let rv = r, CFGetTypeID(rv) == AXValueGetTypeID() {
            var range = CFRange()
            if AXValueGetValue(rv as! AXValue, .cfRange, &range) { return range.length > 0 }
        }
        var s: CFTypeRef?
        guard AXUIElementCopyAttributeValue(el, kAXSelectedTextAttribute as CFString, &s) == .success,
              let str = s as? String else { return false }
        return !str.isEmpty
    }

    /// Backwards-compatible: focused summary only.
    public static func focusedSummary(pid: pid_t) -> String { focusedInfo(pid: pid).focused }

    /// Synchronous capture (headless CLI). Bounded by the AX timeouts.
    public static func capture() -> [String: Any] {
        let app = NSWorkspace.shared.frontmostApplication
        let pid = app?.processIdentifier ?? 0
        let (focused, sel) = focusedInfo(pid: pid)
        return ["app": app?.localizedName ?? "none", "focused": focused,
                "selection": sel, "online": online()]
    }

    /// Start an asynchronous capture at push-to-talk key-down. The app name
    /// and pid are read synchronously (cheap, no AX), so they reflect the
    /// app before any Muselet UI; the AX part runs on a background queue.
    public static func begin() -> PendingCtx {
        let app = NSWorkspace.shared.frontmostApplication
        let pid = app?.processIdentifier ?? 0
        let name = app?.localizedName ?? "none"
        let base: [String: Any] = ["app": name, "focused": "none", "selection": false,
                                   "online": online()]
        return PendingCtx(fallback: base, queue: queue) {
            let (focused, sel) = focusedInfo(pid: pid)
            var d = base
            d["focused"] = focused
            d["selection"] = sel
            return d
        }
    }
}

/// A ctx capture in flight. `ready` is nil until the work finishes;
/// `whenReady` delivers the value, or the fallback (app + online, focused
/// "none") once the timeout passes, exactly once.
public final class PendingCtx {
    private let lock = NSLock()
    private var value: [String: Any]?
    private var waiters: [([String: Any]) -> Void] = []
    public let fallback: [String: Any]

    public init(fallback: [String: Any], queue: DispatchQueue,
                work: @escaping () -> [String: Any]) {
        self.fallback = fallback
        queue.async { [self] in self.fulfill(work()) }
    }

    /// Completed capture, or nil if still running (partials omit ctx then).
    public var ready: [String: Any]? {
        lock.lock(); defer { lock.unlock() }
        return value
    }

    private func fulfill(_ v: [String: Any]) {
        lock.lock()
        value = v
        let ws = waiters
        waiters = []
        lock.unlock()
        ws.forEach { $0(v) }
    }

    /// Call `cb` on `queue` with the capture, or with the fallback after
    /// `timeout` seconds — whichever comes first, once.
    public func whenReady(timeout: TimeInterval, queue: DispatchQueue = .main,
                          _ cb: @escaping ([String: Any]) -> Void) {
        let once = Once()
        let deliver: ([String: Any]) -> Void = { v in
            if once.claim() { queue.async { cb(v) } }
        }
        lock.lock()
        if let v = value {
            lock.unlock()
            deliver(v)
            return
        }
        waiters.append(deliver)
        lock.unlock()
        let fb = fallback
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + timeout) {
            deliver(fb)
        }
    }

    /// Blocking variant (never call on the main thread).
    public func wait(timeout: TimeInterval) -> [String: Any] {
        let sem = DispatchSemaphore(value: 0)
        var out = fallback
        whenReady(timeout: timeout, queue: DispatchQueue.global()) { v in out = v; sem.signal() }
        sem.wait()
        return out
    }

    private final class Once {
        private let lock = NSLock()
        private var done = false
        func claim() -> Bool {
            lock.lock(); defer { lock.unlock() }
            if done { return false }
            done = true
            return true
        }
    }
}
