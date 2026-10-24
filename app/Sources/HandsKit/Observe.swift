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

    /// Breadth-first walk of `root`. Emits interactive roles plus labeled
    /// static text / images; prunes zero-size and offscreen nodes.
    public static func walk(root: Element, deadline: Date, maxDepth: Int = 25) -> [ElementRecord] {
        let screens = screenUnion()
        var interactive: [ElementRecord] = []
        var labeled: [ElementRecord] = []
        var queue: [(Element, Int)] = [(root, 0)]
        var qi = 0
        while qi < queue.count {
            if Date() > deadline { break }
            let (el, depth) = queue[qi]; qi += 1
            if depth > maxDepth { continue }
            let a = el.copyAttrs()
            let axRole = a.role ?? ""
            let frame = a.frame
            let zeroSize = a.size.width <= 0 || a.size.height <= 0
            let offscreen = frame.width > 0 && !frame.intersects(screens)
            let isContainer = kContainerRoles.contains(axRole)
            if !(zeroSize || offscreen) || isContainer {
                if let role = kRoleMap[axRole] {
                    let label = label(of: a, role: role)
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
                            element: el)
                        if kLabelOnlyRoles.contains(role) { labeled.append(rec) }
                        else { interactive.append(rec) }
                    }
                }
            }
            // Traverse children: always descend into containers; for other
            // nodes skip traversal only when the node itself was pruned.
            if isContainer || !(zeroSize || offscreen) {
                for c in a.children { queue.append((c, depth + 1)) }
            }
        }
        // Interactive first, then labeled statics; assign refs in that order.
        var all = interactive + labeled
        for i in all.indices { all[i].ref = i + 1 }
        return all
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
        // Frames match within ~8pt, so quantize to 8pt cells.
        let f = e.frame
        func q(_ v: CGFloat) -> Int { Int((v / 8).rounded()) }
        return "\(e.role)|\(e.label)|\(q(f.minX)),\(q(f.minY)),\(q(f.width)),\(q(f.height))"
    }

    /// Diff the previous epoch's records against the current. Returns lines:
    /// `+ #n role "label"`, `- #n`, `~ #n value="x"`.
    public static func diff(old: [ElementRecord], new: [ElementRecord]) -> String {
        var oldByKey: [String: [Int]] = [:]   // key -> refs of unmatched old
        for e in old { oldByKey[key(e), default: []].append(e.ref) }
        var matchedNew = Set<Int>()
        var lines: [String] = []
        var oldByRef = Dictionary(uniqueKeysWithValues: old.map { ($0.ref, $0) })
        for e in new {
            if var refs = oldByKey[key(e)], let r = refs.first {
                refs.removeFirst()
                if refs.isEmpty { oldByKey.removeValue(forKey: key(e)) } else { oldByKey[key(e)] = refs }
                matchedNew.insert(e.ref)
                let o = oldByRef[r]!
                var changes: [String] = []
                if "\(o.value ?? "")" != "\(e.value ?? "")" {
                    changes.append("value=\"\(Serializer.esc("\(e.value ?? "")"))\"")
                }
                if o.checked != e.checked, let c = e.checked {
                    changes.append(c ? "checked" : "unchecked")
                }
                if o.selected != e.selected { changes.append(e.selected ? "selected" : "unselected") }
                if o.enabled != e.enabled { changes.append(e.enabled ? "enabled" : "disabled") }
                if !changes.isEmpty { lines.append("~ #\(e.ref) \(changes.joined(separator: " "))") }
            } else {
                lines.append("+ \(Serializer.line(e))")
            }
        }
        for (_, refs) in oldByKey.sorted(by: { $0.value[0] < $1.value[0] }) {
            for r in refs { lines.append("- #\(r)") }
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

/// The stateful observation/act engine. Owns epochs and element handles.
public final class Hands {
    public private(set) var epoch = 0
    private var current: [Int: ElementRecord] = [:]
    private var previous: [Int: ElementRecord] = [:]
    private var manualAXPids: Set<pid_t> = []
    private var lastObservation = Observation()
    /// pid of the app seen by the most recent observe.
    public private(set) var lastPid: pid_t = 0

    public init() {}

    public var currentEpoch: Int { epoch }

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
        switch scope {
        case "menubar":
            if let bar = appEl.copySingleAttr("AXMenuBar"),
               CFGetTypeID(bar as CFTypeRef) == AXUIElementGetTypeID() {
                roots = [AXNode(bar as! AXUIElement)]
            } else { roots = [appEl] }
        default:
            var winRef: CFTypeRef?
            var windowEl: AXUIElement?
            if AXUIElementCopyAttributeValue(
                (appEl as! AXNode).el, kAXFocusedWindowAttribute as CFString, &winRef) == .success,
               let w = winRef { windowEl = (w as! AXUIElement) }
            if windowEl == nil,
               AXUIElementCopyAttributeValue(
                   (appEl as! AXNode).el, kAXMainWindowAttribute as CFString, &winRef) == .success,
               let w = winRef { windowEl = (w as! AXUIElement) }
            if windowEl == nil, scope != "app" {
                // fall back to app root if there is no window
                roots = [appEl]
            } else {
                roots = windowEl.map { [AXNode($0)] } ?? [appEl]
            }
            if let w = windowEl {
                var title: CFTypeRef?
                if AXUIElementCopyAttributeValue(w, kAXTitleAttribute as CFString, &title) == .success,
                   let t = title as? String { obs.window = t }
            }
        }

        var records: [ElementRecord] = []
        for r in roots {
            records.append(contentsOf: Walker.walk(root: r, deadline: deadline))
            if Date() > deadline { break }
        }
        if records.count > maxNodes { records = Array(records.prefix(maxNodes)) }

        // Locate the focused element among the records.
        var focusedRef: Int? = nil
        var focusedEl: CFTypeRef?
        if AXUIElementCopyAttributeValue(
            (appEl as! AXNode).el, kAXFocusedUIElementAttribute as CFString, &focusedEl) == .success,
           let fe = focusedEl {
            let fnode = AXNode(fe as! AXUIElement)
            for i in records.indices where sameElement(records[i].element, fnode) {
                focusedRef = records[i].ref
                records[i].focused = true
            }
        }
        obs.focusedRef = focusedRef
        obs.elements = records

        epoch += 1
        obs.epoch = epoch
        previous = current
        current = Dictionary(uniqueKeysWithValues: records.map { ($0.ref, $0) })
        obs.text = Serializer.text(app: obs.app, window: obs.window,
                                   focusedRef: focusedRef, elements: records)
        if diff {
            let prevRecords = previous.sorted { $0.key < $1.key }.map { $0.value }
            obs.diffText = Differ.diff(old: prevRecords, new: records)
        }
        obs.axMs = Date().timeIntervalSince(t0) * 1000
        lastObservation = obs
        lastPid = obs.pid
        return obs
    }

    /// Resolve an element ref for an act call, validating the epoch.
    public func element(ref: Int, epoch e: Int) throws -> ElementRecord {
        guard e == epoch else { throw HandsError.staleEpoch }
        guard let r = current[ref] else { throw HandsError.invalidParams("bad ref #\(ref)") }
        return r
    }

    public func record(ref: Int) -> ElementRecord? { current[ref] }
}
