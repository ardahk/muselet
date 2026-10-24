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
        commandName: "probe", abstract: "Read-only probes: bluetooth | volume | brightness | symbols")
    @Argument(help: "bluetooth | volume | brightness | symbols") var what: String
    func run() throws {
        switch what {
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

struct ObserveCmd: ParsableCommand {
    static var configuration = CommandConfiguration(commandName: "observe")
    @Option(help: "App name (default: frontmost)") var app: String?
    @Option(help: "Max elements") var max: Int = 150
    @Option(help: "Scope: focused_window|app|menubar") var scope = "focused_window"
    @Flag(help: "Emit JSON instead of text") var json = false
    @Flag(help: "Don't turn on the web AX tree (AXManualAccessibility / AXEnhancedUserInterface)")
    var noWebAx = false
    func run() throws {
        Permissions.requireAX()
        if json {
            let rpc = RPCHandler(warmUp: false)
            rpc.hands.webAXEnabled = !noWebAx
            let (ok, r, e) = rpc.handle(method: "observe", params: [
                "app": app as Any, "max_nodes": max, "scope": scope, "diff": true])
            if ok, let r { printJSON(r) }
            else { FileHandle.standardError.write("error: \(e ?? "?")\n".data(using: .utf8)!); throw ExitCode(1) }
        } else {
            let h = Hands()
            h.webAXEnabled = !noWebAx
            let obs = try h.observe(scope: scope, app: app, maxNodes: max)
            print(obs.text)
            if let d = obs.diffText, !d.isEmpty { print("--- diff ---\n\(d)") }
            let web = obs.elements.filter { $0.inWebArea }.count
            var line = "ax_ms=\(obs.axMs.rounded(to: 1)) nodes=\(obs.elements.count) web_nodes=\(web)"
                + (obs.truncated ? " truncated" : "")
            if let m = obs.webAX {
                line += " web_ax=\(m) web_wait_ms=\((obs.webAXWaitMs ?? 0).rounded(to: 1))"
                if let w = h.lastWebAX?.wait {
                    line += " web_area=\(w.foundWebArea) populated=\(w.populated) polls=\(w.polls)"
                }
            }
            FileHandle.standardError.write((line + "\n").data(using: .utf8)!)
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
    func run() throws {
        Permissions.requireAX()
        guard let ra = NSWorkspace.shared.runningApplications.first(where: {
            ($0.localizedName ?? "").localizedCaseInsensitiveCompare(app) == .orderedSame
        }) else { throw ValidationError("not running: \(app)") }
        let node = AXNode(AXUIElementCreateApplication(ra.processIdentifier))
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
            var r: [String: Bool] = [:]
            switch set {
            case "manual": r["manual"] = node.setAttr(WebAX.manualAttribute, true)
            case "enhanced": r["enhanced"] = node.setAttr(WebAX.enhancedAttribute, true)
            case "manual-off": r["manual"] = node.setAttr(WebAX.manualAttribute, false)
            case "enhanced-off": r["enhanced"] = node.setAttr(WebAX.enhancedAttribute, false)
            case "off":
                r["manual"] = node.setAttr(WebAX.manualAttribute, false)
                r["enhanced"] = node.setAttr(WebAX.enhancedAttribute, false)
            default: throw ValidationError("bad --set \(set)")
            }
            d["set_ok"] = r
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
    static var configuration = CommandConfiguration(commandName: "serve")
    @Option(help: "Brain WebSocket URL") var url = "ws://127.0.0.1:8765"
    @Option(help: "Utterance to send after connecting (repeatable)")
    var utterance: [String] = []
    func run() throws {
        Permissions.requireAX()
        guard let u = URL(string: url) else { throw ValidationError("bad url") }
        let client = BrainClient(url: u, utterances: utterance)
        client.run()
    }
}
