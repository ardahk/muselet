import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

public struct ElementRecord {
    public var ref: Int
    public var role: String          // short role name
    public var label: String
    /// Adobe "hot text" numeric controls surface as AX buttons whose label
    /// holds the widget name; clipSpeed is Premiere's Speed/Duration field.
    /// These render their value in the observation and accept typed digits.
    var isHotTextButton: Bool {
        role == "button" && (label.contains("HotText") || label == "clipSpeed")
    }
    public var value: Any?
    public var enabled: Bool
    public var selected: Bool
    public var focused: Bool
    public var frame: CGRect
    public var checked: Bool?        // checkbox/radio state
    public var inWebArea: Bool
    public var element: Element
}

public struct Observation {
    public var epoch: Int = 0
    public var app: String = ""
    public var pid: pid_t = 0
    public var window: String = ""
    public var focusedRef: Int?
    public var elements: [ElementRecord] = []
    public var text: String = ""
    public var diffText: String?
    public var full: Bool = false    // true when window session changed
    /// The walk hit the node cap or the deadline: absent elements may
    /// merely be past the cap (never conclude `gone` from absence alone).
    public var truncated: Bool = false
    public var axMs: Double = 0
    /// Set on the observation that just turned on the app's web AX tree
    /// ("manual" | "chromium" | "enhanced"), with the time spent waiting
    /// for the web area to populate (included in axMs).
    public var webAX: String?
    public var webAXWaitMs: Double?
    /// The app's web tree was switched on < ~2.5 s ago and Chrome is still
    /// debouncing: web content will appear on a later observation.
    public var webAXPending = false
    public var webLoaded: Bool?
    public var webBusy: Bool?
    /// Which root the walk used: "focused" | "main" | "windows" (frontmost
    /// AXWindows entry: the app has windows but none is focused/main, e.g.
    /// it isn't active) | "app" (window-like app children; no AXWindows) |
    /// "none" (no windows at all) | "menubar" | "all_windows" (scope "app").
    public var windowSource = "focused"
}

public enum ObserveError: Error, CustomStringConvertible {
    case appNotFound(String)
    case noWindow
    public var description: String {
        switch self {
        case .appNotFound(let n): return "app not found: \(n)"
        case .noWindow: return "no focused window"
        }
    }
}

// AX role -> short name in the observation text format.
let kRoleMap: [String: String] = [
    "AXButton": "button", "AXTextField": "textfield", "AXTextArea": "textarea",
    "AXCheckBox": "checkbox", "AXRadioButton": "radio", "AXPopUpButton": "popup",
    "AXMenuButton": "popup", "AXLink": "link", "AXSlider": "slider",
    "AXMenuItem": "menuitem", "AXRow": "row", "AXCell": "cell",
    "AXStaticText": "text", "AXComboBox": "combobox", "AXImage": "image",
    "AXDisclosureTriangle": "button", "AXTab": "tab", "AXIncrementor": "button",
    "AXBusyIndicator": "text", "AXValueIndicator": "slider",
    "AXMenuBarItem": "menuitem",
]

// Containers we traverse into but never emit. AXApplication has no frame
// (zero size): without it here an app-element root pruned everything.
let kContainerRoles: Set<String> = [
    "AXGroup", "AXScrollArea", "AXSplitGroup", "AXLayoutArea", "AXApplication",
]

// Scrollable containers that narrow the visible clip rect for descendants.
let kClipRoles: Set<String> = [
    "AXScrollArea", "AXList", "AXTable", "AXOutline", "AXWebArea",
]

// Label-carrying roles that are emitted only when they have a label.
let kLabelOnlyRoles: Set<String> = ["text", "image"]

public enum Walker {
    /// Union of the display bounds (global, top-left points). Active
    /// displays, else the online ones: while the display sleeps (or the
    /// screen is locked overnight) there are no active displays, and an
    /// empty union pruned every element as off-screen.
    public static func screenUnion() -> CGRect {
        func union(_ list: (UInt32, UnsafeMutablePointer<CGDirectDisplayID>?, UnsafeMutablePointer<UInt32>?) -> CGError) -> CGRect {
            var count: UInt32 = 0
            _ = list(0, nil, &count)
            guard count > 0 else { return .null }
            var ids = [CGDirectDisplayID](repeating: 0, count: Int(count))
            _ = list(count, &ids, &count)
            var u = CGRect.null
            for id in ids.prefix(Int(count)) { u = u.union(CGDisplayBounds(id)) }
            return u
        }
        let active = union(CGGetActiveDisplayList)
        return active.isNull ? union(CGGetOnlineDisplayList) : active
    }

