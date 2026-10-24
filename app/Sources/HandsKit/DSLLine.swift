import Foundation

/// Minimal line parser for `hands repl` — parses one DSL action line into
/// act params. The brain has its own full parser in Python.
public enum DSLLine {
    static func quoted(_ s: Substring) -> String? {
        let t = s.trimmingCharacters(in: .whitespaces)
        guard t.count >= 2, t.hasPrefix("\""), t.hasSuffix("\"") else { return nil }
        return unescape(String(t.dropFirst().dropLast()))
    }

    /// Returns act params or throws a user-facing error string.
    public static func parse(_ line: String, epoch: Int) throws -> [String: Any] {
        let t = line.trimmingCharacters(in: .whitespaces)
        guard !t.isEmpty else { throw HandsError.invalidParams("empty") }
        var p: [String: Any] = ["epoch": epoch]
        let sp = t.firstIndex(of: " ") ?? t.endIndex
        let op = String(t[..<sp])
        let rest = sp < t.endIndex ? t[sp...].trimmingCharacters(in: .whitespaces) : ""
        switch op {
        case "press":
            guard let n = refNum(rest) else { throw HandsError.invalidParams("press #ref") }
            p["op"] = "press"; p["ref"] = n
        case "type":
            guard let n = refNum(rest) else { throw HandsError.invalidParams("type #ref \"..\"") }
            let after = String(rest.dropFirst(("\(n)").count + 1))
            var text = ""
            var enter = false
            if let qEnd = after.range(of: "\"", options: .backwards),
               let qStart = after.range(of: "\""), qStart != qEnd {
                text = unescape(String(after[after.index(qStart.lowerBound, offsetBy: 1)..<qEnd.lowerBound]))
                enter = after[qEnd.upperBound...].contains("enter")
            }
            p["op"] = "type"; p["ref"] = n; p["text"] = text; p["enter"] = enter
        case "keys":
            guard !rest.isEmpty else { throw HandsError.invalidParams("keys <combo>") }
            if MediaKey.parse(rest) == nil { _ = try Combo.parse(rest) }  // validate
            p["op"] = "keys"; p["combo"] = rest
        case "scroll":
            guard let n = refNum(rest) else { throw HandsError.invalidParams("scroll #ref dir [n]") }
            let parts = rest.dropFirst(("\(n)").count + 1)
                .split(separator: " ").map(String.init)
            p["op"] = "scroll"; p["ref"] = n
            p["direction"] = parts.first ?? "down"
            if parts.count > 1, let k = Int(parts[1]) { p["n"] = k }
        case "click":
            let parts = rest.split(separator: " ").map(String.init)
            guard let xy = parts.first?.split(separator: ","),
                  xy.count == 2, let x = Double(xy[0]), let y = Double(xy[1]) else {
                throw HandsError.invalidParams("click x,y [right|double]")
            }
            p["op"] = "click"; p["x"] = x; p["y"] = y
            p["right"] = parts.contains("right")
            p["double"] = parts.contains("double")
        case "open":
            guard let name = quoted(rest[rest.startIndex...]) ?? (rest.isEmpty ? nil : rest) else {
                throw HandsError.invalidParams("open \"App\"")
            }
            p["op"] = "open"; p["name"] = name
        case "url":
            guard let u = quoted(rest[rest.startIndex...]) ?? (rest.isEmpty ? nil : rest) else {
                throw HandsError.invalidParams("url \"https://..\"")
            }
            p["op"] = "url"; p["url"] = u
        case "wait":
            guard let ms = Int(rest) else { throw HandsError.invalidParams("wait <ms>") }
            p["op"] = "wait"; p["ms"] = ms
        default:
            throw HandsError.invalidParams("unknown op \(op)")
        }
        return p
    }

    private static func refNum(_ s: String) -> Int? {
        var t = s.trimmingCharacters(in: .whitespaces)
        guard t.hasPrefix("#") else { return nil }
        t = String(t.dropFirst())
        let digits = t.prefix(while: { $0.isNumber })
        return Int(digits)
    }
}
