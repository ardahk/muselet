import AppKit
import ApplicationServices
import CoreGraphics
import EventKit
import Foundation
import IOKit.ps
import UserNotifications

// MARK: - Catalog

public struct SkillDef {
    public var name: String
    public var risk: String          // safe | confirm | confirm_if_unsaved
    public var description: String
    public var args: [(name: String, type: String, required: Bool)]

    static func parse(json: [String: Any]) -> SkillDef? {
        guard let name = json["name"] as? String else { return nil }
        let risk = json["risk"] as? String ?? "safe"
        let desc = json["description"] as? String ?? ""
        var args: [(String, String, Bool)] = []
        for a in json["args"] as? [[String: Any]] ?? [] {
            args.append((a["name"] as? String ?? "",
                         a["type"] as? String ?? "string",
                         a["required"] as? Bool ?? false))
        }
        return SkillDef(name: name, risk: risk, description: desc, args: args)
    }
}

public enum Catalog {
    /// Locate skills/catalog.json: MUSELET_SKILLS env, then walk up from cwd.
    public static func defaultPath() -> String? {
        if let e = ProcessInfo.processInfo.environment["MUSELET_SKILLS"] { return e }
        var dir = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        for _ in 0..<8 {
            let p = dir.appendingPathComponent("skills/catalog.json").path
            if FileManager.default.fileExists(atPath: p) { return p }
            dir.deleteLastPathComponent()
        }
        return NSHomeDirectory() + "/cal13.0/skills/catalog.json"
    }

    public static func load(path: String? = nil) throws -> [String: SkillDef] {
        let p = path ?? defaultPath()
        guard let p, let data = FileManager.default.contents(atPath: p) else {
            throw HandsError.internal("catalog not found")
        }
        let root = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        var out: [String: SkillDef] = [:]
        for s in root?["skills"] as? [[String: Any]] ?? [] {
            if let d = SkillDef.parse(json: s) { out[d.name] = d }
        }
        return out
    }
}

// MARK: - System hooks (private frameworks, sounds, notifications)

/// Side effects that can't run in unit tests, injectable as closures.
/// `live` talks to the real system; tests pass `inert` with overrides.
public struct SystemHooks {
    /// IOBluetoothPreferenceGetControllerPowerState; nil = symbol missing.
    public var bluetoothGet: () -> Bool?
    /// IOBluetoothPreferenceSetControllerPowerState; false = symbol missing.
    public var bluetoothSet: (Bool) -> Bool
    /// Control Center AX toggle fallback; returns the state it left.
    public var bluetoothControlCenter: (Bool) throws -> Bool
    /// SACLockScreenImmediate; false = symbol missing.
    public var lockScreenPrivate: () -> Bool
    public var brightnessGet: () -> Float?
    /// DisplayServicesSetBrightness; false = unavailable.
    public var brightnessSet: (Float) -> Bool
    public var playSound: (String) -> Void
    public var notify: (_ title: String, _ body: String) -> Void
    /// The pending timers changed (live: the `hands probe timers` snapshot file).
    public var timersChanged: ([TimerRegistry.Info]) -> Void
    /// Accessibility and Clock.app are available for direct timer control.
    public var clockAXReady: () -> Bool

    public init(bluetoothGet: @escaping () -> Bool?, bluetoothSet: @escaping (Bool) -> Bool,
                bluetoothControlCenter: @escaping (Bool) throws -> Bool,
                lockScreenPrivate: @escaping () -> Bool,
                brightnessGet: @escaping () -> Float?, brightnessSet: @escaping (Float) -> Bool,
                playSound: @escaping (String) -> Void,
                notify: @escaping (String, String) -> Void,
                timersChanged: @escaping ([TimerRegistry.Info]) -> Void = { _ in },
                clockAXReady: @escaping () -> Bool = { false }) {
        self.bluetoothGet = bluetoothGet
        self.bluetoothSet = bluetoothSet
        self.bluetoothControlCenter = bluetoothControlCenter
        self.lockScreenPrivate = lockScreenPrivate
        self.brightnessGet = brightnessGet
        self.brightnessSet = brightnessSet
        self.playSound = playSound
        self.notify = notify
        self.timersChanged = timersChanged
        self.clockAXReady = clockAXReady
    }

    /// No side effects at all (unit tests start from this).
    public static var inert: SystemHooks {
        SystemHooks(
            bluetoothGet: { nil }, bluetoothSet: { _ in false },
            bluetoothControlCenter: { _ in throw HandsError.skillFailed("inert") },
            lockScreenPrivate: { false },
            brightnessGet: { nil }, brightnessSet: { _ in false },
            playSound: { _ in }, notify: { _, _ in }, timersChanged: { _ in })
    }

    public static var live: SystemHooks {
        SystemHooks(
            bluetoothGet: { PrivateSymbols.bluetoothPower() },
            bluetoothSet: { PrivateSymbols.setBluetoothPower($0) },
            bluetoothControlCenter: { try ControlCenter.setToggle(named: "Bluetooth", on: $0) },
            lockScreenPrivate: { PrivateSymbols.lockScreen() },
            brightnessGet: { PrivateSymbols.brightness() },
            brightnessSet: { PrivateSymbols.setBrightness($0) },
            playSound: { name in
                DispatchQueue.main.async {
                    let s = NSSound(named: NSSound.Name(name))
                    PrivateSymbols.retainedSound = s     // keep alive while playing
                    s?.play()
                }
            },
            notify: { title, body in Notifier.post(title: title, body: body) },
            timersChanged: { TimerSnapshot.write($0) },
            clockAXReady: { ClockAX.liveReady() })
    }
}

/// dlsym'd private/undocumented entry points (resolved lazily, cached).
public enum PrivateSymbols {
    static var retainedSound: NSSound?

    private static let ioBluetooth: UnsafeMutableRawPointer? =
        dlopen("/System/Library/Frameworks/IOBluetooth.framework/IOBluetooth", RTLD_LAZY)
    private static let login: UnsafeMutableRawPointer? =
        dlopen("/System/Library/PrivateFrameworks/login.framework/Versions/Current/login", RTLD_LAZY)
    private static let displayServices: UnsafeMutableRawPointer? =
        dlopen("/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices", RTLD_LAZY)

