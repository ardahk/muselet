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
                $0.label.localizedCaseInsensitiveContains(label)
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
    ///  - `appears`: on a miss, search the whole app (menus, popovers,
    ///    sheets, other windows, window titles) with a large cap.
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
            return (hit, "appears \"\(label)\" -> \(hit)\(hit ? " (outside focused window/cap)" : "")")
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

    /// Search every window, sheet, menu and popover of `pid` for a label or
    /// window title containing `label` (case-insensitive). Read-only; does
    /// not touch ref/session state.
    func searchLabel(_ label: String, pid: pid_t, deadline: Date) -> Bool {
        guard pid > 0, !label.isEmpty else { return false }
        let app = AXNode(AXUIElementCreateApplication(pid))
        app.setMessagingTimeout(0.25)
        if let wins = app.copySingleAttr(kAXWindowsAttribute as String) as? [AXUIElement] {
            for w in wins {
                let n = AXNode(w)
                n.setMessagingTimeout(0.25)
                if let t = n.copySingleAttr(kAXTitleAttribute as String) as? String,
                   t.localizedCaseInsensitiveContains(label) { return true }
            }
        }
        let recs = Walker.walk(root: app, deadline: deadline, interactiveCap: 3000)
        return recs.contains { $0.label.localizedCaseInsensitiveContains(label) }
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
