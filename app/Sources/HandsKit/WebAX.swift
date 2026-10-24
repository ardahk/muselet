import AppKit
import ApplicationServices
import Foundation

/// How an app's web content is exposed to accessibility clients.
public enum WebAXMode: String {
    /// Electron apps: `AXManualAccessibility = true` on the app element.
    case manual
    /// Chromium browsers (Chrome, Edge, Brave, Arc, ...): `AXManualAccessibility`
    /// plus `AXEnhancedUserInterface`. Chrome answers AXManualAccessibility
    /// with kAXErrorAttributeUnsupported and turns its web tree on for
    /// AXEnhancedUserInterface only after a 2 s debounce
    /// (chrome_browser_application_mac.mm, kTwoSecondDelay).
    case chromium
    /// WebKit (Safari) and Gecko (Firefox, Zen) browsers:
    /// `AXEnhancedUserInterface = true`. Restricted to browser bundle ids:
    /// AppKit animates AX-driven window moves while it is set.
    case enhanced
}

/// Turning on the web accessibility tree of browsers / Electron apps, so
/// web pages are observable through AX instead of screenshots.
public enum WebAX {
    public static let manualAttribute = "AXManualAccessibility"
    public static let enhancedAttribute = "AXEnhancedUserInterface"
    /// Max time the first observe of a newly enabled app waits for the web
    /// area to populate.
    public static let populateTimeout: TimeInterval = 0.3
    /// Chrome's AXEnhancedUserInterface debounce.
    public static let chromiumDelay: TimeInterval = 2.0

    /// Chromium-based browsers (need AXEnhancedUserInterface).
    static let chromiumBrowserIds: Set<String> = [
        "com.google.Chrome", "com.google.Chrome.beta", "com.google.Chrome.dev",
        "com.google.Chrome.canary", "org.chromium.Chromium",
        "com.microsoft.edgemac", "com.microsoft.edgemac.Beta", "com.microsoft.edgemac.Dev",
        "com.microsoft.edgemac.Canary",
        "com.brave.Browser", "com.brave.Browser.beta", "com.brave.Browser.nightly",
        "com.vivaldi.Vivaldi", "com.operasoftware.Opera", "com.operasoftware.OperaGX",
        "company.thebrowser.Browser", "company.thebrowser.dia",   // Arc, Dia
    ]

    /// Chromium-family apps (browsers + Electron apps we know by id).
    static let chromiumIds: Set<String> = chromiumBrowserIds.union([
        "com.tinyspeck.slackmacgap", "com.hnc.Discord", "com.microsoft.VSCode",
        "com.visualstudio.code.oss", "com.figma.Desktop", "notion.id",
        "com.spotify.client", "com.todoist.mac.Todoist", "com.microsoft.teams2",
    ])

    /// WebKit / Gecko browsers that need AXEnhancedUserInterface.
    static let enhancedIds: Set<String> = [
        "com.apple.Safari", "com.apple.SafariTechnologyPreview",
        "org.mozilla.firefox", "org.mozilla.firefoxdeveloperedition", "org.mozilla.nightly",
        "app.zen-browser.zen", "io.gitlab.librewolf-community", "net.waterfox.waterfox",
        "org.torproject.torbrowser", "net.mullvad.mullvadbrowser", "one.ablaze.floorp",
        "com.kagi.kagimacOS",                                       // Orion (WebKit)
    ]

    /// Which attribute(s) (if any) enable web content AX for this app.
    public static func mode(bundleId: String?, bundleURL: URL?) -> WebAXMode? {
        if let b = bundleId {
            if enhancedIds.contains(b) { return .enhanced }
            if chromiumBrowserIds.contains(b) { return .chromium }
        }
        if isChromiumFamily(bundleId: bundleId, bundleURL: bundleURL) { return .manual }
        return nil
    }

    /// Outcome of turning a mode on (AXError raw values; 0 = success).
    public struct EnableResult: Equatable {
        public var mode: WebAXMode
        public var manualError: Int32?
        public var enhancedError: Int32?
        /// AXEnhancedUserInterface was already true: left untouched.
        public var enhancedAlreadyOn = false
        /// The web tree can't populate within `populateTimeout`
        /// (Chromium browser that ignored AXManualAccessibility: 2 s debounce).
        public var delayed: Bool {
            mode == .chromium && manualError != 0 && !enhancedAlreadyOn
        }
    }