    /// Symbol availability without calling anything (for probes/reports).
    public static func resolves(_ name: String) -> Bool {
        let h: UnsafeMutableRawPointer?
        switch name {
        case "IOBluetoothPreferenceGetControllerPowerState",
             "IOBluetoothPreferenceSetControllerPowerState": h = ioBluetooth
        case "SACLockScreenImmediate": h = login
        default: h = displayServices
        }
        guard let h else { return false }
        return dlsym(h, name) != nil
    }

    public static func bluetoothPower() -> Bool? {
        typealias Fn = @convention(c) () -> Int32
        guard let h = ioBluetooth,
              let s = dlsym(h, "IOBluetoothPreferenceGetControllerPowerState") else { return nil }
        return unsafeBitCast(s, to: Fn.self)() != 0
    }

    public static func setBluetoothPower(_ on: Bool) -> Bool {
        typealias Fn = @convention(c) (Int32) -> Void
        guard let h = ioBluetooth,
              let s = dlsym(h, "IOBluetoothPreferenceSetControllerPowerState") else { return false }
        unsafeBitCast(s, to: Fn.self)(on ? 1 : 0)
        return true
    }

    public static func lockScreen() -> Bool {
        typealias Fn = @convention(c) () -> Int32
        guard let h = login, let s = dlsym(h, "SACLockScreenImmediate") else { return false }
        _ = unsafeBitCast(s, to: Fn.self)()
        return true
    }

    public static func brightness() -> Float? {
        typealias Fn = @convention(c) (CGDirectDisplayID, UnsafeMutablePointer<Float>) -> Int32
        guard let h = displayServices, let s = dlsym(h, "DisplayServicesGetBrightness") else {
            return nil
        }
        var v: Float = -1
        guard unsafeBitCast(s, to: Fn.self)(CGMainDisplayID(), &v) == 0, v >= 0 else { return nil }
        return v
    }

    public static func setBrightness(_ v: Float) -> Bool {
        typealias Fn = @convention(c) (CGDirectDisplayID, Float) -> Int32
        guard let h = displayServices, let s = dlsym(h, "DisplayServicesSetBrightness") else {
            return false
        }
        _ = unsafeBitCast(s, to: Fn.self)(CGMainDisplayID(), v)
        return true
    }
}

/// User notification for timers. In the bundled app: UNUserNotificationCenter
/// (asks for permission once). Unbundled (CLI): `display notification`.
enum Notifier {
    static func post(title: String, body: String) {
        let bundled = Bundle.main.bundleIdentifier != nil
            && Bundle.main.bundleURL.pathExtension == "app"
        if bundled {
            let c = UNUserNotificationCenter.current()
            c.requestAuthorization(options: [.alert, .sound]) { granted, _ in
                guard granted else { scriptFallback(title: title, body: body); return }
                let content = UNMutableNotificationContent()
                content.title = title
                content.body = body
                c.add(UNNotificationRequest(identifier: UUID().uuidString,
                                            content: content, trigger: nil))
            }
        } else {
            scriptFallback(title: title, body: body)
        }
    }

    private static func scriptFallback(title: String, body: String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        p.arguments = ["-e", "display notification \"\(asq(body))\" with title \"\(asq(title))\""]
        try? p.run()
    }
}

// MARK: - Path aliases

public enum PathAlias {
    static let aliases: [String: String] = [
        "downloads": "~/Downloads", "download": "~/Downloads",
        "documents": "~/Documents", "document": "~/Documents",
        "desktop": "~/Desktop",
        "home": "~",
        "applications": "/Applications", "apps": "/Applications",
    ]
    public static func resolve(_ p: String) -> String {
        let l = p.trimmingCharacters(in: .whitespaces).lowercased()
        if let a = aliases[l] { return (a as NSString).expandingTildeInPath }
        return (p as NSString).expandingTildeInPath
    }

    /// A user-supplied path for a skill: alias/`~` resolved, and only an
    /// absolute result passes. Anything else would silently land in the
    /// hands process's CWD — `relative_path` instead, touching nothing.
    public static func checked(_ p: String) throws -> String {
        let r = resolve(p)
        guard r.hasPrefix("/") else { throw HandsError.relativePath(p) }
        return r
    }
}

// MARK: - Skills engine

/// Native skill executor (catalog skills; `skill {name, args}` RPC).
///
/// Beyond the catalog arg lists:
///  - `set_brightness` takes `delta` (int, +/-) instead of `level`: current
///    brightness + delta, clamped to 0...100, set, read back
///    (`{level, previous, delta}`). The brain sends `delta` only for
///    directional phrasing ("a bit dimmer").
///  - `open_folder` takes an optional `view` (`list|icons|columns|gallery`):
///    cmd+2 / cmd+1 / cmd+3 / cmd+4 on the Finder window it opened, read back
///    from `current view of front Finder window` (`{view, view_applied}`).
///  - `type_text` into a keystroke app (Calculator) posts key presses
///    (`target: "keystroke_app"`); `screen_locked` while the lock screen is up.
///
/// Launches report truthfully: `open_app` waits <= 1.5 s for the app to be
/// frontmost (`{app, frontmost, launched}`); `open_url` / `web_search` wait
/// <= 3 s for the requested (or default) browser frontmost with a changed
/// window title (`{browser, browser_requested?, browser_fallback?, frontmost,
/// window_title, title_changed}`); `open_folder` /
/// `open_file` wait <= 3 s for Finder / the file's app frontmost with the
/// window title read back (`{app, frontmost, window_title, title_matches}`).
/// Never frontmost -> ok=false, error `not_frontmost`, `observed`, and the
/// result payload anyway.
///
/// Timers started by `start_timer` are listed / cancelled with the
/// `timers` / `timers_cancel` RPCs (`timerList()`, `cancelTimers(id:)`).
public final class Skills {
    private let catalog: [String: SkillDef]
    let scripts: ScriptRunning
    let events: EventPosting
    let apps: AppControlling
    let launcher: Launching
    let hooks: SystemHooks
    private var wifiDevice: String?
    /// Receives `handsTimerFired` (set by RPCHandler.delegate).
    public weak var delegate: HandsDelegate?
    /// AX application element for a pid (tests pass a mock app).
    var axApp: (pid_t) -> Element = { pid in
        let n = AXNode(AXUIElementCreateApplication(pid))
        n.setMessagingTimeout(0.25)
        return n
    }