    /// Nearest AXStaticText sibling directly above or left within ~60pt
    /// (unlabeled wheels/pickers pick up their column heading).
    static func nearbyStaticLabel(_ el: Element, _ siblings: [Element]) -> String? {
        let me = el.copyAttrs().frame
        guard me.width > 0 else { return nil }
        var best: (String, CGFloat)?
        for sib in siblings {
            let sa = sib.copyAttrs()
            guard sa.role == "AXStaticText", sa.frame.width > 0 else { continue }
            guard let txt = sa.value as? String ?? sa.title, !txt.isEmpty else { continue }
            let above = abs(sa.frame.midX - me.midX) < 30 && me.minY - sa.frame.maxY >= 0 && me.minY - sa.frame.maxY < 60
            let left = abs(sa.frame.midY - me.midY) < 30 && me.minX - sa.frame.maxX >= 0 && me.minX - sa.frame.maxX < 60
            if above || left {
                let dist = above ? me.minY - sa.frame.maxY : me.minX - sa.frame.maxX
                if best == nil || dist < best!.1 { best = (txt, dist) }
            }
        }
        return best?.0
    }

    static func label(of a: ElAttrs, role: String) -> String {
        if let t = a.title, !t.isEmpty { return t }
        if let d = a.desc, !d.isEmpty { return d }
        if role == "text", let v = a.value as? String, !v.isEmpty {
            return String(v.prefix(80))
        }
        if let p = a.placeholder, !p.isEmpty { return p }
        if let h = a.help, !h.isEmpty { return h }
        return ""
    }

    /// Extra label fallbacks for elements whose batch attrs gave "".
    /// Reuses `a` (already fetched) and reads at most 6 children.
    static func fallbackLabel(for el: Element, role: String,
                              attrs a: ElAttrs) -> String {
        // AXIdentifier if it looks human-readable.
        if let ident = el.copySingleAttr("AXIdentifier") as? String,
           !ident.isEmpty, !ident.hasPrefix("_NS:"), !ident.hasPrefix("_") {
            return ident
        }
        // A static-text (or text-field: Finder list names) child's title,
        // description or value wins over an image child's title/description
        // (<= 6 kids). Rows/cells also look one level into an AXCell/AXGroup
        // child: sidebar rows (Open panel, Finder) are row > cell > {image,
        // text "Downloads"}.
        func nonEmpty(_ s: String?) -> String? { (s?.isEmpty ?? true) ? nil : s }
        var imageLabel: String?
        func scan(_ kids: [Element], depth: Int) -> String? {
            for child in kids.prefix(6) {
                let ca = child.copyAttrs()
                switch ca.role {
                case "AXStaticText", "AXTextField":
                    if let t = nonEmpty(ca.title) ?? nonEmpty(ca.desc)
                        ?? nonEmpty(ca.value as? String) { return String(t.prefix(80)) }
                case "AXImage":
                    if imageLabel == nil { imageLabel = nonEmpty(ca.title) ?? nonEmpty(ca.desc) }
                case "AXCell", "AXGroup":
                    if depth == 0, role == "row" || role == "cell",
                       let t = scan(ca.children, depth: 1) { return t }
                default: break
                }
            }
            return nil
        }
        if let t = scan(a.children, depth: 0) ?? imageLabel { return t }
        // AXRoleDescription (e.g. "close button").
        if let rd = el.copySingleAttr("AXRoleDescription") as? String,
           !rd.isEmpty {
            return rd
        }
        return ""
    }

    /// Breadth-first walk of `root`. Emits interactive roles plus labeled
    /// static text / images; prunes zero-size, offscreen, and clipped nodes.
    /// Stops early once `interactiveCap` interactive records are collected.
    public static func walk(root: Element, deadline: Date, maxDepth: Int = 25,
                            interactiveCap: Int = .max) -> [ElementRecord] {
        walkInfo(root: root, deadline: deadline, maxDepth: maxDepth,
                 interactiveCap: interactiveCap).records
    }

