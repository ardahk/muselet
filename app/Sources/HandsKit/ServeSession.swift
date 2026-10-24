import Foundation

/// `hands serve --utterance ...` bookkeeping: when to send the next
/// utterance and when to exit. Pure logic with an injected clock, so the
/// exit rules are unit-tested without a brain.
///
/// An utterance's outcome is a final `ui` mood (success / confused / idle /
/// sleeping) or a `say`. The next utterance goes out (or, after the last
/// one, the process exits 0) once the outcome arrived, no RPC is pending
/// and nothing happened for `quiet` (1.5 s) — late frames and RPCs (a `say`
/// before the final `ui`, a verify after the reply) still land. With
/// utterances, `timeout` (default 90 s, 0 = none) is a hard cap: exit 2.
/// A turn cut off by a brain disconnect is closed as "disconnected" (never
/// re-sent: it may have acted) and the final exit is 1. Without utterances
/// it serves forever (as before).
public final class ServeSession {
    public struct Config {
        public var utterances: [String]
        public var timeout: TimeInterval
        public var quiet: TimeInterval

        public init(utterances: [String], timeout: TimeInterval = 90, quiet: TimeInterval = 1.5) {
            self.utterances = utterances
            self.timeout = timeout
            self.quiet = quiet
        }

        /// Validated config from CLI arguments.
        public static func make(utterances: [String], timeout: Double) throws -> Config {
            guard timeout.isFinite, timeout >= 0 else {
                throw HandsError.invalidParams("--timeout must be >= 0 seconds (0 = no cap)")
            }
            let texts = utterances.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            guard !texts.contains(where: \.isEmpty) else {
                throw HandsError.invalidParams("--utterance must not be empty")
            }
            return Config(utterances: texts, timeout: timeout)
        }

        /// Exits by itself only when it has utterances to run.
        public var exitsWhenDone: Bool { !utterances.isEmpty }
    }

    public enum Step: Equatable {
        case none
        case send(id: String, text: String)
        case exit(code: Int32)
    }

    static let outcomeMoods: Set<String> = ["success", "confused", "idle", "sleeping"]

    private struct Turn {
        var id: String
        var text: String
        var sentAt: Date
        var outcomeAt: Date?
        var mood: String?
        var say: String?
        var ms: Double?
        var rpcs = 0
        var rpcErrors = 0
        var confirm: String?
    }

    public let config: Config
    private let lock = NSLock()
    private let startedAt: Date
    private var next = 0
    private var turns: [Turn] = []
    private var pending: Set<String> = []
    private var lastActivity: Date
    private var exited: Int32?
    private var exitReason = ""
    private var everConnected = false

    public init(config: Config, now: Date = Date()) {
        self.config = config
        self.startedAt = now
        self.lastActivity = now
    }

    /// The last turn is closed (or none was sent yet): frames are ignored.
    private var finalized = true

    private func sendNext(_ now: Date) -> Step {
        guard next < config.utterances.count else { return .none }
        let text = config.utterances[next]
        next += 1
        let id = "u\(next)"
        turns.append(Turn(id: id, text: text, sentAt: now))
        finalized = false
        lastActivity = now
        return .send(id: id, text: text)
    }

    /// The WebSocket (re)connected: send the first utterance. A turn still
    /// waiting after a reconnect is lost on the brain side: close it as
    /// "disconnected" and move on after the quiet period.
    public func connected(now: Date = Date()) -> Step {
        lock.lock(); defer { lock.unlock() }
        guard exited == nil else { return .none }
        everConnected = true
        if turns.isEmpty { return sendNext(now) }
        if !finalized, turns[turns.count - 1].outcomeAt == nil {
            turns[turns.count - 1].outcomeAt = now
            turns[turns.count - 1].mood = "disconnected"
            lastActivity = now
        }
        return .none
    }