    /// Launch verification bounds (tests shorten them).
    var openAppTimeout: TimeInterval = 1.5
    var openTimeout: TimeInterval = 3.0
    var launchPollInterval: TimeInterval = 0.03
    /// Re-activate an opened app that isn't frontmost yet this often.
    var launchReactivateInterval: TimeInterval = 0.4
    var viewPollInterval: TimeInterval = 0.1
    var clockAXTimeout: TimeInterval = 3.0
    var clockAXSettle: TimeInterval = 1.0
    var clockAXPoll: TimeInterval = 0.05
    var clockAXStepWait: TimeInterval = 0.25
    var clockAXVerify: TimeInterval = 2.0
    /// Folder display name (Finder window title); tests stub it.
    var displayNameOverride: ((String) -> String)?

    /// Muselet-started timers (`start_timer`; `timers` / `timers_cancel` RPCs).
    public let timers = TimerRegistry()

    /// `timer_backend` RPC: `{clock_ax_ready, backend}`; backend is "clock_ax"
    /// (Clock.app over Accessibility) or "muselet" (Muselet's own timer).
    public func timerBackendInfo() -> [String: Any] {
        let axReady = hooks.clockAXReady()
        return ["clock_ax_ready": axReady, "backend": ClockAX.backend(axReady: axReady)]
    }

    /// Premiere Pro default keyboard shortcuts per `premiere_command`.
    public static let premiereKeys: [String: String] = [
        "razor_at_playhead": "cmd+k", "add_marker": "m", "play_toggle": "space",
        "undo": "cmd+z", "go_to_start": "home", "go_to_end": "end", "export": "cmd+m",
    ]
    static let premiereBundlePrefix = "com.adobe.PremierePro"

    /// "<output volume>,<output muted>" as text (a record has no stringValue).
    static let volumeStateScript = """
        set s to get volume settings
        return ((output volume of s) as text) & "," & ((output muted of s) as text)
        """

    /// Precompile AppleScript sources off the hot path (RPCHandler calls
    /// this on a background queue at startup).
    public func warmUp() {
        (scripts as? AppleScriptRunner)?.warmUp()
    }

    public init(catalog: [String: SkillDef], scripts: ScriptRunning = AppleScriptRunner(),
                events: EventPosting = CGEventPoster(), apps: AppControlling = WorkspaceApps(),
                hooks: SystemHooks = .live, launcher: Launching = WorkspaceLauncher()) {
        self.catalog = catalog
        self.scripts = scripts
        self.events = events
        self.apps = apps
        self.hooks = hooks
        self.launcher = launcher
        timers.onChange = { [hooks] in hooks.timersChanged($0) }
    }
    public convenience init() {
        self.init(catalog: (try? Catalog.load()) ?? [:])
    }

    /// Number of timers scheduled and not yet fired.
    public var pendingTimers: Int { timers.count }

    /// Pending timers Muselet started (both backends), soonest first
    /// (`{id, label (null if none), total_s, left_s, minutes, fires_at, backend}`).
    public func timerList(now: Date = Date()) -> [[String: Any]] {
        timers.list().map { TimerRegistry.dict($0, now: now) }
    }

    /// `timers {}` RPC: Muselet's records, Clock AX observations (asked, or
    /// when a Clock timer is pending), and `backend` readiness.
    public func timersReport(askClock: Bool = false, now: Date = Date()) -> [String: Any] {
        var records = timerList(now: now)
        var report: [String: Any] = ["timers": records, "backend": timerBackendInfo()]
        if askClock || records.contains(where: { $0["backend"] as? String == "clock_ax" }) {
            let ax = clockAXRead()
            if ax.status == "read" {
                records = ClockAX.match(records: records, running: ax.running, now: now)
                report["timers"] = records
            }
            report["clock_ax"] = [
                "status": ax.status,
                "running": ax.running.map { timer in
                    var item: [String: Any] = ["left_s": timer.leftS]
                    if let label = timer.label { item["label"] = label }
                    return item
                },
            ]
        }
        return report
    }

    /// `timers_cancel` outcome.
    public struct TimerCancel {
        public var cancelled: [[String: Any]] = []
        /// Clock timer ids that could not be cancelled.
        public var unsupported: [String] = []
        /// Why each unsupported Clock AX cancel failed.
        public var axReasons: [[String: Any]] = []
        public var unknown = false
    }

    /// `timers_cancel {id?}` RPC: cancel one timer, or all when `id` is nil.
    public func cancelTimersDetailed(id: String?, now: Date = Date()) -> TimerCancel {
        var out = TimerCancel()
        let targets = timers.list().filter { id == nil || $0.id == id }
        if id != nil && targets.isEmpty { out.unknown = true; return out }
        for t in targets {
            guard t.backend == "clock_ax" else {
                out.cancelled += timers.cancel(id: t.id).map { TimerRegistry.dict($0, now: now) }
                continue
            }
            if let reason = clockAXCancel(t, now: now) {
                out.unsupported.append(t.id)
                out.axReasons.append(["id": t.id, "reason": reason])
            } else {
                out.cancelled += timers.cancel(id: t.id).map { TimerRegistry.dict($0, now: now) }
            }
        }
        return out
    }

    /// Cancel one timer, or all when `id` is nil. Returns the cancelled
    /// timers (wire form; empty for an unknown id).
    public func cancelTimers(id: String?, now: Date = Date()) -> [[String: Any]] {
        cancelTimersDetailed(id: id, now: now).cancelled
    }

    public func def(_ name: String) -> SkillDef? { catalog[name] }

    /// Required catalog args that another arg may stand in for
    /// (`set_brightness delta=-10` instead of `level`).
    static let argAlternatives: [String: [String: [String]]] = [
        "set_brightness": ["level": ["delta"]],
    ]

    /// Execute a skill by name. Returns {ok, result?, error?, ms}.
    public func execute(name: String, args inArgs: [String: Any]) -> [String: Any] {
        let t0 = Date()
        var out: [String: Any] = [:]
        do {
            guard let def = catalog[name] else {
                throw HandsError.notImplemented(name)
            }
            // Confirmation gate: risk=confirm refuses unless confirmed:true.
            if def.risk == "confirm", inArgs["confirmed"] as? Bool != true {
                throw HandsError.needsConfirmation
            }
            // Required-arg check (an alternative arg satisfies it).
            for a in def.args where a.required {
                let alts = Self.argAlternatives[name]?[a.name] ?? []
                if inArgs[a.name] == nil && !alts.contains(where: { inArgs[$0] != nil }) {
                    throw HandsError.invalidParams("\(name): missing arg \(a.name)")
                }
            }
            let result = try run(name, inArgs)
            out["ok"] = true
            out["result"] = result
            if let r = result as? [String: Any], let f = r["fires_at"] { out["fires_at"] = f }
        } catch let e as HandsError {
            out["ok"] = false
            out["error"] = e.description
            if let o = e.observed { out["observed"] = o }
            if let r = e.result { out["result"] = r }
        } catch {
            out["ok"] = false
            out["error"] = "\(error)"
        }
        out["ms"] = (Date().timeIntervalSince(t0) * 1000).rounded(to: 2)
        return out
    }