    /// `walk` plus whether it stopped early (deadline or cap) with nodes
    /// still queued.
    public static func walkInfo(root: Element, deadline: Date, maxDepth: Int = 25,
                                interactiveCap: Int = .max)
        -> (records: [ElementRecord], truncated: Bool) {
        let screens = screenUnion()
        var interactive: [ElementRecord] = []
        var labeled: [ElementRecord] = []
        var truncated = false
        // (element, depth, clip rect, inWebArea)
        let rootAttrs = root.copyAttrs()
        var queue: [(Element, Int, CGRect, Bool, [Element])] =
            [(root, 0, rootAttrs.frame.isEmpty ? screens : rootAttrs.frame, false, [])]
        var qi = 0
        while qi < queue.count {
            if Date() > deadline || interactive.count >= interactiveCap {
                truncated = true
                break
            }
            let (el, depth, clip, web, siblings) = queue[qi]; qi += 1
            if depth > maxDepth { continue }
            let a = el.copyAttrs()
            let axRole = a.role ?? ""
            let frame = a.frame
            let isContainer = kContainerRoles.contains(axRole)
            let isClipper = kClipRoles.contains(axRole)
            let isWeb = web || axRole == "AXWebArea"
            let zeroSize = a.size.width <= 0 || a.size.height <= 0
            let offscreen = frame.width > 0 && !frame.intersects(screens)
            let clipped = depth > 0 && frame.width > 0 && !frame.intersects(clip)
            if !(zeroSize || offscreen || clipped) || isContainer {
                if let role = kRoleMap[axRole] {
                    var label = label(of: a, role: role)
                    if label.isEmpty && !clipped {
                        label = fallbackLabel(for: el, role: role, attrs: a)
                    }
                    // unlabeled/generic labels get a real one: title element,
                    // placeholder, or the nearest sibling static text just
                    // above/left (clock wheels, custom controls)
                    if label.isEmpty || label.lowercased() == role {
                        if let t = el.copySingleAttr("AXTitleUIElement") as? Element {
                            if let tl = t.copyAttrs().title, !tl.isEmpty { label = tl }
                        }
                    }
                    if label.isEmpty || label.lowercased() == role {
                        label = Self.nearbyStaticLabel(el, siblings) ?? label
                    }

                    let emit = kLabelOnlyRoles.contains(role) ? !label.isEmpty : true
                    if emit {
                        var checked: Bool? = nil
                        if role == "checkbox" || role == "radio" {
                            if let b = a.value as? Bool { checked = b }
                            else if let n = a.value as? NSNumber { checked = n.intValue != 0 }
                        }
                        var scalarValue: Any? = nil
                        if let s = a.value as? String { scalarValue = s }
                        else if let n = a.value as? NSNumber { scalarValue = n }
                        let rec = ElementRecord(
                            ref: 0, role: role, label: label, value: scalarValue,
                            enabled: a.enabled, selected: a.selected ?? false,
                            focused: a.focused, frame: frame, checked: checked,
                            inWebArea: isWeb, element: el)
                        if kLabelOnlyRoles.contains(role) { labeled.append(rec) }
                        else { interactive.append(rec) }
                    }
                }
            }
            // Carry clip into children: scroll-ish containers narrow it.
            var childClip = clip
            if isClipper && frame.width > 0 {
                childClip = clip.isEmpty ? frame : clip.intersection(frame)
            }
            if isContainer || !(zeroSize || offscreen || clipped) {
                for c in a.children { queue.append((c, depth + 1, childClip, isWeb, a.children)) }
            }
        }
        var all = interactive + labeled
        // unlabeled controls pick the nearest static text directly above
        // (x-centre inside its width, gap <= 80pt) or directly left
        // (y-centre inside its height, gap <= 120pt)
        let statics = all.filter { $0.role == "text" && !$0.label.isEmpty }
        for i in all.indices where all[i].label.isEmpty ||
            all[i].label.lowercased() == all[i].role {
            let f = all[i].frame
            var best: (String, CGFloat)?
            for t in statics where t.ref != all[i].ref {
                let tf = t.frame
                let above = tf.midX >= f.minX - 2 && tf.midX <= f.maxX + 2 &&
                    f.minY - tf.maxY >= 0 && f.minY - tf.maxY <= 80
                let left = tf.midY >= f.minY - 2 && tf.midY <= f.maxY + 2 &&
                    f.minX - tf.maxX >= 0 && f.minX - tf.maxX <= 120
                guard above || left else { continue }
                let d = above ? f.minY - tf.maxY : f.minX - tf.maxX
                if best == nil || d < best!.1 { best = (t.label, d) }
            }
            if let b = best { all[i].label = b.0 }
        }
        for i in all.indices { all[i].ref = i + 1 }   // provisional; Hands reassigns
        return (all, truncated)
    }
}

public enum Serializer {
    static func esc(_ s: String) -> String {
        s.replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
    }

    public static func line(_ e: ElementRecord) -> String {
        var s = "#\(e.ref) \(e.role) \"\(esc(e.label))\""
        if let v = e.value as? String, (e.role == "textfield" || e.role == "textarea" || e.role == "combobox") {
            s += " value=\"\(esc(v))\""
        } else if ["slider", "stepper", "incrementor", "picker"].contains(e.role)
                || e.isHotTextButton {
            if let n = e.value as? NSNumber {
                s += " value=\"\(n)\""
            } else if let v = e.value as? String, !v.isEmpty {
                s += " value=\"\(esc(v))\""
            }
        }
        if let c = e.checked { s += c ? " checked" : " unchecked" }
        if e.selected { s += " selected" }
        if !e.enabled { s += " disabled" }
        return s
    }

