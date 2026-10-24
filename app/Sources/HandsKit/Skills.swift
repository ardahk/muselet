import AppKit
import ApplicationServices
import CoreGraphics
import EventKit
import Foundation
import IOKit.ps

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

// MARK: - Script runner (NSAppleScript, compiled once, cached)

public protocol ScriptRunning {
    func run(_ source: String) throws -> String
}

public final class AppleScriptRunner: ScriptRunning {
    private static let capacity = 64
    private var cache: [String: NSAppleScript] = [:]
    private var lru: [String] = []          // oldest first
    private let lock = NSLock()
    public init() {}
    public func run(_ source: String) throws -> String {
        lock.lock(); defer { lock.unlock() }
        let script: NSAppleScript
        if let s = cache[source] {
            lru.removeAll { $0 == source }
            lru.append(source)
            script = s
        } else {
            var err: NSDictionary?
            guard let s = NSAppleScript(source: source) else {
                throw HandsError.skillFailed("applescript init failed")
            }
            s.compileAndReturnError(&err)
            if let e = err { throw HandsError.skillFailed("applescript compile: \(e)") }
            cache[source] = s
            lru.append(source)
            if lru.count > Self.capacity {
                cache.removeValue(forKey: lru.removeFirst())
            }
            script = s
        }
        var err: NSDictionary?
        let out = script.executeAndReturnError(&err)
        if let e = err {
            throw HandsError.skillFailed(
                "applescript: \((e["NSAppleScriptErrorMessage"] as? String) ?? "\(e)")")
        }
        return out.stringValue ?? ""
    }

    /// Precompile and run `return 1` + the fixed (argument-free) skill
    /// scripts, so the first real call doesn't pay the ~9 s compile cost.
    public func warmUp() {
        let fixed: [String] = [
            "return 1",
            "output volume of (get volume settings)",
            "tell application \"System Events\" to tell appearance preferences to get dark mode",
        ]
        for src in fixed { _ = try? run(src) }
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
}

// MARK: - Skills engine

public final class Skills {
    private let catalog: [String: SkillDef]
    private let scripts: ScriptRunning
    private var wifiDevice: String?

    /// Precompile AppleScript sources off the hot path (RPCHandler calls
    /// this on a background queue at startup).
    public func warmUp() {
        (scripts as? AppleScriptRunner)?.warmUp()
    }

    public init(catalog: [String: SkillDef], scripts: ScriptRunning = AppleScriptRunner()) {
        self.catalog = catalog
        self.scripts = scripts
    }
    public convenience init() {
        self.init(catalog: (try? Catalog.load()) ?? [:])
    }