    private func run(_ name: String, _ a: [String: Any]) throws -> Any {
        switch name {
        // ---- system ----
        // Read-back skills return the state actually observed afterwards
        // (drives the app's feedback HUD): volume {level, muted},
        // brightness {level}, toggles {on}.
        // Scripts with arguments are handlers of precompiled SkillScripts
        // (compiled once, never per argument).
        case "set_volume":
            let lvl = max(0, min(100, try intArg(a, "level")))
            let st = try scripts.call(SkillScripts.volume, "set_level", [lvl])
            return volumeResult(st, fallbackLevel: lvl, fallbackMuted: false)
        case "change_volume":
            let d = try intArg(a, "delta")
            let cur = Int(try scripts.run("output volume of (get volume settings)").trimmingCharacters(in: .whitespacesAndNewlines)) ?? 50
            let lvl = max(0, min(100, cur + d))
            let st = try scripts.call(SkillScripts.volume, "set_level", [lvl])
            return volumeResult(st, fallbackLevel: lvl, fallbackMuted: false)
        case "mute":
            let on = try boolArg(a, "on")
            let st = try scripts.call(SkillScripts.volume, "set_muted", [on])
            return volumeResult(st, fallbackLevel: nil, fallbackMuted: on)
        case "dark_mode":
            let on = try boolArg(a, "on")
            let back = try scripts.call(SkillScripts.appearance, "set_dark", [on])
            let read = parseBool(back) ?? (try? scripts.run(
                "tell application \"System Events\" to tell appearance preferences to get dark mode"))
                .flatMap { parseBool($0) }
            let now = read ?? on
            return ["on": now, "dark": now]
        case "set_brightness":
            // `level` (absolute) wins; else `delta` relative to the current level.
            var r: [String: Any] = [:]
            let lvl: Int
            if a["level"] != nil {
                lvl = max(0, min(100, try intArg(a, "level")))
            } else {
                let d = try intArg(a, "delta")
                guard let cur = hooks.brightnessGet().map({ Int(($0 * 100).rounded()) }) else {
                    throw HandsError.notImplemented("set_brightness delta (brightness unreadable)")
                }
                lvl = Self.brightnessTarget(current: cur, delta: d)
                r["previous"] = cur
                r["delta"] = d
            }
            guard hooks.brightnessSet(Float(lvl) / 100.0) else {
                throw HandsError.notImplemented("set_brightness (DisplayServices unavailable)")
            }
            usleep(30_000)
            let read = hooks.brightnessGet().map { Int(($0 * 100).rounded()) }
            r["level"] = read ?? lvl
            return r
        case "wifi":
            let on = try boolArg(a, "on")
            try setWifi(on)
            let now = wifiPower() ?? on
            return ["on": now, "wifi": now]
        case "bluetooth":
            return try bluetooth(on: try boolArg(a, "on"))
        case "lock_screen":
            if hooks.lockScreenPrivate() {
                return ["locked": true, "method": "SACLockScreenImmediate"]
            }
            events.post(try Combo.parse("ctrl+cmd+q"))
            return ["locked": true, "method": "ctrl+cmd+q"]
        case "sleep_display":
            try process("/usr/bin/pmset", ["displaysleepnow"])
            return ["sleeping": true]
        case "battery_status":
            return try battery()
        case "take_screenshot":
            let region = a["region"] as? String ?? "full"
            if region == "selection" {
                throw HandsError.notImplemented("region=selection (interactive capture)")
            }
            let out = NSTemporaryDirectory()
            let r = try Screenshot.captureSync(
                windowOnly: region == "window", maxPixels: 4_000_000,
                excludeBundleId: Bundle.main.bundleIdentifier,
                outDir: URL(fileURLWithPath: out))
            let fm = FileManager.default
            let dst = NSHomeDirectory()
                + "/Desktop/screenshot-\(Int(Date().timeIntervalSince1970)).png"
            try? fm.removeItem(atPath: dst)
            try fm.copyItem(atPath: r.path, toPath: dst)
            return ["path": dst, "width": r.width, "height": r.height]

        // ---- apps ----
        case "open_app":
            return try openApp(named: try strArg(a, "app"))
        case "quit_app":
            let app = try strArg(a, "app")
            guard let r = runningApp(app) else {
                throw HandsError.skillFailed("not running: \(app)")
            }
            return ["terminated": r.terminate()]
        case "hide_app":
            let app = try strArg(a, "app")
            guard let r = runningApp(app) else {
                throw HandsError.skillFailed("not running: \(app)")
            }
            return ["hidden": r.hide()]
        case "window_layout":
            return try windowLayout(try strArg(a, "layout"))

        // ---- web ----
        case "open_url":
            var s = try strArg(a, "url")
            if !s.contains("://") { s = "https://" + s }
            guard let u = URL(string: s) else {
                throw HandsError.invalidParams("bad url")
            }
            return try openInBrowser(
                u, extra: ["url": s], browser: a["browser"] as? String)
        case "web_search":
            let q = try strArg(a, "query")
            // Strict: "AT&T", "c++", "a=b" stay part of the query value.
            guard let u = URL(string: "https://www.google.com/search?q=\(pctStrict(q))") else {
                throw HandsError.invalidParams("bad query")
            }
            return try openInBrowser(
                u, extra: ["query": q], browser: a["browser"] as? String)

        // ---- files ----
        case "open_folder":
            let p = try PathAlias.checked(try strArg(a, "path"))
            // Validate the view before anything opens.
            var view: FinderView?
            if let v = a["view"] as? String, !v.isEmpty {
                guard let fv = FinderView.parse(v) else {
                    throw HandsError.invalidParams("open_folder: view must be list|icons|columns|gallery")
                }
                view = fv
            }
            guard FileManager.default.fileExists(atPath: p) else {
                throw HandsError.skillFailed("no such folder: \(p)")
            }
            return try openFolder(path: p, view: view)
        case "open_file":
            let p = try PathAlias.checked(try strArg(a, "path"))
            guard FileManager.default.fileExists(atPath: p) else {
                throw HandsError.skillFailed("no such file: \(p)")
            }
            return try openFile(path: p)
        case "new_folder":
            let parent = try PathAlias.checked(try strArg(a, "parent"))
            let name = try strArg(a, "name")
            let p = parent + "/" + name
            try FileManager.default.createDirectory(
                atPath: p, withIntermediateDirectories: true)
            return ["path": p]
        case "find_file":
            return try findFile(query: try strArg(a, "query"),
                                kind: a["kind"] as? String ?? "any")
        case "move_to_trash":
            let p = try PathAlias.checked(try strArg(a, "path"))
            var resulting: NSURL?
            try FileManager.default.trashItem(
                at: URL(fileURLWithPath: p), resultingItemURL: &resulting)
            return ["trashed": p]
        case "empty_trash":
            // risk=confirm: execute() already required confirmed:true.
            _ = try scripts.run("tell application \"Finder\" to empty trash")
            return ["emptied": true]

        // ---- time ----
        case "start_timer":
            guard let secs = Skills.parseDuration(a["duration"]), secs > 0, secs <= 86_400 else {
                throw HandsError.invalidParams("start_timer: duration must be seconds in (0, 86400]")
            }
            let label = (a["label"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            return startTimer(seconds: secs, label: label)

        // ---- premiere ----
        case "premiere_command":
            return try premiereCommand(try strArg(a, "command"), preset: a["preset"] as? String)
        case "create_event":
            return try createEvent(a)
        case "create_reminder":
            return try createReminder(a)
        case "todays_agenda":
            return try todaysAgenda()

        // ---- notes ----
        case "new_note":
            let body = try strArg(a, "body")
            let title = a["title"] as? String ?? String(body.prefix(40))
            _ = try scripts.call(SkillScripts.notes, "new_note",
                                 [title, Self.noteHTML(title: title, body: body)])
            return ["title": title]

        // ---- media ----
        case "media_control":
            let action = try strArg(a, "action")
            guard let key = MediaKey.forMediaAction(action) else {
                throw HandsError.invalidParams("media action \(action)")
            }
            events.postMediaKey(key)
            return ["action": action]
        case "play_music":
            let q = try strArg(a, "query")
            _ = try scripts.call(SkillScripts.music, "play_query", [q])
            return ["query": q]

        // ---- input ----
        case "type_text":
            // Types to the keyboard focus of the frontmost app; refuse when
            // nothing there takes text (never "ok" while typing into nothing),
            // and never into the lock screen. A keystroke app (Calculator)
            // gets key presses.
            let text = try strArg(a, "text")
            if apps.screenLocked() { throw HandsError.screenLocked }
            let pid = apps.frontmostPid()
            let info = apps.app(pid: pid)
            let chk = TextTarget.check(app: axApp(pid), appName: info?.name ?? apps.name(pid: pid),
                                       bundleId: info?.bundleId)
            guard chk.ok else { throw HandsError.noTextTarget(observed: chk.observed) }
            if chk.via == TextTarget.keystrokeVia {
                events.typeKeystrokes(TextTarget.keystrokeText(text))
            } else {
                if let t = chk.focusTarget {
                    _ = t.setAttr(kAXFocusedAttribute, true)
                    usleep(30_000)
                }
                events.typeText(text)
            }
            return ["typed": text.count, "target": chk.via ?? "focused", "observed": chk.observed]
        case "copy_selection":
            Combo.post(try Combo.parse("cmd+c"))
            return ["copied": true]

        // ---- comms ----
        case "send_message":
            // Defense in depth: never AppleScript-send to a bare name —
            // only a verbatim phone (>= 7 digits) or email. The comms
            // route (contacts_search -> messages_compose -> messages_send)
            // resolves names first.
            let to = try strArg(a, "to")
            let body = try strArg(a, "body")
            guard MessageHandles.parse(to) != nil else {
                throw HandsError.skillFailed("unresolved_recipient")
            }
            _ = try scripts.call(SkillScripts.messages, "send_text", [to, body])
            return ["to": to]
        case "compose_email":
            let to = try strArg(a, "to")
            let subject = a["subject"] as? String ?? ""
            let body = try strArg(a, "body")
            var s = "mailto:\(pct(to))?body=\(pctStrict(body))"
            if !subject.isEmpty { s += "&subject=\(pctStrict(subject))" }
            guard let u = URL(string: s) else {
                throw HandsError.invalidParams("bad mailto")
            }
            NSWorkspace.shared.open(u)
            return ["to": to, "draft": true]

        default:
            throw HandsError.notImplemented(name)
        }
    }

    // MARK: helpers

    private func runningApp(_ name: String) -> NSRunningApplication? {
        NSWorkspace.shared.runningApplications.first {
            ($0.localizedName ?? "").localizedCaseInsensitiveCompare(name) == .orderedSame
        } ?? NSWorkspace.shared.runningApplications.first {
            ($0.localizedName ?? "").localizedCaseInsensitiveContains(name)
        }
    }

    private func intArg(_ a: [String: Any], _ k: String) throws -> Int {
        if let i = a[k] as? Int { return i }
        if let n = a[k] as? NSNumber { return n.intValue }
        if let s = a[k] as? String, let i = Int(s) { return i }
        throw HandsError.invalidParams("arg \(k) must be int")
    }
    private func boolArg(_ a: [String: Any], _ k: String) throws -> Bool {
        if let b = a[k] as? Bool { return b }
        if let n = a[k] as? NSNumber { return n.boolValue }
        if let s = a[k] as? String { return ["true", "1", "yes", "on"].contains(s.lowercased()) }
        throw HandsError.invalidParams("arg \(k) must be bool")
    }
    private func strArg(_ a: [String: Any], _ k: String) throws -> String {
        if let s = a[k] as? String, !s.isEmpty { return s }
        if let n = a[k] { return "\(n)" }
        throw HandsError.invalidParams("arg \(k) must be string")
    }

    @discardableResult
    private func process(_ path: String, _ args: [String]) throws -> String {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        try p.run()
        p.waitUntilExit()
        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(),
                         encoding: .utf8) ?? ""
        guard p.terminationStatus == 0 else {
            throw HandsError.skillFailed("\(path): \(out.prefix(200))")
        }
        return out
    }

    // MARK: read-backs

    /// Notes body HTML: `<h1>title</h1><br>body`, text HTML-escaped and
    /// newlines as <br> (handler args are passed verbatim, not spliced into
    /// AppleScript source, so no AppleScript escaping is needed).
    static func noteHTML(title: String, body: String) -> String {
        func esc(_ s: String) -> String {
            s.replacingOccurrences(of: "&", with: "&amp;")
                .replacingOccurrences(of: "<", with: "&lt;")
                .replacingOccurrences(of: ">", with: "&gt;")
                .replacingOccurrences(of: "\r\n", with: "\n")
                .replacingOccurrences(of: "\n", with: "<br>")
        }
        return "<h1>\(esc(title))</h1><br>\(esc(body))"
    }

    /// Parse "30,false" from `volumeStateScript` ("missing value" volume ->
    /// nil level, e.g. outputs without a volume control).
    static func parseVolumeState(_ s: String) -> (level: Int?, muted: Bool?) {
        let parts = s.trimmingCharacters(in: .whitespacesAndNewlines)
            .split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        guard parts.count == 2 else { return (nil, nil) }
        return (Int(parts[0]) ?? Double(parts[0]).map { Int($0.rounded()) }, parseBool(parts[1]))
    }

    /// `state`: the "<volume>,<muted>" the volume handler read back; when it
    /// doesn't parse, read again with `volumeStateScript`.
    private func volumeResult(_ state: String?, fallbackLevel: Int?, fallbackMuted: Bool) -> [String: Any] {
        var st = Self.parseVolumeState(state ?? "")
        if st.muted == nil { st = Self.parseVolumeState((try? scripts.run(Self.volumeStateScript)) ?? "") }
        var r: [String: Any] = ["muted": st.muted ?? fallbackMuted]
        if let l = st.level ?? fallbackLevel { r["level"] = l }
        return r
    }

    private func wifiPower() -> Bool? {
        guard let dev = wifiDevice,
              let out = try? process("/usr/sbin/networksetup", ["-getairportpower", dev]) else {
            return nil
        }
        // "Wi-Fi Power (en0): On"
        if out.range(of: ": On", options: .caseInsensitive) != nil { return true }
        if out.range(of: ": Off", options: .caseInsensitive) != nil { return false }
        return nil
    }

    // MARK: bluetooth

    /// IOBluetooth power setter, verified by polling the getter <= 1 s;
    /// falls back to the Control Center toggle when the symbol is missing
    /// or the state didn't change.
    private func bluetooth(on: Bool) throws -> [String: Any] {
        if let cur = hooks.bluetoothGet(), cur == on {
            return ["on": on, "changed": false, "method": "none"]
        }
        if hooks.bluetoothSet(on) {
            let end = Date().addingTimeInterval(1.0)
            while Date() < end {
                if hooks.bluetoothGet() == on {
                    return ["on": on, "changed": true, "method": "iobluetooth"]
                }
                usleep(50_000)
            }
        }
        let left = try hooks.bluetoothControlCenter(on)
        let now = hooks.bluetoothGet() ?? left
        if now != on {
            throw HandsError.skillFailed("bluetooth: still \(now ? "on" : "off") after toggling")
        }
        return ["on": now, "changed": true, "method": "control_center"]
    }

    // MARK: timer

    /// Seconds from a number or a duration string ("90", "90s", "10 minutes",
    /// "1h 30m", "1:30", "PT10M"). The brain normally sends seconds.
    public static func parseDuration(_ v: Any?) -> Double? {
        if let n = v as? NSNumber {
            // JSON booleans are NSNumbers too; a bool is not a duration.
            if CFGetTypeID(n) == CFBooleanGetTypeID() { return nil }
            return n.doubleValue
        }
        guard var s = (v as? String)?.lowercased().trimmingCharacters(in: .whitespaces),
              !s.isEmpty else { return nil }
        if let d = Double(s) { return d }
        if s.hasPrefix("pt") || s.hasPrefix("p") {
            s = s.replacingOccurrences(of: "pt", with: "").replacingOccurrences(of: "p", with: "")
        }
        let colon = s.split(separator: ":").map { Double($0) }
        if colon.count >= 2, colon.allSatisfy({ $0 != nil }) {
            return colon.compactMap { $0 }.reduce(0) { $0 * 60 + $1 }
        }
        guard let re = try? NSRegularExpression(
            pattern: #"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)(?![a-z])"#)
        else { return nil }
        var total = 0.0
        var found = false
        for m in re.matches(in: s, range: NSRange(s.startIndex..., in: s)) {
            guard let nr = Range(m.range(at: 1), in: s), let ur = Range(m.range(at: 2), in: s),
                  let n = Double(s[nr]) else { continue }
            let u = s[ur]
            let mult: Double = u.hasPrefix("h") ? 3600 : u.hasPrefix("m") ? 60 : 1
            total += n * mult
            found = true
        }
        return found ? total : nil
    }

    /// Clock.app via AX; if that fails, Muselet's own timer (silently).
    /// Both backends are kept in `timers` and the snapshot.
    private func startTimer(seconds: Double, label: String?) -> [String: Any] {
        let ax = clockAXStart(seconds: seconds, label: label)
        if ax.reason == nil {
            let info = timers.start(seconds: seconds, label: label, backend: "clock_ax") { _ in }
            var r: [String: Any] = [
                "backend": "clock_ax", "seconds": seconds, "ms": ax.ms,
                "verified": true, "clock_ax_steps": ax.steps,
                "fires_at": TimerRegistry.isoString(info.firesAt), "timer_id": info.id,
            ]
            if let label { r["label"] = label }
            if let signal = ax.signal { r["verify_signal"] = signal }
            if let method = ax.method { r["wheel_method"] = method }
            if let labelSet = ax.labelSet { r["label_set"] = labelSet }
            return r
        }
        let hooks = self.hooks
        let info = timers.start(seconds: seconds, label: label) { [weak self, weak delegate = self.delegate] _ in
            hooks.playSound("Glass")
            hooks.notify("Timer done", label ?? "Your \(Self.humanDuration(seconds)) timer is up.")
            (self?.delegate ?? delegate)?.handsTimerFired(label: label)
        }
        var r: [String: Any] = ["fires_at": TimerRegistry.isoString(info.firesAt), "seconds": seconds,
                                "timer_id": info.id, "backend": "muselet"]
        if let reason = ax.reason {
            r["fallback_reason"] = reason
            r["clock_ax_reason"] = reason
            r["verified"] = false
            r["clock_ax_steps"] = ax.steps
        }
        if let label { r["label"] = label }
        return r
    }

    /// `set_brightness delta`: current + delta, clamped to 0...100.
    static func brightnessTarget(current: Int, delta: Int) -> Int {
        max(0, min(100, current + delta))
    }

    static func humanDuration(_ s: Double) -> String {
        let n = Int(s.rounded())
        if n >= 3600, n % 3600 == 0 { return "\(n / 3600)-hour" }
        if n >= 60, n % 60 == 0 { return "\(n / 60)-minute" }
        return "\(n)-second"
    }

    // MARK: premiere

    private func focusPremiereTimeline(_ app: Element) throws {
        guard let bar = axElement(app.copySingleAttr("AXMenuBar")) else {
            throw HandsError.skillFailed("Premiere: Window menu unavailable")
        }
        let windows = bar.copyAttrs().children.filter {
            let a = $0.copyAttrs()
            return a.role == "AXMenuBarItem" && a.title == "Window"
        }
        guard windows.count == 1, let window = windows.first,
              window.copyAttrs().enabled, window.performAction("AXPress") else {
            throw HandsError.skillFailed("Premiere: Window menu press failed")
        }
        let items = window.copyAttrs().children.filter { $0.copyAttrs().role == "AXMenu" }
            .flatMap { $0.copyAttrs().children }.filter {
                let a = $0.copyAttrs()
                return a.role == "AXMenuItem" && a.title == "Timeline"
            }
        guard items.count == 1, let timeline = items.first,
              timeline.copyAttrs().enabled,
              !timeline.copyAttrs().children.contains(where: { $0.copyAttrs().role == "AXMenu" }),
              timeline.performAction("AXPress") else {
            throw HandsError.skillFailed("Premiere: Timeline menu press failed")
        }
    }

    /// Activate Premiere Pro, focus Timeline, then send its default shortcut.
    private func premiereCommand(_ command: String, preset: String?) throws -> [String: Any] {
        guard let keys = Self.premiereKeys[command] else {
            throw HandsError.invalidParams("premiere_command: unknown command \(command)")
        }
        let combo = try Combo.parse(keys)
        guard let app = apps.runningApp(bundlePrefix: Self.premiereBundlePrefix) else {
            throw HandsError.skillFailed("Premiere Pro isn't open")
        }
        // A heavy app: allow up to 1 s to come forward; never send the
        // keystroke to another app.
        guard apps.ensureFrontmost(pid: app.pid, timeout: 1.0) else {
            throw HandsError.focusChanged(expected: app.name,
                                          frontmost: apps.name(pid: apps.frontmostPid()))
        }
        try focusPremiereTimeline(axApp(app.pid))
        guard apps.frontmostPid() == app.pid else {
            throw HandsError.focusChanged(expected: app.name,
                                          frontmost: apps.name(pid: apps.frontmostPid()))
        }
        events.post(combo)
        var r: [String: Any] = ["command": command, "keys": keys, "app": app.name]
        if command == "export" {
            // cmd+m opens Export; presets are picked in the export UI.
            r["preset_applied"] = false
            if let preset { r["preset"] = preset }
        }
        return r
    }

    private func setWifi(_ on: Bool) throws {
        if wifiDevice == nil {
            let out = (try? process("/usr/sbin/networksetup", ["-listallhardwareports"])) ?? ""
            // "Hardware Port: Wi-Fi\nDevice: en0"
            let lines = out.components(separatedBy: "\n")
            for (i, l) in lines.enumerated()
            where l.contains("Wi-Fi") || l.contains("AirPort") {
                if i + 1 < lines.count, let r = lines[i + 1].range(of: "Device:") {
                    wifiDevice = lines[i + 1][r.upperBound...]
                        .trimmingCharacters(in: .whitespaces)
                }
            }
            if wifiDevice == nil { wifiDevice = "en0" }
        }
        _ = try process("/usr/sbin/networksetup",
                        ["-setairportpower", wifiDevice!, on ? "on" : "off"])
    }

    private func battery() throws -> [String: Any] {
        guard let info = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
              let list = IOPSCopyPowerSourcesList(info)?.takeRetainedValue() as? [CFTypeRef],
              let src = list.first,
              let d = IOPSGetPowerSourceDescription(info, src)?
                  .takeUnretainedValue() as? [String: Any] else {
            throw HandsError.skillFailed("no power source info")
        }
        let cur = d["Current Capacity"] as? Int ?? -1
        let maxc = d["Max Capacity"] as? Int ?? 100
        let charging = (d["Is Charging"] as? Bool) ?? false
        let attached = (d["Power Source State"] as? String) ?? ""
        return ["percent": maxc > 0 ? Int(100.0 * Double(cur) / Double(maxc)) : cur,
                "charging": charging, "source": attached]
    }

    private func windowLayout(_ layout: String) throws -> [String: Any] {
        guard let app = NSWorkspace.shared.frontmostApplication else {
            throw HandsError.skillFailed("no frontmost app")
        }
        let appEl = AXUIElementCreateApplication(app.processIdentifier)
        // Focused, else main, else frontmost AXWindows entry (an app that
        // isn't active has no focused window although its window is up).
        guard let picked = Hands.pickWindow(app: AXNode(appEl))?.window as? AXNode else {
            throw HandsError.skillFailed("no window")
        }
        let win: CFTypeRef = picked.el
        guard let screen = NSScreen.main else {
            throw HandsError.skillFailed("no screen")
        }
        // NSScreen frames are bottom-left origin; AX positions are top-left.
        let vf = screen.visibleFrame
        let totalH = screen.frame.height
        func toAX(_ r: CGRect) -> CGRect {
            CGRect(x: r.minX, y: totalH - r.maxY, width: r.width, height: r.height)
        }
        let target: CGRect
        switch layout {
        case "full": target = vf
        case "left": target = CGRect(x: vf.minX, y: vf.minY,
                                     width: vf.width / 2, height: vf.height)
        case "right": target = CGRect(x: vf.midX, y: vf.minY,
                                      width: vf.width / 2, height: vf.height)
        case "center":
            target = CGRect(x: vf.midX - vf.width * 0.35, y: vf.midY - vf.height * 0.4,
                            width: vf.width * 0.7, height: vf.height * 0.8)
        default: throw HandsError.invalidParams("layout \(layout)")
        }
        let ax = toAX(target)
        var pos = ax.origin, size = ax.size
        let posV = AXValueCreate(.cgPoint, &pos)!
        let sizeV = AXValueCreate(.cgSize, &size)!
        // With AXEnhancedUserInterface on (web AX for Safari/Gecko), AppKit
        // animates AX frame changes and a size set mid-animation can be
        // lost: switch it off around the move (Rectangle does the same).
        // Not for Chromium browsers: turning it off drops Chrome's web tree
        // at once and it only comes back after a 2 s debounce.
        let enhanced = WebAX.enhancedAttribute as CFString
        var cur: CFTypeRef?
        let pauseEnhanced = WebAX.mode(bundleId: app.bundleIdentifier, bundleURL: app.bundleURL) != .chromium
            && AXUIElementCopyAttributeValue(appEl, enhanced, &cur) == .success
            && (cur as? Bool) == true
        if pauseEnhanced { AXUIElementSetAttributeValue(appEl, enhanced, kCFBooleanFalse) }
        defer { if pauseEnhanced { AXUIElementSetAttributeValue(appEl, enhanced, kCFBooleanTrue) } }
        // size, position, size: the first size may be clamped by the old position.
        AXUIElementSetAttributeValue(win as! AXUIElement, kAXSizeAttribute as CFString, sizeV)
        AXUIElementSetAttributeValue(win as! AXUIElement, kAXPositionAttribute as CFString, posV)
        AXUIElementSetAttributeValue(win as! AXUIElement, kAXSizeAttribute as CFString, sizeV)
        return ["layout": layout,
                "frame": [ax.minX, ax.minY, ax.width, ax.height]]
    }

    private func findFile(query: String, kind: String) throws -> [String: Any] {
        // escape mdfind-wildcard and quote chars in the user query
        let q = query.replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "*", with: "\\*")
        var predicate = "kMDItemDisplayName == \"*\(q)*\"cd || kMDItemTextContent == \"*\(q)*\"cd"
        let kinds: [String: String] = [
            "pdf": "public.pdf", "image": "public.image", "video": "public.movie",
            "document": "public.content", "folder": "public.folder",
        ]
        if let uti = kinds[kind] {
            predicate = "kMDItemContentTypeTree == \"\(uti)\" && kMDItemDisplayName == \"*\(query)*\"cd"
        }
        let out = try process("/usr/bin/mdfind", [predicate])
        let paths = out.components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let top = Array(paths.prefix(10))
        return ["results": top, "count": paths.count]
    }

    // MARK: EventKit

    private func store() throws -> EKEventStore { EKEventStore() }

    private func requestAccess(_ s: EKEventStore, entity: EKEntityType) throws {
        let sem = DispatchSemaphore(value: 0)
        var granted = false, err: Error?
        if #available(macOS 14, *) {
            if entity == .event {
                s.requestFullAccessToEvents { g, e in granted = g; err = e; sem.signal() }
            } else {
                s.requestFullAccessToReminders { g, e in granted = g; err = e; sem.signal() }
            }
        } else {
            s.requestAccess(to: entity) { g, e in granted = g; err = e; sem.signal() }
        }
        _ = sem.wait(timeout: .now() + 30)
        if let e = err { throw HandsError.skillFailed(e.localizedDescription) }
        guard granted else { throw HandsError.permission("calendar/reminders access denied") }
    }