    public static func text(app: String, window: String, focusedRef: Int?, elements: [ElementRecord]) -> String {
        var out = "app: \(app) | window: \"\(esc(window))\""
        if let f = focusedRef { out += " | focused: #\(f)" }
        for e in elements { out += "\n" + line(e) }
        return out
    }
}

public enum Differ {
    static func key(_ e: ElementRecord) -> String {
        let f = e.frame
        func q(_ v: CGFloat) -> Int { Int((v / 8).rounded()) }
        return "\(e.role)|\(e.label)|\(q(f.minX)),\(q(f.minY)),\(q(f.width)),\(q(f.height))"
    }

    /// Pair new records to old records: exact key match, else unique
    /// role+label fallback (scrolled content). Returns (newRef->oldRef).
    public static func match(old: [ElementRecord], new: [ElementRecord]) -> [Int: Int] {
        var oldByKey: [String: [Int]] = [:]
        for e in old { oldByKey[key(e), default: []].append(e.ref) }
        var matched: [Int: Int] = [:]
        var usedOld = Set<Int>()
        // pass 1: exact key
        for e in new {
            if var refs = oldByKey[key(e)], let r = refs.first {
                refs.removeFirst()
                if refs.isEmpty { oldByKey.removeValue(forKey: key(e)) } else { oldByKey[key(e)] = refs }
                matched[e.ref] = r
                usedOld.insert(r)
            }
        }
        // pass 2: unique role+label fallback
        var byRL: [String: [ElementRecord]] = [:]
        for e in old where !usedOld.contains(e.ref) {
            byRL["\(e.role)|\(e.label)", default: []].append(e)
        }
        for e in new where matched[e.ref] == nil {
            let k = "\(e.role)|\(e.label)"
            if let cands = byRL[k], cands.count == 1 {
                matched[e.ref] = cands[0].ref
                usedOld.insert(cands[0].ref)
            }
        }
        return matched
    }

    /// Diff previous-epoch records vs current (refs already stabilized).
    public static func diff(old: [ElementRecord], new: [ElementRecord],
                            matched: [Int: Int]) -> String {
        let oldByRef = Dictionary(old.map { ($0.ref, $0) }, uniquingKeysWith: { first, _ in first })
        var matchedOld = Set(matched.values)
        var lines: [String] = []
        for e in new {
            if let oldRef = matched[e.ref], let o = oldByRef[oldRef] {
                var changes: [String] = []
                if "\(o.value ?? "")" != "\(e.value ?? "")" {
                    changes.append("value=\"\(Serializer.esc("\(e.value ?? "")"))\"")
                }
                if o.checked != e.checked, let c = e.checked {
                    changes.append(c ? "checked" : "unchecked")
                }
                if o.selected != e.selected { changes.append(e.selected ? "selected" : "unselected") }
                if o.enabled != e.enabled { changes.append(e.enabled ? "enabled" : "disabled") }
                // Only flag a move beyond the ~8 pt match tolerance.
                let f = e.frame, g = o.frame
                if abs(f.minX - g.minX) > 8 || abs(f.minY - g.minY) > 8
                    || abs(f.width - g.width) > 8 || abs(f.height - g.height) > 8 {
                    changes.append("moved")
                }
                if !changes.isEmpty { lines.append("~ #\(e.ref) \(changes.joined(separator: " "))") }
            } else {
                lines.append("+ \(Serializer.line(e))")
            }
        }
        for o in old where !matchedOld.contains(o.ref) {
            lines.append("- #\(o.ref)")
        }
        return lines.joined(separator: "\n")
    }
}

/// Chromium-family apps need AXManualAccessibility before the walk.
public func isChromiumFamily(bundleId: String?, bundleURL: URL?) -> Bool {
    if let b = bundleId {
        if WebAX.chromiumIds.contains(b) || b.contains("electron") || b.contains("chromium") {
            return true
        }
    }
    if let u = bundleURL {
        let fw = u.appendingPathComponent("Contents/Frameworks/Electron.framework")
        if FileManager.default.fileExists(atPath: fw.path) { return true }
    }
    return false
}

