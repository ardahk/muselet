import AppKit
import ApplicationServices
import ArgumentParser
import Foundation
import HandsKit

func printJSON(_ v: Any) {
    if let d = try? JSONSerialization.data(
        withJSONObject: v, options: [.prettyPrinted, .sortedKeys]),
       let s = String(data: d, encoding: .utf8) { print(s) }
}

@main
struct HandsCLI: ParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "hands",
        abstract: "HandsKit headless CLI: observe, act, skills, brain client.",
        subcommands: [ObserveCmd.self, ReplCmd.self, SkillCmd.self,
                      BenchObserveCmd.self, ServeCmd.self, OcrCmd.self, ProbeCmd.self,
                      WebAXCmd.self])
}

struct OcrCmd: ParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "ocr", abstract: "Apple Vision OCR on an image file (or a screen region).")
    @Option(help: "Image path") var path: String?
    @Option(help: "Screen region x,y,w,h in global points (needs Screen Recording)")
    var region: String?
    @Flag(help: "Print only the joined text") var text = false
    @Flag(help: "Run the OCR warm-up first (prints its ms to stderr)") var warm = false
    func run() throws {
        if warm {
            let ms = OCR.warmUp()
            FileHandle.standardError.write("warmup_ms=\(Int(ms))\n".data(using: .utf8)!)
        }
        var rect: CGRect?
        if let region {
            let v = region.split(separator: ",").compactMap { Double($0) }
            guard v.count == 4 else { throw ValidationError("region must be x,y,w,h") }
            rect = CGRect(x: v[0], y: v[1], width: v[2], height: v[3])
        }
        guard path != nil || rect != nil else { throw ValidationError("--path or --region") }
        // Direct call (no RPCHandler: its AppleScript warm-up isn't needed here).
        let d = try OCR.run(path: path, region: path == nil ? rect : nil, excludeBundleId: nil)
        if text { print(d["text"] as? String ?? "") } else { printJSON(d) }
    }
}