    public func rpcStarted(id: String, now: Date = Date()) {
        lock.lock(); defer { lock.unlock() }
        pending.insert(id)
        lastActivity = now
        if !finalized { turns[turns.count - 1].rpcs += 1 }
    }

    public func rpcFinished(id: String, ok: Bool, now: Date = Date()) {
        lock.lock(); defer { lock.unlock() }
        pending.remove(id)
        lastActivity = now
        if !finalized, !ok { turns[turns.count - 1].rpcErrors += 1 }
    }

    public func ui(mood: String?, bubble: String?, ms: Double?, now: Date = Date()) {
        lock.lock(); defer { lock.unlock() }
        lastActivity = now
        guard !finalized else { return }
        var t = turns[turns.count - 1]
        if let m = mood, Self.outcomeMoods.contains(m) {
            t.mood = m
            if t.outcomeAt == nil { t.outcomeAt = now }
        }
        if let ms { t.ms = ms }
        if let b = bubble, !b.isEmpty, t.say == nil { t.say = b }
        turns[turns.count - 1] = t
    }

    public func say(_ text: String, now: Date = Date()) {
        lock.lock(); defer { lock.unlock() }
        lastActivity = now
        guard !finalized else { return }
        turns[turns.count - 1].say = text
        if turns[turns.count - 1].outcomeAt == nil { turns[turns.count - 1].outcomeAt = now }
    }

    /// Headless serve never answers confirms (no auto-yes); recorded only.
    public func confirm(_ summary: String, now: Date = Date()) {
        lock.lock(); defer { lock.unlock() }
        lastActivity = now
        if !finalized { turns[turns.count - 1].confirm = summary }
    }

    /// Call periodically (e.g. every 100 ms).
    public func tick(now: Date = Date()) -> Step {
        lock.lock(); defer { lock.unlock() }
        guard exited == nil, config.exitsWhenDone else { return .none }
        if config.timeout > 0, now.timeIntervalSince(startedAt) >= config.timeout {
            exited = 2
            exitReason = "timeout"
            return .exit(code: 2)
        }
        guard !finalized, turns[turns.count - 1].outcomeAt != nil, pending.isEmpty,
              now.timeIntervalSince(lastActivity) >= config.quiet else { return .none }
        finalized = true
        if next < config.utterances.count { return sendNext(now) }
        // A turn cut off by a brain disconnect has no real outcome: exit 1.
        let lost = turns.contains { $0.mood == "disconnected" }
        exited = lost ? 1 : 0
        exitReason = lost ? "disconnected" : "done"
        return .exit(code: exited!)
    }

    /// One-line JSON printed on exit.
    public func summary(now: Date = Date()) -> [String: Any] {
        lock.lock(); defer { lock.unlock() }
        var out: [String: Any] = [
            "t": "serve_summary",
            "exit": Int(exited ?? -1),
            "reason": exitReason,
            "elapsed_ms": (now.timeIntervalSince(startedAt) * 1000).rounded(to: 1),
            "connected": everConnected,
            "sent": turns.count,
            "total": config.utterances.count,
            "pending_rpcs": pending.count,
        ]
        out["utterances"] = turns.map { t -> [String: Any] in
            var d: [String: Any] = ["id": t.id, "text": t.text, "rpcs": t.rpcs, "rpc_errors": t.rpcErrors]
            d["mood"] = t.mood ?? NSNull()
            d["say"] = t.say ?? NSNull()
            if let ms = t.ms { d["ms"] = ms.rounded(to: 1) }
            if let o = t.outcomeAt { d["outcome_ms"] = (o.timeIntervalSince(t.sentAt) * 1000).rounded(to: 1) }
            if let c = t.confirm { d["confirm"] = c }
            return d
        }
        return out
    }

    public func summaryLine(now: Date = Date()) -> String {
        let d = summary(now: now)
        guard let data = try? JSONSerialization.data(withJSONObject: d, options: [.sortedKeys]),
              let s = String(data: data, encoding: .utf8) else { return "{}" }
        return s
    }
}