/// The stateful observation/act engine. Owns epochs, element handles, and
/// the per-window stable-ref session.
public final class Hands {
    public private(set) var epoch = 0
    private var current: [Int: ElementRecord] = [:]
    private(set) var previous: [ElementRecord] = []
    /// Turn on browsers' / Electron apps' web accessibility trees when
    /// observing them (CLI `--no-web-ax` disables it for comparisons).
    /// Which processes are already on lives in `webAXRegistry` (shared with
    /// the app's activation watcher).
    public var webAXEnabled = true
    var webAXRegistry = WebAX.Registry.shared
    /// Last web AX enable (result + populate wait), for the CLI / debugging.
    public private(set) var lastWebAX: (result: WebAX.EnableResult, wait: WebAX.WaitResult?)?
    private var sessionKey = ""
    /// First epoch of the current window session; acts carrying an older
    /// epoch were planned against another window -> stale_ref.
    public private(set) var sessionStartEpoch = 0
    /// Refs minted in the current window session.
    private var sessionRefs: Set<Int> = []
    /// Element handle for every ref minted recently (any session; refs are
    /// unique so there is no aliasing). Kept across epochs so `gone #ref`
    /// can test liveness when the ref fell past the node cap.
    private var knownElements: [Int: Element] = [:]
    /// Recently left window sessions (LRU, 4): returning to a window (e.g.
    /// after an Open dialog or popover window closes) resumes its refs, so
    /// refs stay stable while the element persists.
    private struct SessionSnapshot {
        var previous: [ElementRecord]
        var refs: Set<Int>
        var startEpoch: Int
    }
    private var pastSessions: [String: SessionSnapshot] = [:]
    private var pastOrder: [String] = []

    /// The app owning the topmost normal-layer on-screen window that is
    /// not `ownPid` — i.e. the next app in z-order behind our UI.
    static func nextAppInZOrder(excluding ownPid: pid_t)
        -> NSRunningApplication? {
        let infos = CGWindowListCopyWindowInfo(
            [.optionOnScreenOnly, .excludeDesktopElements],
            kCGNullWindowID) as? [[String: Any]] ?? []
        for w in infos {
            guard let pid = w[kCGWindowOwnerPID as String] as? pid_t,
                  pid != ownPid,
                  (w[kCGWindowLayer as String] as? Int) == 0,
                  let app = NSRunningApplication(processIdentifier: pid)
            else { continue }
            return app
        }
        return nil
    }

    public weak var delegate: HandsDelegate?
    /// Injectable script runner for the `script` op (cached NSAppleScript).
    public var scripts: ScriptRunning = AppleScriptRunner()
    /// Frontmost-app queries/activation (mocked in tests).
    public var apps: AppControlling = WorkspaceApps()

    public private(set) var lastPid: pid_t = 0
    /// Set when something outside an observation intentionally switched
    /// apps (a skill such as open_app); the next input act binds to the
    /// current frontmost app instead of re-activating the observed one.
    public private(set) var focusRebindPending = false

    // Test seams: replace the fused re-observation / settle wait / label search.
    var observeOverride: (() throws -> Observation)?
    var settleOverride: ((pid_t) -> Double)?
    var labelSearchOverride: ((String, pid_t) -> Bool)?
    /// Synthetic typing (tests record instead of posting key events).
    var typeTextOverride: ((String) -> Void)?
    /// Keystroke-app typing (Calculator); tests record instead of posting.
    var typeKeystrokesOverride: ((String) -> Void)?
    /// Media-key posting / level read-back (tests: no real events).
    var mediaKeyPostOverride: ((MediaKey) -> Void)?
    var mediaLevelOverride: ((MediaKey.Kind) -> [String: AnyHashable]?)?
    /// Max wait for a volume / brightness change after a media key.
    var mediaReadBackTimeout: TimeInterval = 0.4
    /// AX application element for a pid (tests pass a mock app).
    var axAppOverride: ((pid_t) -> Element)?

    // Process-wide monotonic ref counter: a ref number is never reused,
    // so a ref from a previous window can never alias a new element.
    private static let refLock = NSLock()
    private static var refCounter = 0
    static func mintRef() -> Int {
        refLock.lock(); defer { refLock.unlock() }
        refCounter += 1
        return refCounter
    }

    public init() {}

    public var currentEpoch: Int { epoch }

    /// A skill or other non-observed action switched apps on purpose.
    public func noteExternalFocusChange() { focusRebindPending = true }

    func appElement(forAppName name: String?) throws -> (Element, NSRunningApplication) {
        let app: NSRunningApplication?
        if let n = name {
            app = NSWorkspace.shared.runningApplications.first {
                ($0.localizedName ?? "").localizedCaseInsensitiveCompare(n) == .orderedSame
                    || ($0.localizedName ?? "").localizedCaseInsensitiveContains(n)
            }
            guard let a = app else { throw ObserveError.appNotFound(n) }
        } else {
            let front = NSWorkspace.shared.frontmostApplication
            // Muselet's own UI key (panel, pill): never observe our
            // windows — target the next app in z-order instead.
            app = front?.processIdentifier == getpid()
                ? Hands.nextAppInZOrder(excluding: getpid()) : front
            guard let a = app else { throw ObserveError.appNotFound("<frontmost>") }
        }
        let running = app!
        let el = AXUIElementCreateApplication(running.processIdentifier)
        let node = AXNode(el)
        node.setMessagingTimeout(0.25)
        return (node, running)
    }