/// Read-only state probes (never change anything).
struct ProbeCmd: ParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "probe",
        abstract: "Read-only probes: bluetooth | volume | brightness | symbols | skill-targets | applescript | automation | control-center | timers | clock | session")
    @Argument(help: "bluetooth | volume | brightness | symbols | skill-targets | applescript | automation | control-center | timers | clock | session | contacts | windows")
    var what: String
    @Option(help: "contacts: the search query")
    var query: String = ""
    @Option(help: "windows: bundle id(s), repeatable")
    var bundleId: [String] = []
    @Flag(help: "applescript: time the old per-argument compile path instead")
    var legacy = false
    @Flag(help: "control-center: open the panel; clock: open Clock and select Timers (never starts or cancels)")
    var open = false
    @Flag(help: "timers: run start_timer / timers / timers_cancel in this process instead (nothing fires)")
    var demo = false
    func run() throws {
        switch what {
        case "session":
            // Live-test precondition: input acts refuse (screen_locked) while locked.
            let front = NSWorkspace.shared.frontmostApplication
            var active: UInt32 = 0
            CGGetActiveDisplayList(0, nil, &active)
            printJSON(["screen_locked": SessionState.screenLocked(),
                       "frontmost": front?.localizedName ?? NSNull(),
                       "frontmost_bundle_id": front?.bundleIdentifier ?? NSNull(),
                       "main_display_asleep": CGDisplayIsAsleep(CGMainDisplayID()) != 0,
                       "active_displays": Int(active)])
        case "timers":
            // Live: the timers of running Muselet / `hands serve` processes
            // (their snapshot files). --demo: the RPC round trip in-process.
            if demo {
                printJSON(TimerProbe.demo())
            } else {
                let info = ClockTimers(runner: ShortcutsCLI()).info(refresh: true)
                let axReady = ClockAX.liveReady()
                var backend = info
                backend["clock_ax_ready"] = axReady
                backend["backend"] = ClockAX.backend(
                    enabled: true, axReady: axReady,
                    shortcutReady: info["clock_ready"] as? Bool ?? false)
                printJSON(["timers": TimerSnapshot.read(),
                           "source": TimerSnapshot.directory.path, "backend": backend])
            }
        case "clock":
            printJSON(ClockAXProbe.run(open: open))
        case "applescript":
            printJSON(legacy ? AppleScriptProbe.legacy() : AppleScriptProbe.handlers())
        case "automation":
            // Status for THIS process (the terminal), never prompts.
            var d: [String: Any] = [:]
            for (t, s) in Automation.statuses() { d[t.name] = "\(s)" }
            printJSON(d)
        case "contacts":
            // The contacts_search RPC end to end in this process (may
            // trigger the system Contacts prompt once).
            let (ok, r, e) = ContactsSearch.rpc(query: query, limit: 5)
            var d: [String: Any] = ["ok": ok]
            if let r { d["result"] = r }
            if let e { d["error"] = e }
            printJSON(d)
        case "windows":
            // AX-only window inventory per bundle id — never Apple Events.
            printJSON(WindowsProbe.probe(bundleIds: bundleId))
        case "control-center":
            Permissions.requireAX()
            printJSON(ControlCenterProbe.locate(named: "Bluetooth", open: open))
        case "skill-targets":
            // Ghost-cursor targets for skills (Dock icons, menu extras), read over AX.
            let t = SkillTargets()
            let browser = NSWorkspace.shared.urlForApplication(toOpen: URL(string: "https://example.com")!)
            var d: [String: Any] = ["default_browser": browser?.path ?? NSNull()]
            let cases: [(String, [String: Any])] = [
                ("open_app", ["app": "Safari"]), ("open_app", ["app": "Google Chrome"]),
                ("quit_app", ["app": "Numbers"]), ("open_folder", ["path": "~/Downloads"]),
                ("web_search", ["query": "x"]), ("set_volume", ["level": 30]),
                ("wifi", ["on": true]), ("bluetooth", ["on": true]), ("dark_mode", ["on": true]),
            ]
            for (name, args) in cases {
                let t0 = Date()
                let r = t.target(skill: name, args: args)
                let key = "\(name) \(args.values.map { "\($0)" }.joined(separator: ","))"
                d[key] = r.map { ["frame": [$0.frame.minX, $0.frame.minY, $0.frame.width, $0.frame.height],
                                  "label": $0.label ?? "", "ms": (Date().timeIntervalSince(t0) * 1000).rounded(to: 1)] as Any }
                    ?? "none (\((Date().timeIntervalSince(t0) * 1000).rounded(to: 1)) ms)"
            }
            printJSON(d)
        case "bluetooth":
            let get = PrivateSymbols.resolves("IOBluetoothPreferenceGetControllerPowerState")
            let set = PrivateSymbols.resolves("IOBluetoothPreferenceSetControllerPowerState")
            let v = get ? PrivateSymbols.bluetoothPower() : nil
            printJSON(["getter_resolves": get, "setter_resolves": set,
                       "power_on": v.map { $0 as Any } ?? NSNull()])
        case "volume":
            let out = try AppleScriptRunner().run("""
                set s to get volume settings
                return ((output volume of s) as text) & "," & ((output muted of s) as text)
                """)
            printJSON(["raw": out])
        case "brightness":
            printJSON(["brightness": PrivateSymbols.brightness().map { Double($0) as Any } ?? NSNull()])
        case "symbols":
            var d: [String: Any] = [:]
            for s in ["IOBluetoothPreferenceGetControllerPowerState",
                      "IOBluetoothPreferenceSetControllerPowerState", "SACLockScreenImmediate",
                      "DisplayServicesGetBrightness", "DisplayServicesSetBrightness"] {
                d[s] = PrivateSymbols.resolves(s)
            }
            printJSON(d)
        default:
            throw ValidationError("unknown probe \(what)")
        }
    }
}

/// `hands probe timers --demo`: the timers RPCs end to end in this process
/// (two timers started, listed, one cancelled, the rest cancelled). Inert
/// hooks: no sound, no notification, no snapshot file; nothing fires.
enum TimerProbe {
    static func demo() -> [String: Any] {
        let skills = Skills(catalog: (try? Catalog.load()) ?? [:], hooks: .inert)
        let rpc = RPCHandler(skills: skills, warmUp: false)
        var steps: [[String: Any]] = []
        func call(_ method: String, _ params: [String: Any]) -> Any? {
            let (ok, r, e) = rpc.handle(method: method, params: params)
            var d: [String: Any] = ["rpc": method, "params": params, "ok": ok]
            if let r { d["result"] = r }
            if let e { d["error"] = e }
            steps.append(d)
            return r
        }
        let a = call("skill", ["name": "start_timer", "args": ["duration": 600, "label": "probe tea"]])
        _ = call("skill", ["name": "start_timer", "args": ["duration": "90s"]])
        _ = call("timers", [:])
        let id = ((a as? [String: Any])?["result"] as? [String: Any])?["timer_id"] as? String ?? "?"
        _ = call("timers_cancel", ["id": id])
        _ = call("timers_cancel", ["id": "timer-nope"])
        _ = call("timers_cancel", [:])
        _ = call("timers", [:])
        return ["steps": steps, "pending_after": skills.pendingTimers]
    }
}