    func iso(_ s: String) throws -> Date {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        let f2 = ISO8601DateFormatter()
        f2.formatOptions = [.withInternetDateTime]
        if let d = f2.date(from: s) { return d }
        // Naive local ISO (no offset): read in the current time zone.
        for fmt in ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd'T'HH:mm"] {
            let df = DateFormatter()
            df.locale = Locale(identifier: "en_US_POSIX")
            df.timeZone = .current
            df.dateFormat = fmt
            if let d = df.date(from: s) { return d }
        }
        throw HandsError.invalidParams("bad datetime: \(s)")
    }

    private func createEvent(_ a: [String: Any]) throws -> [String: Any] {
        let s = try store()
        try requestAccess(s, entity: .event)
        let ev = EKEvent(eventStore: s)
        ev.title = try strArg(a, "title")
        ev.startDate = try iso(try strArg(a, "start"))
        ev.endDate = a["end"] != nil ? try iso(try strArg(a, "end"))
                                     : ev.startDate.addingTimeInterval(3600)
        ev.location = a["location"] as? String
        ev.calendar = s.defaultCalendarForNewEvents
        try s.save(ev, span: .thisEvent)
        return ["event_id": ev.eventIdentifier ?? "", "title": ev.title ?? ""]
    }

    private func createReminder(_ a: [String: Any]) throws -> [String: Any] {
        let s = try store()
        try requestAccess(s, entity: .reminder)
        let r = EKReminder(eventStore: s)
        r.title = try strArg(a, "title")
        if let due = a["due"] as? String {
            let d = try iso(due)
            r.dueDateComponents = Calendar.current.dateComponents(
                [.year, .month, .day, .hour, .minute, .second], from: d)
        }
        r.calendar = s.defaultCalendarForNewReminders()
        try s.save(r, commit: true)
        return ["reminder_id": r.calendarItemIdentifier, "title": r.title ?? ""]
    }

    private func todaysAgenda() throws -> [String: Any] {
        let s = try store()
        try requestAccess(s, entity: .event)
        let cal = Calendar.current
        let start = cal.startOfDay(for: Date())
        let end = cal.date(byAdding: .day, value: 1, to: start)!
        let pred = s.predicateForEvents(withStart: start, end: end, calendars: nil)
        let fmt = ISO8601DateFormatter()
        let events = s.events(matching: pred).map {
            ["title": $0.title ?? "", "start": fmt.string(from: $0.startDate),
             "end": fmt.string(from: $0.endDate), "location": $0.location ?? ""]
        }
        return ["events": events, "count": events.count]
    }
}

/// "true"/"false"/"yes"/"no"/"1"/"0"/"on"/"off" -> Bool.
func parseBool(_ s: String) -> Bool? {
    switch s.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
    case "true", "yes", "1", "on": return true
    case "false", "no", "0", "off": return false
    default: return nil
    }
}

/// Escape a value for embedding inside an AppleScript string literal.
func asq(_ s: String) -> String {
    s.replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\"", with: "\\\"")
        .replacingOccurrences(of: "\n", with: " ")
}

func pct(_ s: String) -> String {
    s.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? s
}

/// Strict mailto encoding: also escapes & = + # ? inside values.
func pctStrict(_ s: String) -> String {
    var allowed = CharacterSet.urlQueryAllowed
    allowed.remove(charactersIn: "&=+#?")
    return s.addingPercentEncoding(withAllowedCharacters: allowed) ?? s
}
