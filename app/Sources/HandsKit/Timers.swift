import Foundation

/// Muselet-started countdown timers (`start_timer`), listed and cancelled
/// through the `timers` / `timers_cancel` RPCs (RPCs, not skills, so the
/// catalog is unchanged). Thread-safe; timers fire on a private queue.
public final class TimerRegistry {
    public struct Info: Equatable {
        public let id: String
        public let label: String?
        /// Requested duration (seconds).
        public let total: Double
        public let startedAt: Date
        public let firesAt: Date
    }

    private struct Entry {
        let info: Info
        let source: DispatchSourceTimer
    }

    private let queue = DispatchQueue(label: "hands.timers")
    private let lock = NSLock()
    private var entries: [String: Entry] = [:]
    /// Called (outside the lock) after every start / fire / cancel with the
    /// remaining timers, soonest first (live: the snapshot file for
    /// `hands probe timers`).
    var onChange: (([Info]) -> Void)?

    public init() {}

    /// Timers scheduled and not yet fired or cancelled.
    public var count: Int {
        lock.lock(); defer { lock.unlock() }
        return entries.count
    }

    /// Schedule a timer; `fire` runs on the timer queue when it is due
    /// (wall clock: it keeps counting across system sleep, like a kitchen timer).
    @discardableResult
    public func start(seconds: Double, label: String?, now: Date = Date(),
                      fire: @escaping (Info) -> Void) -> Info {
        let info = Info(id: "timer-\(UUID().uuidString.prefix(8).lowercased())", label: label,
                        total: seconds, startedAt: now, firesAt: now.addingTimeInterval(seconds))
        let t = DispatchSource.makeTimerSource(queue: queue)
        t.schedule(wallDeadline: .now() + seconds, leeway: .milliseconds(20))
        t.setEventHandler { [weak self, weak t] in
            t?.cancel()
            // A timer cancelled while this handler was already queued does
            // nothing: only an entry still registered fires.
            guard let self, self.remove(info.id) != nil else { return }
            fire(info)
            self.changed()
        }
        lock.lock()
        entries[info.id] = Entry(info: info, source: t)
        lock.unlock()
        t.resume()
        changed()
        return info
    }

    /// Pending timers, soonest first.
    public func list() -> [Info] {
        lock.lock(); defer { lock.unlock() }
        return entries.values.map(\.info).sorted { $0.firesAt < $1.firesAt }
    }

    /// Cancel timer `id`, or every timer when `id` is nil. Returns the
    /// cancelled timers (empty: unknown id / nothing pending).
    @discardableResult
    public func cancel(id: String?) -> [Info] {
        lock.lock()
        let victims: [Entry]
        if let id {
            victims = entries[id].map { [$0] } ?? []
        } else {
            victims = Array(entries.values)
        }
        for v in victims {
            entries.removeValue(forKey: v.info.id)
            v.source.cancel()
        }
        lock.unlock()
        if !victims.isEmpty { changed() }
        return victims.map(\.info).sorted { $0.firesAt < $1.firesAt }
    }

    private func remove(_ id: String) -> Entry? {
        lock.lock(); defer { lock.unlock() }
        return entries.removeValue(forKey: id)
    }

    /// Serializes "read the list + report it", so reports arrive in the
    /// order the lists were read (a fire racing a start can't leave a
    /// stale snapshot last).
    private let changeLock = NSLock()

    private func changed() {
        changeLock.lock(); defer { changeLock.unlock() }
        onChange?(list())
    }

    /// Wire form: {id, label (null if none), total_s, left_s, minutes, fires_at}.
    /// `minutes` = whole minutes left, rounded up ("about 7 minutes left");
    /// `left_s` = seconds left (1 decimal, never negative).
    public static func dict(_ i: Info, now: Date = Date()) -> [String: Any] {
        // Minutes from the reported (0.1 s) value: 540.0000001 s is 9 minutes.
        let left = max(0, i.firesAt.timeIntervalSince(now)).rounded(to: 1)
        return [
            "id": i.id, "label": i.label ?? NSNull(), "total_s": i.total.rounded(to: 1), "left_s": left,
            "minutes": Int((left / 60).rounded(.up)), "fires_at": isoString(i.firesAt),
        ]
    }