struct ObserveCmd: ParsableCommand {
    static var configuration = CommandConfiguration(commandName: "observe")
    @Option(help: "App name (default: frontmost)") var app: String?
    @Option(help: "Max elements") var max: Int = 150
    @Option(help: "Scope: focused_window|app|menubar") var scope = "focused_window"
    @Flag(help: "Emit JSON instead of text") var json = false
    @Flag(help: "Don't turn on the web AX tree (AXManualAccessibility / AXEnhancedUserInterface)")
    var noWebAx = false
    @Option(help: "Re-observe N more times (stats lines only), e.g. to watch a web tree populate")
    var repeatCount: Int = 0
    @Option(help: "Interval between repeats (ms)") var intervalMs: Int = 250
    func run() throws {
        Permissions.requireAX()
        WebAX.Registry.shared.isEnabled = !noWebAx
        if json {
            let rpc = RPCHandler(warmUp: false)
            let (ok, r, e) = rpc.handle(method: "observe", params: [
                "app": app as Any, "max_nodes": max, "scope": scope, "diff": true])
            if ok, let r { printJSON(r) }
            else { FileHandle.standardError.write("error: \(e ?? "?")\n".data(using: .utf8)!); throw ExitCode(1) }
        } else {
            let h = Hands()
            h.webAXEnabled = !noWebAx
            let t0 = Date()
            func stats(_ obs: Observation) -> String {
                let web = obs.elements.filter { $0.inWebArea }.count
                var line = "t_ms=\(Int(Date().timeIntervalSince(t0) * 1000)) ax_ms=\(obs.axMs.rounded(to: 1))"
                    + " nodes=\(obs.elements.count) web_nodes=\(web) window_source=\(obs.windowSource)"
                    + (obs.truncated ? " truncated" : "") + (obs.webAXPending ? " web_ax_pending" : "")
                if let m = obs.webAX, let last = h.lastWebAX {
                    line += " web_ax=\(m) manual_err=\(last.result.manualError.map(String.init) ?? "-")"
                        + " enhanced_err=\(last.result.enhancedError.map(String.init) ?? (last.result.enhancedAlreadyOn ? "already_on" : "-"))"
                    if let w = last.wait {
                        line += " web_wait_ms=\(w.ms.rounded(to: 1)) web_area=\(w.foundWebArea)"
                            + " populated=\(w.populated) polls=\(w.polls)"
                    } else {
                        line += " web_wait=skipped"
                    }
                }
                return line
            }
            let obs = try h.observe(scope: scope, app: app, maxNodes: max)
            print(obs.text)
            if let d = obs.diffText, !d.isEmpty { print("--- diff ---\n\(d)") }
            FileHandle.standardError.write((stats(obs) + "\n").data(using: .utf8)!)
            for _ in 0..<Swift.max(0, repeatCount) {
                usleep(UInt32(Swift.max(0, intervalMs)) * 1000)
                let o = try h.observe(scope: scope, app: app, maxNodes: max, diff: false)
                FileHandle.standardError.write((stats(o) + "\n").data(using: .utf8)!)
            }
            if repeatCount > 0, let last = try? h.observe(scope: scope, app: app, maxNodes: max, diff: false) {
                print("--- last ---\n\(last.text)")
            }
        }
    }
}