    /// Turn on the app's web accessibility tree once per process
    /// (Electron: AXManualAccessibility; Chromium browsers: that plus
    /// AXEnhancedUserInterface; Safari/Gecko browsers: AXEnhancedUserInterface).
    /// Returns the result when it was set just now, else nil.
    func ensureWebAX(app: Element, pid: pid_t, bundleId: String?, bundleURL: URL?,
                     launchDate: Date?) -> WebAX.EnableResult? {
        guard webAXEnabled else { return nil }
        return webAXRegistry.ensure(pid: pid, bundleId: bundleId, bundleURL: bundleURL,
                                    launchDate: launchDate, app: app)
    }

    /// scope: "focused_window" | "app" | "menubar". app: optional app name.
    public func observe(scope: String = "focused_window", app appName: String? = nil,
                        maxNodes: Int = 150, diff: Bool = true) throws -> Observation {
        let t0 = Date()
        let deadline = t0.addingTimeInterval(1.5)
        let (appEl, running) = try appElement(forAppName: appName)
        var obs = Observation()
        obs.app = running.localizedName ?? "?"
        obs.pid = running.processIdentifier
        let webOn = ensureWebAX(app: appEl, pid: running.processIdentifier,
                                bundleId: running.bundleIdentifier,
                                bundleURL: running.bundleURL,
                                launchDate: running.launchDate)

        // An app launched a moment ago (open_app) may not have a window
        // yet: give it up to ~0.8 s to show one before falling back.
        let justLaunched = running.launchDate.map { t0.timeIntervalSince($0) < 5 } ?? false
        let picked = Self.observationRoots(
            app: appEl, scope: scope,
            waitForWindowUntil: justLaunched ? t0.addingTimeInterval(0.8) : nil)
        let roots = picked.roots
        obs.window = picked.window
        // Just turned on the web AX tree: let the web area populate
        // (<= 300 ms, once per process) so this observation already sees
        // it. Skipped when it can't populate that fast (Chrome's 2 s debounce).
        var webWait: WebAX.WaitResult?
        if let webOn {
            if !webOn.delayed, scope != "menubar", let root = roots.first {
                webWait = WebAX.waitForWebArea(root: root)
            }
            lastWebAX = (webOn, webWait)
        } else if webAXEnabled, scope != "menubar", let root = roots.first,
                  let left = webAXRegistry.populateTimeLeft(pid: obs.pid) {
            // The activation watcher switched it on a moment ago: wait the rest.
            webWait = WebAX.waitForWebArea(root: root, timeout: left)
        }
        var out = processObservation(roots: roots, app: obs.app,
                                     window: obs.window, pid: obs.pid,
                                     maxNodes: maxNodes, diff: diff,
                                     deadline: deadline, appEl: appEl, t0: t0)
        if let webOn { out.webAX = webOn.mode.rawValue }
        if let w = webWait { out.webAXWaitMs = w.ms }
        out.webAXPending = webAXEnabled && webAXRegistry.pending(pid: obs.pid)
        if let root = roots.first, let area = firstWebArea(root) {
            if let loaded = webBool(area, "AXLoaded") { out.webLoaded = loaded }
            if let busy = webBool(area, "AXElementBusy") { out.webBusy = busy }
        }
        out.windowSource = picked.source
        return out
    }

    /// Window the user is looking at in `app`: AXFocusedWindow, else
    /// AXMainWindow, else the frontmost usable AXWindows entry (AXWindows
    /// is front-to-back; minimized / zero-size / off-screen ones skipped).
    /// An app that isn't active (launched in the background, or its key
    /// window just closed) reports no focused or main window although its
    /// windows are on screen (TextEdit after open_app). nil = no window.
    public static func pickWindow(app: Element) -> (window: Element, source: String)? {
        if let w = axElement(app.copySingleAttr(kAXFocusedWindowAttribute as String)) {
            return (w, "focused")
        }
        if let w = axElement(app.copySingleAttr(kAXMainWindowAttribute as String)) {
            return (w, "main")
        }
        let screens = Walker.screenUnion()
        for w in axElements(app.copySingleAttr(kAXWindowsAttribute as String)) {
            if (w.copySingleAttr(kAXMinimizedAttribute as String) as? Bool) == true { continue }
            let f = w.copyAttrs().frame
            guard f.width > 0, f.height > 0 else { continue }
            if !screens.isNull, !screens.isEmpty, !f.intersects(screens) { continue }
            return (w, "windows")
        }
        return nil
    }

    static func windowTitle(_ w: Element) -> String {
        (w.copySingleAttr(kAXTitleAttribute as String) as? String) ?? w.copyAttrs().title ?? ""
    }

