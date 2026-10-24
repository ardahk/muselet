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
        return focusedInfo(app: AXNode(AXUIElementCreateApplication(pid)))
    }

    /// Testable core (mock app element).
    static func focusedInfo(app: Element,
                            budget: TimeInterval = 0.3) -> (focused: String, selection: Bool) {
        let deadline = Date().addingTimeInterval(budget)
        app.setMessagingTimeout(axTimeout)
        guard let fel = node(app.copySingleAttr(kAXFocusedUIElementAttribute as String)) else {
            return ("none", false)
        }
        let a = fel.copyAttrs()
        var focused = "none"
        if let axRole = a.role, let role = kRoleMap[axRole] {
            focused = "\(role) \"\(Walker.label(of: a, role: role))\""
        }
        return (focused, hasSelection(fel, role: a.role, attrs: a, deadline: deadline))
    }

    /// AX element with the short messaging timeout.
    private static func node(_ v: Any?) -> Element? {
        guard let e = axElement(v) else { return nil }
        e.setMessagingTimeout(axTimeout)
        return e
    }

    static let itemSelectionAttrs = ["AXSelectedRows", "AXSelectedChildren", "AXSelectedCells"]
    /// Lists whose AXSelectedRows/Children/Cells are a user selection
    /// (Finder list/icon/column views, Mail, Notes lists, Numbers tables).
    static let listRoles: Set<String> = ["AXList", "AXOutline", "AXTable", "AXBrowser", "AXGrid"]
    /// Roles whose "selected children" are not a user selection.
    static let noItemSelectionRoles: Set<String> = [
        "AXMenuBar", "AXMenu", "AXMenuBarItem", "AXTabGroup", "AXRadioGroup", "AXToolbar",
    ]
    /// Focus on one of these: look for the list it belongs to (parents).
    static let itemRoles: Set<String> = ["AXRow", "AXCell", "AXStaticText", "AXImage", "AXTextField"]
    /// Focus on one of these: look for a list inside (Finder column view, scroll areas).
    static let containerRoles: Set<String> = ["AXScrollArea", "AXBrowser", "AXSplitGroup", "AXGroup"]

    /// Selection (training-11): selected text (AXSelectedTextRange length
    /// > 0, else non-empty AXSelectedText), or selected items — non-empty
    /// AXSelectedRows / AXSelectedChildren / AXSelectedCells on the focused
    /// element or on its list/outline/table (parent of a focused row/cell,
    /// or the focused list inside a focused container). Bounded by `deadline`.
    static func hasSelection(_ el: Element, role: String?, attrs: ElAttrs? = nil,
                             deadline: Date) -> Bool {
        if hasTextSelection(el) { return true }
        let r = role ?? ""
        if !noItemSelectionRoles.contains(r), hasItemSelection(el) { return true }
        if itemRoles.contains(r) {
            // A focused row/cell (or rename field): its list owns the selection.
            var cur: Element? = el
            for _ in 0..<3 {
                guard Date() < deadline,
                      let p = node(cur?.copySingleAttr(kAXParentAttribute as String)) else { break }
                if let pr = p.copyAttrs().role, listRoles.contains(pr) { return hasItemSelection(p) }
                cur = p
            }
        } else if containerRoles.contains(r) {
            // Breadth-first (<= 12 nodes, depth <= 3) for the list inside;
            // the focused one first.
            var queue: [(Element, Int)] = (attrs ?? el.copyAttrs()).children.map { ($0, 1) }
            var lists: [(Element, Bool)] = []
            var qi = 0
            while qi < queue.count && qi < 12 && Date() < deadline {
                let (c, depth) = queue[qi]; qi += 1
                c.setMessagingTimeout(axTimeout)
                let ca = c.copyAttrs()
                if let cr = ca.role, listRoles.contains(cr) { lists.append((c, ca.focused)); continue }
                if depth < 3 { queue.append(contentsOf: ca.children.map { ($0, depth + 1) }) }
            }
            for (l, _) in lists.sorted(by: { $0.1 && !$1.1 }) {
                if Date() > deadline { break }
                if hasItemSelection(l) { return true }
            }
        }
        return false
    }

    static func hasTextSelection(_ el: Element) -> Bool {
        if let rv = el.copySingleAttr(kAXSelectedTextRangeAttribute as String),
           CFGetTypeID(rv as CFTypeRef) == AXValueGetTypeID() {
            var range = CFRange()
            if AXValueGetValue(rv as! AXValue, .cfRange, &range) { return range.length > 0 }
        }
        guard let s = el.copySingleAttr(kAXSelectedTextAttribute as String) as? String else { return false }
        return !s.isEmpty
    }

    static func hasItemSelection(_ el: Element) -> Bool {
        for attr in itemSelectionAttrs {
            if let arr = el.copySingleAttr(attr) as? [Any], !arr.isEmpty { return true }
        }
        return false
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