    /// Set the mode's attribute(s) on the app element. Never re-sets an
    /// AXEnhancedUserInterface that is already true (each set restarts
    /// Chrome's 2 s debounce).
    @discardableResult
    public static func enable(_ mode: WebAXMode, app: Element) -> EnableResult {
        var r = EnableResult(mode: mode)
        if mode == .manual || mode == .chromium {
            r.manualError = setBool(app, manualAttribute, true)
        }
        if mode == .enhanced || mode == .chromium {
            if (app.copySingleAttr(enhancedAttribute) as? Bool) == true {
                r.enhancedAlreadyOn = true
            } else {
                r.enhancedError = setBool(app, enhancedAttribute, true)
            }
        }
        return r
    }

    /// AXError raw value of setting a boolean attribute (0 = success).
    static func setBool(_ el: Element, _ attr: String, _ v: Bool) -> Int32 {
        if let n = el as? AXNode {
            n.setMessagingTimeout(0.25)
            return AXUIElementSetAttributeValue(
                n.el, attr as CFString, (v ? kCFBooleanTrue : kCFBooleanFalse)!).rawValue
        }
        return el.setAttr(attr, v) ? 0 : AXError.failure.rawValue
    }

    /// Breadth-first search for the first AXWebArea under `root`
    /// (bounded by node count and deadline).
    public static func findWebArea(in root: Element, deadline: Date,
                                   maxNodes: Int = 400, maxDepth: Int = 16) -> Element? {
        var queue: [(Element, Int)] = [(root, 0)]
        var qi = 0
        while qi < queue.count && qi < maxNodes && Date() < deadline {
            let (el, depth) = queue[qi]; qi += 1
            let a = el.copyAttrs()
            if a.role == "AXWebArea" { return el }
            if depth >= maxDepth { continue }
            // Leaves / chrome never contain a web area: skip their children.
            if let r = a.role, kSkipRoles.contains(r) { continue }
            for c in a.children { queue.append((c, depth + 1)) }
        }
        return nil
    }

    private static let kSkipRoles: Set<String> = [
        "AXButton", "AXStaticText", "AXImage", "AXTextField", "AXCheckBox",
        "AXRadioButton", "AXMenuButton", "AXPopUpButton", "AXSlider", "AXLink",
        "AXMenuBar", "AXMenuBarItem", "AXIncrementor", "AXDisclosureTriangle",
        "AXToolbar",
    ]

    public struct WaitResult {
        public var populated: Bool
        public var foundWebArea: Bool
        public var ms: Double
        public var polls: Int
    }

    /// Poll (every ~25 ms) until an AXWebArea under `root` has children,
    /// bounded by `timeout` (<= 300 ms by default).
    public static func waitForWebArea(root: Element,
                                      timeout: TimeInterval = populateTimeout) -> WaitResult {
        let t0 = Date()
        let end = t0.addingTimeInterval(min(timeout, populateTimeout))
        var area: Element?
        var polls = 0
        while true {
            polls += 1
            if area == nil { area = findWebArea(in: root, deadline: end) }
            if let a = area {
                if !a.isAlive() { area = nil }
                else if !a.copyAttrs().children.isEmpty {
                    return WaitResult(populated: true, foundWebArea: true,
                                      ms: Date().timeIntervalSince(t0) * 1000, polls: polls)
                }
            }
            let left = end.timeIntervalSinceNow
            if left <= 0 { break }
            usleep(UInt32(min(0.025, left) * 1_000_000))
        }
        return WaitResult(populated: false, foundWebArea: area != nil,
                          ms: Date().timeIntervalSince(t0) * 1000, polls: polls)
    }

    // MARK: - Per-process registry (thread-safe, shared)

    /// Which processes already had their web tree turned on. Shared by
    /// every `Hands` and the app's activation watcher, so a browser is
    /// enabled once per process, whoever gets there first.
    public final class Registry {
        public static let shared = Registry()
        private let lock = NSLock()
        private struct Entry {
            var launch: Date
            var result: EnableResult?
            var at: Date
        }
        private var entries: [pid_t: Entry] = [:]
        /// Global switch (CLI `--no-web-ax`, comparisons).
        public var isEnabled = true

        public init() {}