    static func isoString(_ d: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.string(from: d)
    }
}

/// Cross-process view of Muselet's timers for `hands probe timers`: each
/// process with timers keeps `$TMPDIR/muselet-timers/<pid>.json` current
/// (written on every change, removed when none are left); the probe reads
/// the files of processes that are still alive. Read-only for the probe.
public enum TimerSnapshot {
    public static var directory: URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("muselet-timers", isDirectory: true)
    }

    private static let writeQueue = DispatchQueue(label: "hands.timers.snapshot", qos: .utility)

    /// Write this process's timers (async, in order); no timers -> remove the
    /// file. `gc`: also remove the files of processes that are gone.
    public static func write(_ timers: [TimerRegistry.Info], pid: pid_t = getpid(),
                             process: String = ProcessInfo.processInfo.processName,
                             directory dir: URL = directory, gc: Bool = true) {
        writeQueue.async {
            let fm = FileManager.default
            if gc, let files = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) {
                for f in files where f.pathExtension == "json" {
                    if let other = Int32(f.deletingPathExtension().lastPathComponent),
                       other != pid, !processAlive(other) {
                        try? fm.removeItem(at: f)
                    }
                }
            }
            let file = dir.appendingPathComponent("\(pid).json")
            if timers.isEmpty {
                try? fm.removeItem(at: file)
                return
            }
            let body: [String: Any] = [
                "pid": Int(pid), "process": process,
                "timers": timers.map { i -> [String: Any] in
                    var d: [String: Any] = ["id": i.id, "total_s": i.total,
                                            "started_at": i.startedAt.timeIntervalSince1970,
                                            "fires_at": i.firesAt.timeIntervalSince1970]
                    if let l = i.label { d["label"] = l }
                    return d
                },
            ]
            guard let data = try? JSONSerialization.data(withJSONObject: body) else { return }
            try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
            try? data.write(to: file, options: .atomic)
        }
    }

    /// Wait for queued writes (tests).
    static func flush() { writeQueue.sync {} }

    /// The process exists (EPERM: someone else's, still alive).
    public static func processAlive(_ pid: pid_t) -> Bool { kill(pid, 0) == 0 || errno == EPERM }

    /// Timers of live processes, soonest first, in the RPC wire form plus
    /// `pid` / `process`. Files of dead processes and past timers are skipped.
    public static func read(directory dir: URL = directory, now: Date = Date(),
                            isAlive: (pid_t) -> Bool = processAlive) -> [[String: Any]] {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) else { return [] }
        var out: [(Date, [String: Any])] = []
        for f in files where f.pathExtension == "json" {
            guard let data = try? Data(contentsOf: f),
                  let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let pid = (root["pid"] as? NSNumber)?.int32Value, isAlive(pid) else { continue }
            let process = root["process"] as? String ?? "?"
            for t in root["timers"] as? [[String: Any]] ?? [] {
                guard let id = t["id"] as? String,
                      let total = (t["total_s"] as? NSNumber)?.doubleValue,
                      let fires = (t["fires_at"] as? NSNumber)?.doubleValue else { continue }
                let firesAt = Date(timeIntervalSince1970: fires)
                guard firesAt > now else { continue }
                let started = (t["started_at"] as? NSNumber).map { Date(timeIntervalSince1970: $0.doubleValue) }
                    ?? firesAt.addingTimeInterval(-total)
                let info = TimerRegistry.Info(id: id, label: t["label"] as? String, total: total,
                                              startedAt: started, firesAt: firesAt)
                var d = TimerRegistry.dict(info, now: now)
                d["pid"] = Int(pid)
                d["process"] = process
                out.append((firesAt, d))
            }
        }
        return out.sorted { $0.0 < $1.0 }.map(\.1)
    }
}