/// Inspect (and optionally set) an app's web AX switches.
struct WebAXCmd: ParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "webax",
        abstract: "Show an app's AXManualAccessibility / AXEnhancedUserInterface and web area; --set changes them.")
    @Option(help: "App name") var app: String
    @Option(help: "manual | enhanced | off (sets both false) | manual-off | enhanced-off") var set: String?
    @Option(help: "Print the focused window's role tree to this depth (stderr)") var dump: Int?
    func run() throws {
        Permissions.requireAX()
        guard let ra = NSWorkspace.shared.runningApplications.first(where: {
            ($0.localizedName ?? "").localizedCaseInsensitiveCompare(app) == .orderedSame
        }) else { throw ValidationError("not running: \(app)") }
        let appEl = AXUIElementCreateApplication(ra.processIdentifier)
        let node = AXNode(appEl)
        node.setMessagingTimeout(0.5)
        var d: [String: Any] = ["app": ra.localizedName ?? app, "pid": ra.processIdentifier,
                                "bundle_id": ra.bundleIdentifier ?? "",
                                "mode": WebAX.mode(bundleId: ra.bundleIdentifier,
                                                   bundleURL: ra.bundleURL)?.rawValue ?? "none"]
        func state(_ prefix: String) {
            for a in [WebAX.manualAttribute, WebAX.enhancedAttribute] {
                let v = node.copySingleAttr(a)
                d["\(prefix)\(a)"] = (v as? Bool).map { $0 as Any } ?? (v.map { "\($0)" } ?? "unset")
            }
        }
        state("before_")
        if let set {
            // Raw AXError codes (0 = success; Chromium may report an error yet apply it).
            var r: [String: Int] = [:]
            func put(_ attr: String, _ v: Bool) -> Int {
                Int(AXUIElementSetAttributeValue(appEl, attr as CFString,
                                                 (v ? kCFBooleanTrue : kCFBooleanFalse)!).rawValue)
            }
            switch set {
            case "manual": r["manual"] = put(WebAX.manualAttribute, true)
            case "enhanced": r["enhanced"] = put(WebAX.enhancedAttribute, true)
            case "manual-off": r["manual"] = put(WebAX.manualAttribute, false)
            case "enhanced-off": r["enhanced"] = put(WebAX.enhancedAttribute, false)
            case "off":
                r["manual"] = put(WebAX.manualAttribute, false)
                r["enhanced"] = put(WebAX.enhancedAttribute, false)
            default: throw ValidationError("bad --set \(set)")
            }
            d["set_axerror"] = r
            state("after_")
        }
        let wins = (node.copySingleAttr(kAXWindowsAttribute as String) as? [AXUIElement]) ?? []
        d["windows"] = wins.map { w -> String in
            let n = AXNode(w)
            n.setMessagingTimeout(0.5)
            return n.copySingleAttr(kAXTitleAttribute as String) as? String ?? ""
        }
        if let w = node.copySingleAttr(kAXFocusedWindowAttribute as String),
           CFGetTypeID(w as CFTypeRef) == AXUIElementGetTypeID() {
            let win = AXNode(w as! AXUIElement)
            win.setMessagingTimeout(0.5)
            d["window"] = win.copySingleAttr(kAXTitleAttribute as String) as? String ?? ""
            if let area = WebAX.findWebArea(in: win, deadline: Date().addingTimeInterval(1)) {
                d["web_area_children"] = area.copyAttrs().children.count
            } else {
                d["web_area_children"] = NSNull()
            }
            if let depth = dump {
                var lines: [String] = []
                func walk(_ el: Element, _ lvl: Int) {
                    guard lines.count < 400 else { return }
                    let a = el.copyAttrs()
                    let name = [a.title, a.desc].compactMap { $0 }.first { !$0.isEmpty } ?? ""
                    lines.append(String(repeating: "  ", count: lvl)
                                 + "\(a.role ?? "?")\(a.subrole.map { "/\($0)" } ?? "") \"\(name.prefix(40))\" kids=\(a.children.count)")
                    if lvl < depth { a.children.forEach { walk($0, lvl + 1) } }
                }
                walk(win, 0)
                FileHandle.standardError.write((lines.joined(separator: "\n") + "\n").data(using: .utf8)!)
            }
        }
        printJSON(d)
    }
}

struct ReplCmd: ParsableCommand {
    static var configuration = CommandConfiguration(commandName: "repl")
    @Option(help: "App name (default: frontmost)") var app: String?
    func run() throws {
        Permissions.requireAX()
        let h = Hands()
        print("hands repl — commands: observe | <dsl action> | quit")
        func doObserve() {
            do {
                let obs = try h.observe(app: app)
                print(obs.text)
                if let d = obs.diffText, !d.isEmpty { print("--- diff ---\n\(d)") }
                FileHandle.standardError.write(
                    "ax_ms=\(obs.axMs.rounded(to: 1)) nodes=\(obs.elements.count) epoch=\(obs.epoch)\n"
                        .data(using: .utf8)!)
            } catch { print("observe error: \(error)") }
        }
        doObserve()
        while true {
            FileHandle.standardOutput.write("> ".data(using: .utf8)!)
            guard let line = readLine() else { break }
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.isEmpty { continue }
            if t == "quit" || t == "exit" { break }
            if t == "observe" { doObserve(); continue }
            do {
                let params = try DSLLine.parse(t, epoch: h.currentEpoch)
                let r = h.act(params)
                printJSON(r)
            } catch { print("error: \(error)") }
        }
    }
}

