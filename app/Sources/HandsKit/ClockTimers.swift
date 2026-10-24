import Foundation

// Clock.app timers through the user's own shortcuts (`/usr/bin/shortcuts`,
// docs/CLOCK_TIMERS.md). No shell, no AppleScript: Process with argv only.

/// One `shortcuts` invocation. `exitCode` -1: the binary could not be launched.
public struct ShortcutRun: Equatable {
    public var exitCode: Int32
    public var stdout: String
    public var stderr: String
    public var timedOut: Bool
    public var ms: Double

    public init(exitCode: Int32, stdout: String = "", stderr: String = "", timedOut: Bool = false, ms: Double = 0) {
        self.exitCode = exitCode
        self.stdout = stdout
        self.stderr = stderr
        self.timedOut = timedOut
        self.ms = ms
    }
}

/// `shortcuts list` / `shortcuts run` (tests inject a fake).
public protocol ShortcutsRunning {
    func list() -> ShortcutRun
    func run(_ name: String, inputPath: String?) -> ShortcutRun
}

/// No Shortcuts at all (unit tests: `SystemHooks.inert`). Never launches anything.
public struct NoShortcuts: ShortcutsRunning {
    public init() {}
    public func list() -> ShortcutRun { ShortcutRun(exitCode: 0) }
    public func run(_ name: String, inputPath: String?) -> ShortcutRun {
        ShortcutRun(exitCode: 1, stderr: "no shortcuts runner")
    }
}

/// The real `/usr/bin/shortcuts`, killed after `timeout` seconds.
public final class ShortcutsCLI: ShortcutsRunning {
    public let path: String
    public let timeout: TimeInterval

    public init(path: String = "/usr/bin/shortcuts", timeout: TimeInterval = 10) {
        self.path = path
        self.timeout = timeout
    }

    public func list() -> ShortcutRun { exec(["list"]) }

    public func run(_ name: String, inputPath: String?) -> ShortcutRun {
        var args = ["run", name]
        if let inputPath { args += ["--input-path", inputPath] }
        return exec(args)
    }

    private final class Box {
        let lock = NSLock()
        var out = Data()
        var err = Data()
    }

    func exec(_ args: [String]) -> ShortcutRun {
        let t0 = Date()
        func ms() -> Double { (Date().timeIntervalSince(t0) * 1000).rounded(to: 1) }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        p.standardInput = FileHandle.nullDevice
        let outPipe = Pipe(), errPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = errPipe
        let done = DispatchSemaphore(value: 0)
        p.terminationHandler = { _ in done.signal() }
        do { try p.run() } catch {
            return ShortcutRun(exitCode: -1, stderr: "\(error)", ms: ms())
        }
        // Drain both pipes while the child runs (a full pipe would block it).
        let box = Box()
        let group = DispatchGroup()
        for (pipe, isOut) in [(outPipe, true), (errPipe, false)] {
            group.enter()
            DispatchQueue.global(qos: .userInitiated).async {
                let d = pipe.fileHandleForReading.readDataToEndOfFile()
                box.lock.lock()
                if isOut { box.out = d } else { box.err = d }
                box.lock.unlock()
                group.leave()
            }
        }
        var timedOut = false
        if done.wait(timeout: .now() + timeout) == .timedOut {
            timedOut = true
            p.terminate()
            if done.wait(timeout: .now() + 1) == .timedOut {
                kill(p.processIdentifier, SIGKILL)
                _ = done.wait(timeout: .now() + 1)
            }
        }
        _ = group.wait(timeout: .now() + 1)
        box.lock.lock(); defer { box.lock.unlock() }
        return ShortcutRun(exitCode: p.isRunning ? -2 : p.terminationStatus,
                           stdout: String(data: box.out, encoding: .utf8) ?? "",
                           stderr: String(data: box.err, encoding: .utf8) ?? "",
                           timedOut: timedOut, ms: ms())
    }
}

/// Names and pure helpers for the Muselet timer shortcuts.
public enum ClockShortcut {
    public static let start = "Muselet Start Timer"
    public static let cancel = "Muselet Cancel Timer"
    public static let status = "Muselet Timer Status"
    public static let all = [start, cancel, status]

    /// Muselet timer shortcuts in `shortcuts list` output (one name per
    /// line, exact names after trimming whitespace), in `all` order.
    public static func parseList(_ output: String) -> [String] {
        let names = Set(output.split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespaces) })
        return all.filter { names.contains($0) }
    }

    /// `--input-path` file body: whole seconds (at least 1), no newline.
    public static func inputText(seconds: Double) -> String {
        String(max(1, Int(seconds.rounded())))
    }

    /// nil = the run succeeded; otherwise the fallback reason.
    public static func failureReason(_ r: ShortcutRun) -> String? {
        if r.timedOut { return "shortcut_timeout" }
        if r.exitCode == -1 { return "shortcuts_unavailable" }
        if r.exitCode != 0 { return "shortcut_exit_\(r.exitCode)" }
        return nil
    }

    /// What `Muselet Timer Status` printed (Get Current Timer -> Stop and Output).
    public enum Status: Equatable {
        case none
        case running(left: Double)
        case unknown(String)
    }

    /// Empty / 0 -> none; seconds, "m:ss", "h:mm:ss" or "9 minutes 58 seconds" -> running.
    public static func parseStatus(_ output: String) -> Status {
        let s = output.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.isEmpty { return .none }
        guard let left = Skills.parseDuration(s) else { return .unknown(String(s.prefix(80))) }
        return left > 0 ? .running(left: left) : .none
    }
}

