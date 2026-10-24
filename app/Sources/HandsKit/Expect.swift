import ApplicationServices
import Foundation

public enum ExpectError: Error, CustomStringConvertible {
    case badPredicate(String)
    public var description: String {
        switch self { case .badPredicate(let s): return "bad expect predicate: \(s)" }
    }
}

/// expect predicates from AGENTS.md:
///   title~"<text>" | focused #<ref> | value #<ref>="<text>"
///   | app "<name>" | appears "<label>" | gone #<ref>
public enum ExpectPredicate {
    case titleContains(String)
    case focused(Int)
    case valueEquals(Int, String)
    case appIs(String)
    case appears(String)
    case gone(Int)
}

public enum Expect {
    /// Parse the DSL string form.
    public static func parse(_ s: String) throws -> ExpectPredicate {
        let t = s.trimmingCharacters(in: .whitespaces)
        func quoted(_ rest: String) throws -> String {
            let q = rest.trimmingCharacters(in: .whitespaces)
            guard q.count >= 2, q.hasPrefix("\""), q.hasSuffix("\"") else {
                throw ExpectError.badPredicate(s)
            }
            return unescape(String(q.dropFirst().dropLast()))
        }
        if t.hasPrefix("title~") { return .titleContains(try quoted(String(t.dropFirst(6)))) }
        if t.hasPrefix("focused") {
            let rest = t.dropFirst(7).trimmingCharacters(in: .whitespaces)
            guard rest.hasPrefix("#"), let n = Int(rest.dropFirst()) else {
                throw ExpectError.badPredicate(s)
            }
            return .focused(n)
        }
        if t.hasPrefix("value") {
            let rest = t.dropFirst(5).trimmingCharacters(in: .whitespaces)
            guard rest.hasPrefix("#") else { throw ExpectError.badPredicate(s) }
            let body = String(rest.dropFirst())
            guard let eq = body.firstIndex(of: "=") else { throw ExpectError.badPredicate(s) }
            guard let n = Int(body[..<eq].trimmingCharacters(in: .whitespaces)) else {
                throw ExpectError.badPredicate(s)
            }
            return .valueEquals(n, try quoted(String(body[body.index(after: eq)...])))
        }
        if t.hasPrefix("appears") { return .appears(try quoted(String(t.dropFirst(7)))) }
        if t.hasPrefix("app") { return .appIs(try quoted(String(t.dropFirst(3)))) }
        if t.hasPrefix("gone") {
            let rest = t.dropFirst(4).trimmingCharacters(in: .whitespaces)
            guard rest.hasPrefix("#"), let n = Int(rest.dropFirst()) else {
                throw ExpectError.badPredicate(s)
            }
            return .gone(n)
        }
        throw ExpectError.badPredicate(s)
    }

    /// Parse the JSON wire form: {"op":"appears","arg":"Save"} or
    /// {"op":"value","ref":4,"arg":"x"} — or the DSL string itself.
    public static func parse(json v: Any) throws -> ExpectPredicate {
        if let s = v as? String { return try parse(s) }
        guard let d = v as? [String: Any], let op = d["op"] as? String else {
            throw ExpectError.badPredicate("\(v)")
        }
        switch op {
        case "title~": return .titleContains(d["arg"] as? String ?? "")
        case "focused": return .focused(d["ref"] as? Int ?? -1)
        case "value": return .valueEquals(d["ref"] as? Int ?? -1, d["arg"] as? String ?? "")
        case "app": return .appIs(d["arg"] as? String ?? "")
        case "appears": return .appears(d["arg"] as? String ?? "")
        case "gone": return .gone(d["ref"] as? Int ?? -1)
        default: throw ExpectError.badPredicate("\(v)")
        }
    }

    static func labelMatches(_ label: String, in text: String) -> Bool {
        guard !label.isEmpty else { return false }
        let pattern = "(?<!\\w)" + NSRegularExpression.escapedPattern(for: label) + "(?!\\w)"
        return text.range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
    }

    /// Evaluate against an observation. Returns (ok, observed-detail).
    public static func eval(_ p: ExpectPredicate, _ obs: Observation) -> (Bool, String) {
        switch p {
        case .titleContains(let want):
            let ok = obs.window.localizedCaseInsensitiveContains(want)
            return (ok, "window=\"\(obs.window)\"")
        case .focused(let ref):
            return (obs.focusedRef == ref, "focused=\(obs.focusedRef.map { "#\($0)" } ?? "none")")
        case .valueEquals(let ref, let want):
            guard let e = obs.elements.first(where: { $0.ref == ref }) else {
                return (false, "#\(ref) absent")
            }
            let got = "\(e.value ?? "")"
            return (got == want, "#\(ref) value=\"\(got)\"")
        case .appIs(let want):
            let ok = obs.app.localizedCaseInsensitiveCompare(want) == .orderedSame
                || obs.app.localizedCaseInsensitiveContains(want)
            return (ok, "app=\(obs.app)")
        case .appears(let label):
            let hit = obs.elements.contains {
                labelMatches(label, in: $0.label)
            }
            return (hit, "appears \"\(label)\" -> \(hit)")
        case .gone(let ref):
            let ok = !obs.elements.contains { $0.ref == ref }
            return (ok, "#\(ref) \(ok ? "gone" : "still present")")
        }
    }
}

// MARK: - Live evaluation (beyond the observation cap)

extension Hands {
    /// Evaluate `p` against `obs`, with live fallbacks so the 150-node cap
    /// never decides the answer:
    ///  - `appears`: on a miss, search the focused window and its sheets,
    ///    popovers and open menus with a large cap.
    ///  - `gone`: absent from the list is not enough; test the element's
    ///    own liveness/visibility, and never report gone from a truncated walk.
    public func evalExpect(_ p: ExpectPredicate, _ obs: Observation,
                           deadline: Date? = nil) -> (Bool, String) {
        switch p {
        case .appears(let label):
            let first = Expect.eval(p, obs)
            if first.0 { return first }
            let now = Date()
            let budget = max(0.1, min(0.4, (deadline ?? now.addingTimeInterval(0.4))
                .timeIntervalSince(now)))
            let hit = labelSearchOverride?(label, obs.pid)
                ?? searchLabel(label, pid: obs.pid, deadline: now.addingTimeInterval(budget))
            return (hit, "appears \"\(label)\" -> \(hit)\(hit ? " (beyond observation cap/open menu)" : "")")
        case .gone(let ref):
            if obs.elements.contains(where: { $0.ref == ref }) {
                return (false, "#\(ref) still present")
            }
            if let el = knownElement(ref: ref) {
                if !el.isAlive() { return (true, "#\(ref) gone") }
                let a = el.copyAttrs()
                let visible = a.size.width > 0 && a.size.height > 0
                    && a.frame.intersects(Walker.screenUnion())
                return visible ? (false, "#\(ref) still present (beyond observation cap)")
                               : (true, "#\(ref) gone (hidden)")
            }
            if obs.truncated { return (false, "#\(ref) unknown; observation truncated") }
            return (true, "#\(ref) gone")
        default:
            return Expect.eval(p, obs)
        }
    }

