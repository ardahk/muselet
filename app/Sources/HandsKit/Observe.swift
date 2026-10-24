import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

public struct ElementRecord {
    public var ref: Int
    public var role: String          // short role name
    public var label: String
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

// Containers we traverse into but never emit.
let kContainerRoles: Set<String> = [
    "AXGroup", "AXScrollArea", "AXSplitGroup", "AXLayoutArea",
]

// Scrollable containers that narrow the visible clip rect for descendants.
let kClipRoles: Set<String> = [
    "AXScrollArea", "AXList", "AXTable", "AXOutline", "AXWebArea",
]

// Label-carrying roles that are emitted only when they have a label.
let kLabelOnlyRoles: Set<String> = ["text", "image"]

public enum Walker {
    public static func screenUnion() -> CGRect {
        var count: UInt32 = 0
        CGGetActiveDisplayList(0, nil, &count)
        guard count > 0 else { return .null }
        var ids = [CGDirectDisplayID](repeating: 0, count: Int(count))
        CGGetActiveDisplayList(count, &ids, &count)
        var u = CGRect.null
        for id in ids.prefix(Int(count)) { u = u.union(CGDisplayBounds(id)) }
        return u
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
        // First AXImage / AXStaticText child's title or description (<=6 kids).
        for child in a.children.prefix(6) {
            let ca = child.copyAttrs()
            if ca.role == "AXImage" || ca.role == "AXStaticText" {
                if let t = ca.title, !t.isEmpty { return t }
                if let d = ca.desc, !d.isEmpty { return d }
            }
        }
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
        var queue: [(Element, Int, CGRect, Bool)] =
            [(root, 0, rootAttrs.frame.isEmpty ? screens : rootAttrs.frame, false)]
        var qi = 0
        while qi < queue.count {
            if Date() > deadline || interactive.count >= interactiveCap {
                truncated = true
                break
            }
            let (el, depth, clip, web) = queue[qi]; qi += 1
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
                for c in a.children { queue.append((c, depth + 1, childClip, isWeb)) }
            }
        }
        var all = interactive + labeled
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
        let oldByRef = Dictionary(uniqueKeysWithValues: old.map { ($0.ref, $0) })
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
    let ids = [
        "com.google.Chrome", "com.google.Chrome.canary", "org.chromium.Chromium",
        "com.microsoft.edgemac", "com.brave.Browser", "com.vivaldi.Vivaldi",
        "com.operasoftware.Opera", "com.tinyspeck.slackmacgap", "com.hnc.Discord",
        "com.microsoft.VSCode", "com.visualstudio.code.oss", "com.figma.Desktop",
        "notion.id", "com.spotify.client", "com.todoist.mac.Todoist",
    ]
    if let b = bundleId {
        if ids.contains(b) || b.contains("electron") || b.contains("chromium") { return true }
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
    private var manualAXPids: Set<pid_t> = []
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
            app = NSWorkspace.shared.frontmostApplication
            guard let a = app else { throw ObserveError.appNotFound("<frontmost>") }
        }
        let running = app!
        let el = AXUIElementCreateApplication(running.processIdentifier)
        let node = AXNode(el)
        node.setMessagingTimeout(0.25)
        if !manualAXPids.contains(running.processIdentifier),
           isChromiumFamily(bundleId: running.bundleIdentifier, bundleURL: running.bundleURL) {
            _ = node.setAttr("AXManualAccessibility", true)
            manualAXPids.insert(running.processIdentifier)
        }
        return (node, running)
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

        var roots: [Element]
        var windowEl: AXUIElement?
        switch scope {
        case "menubar":
            if let bar = appEl.copySingleAttr("AXMenuBar"),
               CFGetTypeID(bar as CFTypeRef) == AXUIElementGetTypeID() {
                roots = [AXNode(bar as! AXUIElement)]
            } else { roots = [appEl] }
        default:
            var winRef: CFTypeRef?
            if AXUIElementCopyAttributeValue(
                (appEl as! AXNode).el, kAXFocusedWindowAttribute as CFString, &winRef) == .success,
               let w = winRef { windowEl = (w as! AXUIElement) }
            if windowEl == nil,
               AXUIElementCopyAttributeValue(
                   (appEl as! AXNode).el, kAXMainWindowAttribute as CFString, &winRef) == .success,
               let w = winRef { windowEl = (w as! AXUIElement) }
            if let w = windowEl {
                roots = [AXNode(w)]
                var title: CFTypeRef?
                if AXUIElementCopyAttributeValue(w, kAXTitleAttribute as CFString, &title) == .success,
                   let t = title as? String { obs.window = t }
            } else {
                roots = [appEl]
            }
        }
        return processObservation(roots: roots, app: obs.app,
                                  window: obs.window, pid: obs.pid,
                                  maxNodes: maxNodes, diff: diff,
                                  deadline: deadline, appEl: appEl, t0: t0)
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
            records = Array(records.prefix(maxNodes))
            truncated = true
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
        current = Dictionary(uniqueKeysWithValues: records.map { ($0.ref, $0) })
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