/// Clock backend state: the Settings toggle and the cached `shortcuts list`.
public final class ClockTimers {
    public static let cacheTTL: TimeInterval = 60
    /// A cache missing the wanted shortcut is re-listed, but not more often than this.
    public static let missRefreshInterval: TimeInterval = 2

    let runner: ShortcutsRunning
    var now: () -> Date = { Date() }
    var tempDir: URL = FileManager.default.temporaryDirectory
    private let lock = NSLock()
    private var listed: (at: Date, names: [String])?
    private var _enabled = true

    public init(runner: ShortcutsRunning) {
        self.runner = runner
    }

    /// "Use the Clock app for timers" (Settings; default on). The Clock is
    /// used only when this is on and `Muselet Start Timer` is installed.
    public var enabled: Bool {
        get { lock.lock(); defer { lock.unlock() }; return _enabled }
        set { lock.lock(); _enabled = newValue; lock.unlock() }
    }

    /// Installed Muselet timer shortcuts: cached 60 s; a cache without
    /// `need` is refreshed (a shortcut the user just added); `refresh` forces.
    public func installed(need: String? = nil, refresh: Bool = false) -> [String] {
        lock.lock(); let c = listed; lock.unlock()
        let t = now()
        if !refresh, let c {
            let age = t.timeIntervalSince(c.at)
            let hit = need.map { c.names.contains($0) } ?? true
            if age < Self.cacheTTL && (hit || age < Self.missRefreshInterval) { return c.names }
        }
        let r = runner.list()
        let names = r.exitCode == 0 && !r.timedOut ? ClockShortcut.parseList(r.stdout) : []
        lock.lock(); listed = (t, names); lock.unlock()
        return names
    }

    public func has(_ name: String) -> Bool { installed(need: name).contains(name) }

    public func invalidate() {
        lock.lock(); listed = nil; lock.unlock()
    }

    /// `timer_backend {}` RPC: `{clock_ready, shortcuts, enabled, backend, cancel_ready, status_ready}`.
    public func info(refresh: Bool = false) -> [String: Any] {
        let names = installed(need: ClockShortcut.start, refresh: refresh)
        let ready = names.contains(ClockShortcut.start)
        return ["clock_ready": ready, "shortcuts": names, "enabled": enabled,
                "backend": enabled && ready ? "clock" : "muselet",
                "cancel_ready": names.contains(ClockShortcut.cancel),
                "status_ready": names.contains(ClockShortcut.status)]
    }

    /// Outcome of trying the Clock: `reason` nil = timer started in Clock.
    public struct Attempt {
        public var reason: String?
        public var ms: Double
        public var run: ShortcutRun?
    }

    /// Run `Muselet Start Timer` with the seconds in a temp input file.
    public func start(seconds: Double) -> Attempt {
        guard has(ClockShortcut.start) else { return Attempt(reason: "shortcut_missing", ms: 0) }
        let file = tempDir.appendingPathComponent("muselet-timer-\(UUID().uuidString).txt")
        do {
            try ClockShortcut.inputText(seconds: seconds).write(to: file, atomically: true, encoding: .utf8)
        } catch {
            return Attempt(reason: "input_file_failed", ms: 0)
        }
        defer { try? FileManager.default.removeItem(at: file) }
        let r = runner.run(ClockShortcut.start, inputPath: file.path)
        let reason = ClockShortcut.failureReason(r)
        if reason != nil { invalidate() }
        return Attempt(reason: reason, ms: r.ms, run: r)
    }

    /// Run a no-input shortcut (Cancel / Status). nil when it isn't installed.
    public func runPlain(_ name: String) -> ShortcutRun? {
        guard has(name) else { return nil }
        let r = runner.run(name, inputPath: nil)
        if ClockShortcut.failureReason(r) != nil { invalidate() }
        return r
    }
}

/// `timers {}` merge: Muselet's own record of the timers it started (label,
/// fires_at) with what Clock reports for its current timer.
public enum TimerMerge {
    /// Seconds of disagreement still counted as the same timer.
    public static let tolerance: Double = 5

    /// `status` nil: Clock wasn't asked (no status shortcut / no clock
    /// timers). Records are never dropped: Clock reports one timer only.
    /// Clock records get `clock_seen` (true: matched, false: Clock has no
    /// timer); an unmatched running Clock timer is reported in `clock`.
    public static func merge(_ records: [[String: Any]], status: ClockShortcut.Status?)
        -> (timers: [[String: Any]], clock: [String: Any]) {
        var out = records
        guard let status else { return (out, ["status": "unavailable"]) }
        let clockIdx = out.indices.filter { out[$0]["backend"] as? String == "clock" }
        switch status {
        case .none:
            for i in clockIdx { out[i]["clock_seen"] = false }
            return (out, ["status": "none"])
        case .unknown(let raw):
            return (out, ["status": "unknown", "raw": raw])
        case .running(let left):
            var clock: [String: Any] = ["status": "running", "left_s": left.rounded(to: 1)]
            let best = clockIdx.min { a, b in
                abs(leftS(out[a]) - left) < abs(leftS(out[b]) - left)
            }
            if let best, abs(leftS(out[best]) - left) <= tolerance {
                out[best]["clock_seen"] = true
                out[best]["clock_left_s"] = left.rounded(to: 1)
                clock["matched_id"] = out[best]["id"]
            } else {
                clock["unmatched"] = true
            }
            return (out, clock)
        }
    }

    private static func leftS(_ d: [String: Any]) -> Double {
        (d["left_s"] as? Double) ?? (d["left_s"] as? NSNumber)?.doubleValue ?? .infinity
    }
}
