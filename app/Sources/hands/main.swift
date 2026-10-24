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
                      BenchObserveCmd.self, ServeCmd.self])
}

struct ObserveCmd: ParsableCommand {
    static var configuration = CommandConfiguration(commandName: "observe")
    @Option(help: "App name (default: frontmost)") var app: String?
    @Option(help: "Max elements") var max: Int = 150
    @Option(help: "Scope: focused_window|app|menubar") var scope = "focused_window"
    @Flag(help: "Emit JSON instead of text") var json = false
    func run() throws {
        Permissions.requireAX()
        let h = Hands()
        let rpc = RPCHandler()
        if json {
            let (ok, r, e) = rpc.handle(method: "observe", params: [
                "app": app as Any, "max_nodes": max, "scope": scope, "diff": true])
            if ok, let r { printJSON(r) }
            else { FileHandle.standardError.write("error: \(e ?? "?")\n".data(using: .utf8)!); throw ExitCode(1) }
        } else {
            let obs = try h.observe(scope: scope, app: app, maxNodes: max)
            print(obs.text)
            if let d = obs.diffText, !d.isEmpty { print("--- diff ---\n\(d)") }
            FileHandle.standardError.write(
                "ax_ms=\(obs.axMs.rounded(to: 1)) nodes=\(obs.elements.count)\n".data(using: .utf8)!)
        }
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
    func run() throws {
        Permissions.requireAX()
        guard let u = URL(string: url) else { throw ValidationError("bad url") }
        let client = BrainClient(url: u)
        client.run()
    }
}