struct SkillCmd: ParsableCommand {
    static var configuration = CommandConfiguration(commandName: "skill")
    @Argument(help: "Skill name") var name: String
    @Argument(parsing: .remaining, help: "key=value args") var args: [String] = []
    func run() throws {
        var dict: [String: Any] = [:]
        for a in args {
            guard let eq = a.firstIndex(of: "=") else {
                throw ValidationError("bad arg \(a); use key=value")
            }
            let k = String(a[..<eq]), v = String(a[a.index(after: eq)...])
            if v == "true" { dict[k] = true }
            else if v == "false" { dict[k] = false }
            else if let i = Int(v) { dict[k] = i }
            else if let f = Double(v), v.contains(".") { dict[k] = f }
            else { dict[k] = v }
        }
        let rpc = RPCHandler()
        let (ok, r, e) = rpc.handle(method: "skill",
                                    params: ["name": name, "args": dict])
        if let r { printJSON(r) }
        if !ok { throw ExitCode(1) }
        _ = e
    }
}

struct BenchObserveCmd: ParsableCommand {
    static var configuration = CommandConfiguration(commandName: "bench-observe")
    @Option(help: "Comma-separated app names") var apps = "Finder,Safari,Notes,System Settings"
    @Option(help: "Iterations per app") var n = 20
    func run() throws {
        Permissions.requireAX()
        let h = Hands()
        let names = apps.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        func pad(_ s: String, _ w: Int) -> String {
            s.count >= w ? String(s.prefix(w)) : s + String(repeating: " ", count: w - s.count)
        }
        print([pad("app", 20), pad("p50_ms", 8), pad("p95_ms", 8),
               pad("nodes", 8), pad("chars", 10)].joined(separator: " "))
        for name in names {
            var times: [Double] = []
            var nodes = 0, chars = 0
            for _ in 0..<n {
                do {
                    let o = try h.observe(app: name, diff: false)
                    times.append(o.axMs)
                    nodes = o.elements.count
                    chars = o.text.count
                } catch {
                    FileHandle.standardError.write(
                        "\(name): \(error)\n".data(using: .utf8)!)
                    break
                }
            }
            guard !times.isEmpty else {
                print([pad(name, 20), pad("-", 8), pad("-", 8),
                       pad("0", 8), pad("0", 10)].joined(separator: " "))
                continue
            }
            times.sort()
            let p50 = times[times.count / 2]
            let p95 = times[min(times.count - 1, Int((Double(times.count) * 0.95).rounded(.up)) - 1)]
            print([pad(name, 20), pad(String(format: "%.1f", p50), 8),
                   pad(String(format: "%.1f", p95), 8),
                   pad("\(nodes)", 8), pad("\(chars)", 10)].joined(separator: " "))
        }
    }
}

struct ServeCmd: ParsableCommand {
    static var configuration = CommandConfiguration(
        commandName: "serve",
        abstract: "Headless brain client. With --utterance: send each one, exit after the last outcome.",
        discussion: """
            With --utterance the next utterance (or the exit) follows the current one's outcome \
            (final ui mood success/confused/idle/sleeping, or a say) once no RPC has been pending \
            for 1.5 s. Exit 0 = done, 1 = a turn was cut off by a brain disconnect, 2 = --timeout. \
            A one-line JSON summary is printed on exit. Without --utterance it serves forever.
            """)
    @Option(help: "Brain WebSocket URL") var url = "ws://127.0.0.1:8765"
    @Option(help: "Utterance to send after connecting (repeatable)")
    var utterance: [String] = []
    @Option(help: "Hard cap in seconds when --utterance is given (exit 2); 0 = no cap")
    var timeout: Double = 90

    func validate() throws {
        do { _ = try ServeSession.Config.make(utterances: utterance, timeout: timeout) }
        catch { throw ValidationError("\(error)") }
        guard URL(string: url) != nil else { throw ValidationError("bad url") }
    }

    func run() throws {
        Permissions.requireAX()
        guard let u = URL(string: url) else { throw ValidationError("bad url") }
        let config = try ServeSession.Config.make(utterances: utterance, timeout: timeout)
        WebAX.watchActivations()
        let client = BrainClient(url: u, config: config)
        client.run()
    }
}
