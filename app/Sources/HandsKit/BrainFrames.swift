import Foundation

/// Brain -> app frames (AGENTS.md protocol), decoded in one place so the
/// app and the tests agree on the wire format.
public enum BrainInbound {
    case rpc(id: String, method: String, params: [String: Any])
    /// `ms`: release-to-first-action (skills) or total (planner) latency,
    /// on the final ui message of a request.
    case ui(mascot: String?, bubble: String?, ms: Double?)
    case say(String)
    case confirm(id: String, summary: String)
    /// The confirm timed out or the task was cancelled: leave confirm mode.
    /// A missing id cancels whatever confirm is pending.
    case confirmCancel(id: String?)
    case memory([[String: Any]])
    case unknown(String)

    /// nil for non-JSON / frames without `t` / incomplete rpc or confirm.
    public static func decode(_ text: String) -> BrainInbound? {
        guard let data = text.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let t = obj["t"] as? String else { return nil }
        switch t {
        case "rpc":
            guard let id = obj["id"] as? String, let method = obj["method"] as? String else { return nil }
            return .rpc(id: id, method: method, params: obj["params"] as? [String: Any] ?? [:])
        case "ui":
            var ms: Double?
            if let n = obj["ms"] as? NSNumber, n.doubleValue.isFinite, n.doubleValue >= 0 {
                ms = n.doubleValue
            }
            return .ui(mascot: obj["mascot"] as? String, bubble: obj["bubble"] as? String, ms: ms)
        case "say":
            return .say(obj["text"] as? String ?? "")
        case "confirm":
            guard let id = obj["id"] as? String else { return nil }
            return .confirm(id: id, summary: obj["summary"] as? String ?? "Continue?")
        case "confirm_cancel":
            let id = (obj["id"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            return .confirmCancel(id: id)
        case "memory":
            return .memory(obj["items"] as? [[String: Any]] ?? [])
        default:
            return .unknown(t)
        }
    }
}

/// confirm_cancel decision: does a cancel for `cancelId` end the pending
/// confirm `pendingId`? A cancel for an older confirm must not dismiss a
/// newer one; a cancel without an id ends whatever is pending.
public enum ConfirmCancel {
    public static func clears(pendingId: String?, cancelId: String?) -> Bool {
        guard let p = pendingId else { return false }
        guard let c = cancelId else { return true }
        return c == p
    }
}

/// Latency chip text: "0.21 s" (< 10 s: two decimals), "12.4 s" (>= 10 s).
public enum LatencyFormat {
    public static func seconds(_ ms: Double) -> String {
        let s = max(0, ms) / 1000
        return s < 10 ? String(format: "%.2f s", s) : String(format: "%.1f s", s)
    }
}