    /// Walk roots for `scope`:
    ///  - "menubar": the AXMenuBar (else the app element).
    ///  - "app": every window-like root (AXWindows, sheets/popovers/drawers
    ///    that are app children, open menus), front to back.
    ///  - else (focused_window): `pickWindow`, polling until
    ///    `waitForWindowUntil` when there is none yet; then the app-scope
    ///    roots (window-like app children outside AXWindows); else none.
    /// The menu bar is never a fallback root (its File/Edit/Format titles
    /// would satisfy `appears` predicates).
    static func observationRoots(app: Element, scope: String,
                                 waitForWindowUntil: Date? = nil)
        -> (roots: [Element], window: String, source: String) {
        switch scope {
        case "menubar":
            if let bar = axElement(app.copySingleAttr("AXMenuBar")) { return ([bar], "", "menubar") }
            return ([app], "", "menubar")
        case "app":
            let all = labelSearchRoots(app: app)
            let title = all.first { $0.window }.map { windowTitle($0.el) } ?? ""
            return (all.map(\.el), title, all.isEmpty ? "none" : "all_windows")
        default:
            var pick = pickWindow(app: app)
            if pick == nil, let until = waitForWindowUntil {
                while pick == nil && Date() < until {
                    usleep(50_000)
                    pick = pickWindow(app: app)
                }
            }
            if let p = pick { return ([p.window], windowTitle(p.window), p.source) }
            let rest = labelSearchRoots(app: app).filter {
                !$0.window || ($0.el.copySingleAttr(kAXMinimizedAttribute as String) as? Bool) != true
            }
            if !rest.isEmpty {
                let title = rest.first { $0.window }.map { windowTitle($0.el) } ?? ""
                return (rest.map(\.el), title, "app")
            }
            return ([], "", "none")
        }
    }