    public func def(_ name: String) -> SkillDef? { catalog[name] }

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
            // Required-arg check.
            for a in def.args where a.required {
                if inArgs[a.name] == nil {
                    throw HandsError.invalidParams("\(name): missing arg \(a.name)")
                }
            }
            let result = try run(name, inArgs)
            out["ok"] = true
            out["result"] = result
        } catch let e as HandsError {
            out["ok"] = false
            out["error"] = e.description
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
        case "set_volume":
            let lvl = try intArg(a, "level")
            _ = try scripts.run("set volume output volume \(lvl)")
            return ["level": lvl]
        case "change_volume":
            let d = try intArg(a, "delta")
            let cur = Int(try scripts.run("output volume of (get volume settings)").trimmingCharacters(in: .whitespacesAndNewlines)) ?? 50
            let lvl = max(0, min(100, cur + d))
            _ = try scripts.run("set volume output volume \(lvl)")
            return ["level": lvl]
        case "mute":
            let on = try boolArg(a, "on")
            _ = try scripts.run(on ? "set volume with output muted"
                                   : "set volume without output muted")
            return ["muted": on]
        case "dark_mode":
            let on = try boolArg(a, "on")
            _ = try scripts.run(
                "tell application \"System Events\" to tell appearance preferences to set dark mode to \(on)")
            return ["dark": on]
        case "set_brightness":
            let lvl = try intArg(a, "level")
            try setBrightness(Float(lvl) / 100.0)
            return ["level": lvl]
        case "wifi":
            let on = try boolArg(a, "on")
            try setWifi(on)
            return ["wifi": on]
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
            try openAppNamed(try strArg(a, "app"))
            return ["app": a["app"]!]
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
            NSWorkspace.shared.open(u)
            return ["url": s]
        case "web_search":
            let q = try strArg(a, "query")
            let enc = q.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? q
            guard let u = URL(string: "https://www.google.com/search?q=\(enc)") else {
                throw HandsError.invalidParams("bad query")
            }
            NSWorkspace.shared.open(u)
            return ["query": q]

        // ---- files ----
        case "open_folder":
            let p = PathAlias.resolve(try strArg(a, "path"))
            guard FileManager.default.fileExists(atPath: p) else {
                throw HandsError.skillFailed("no such folder: \(p)")
            }
            NSWorkspace.shared.open(URL(fileURLWithPath: p))
            return ["path": p]
        case "open_file":
            let p = PathAlias.resolve(try strArg(a, "path"))
            guard FileManager.default.fileExists(atPath: p) else {
                throw HandsError.skillFailed("no such file: \(p)")
            }
            NSWorkspace.shared.open(URL(fileURLWithPath: p))
            return ["path": p]
        case "new_folder":
            let parent = PathAlias.resolve(try strArg(a, "parent"))
            let name = try strArg(a, "name")
            let p = parent + "/" + name
            try FileManager.default.createDirectory(
                atPath: p, withIntermediateDirectories: true)
            return ["path": p]
        case "find_file":
            return try findFile(query: try strArg(a, "query"),
                                kind: a["kind"] as? String ?? "any")
        case "move_to_trash":
            let p = PathAlias.resolve(try strArg(a, "path"))
            var resulting: NSURL?
            try FileManager.default.trashItem(
                at: URL(fileURLWithPath: p), resultingItemURL: &resulting)
            return ["trashed": p]

        // ---- time ----
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
            _ = try scripts.run("""
                tell application "Notes"
                    make new note at folder "Notes" with properties {name:"\(asq(title))", body:"<h1>\(asq(title))</h1><br>\(asq(body))"}
                end tell
                """)
            return ["title": title]

        // ---- media ----
        case "media_control":
            let action = try strArg(a, "action")
            let key: Int32
            switch action {
            case "play", "pause", "toggle": key = 16
            case "next": key = 17
            case "previous": key = 18
            default: throw HandsError.invalidParams("media action \(action)")
            }
            postMediaKey(key)
            return ["action": action]
        case "play_music":
            let q = try strArg(a, "query")
            _ = try scripts.run("""
                tell application "Music"
                    activate
                    if (count (every track of library playlist 1 whose name contains "\(asq(q))")) > 0 then
                        play (first track of library playlist 1 whose name contains "\(asq(q))")
                    else if (count (every playlist whose name contains "\(asq(q))")) > 0 then
                        play (first playlist whose name contains "\(asq(q))")
                    else
                        play (first track of library playlist 1 whose artist contains "\(asq(q))")
                    end if
                end tell
                """)
            return ["query": q]

        // ---- input ----
        case "type_text":
            Events.typeText(try strArg(a, "text"))
            return ["typed": (a["text"] as? String)?.count ?? 0]
        case "copy_selection":
            Combo.post(try Combo.parse("cmd+c"))
            return ["copied": true]

        // ---- comms ----
        case "send_message":
            let to = try strArg(a, "to")
            let body = try strArg(a, "body")
            _ = try scripts.run("""
                tell application "Messages"
                    send "\(asq(body))" to participant "\(asq(to))" of first account
                end tell
                """)
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

    private func setBrightness(_ v: Float) throws {
        typealias Fn = @convention(c) (CGDirectDisplayID, Float) -> Int32
        guard let h = dlopen(
            "/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices",
            RTLD_LAZY),
              let sym = dlsym(h, "DisplayServicesSetBrightness") else {
            throw HandsError.notImplemented("set_brightness (DisplayServices unavailable)")
        }
        let f = unsafeBitCast(sym, to: Fn.self)
        _ = f(CGMainDisplayID(), v)
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
        var w: CFTypeRef?
        guard AXUIElementCopyAttributeValue(appEl, kAXFocusedWindowAttribute as CFString, &w) == .success,
              let win = w else { throw HandsError.skillFailed("no focused window") }
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

    private func iso(_ s: String) throws -> Date {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        let f2 = ISO8601DateFormatter()
        f2.formatOptions = [.withInternetDateTime]
        if let d = f2.date(from: s) { return d }
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

    // MARK: media keys

    private func postMediaKey(_ key: Int32) {
        // data1 = key<<16 | state<<8 where 0xA=down, 0xB=up
        func ev(_ down: Bool) -> NSEvent? {
            let flags = down ? 0xA00 : 0xB00
            let state = down ? 0xA : 0xB
            return NSEvent.otherEvent(
                with: .systemDefined, location: .zero,
                modifierFlags: NSEvent.ModifierFlags(rawValue: UInt(flags)),
                timestamp: 0, windowNumber: 0, context: nil,
                subtype: 8, data1: (Int(key) << 16) | (state << 8), data2: -1)
        }
        ev(true)?.cgEvent?.post(tap: .cghidEventTap)
        ev(false)?.cgEvent?.post(tap: .cghidEventTap)
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
