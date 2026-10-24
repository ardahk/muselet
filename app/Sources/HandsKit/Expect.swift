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