        /// Turn the app's web tree on once per process. Returns the result
        /// when it was turned on just now (the caller may wait for the
        /// web area), nil if already handled or not a web app.
        /// `app`: injectable app element (tests); default AX app element.
        public func ensure(pid: pid_t, bundleId: String?, bundleURL: URL?,
                           launchDate: Date?, app: Element? = nil) -> EnableResult? {
            guard isEnabled, pid > 0, pid != getpid() else { return nil }
            let stamp = launchDate ?? .distantPast
            lock.lock()
            if let e = entries[pid], e.launch == stamp { lock.unlock(); return nil }
            if entries.count > 256 { entries = [:] }
            // Claim before the (possibly slow) AX calls: concurrent callers skip.
            entries[pid] = Entry(launch: stamp, result: nil, at: Date())
            lock.unlock()
            // Not a web app: nothing to do, and never re-checked for this process.
            guard let mode = WebAX.mode(bundleId: bundleId, bundleURL: bundleURL) else { return nil }
            let el = app ?? AXNode(AXUIElementCreateApplication(pid))
            let r = WebAX.enable(mode, app: el)
            lock.lock()
            entries[pid]?.result = r
            lock.unlock()
            return r
        }

        /// Turned on for this process (and when)?
        public func enabledAt(pid: pid_t) -> Date? {
            lock.lock(); defer { lock.unlock() }
            guard let e = entries[pid], e.result != nil else { return nil }
            return e.at
        }

        /// Populate time left for a process someone else (the activation
        /// watcher) just switched on (< `populateTimeout` ago, not delayed).
        public func populateTimeLeft(pid: pid_t, now: Date = Date()) -> TimeInterval? {
            lock.lock(); defer { lock.unlock() }
            guard let e = entries[pid], let r = e.result, !r.delayed else { return nil }
            let left = WebAX.populateTimeout - now.timeIntervalSince(e.at)
            return left > 0.01 ? left : nil
        }

        /// The Chromium debounce for `pid` is still running.
        public func pending(pid: pid_t, now: Date = Date()) -> Bool {
            lock.lock(); defer { lock.unlock() }
            guard let e = entries[pid], let r = e.result, r.delayed else { return false }
            return now.timeIntervalSince(e.at) < WebAX.chromiumDelay + 0.5
        }

        /// Turn off what we turned on (app quit), so browsers don't keep
        /// enhanced UI / full accessibility after Muselet exits.
        public func restoreAll() {
            lock.lock()
            let all = entries
            entries = [:]
            lock.unlock()
            for (pid, e) in all {
                guard let r = e.result,
                      let ra = NSRunningApplication(processIdentifier: pid),
                      (ra.launchDate ?? .distantPast) == e.launch else { continue }
                // The set's AXError is unreliable (Chrome/Safari/Zen answer
                // -25208 yet apply it): undo whatever we attempted.
                let el = AXNode(AXUIElementCreateApplication(pid))
                if let m = r.manualError, m != AXError.attributeUnsupported.rawValue {
                    _ = WebAX.setBool(el, manualAttribute, false)
                }
                if r.enhancedError != nil, !r.enhancedAlreadyOn {
                    _ = WebAX.setBool(el, enhancedAttribute, false)
                }
            }
        }

        /// Test seam.
        func reset() {
            lock.lock(); entries = [:]; lock.unlock()
        }
    }

    // MARK: - Pre-enable on activation

    private static var activationObserver: NSObjectProtocol?
    private static let prewarmQueue = DispatchQueue(label: "hands.webax.prewarm", qos: .utility)

    /// Turn on the web tree of browsers / Electron apps as soon as they
    /// become frontmost (and of the current frontmost app now), off the
    /// main thread. Chrome needs ~2 s after the switch, so doing it at
    /// activation means the tree is ready by the time the user has spoken.
    public static func watchActivations() {
        guard activationObserver == nil else { return }
        if let front = NSWorkspace.shared.frontmostApplication { prewarm(front) }
        activationObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: nil) { n in
            if let app = n.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication {
                prewarm(app)
            }
        }
    }

    static func prewarm(_ app: NSRunningApplication) {
        guard mode(bundleId: app.bundleIdentifier, bundleURL: app.bundleURL) != nil else { return }
        let pid = app.processIdentifier, bid = app.bundleIdentifier
        let url = app.bundleURL, launch = app.launchDate
        prewarmQueue.async {
            _ = Registry.shared.ensure(pid: pid, bundleId: bid, bundleURL: url, launchDate: launch)
        }
    }
}