    /// Shared tail of observe(): walk, ref/session bookkeeping, serialize, diff.
    /// Exposed for tests (mock roots).
    func processObservation(roots: [Element], app: String, window: String,
                            pid: pid_t, maxNodes: Int, diff: Bool,
                            deadline: Date, appEl: Element?, t0: Date) -> Observation {
        var obs = Observation()
        obs.app = app; obs.window = window; obs.pid = pid

        var records: [ElementRecord] = []
        var truncated = false
        for (i, r) in roots.enumerated() {
            let w = Walker.walkInfo(root: r, deadline: deadline, interactiveCap: maxNodes * 2)
            records.append(contentsOf: w.records)
            truncated = truncated || w.truncated
            if Date() > deadline {
                if i < roots.count - 1 { truncated = true }
                break
            }
        }
        if records.count > maxNodes {
            // keep the focused element and text inputs past the cap (e.g. a
            // Gmail reply box at the bottom of a long thread)
            let pinned = records.dropFirst(maxNodes).filter {
                $0.focused || ["textarea", "textfield", "searchfield"].contains($0.role)
            }.prefix(20)
            records = Array(records.prefix(maxNodes)) + pinned
            truncated = true
        }
        // A focused text input the walk never reached (deep web DOMs such as
        // Gmail's reply body, past maxDepth) is still added.
        if let axApp = (appEl as? AXNode)?.el {
            var fe: CFTypeRef?
            if AXUIElementCopyAttributeValue(axApp, kAXFocusedUIElementAttribute as CFString, &fe) == .success,
               let fe {
                let fnode = AXNode(fe as! AXUIElement)
                let a = fnode.copyAttrs()
                if let role = kRoleMap[a.role ?? ""], ["textarea", "textfield", "combobox"].contains(role),
                   !records.contains(where: { sameElement($0.element, fnode) }) {
                    var web = false
                    var p = fnode.copySingleAttr(kAXParentAttribute as String) as? Element
                    for _ in 0..<60 {
                        guard let cur = p else { break }
                        if cur.copyAttrs().role == "AXWebArea" { web = true; break }
                        p = cur.copySingleAttr(kAXParentAttribute as String) as? Element
                    }
                    var label = Walker.label(of: a, role: role)
                    if label.isEmpty { label = role }
                    records.append(ElementRecord(
                        ref: 0, role: role, label: label, value: a.value as? String,
                        enabled: a.enabled, selected: a.selected ?? false,
                        focused: true, frame: a.frame, checked: nil,
                        inWebArea: web, element: fnode))
                }
            }
        }
        obs.truncated = truncated

        // Window session: same app+window ELEMENT keeps stable refs (titles
        // may change); a different window starts a new session (fresh refs
        // from the process-wide counter, never reused) and replaces the
        // diff with the full text.
        let key = "\(pid)|\(roots.first?.stableId ?? 0)"
        var resumed = false
        if key != sessionKey {
            if !sessionKey.isEmpty {
                pastSessions[sessionKey] = SessionSnapshot(
                    previous: previous, refs: sessionRefs, startEpoch: sessionStartEpoch)
                pastOrder.removeAll { $0 == sessionKey }
                pastOrder.append(sessionKey)
                while pastOrder.count > 4 { pastSessions.removeValue(forKey: pastOrder.removeFirst()) }
            }
            sessionKey = key
            if let snap = pastSessions.removeValue(forKey: key) {
                pastOrder.removeAll { $0 == key }
                previous = snap.previous
                sessionRefs = snap.refs
                sessionStartEpoch = snap.startEpoch
                resumed = true
            } else {
                previous = []
                sessionRefs = []
                sessionStartEpoch = epoch + 1      // the epoch this observation gets
            }
            obs.full = true                        // the brain last saw another window
        }

        // Stabilize refs against the previous epoch (or the resumed
        // session's last epoch). matched maps provisional ref -> old ref.
        let provMatched = (obs.full && !resumed) ? [:] : Differ.match(old: previous, new: records)
        var matched: [Int: Int] = [:]           // stableRef -> oldRef
        for i in records.indices {
            let prov = records[i].ref
            if let oldRef = provMatched[prov] {
                records[i].ref = oldRef
                matched[oldRef] = oldRef
            } else {
                records[i].ref = Self.mintRef()
            }
        }
        if knownElements.count > 5000 { knownElements = [:] }
        for r in records {
            sessionRefs.insert(r.ref)
            knownElements[r.ref] = r.element
        }

        // Focused element -> ref.
        var focusedRef: Int? = nil
        if let appEl {
            var focusedEl: CFTypeRef?
            if let axApp = (appEl as? AXNode)?.el,
               AXUIElementCopyAttributeValue(axApp, kAXFocusedUIElementAttribute as CFString, &focusedEl) == .success,
               let fe = focusedEl {
                let fnode = AXNode(fe as! AXUIElement)
                for i in records.indices where sameElement(records[i].element, fnode) {
                    focusedRef = records[i].ref
                    records[i].focused = true
                }
            }
        }
        if focusedRef == nil {
            for i in records.indices where records[i].focused { focusedRef = records[i].ref }
        }
        obs.focusedRef = focusedRef
        obs.elements = records

        epoch += 1
        obs.epoch = epoch
        if diff && !obs.full {
            obs.diffText = Differ.diff(old: previous, new: records, matched: matched)
        } else if diff && obs.full {
            obs.diffText = ""
        }
        previous = records
        current = Dictionary(records.map { ($0.ref, $0) }, uniquingKeysWith: { first, _ in first })
        obs.text = Serializer.text(app: obs.app, window: obs.window,
                                   focusedRef: focusedRef, elements: records)
        obs.axMs = Date().timeIntervalSince(t0) * 1000
        lastPid = obs.pid
        focusRebindPending = false
        return obs
    }

    /// Resolve an element ref for an act call. stale_ref when the ref was
    /// not minted in the current window session, is absent from the latest
    /// epoch, or `epoch` predates the session (planned against another window).
    public func element(ref: Int, epoch e: Int? = nil) throws -> ElementRecord {
        if let e, e < sessionStartEpoch { throw HandsError.staleRef(ref) }
        guard sessionRefs.contains(ref), let r = current[ref] else {
            throw HandsError.staleRef(ref)
        }
        return r
    }

    public func record(ref: Int) -> ElementRecord? { current[ref] }

    /// Element handle for a recently minted ref (any session).
    func knownElement(ref: Int) -> Element? { knownElements[ref] }
}

/// First AXWebArea in a window — BFS, shallow (page-load signal lives on it).
func firstWebArea(_ root: any Element) -> (any Element)? {
    func kids(_ el: any Element) -> [any Element] {
        let v = el.copySingleAttr(kAXChildrenAttribute)
        if let els = v as? [any Element] { return els }
        if let els = v as? [AXUIElement] { return els.map { AXNode($0) as any Element } }
        return []
    }
    var queue = kids(root).map { ($0, 1) }
    var seen = 0
    while !queue.isEmpty && seen < 400 {
        let (el, depth) = queue.removeFirst(); seen += 1
        if (el.copySingleAttr(kAXRoleAttribute) as? String) == "AXWebArea" {
            return el
        }
        if depth < 15 {
            for child in kids(el) { queue.append((child, depth + 1)) }
        }
    }
    return nil
}

func webBool(_ el: any Element, _ name: String) -> Bool? {
    let v = el.copySingleAttr(name)
    if let b = v as? Bool { return b }
    if let n = v as? NSNumber { return n.boolValue }
    return nil
}