    /// Search the target app's focused window (with its sheets and popovers)
    /// and open menus for a word-bounded, case-insensitive label match.
    /// The menu bar is never searched (its
    /// File/Edit/View/Format titles would pass any `appears "Format"`),
    /// except the items of a menu that is open right now (hands-12).
    /// Read-only; does not touch ref/session state.
    func searchLabel(_ label: String, pid: pid_t, deadline: Date) -> Bool {
        guard pid > 0, !label.isEmpty else { return false }
        let app = AXNode(AXUIElementCreateApplication(pid))
        app.setMessagingTimeout(0.25)
        return Self.searchLabel(label, app: app, deadline: deadline)
    }

    /// Testable core of `searchLabel` (mock app element).
    static func searchLabel(_ label: String, app: Element, deadline: Date) -> Bool {
        guard !label.isEmpty else { return false }
        let roots = labelSearchRoots(app: app, focusedOnly: true)
        for r in roots where r.window {
            if let t = r.el.copyAttrs().title, Expect.labelMatches(label, in: t) { return true }
        }
        for r in roots {
            if Date() > deadline { break }
            let recs = Walker.walk(root: r.el, deadline: deadline, interactiveCap: 3000)
            if recs.contains(where: { Expect.labelMatches(label, in: $0.label) }) { return true }
        }
        return false
    }

    struct SearchRoot {
        var el: Element
        var window: Bool        // its title counts as a match
    }

    /// Windows (AXWindows + window-like app children: sheets, popovers,
    /// drawers), open context menus (AXMenu children of the app) and the
    /// AXMenu of an open menu-bar item. Never the AXMenuBar itself.
    /// `focusedOnly` restricts windows and overlays to `pickWindow`'s target.
    static func labelSearchRoots(app: Element, focusedOnly: Bool = false) -> [SearchRoot] {
        var roots: [SearchRoot] = []
        func add(_ el: Element, window: Bool) {
            if roots.contains(where: { sameElement($0.el, el) }) { return }
            roots.append(SearchRoot(el: el, window: window))
        }
        let windows = focusedOnly
            ? pickWindow(app: app).map { [$0.window] } ?? []
            : axElements(app.copySingleAttr(kAXWindowsAttribute as String))
        for w in windows {
            add(w, window: true)
            if focusedOnly {
                for sheet in axElements(w.copySingleAttr("AXSheets")) { add(sheet, window: true) }
            }
        }
        let windowish: Set<String> = ["AXWindow", "AXSheet", "AXPopover", "AXDrawer"]
        for c in app.copyAttrs().children {
            let role = c.copyAttrs().role ?? ""
            if windowish.contains(role) {
                if focusedOnly {
                    guard let w = windows.first, role != "AXWindow" else { continue }
                    let owner = axElement(c.copySingleAttr("AXWindow"))
                        ?? axElement(c.copySingleAttr(kAXParentAttribute as String))
                    guard let owner, sameElement(owner, w) else { continue }
                }
                add(c, window: role == "AXWindow" || role == "AXSheet")
            } else if role == "AXMenu" && isOpen(c) { add(c, window: false) }
        }
        // Menu bar: only the menu that is open (its AXMenu has a frame).
        if let bar = axElement(app.copySingleAttr("AXMenuBar")) {
            for item in bar.copyAttrs().children {
                for m in item.copyAttrs().children where m.copyAttrs().role == "AXMenu" && isOpen(m) {
                    add(m, window: false)
                }
            }
        }
        return roots
    }

    /// An AXMenu is open when it has a visible frame (closed menus report 0x0).
    static func isOpen(_ menu: Element) -> Bool {
        let a = menu.copyAttrs()
        return a.size.width > 0 && a.size.height > 0
    }

}

func unescape(_ s: String) -> String {
    var out = ""; var it = s.makeIterator()
    while let c = it.next() {
        if c == "\\", let n = it.next() {
            switch n {
            case "n": out.append("\n"); case "t": out.append("\t")
            case "\\": out.append("\\"); case "\"": out.append("\"")
            default: out.append(n)
            }
        } else { out.append(c) }
    }
    return out
}
