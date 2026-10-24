import AppKit
import Foundation
import HandsKit

/// App-side brain client. HandsKit's `BrainClient` is headless (private send,
/// ignores ui/say/confirm), so the app owns its own socket and reuses
/// HandsKit's `RPCHandler` for every rpc.
///
/// Threading: socket state lives on `stateQueue` (also the URLSession delegate
/// queue); rpcs execute serially on `rpcQueue` (Hands is not thread-safe);
/// UI callbacks hop to the main queue.
final class BrainConnection: NSObject, URLSessionWebSocketDelegate {
    let url: URL
    let handler: RPCHandler

    // Main-queue callbacks.
    var onStatus: ((BrainStatus) -> Void)?
    var onUI: ((_ mascot: String?, _ bubble: String?) -> Void)?
    var onSay: ((String) -> Void)?
    var onConfirm: ((_ id: String, _ summary: String) -> Void)?
    var onRPC: ((_ method: String, _ summary: String, _ ms: Double, _ ok: Bool) -> Void)?

    private let stateQueue = DispatchQueue(label: "ai.muselet.brain.state")
    private let rpcQueue = DispatchQueue(label: "ai.muselet.brain.rpc", qos: .userInitiated)
    private var session: URLSession!
    private var task: URLSessionWebSocketTask?
    private var generation = 0
    private var backoff: TimeInterval = 0.5
    private var isOpen = false
    private var lastCloseWasBusy = false
    private var outbox: [String] = []   // utterances queued while offline (latest few)

    init(url: URL = URL(string: "ws://127.0.0.1:8765")!, handler: RPCHandler) {
        self.url = url
        self.handler = handler
        super.init()
        let q = OperationQueue()
        q.maxConcurrentOperationCount = 1
        q.underlyingQueue = stateQueue
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 3600
        cfg.waitsForConnectivity = false
        session = URLSession(configuration: cfg, delegate: self, delegateQueue: q)
    }

    var connected: Bool { stateQueue.sync { isOpen } }

    func start() {
        stateQueue.async { self.connect() }
    }

    func reconnectNow() {
        stateQueue.async {
            self.backoff = 0.5
            self.task?.cancel(with: .goingAway, reason: nil)
            self.connect()
        }
    }

    // MARK: outbound

    func sendUtterance(id: String, text: String, final: Bool) {
        send(["t": "utterance", "id": id, "text": text, "final": final])
    }

    func sendCancel() { send(["t": "cancel"]) }

    func sendConfirmReply(id: String, yes: Bool) {
        send(["t": "confirm_reply", "id": id, "yes": yes])
    }

    func sendHello() {
        DispatchQueue.main.async {
            let screens = BrainConnection.screenDescriptors()
            self.send(["t": "hello", "screens": screens, "client": "muselet-app",
                       "bundle_id": Bundle.main.bundleIdentifier ?? "ai.muselet.app"])
        }
    }

    /// Screens in global top-left points (same space as AX frames).
    static func screenDescriptors() -> [[String: Any]] {
        NSScreen.screens.enumerated().map { i, s in
            let b = ScreenGeometry.cgBounds(of: s)
            return ["id": i + 1, "frame": [b.minX, b.minY, b.width, b.height],
                    "scale": s.backingScaleFactor]
        }
    }

    private func send(_ obj: [String: Any]) {
        guard JSONSerialization.isValidJSONObject(obj),
              let data = try? JSONSerialization.data(withJSONObject: obj),
              let s = String(data: data, encoding: .utf8) else {
            NSLog("muselet: dropping non-JSON frame %@", "\(obj["t"] ?? "?")")
            return
        }
        stateQueue.async {
            guard let task = self.task, self.isOpen else {
                if (obj["t"] as? String) == "utterance", obj["final"] as? Bool == true {
                    self.outbox.append(s)
                    if self.outbox.count > 3 { self.outbox.removeFirst() }
                }
                return
            }
            task.send(.string(s)) { err in
                if let e = err { NSLog("muselet: send failed: %@", e.localizedDescription) }
            }
        }
    }

    // MARK: connection lifecycle (stateQueue)

    private func connect() {
        generation += 1
        isOpen = false
        let t = session.webSocketTask(with: url)
        t.maximumMessageSize = 64 << 20
        task = t
        if lastPublished == nil || lastPublished == .connected { publish(.connecting) }
        t.resume()
        receive(on: t, gen: generation)
    }

    private func receive(on t: URLSessionWebSocketTask, gen: Int) {
        t.receive { [weak self] result in
            guard let self else { return }
            self.stateQueue.async {
                guard gen == self.generation else { return }
                switch result {
                case .success(let msg):
                    switch msg {
                    case .string(let s): self.onText(s)
                    case .data(let d): if let s = String(data: d, encoding: .utf8) { self.onText(s) }
                    @unknown default: break
                    }
                    self.receive(on: t, gen: gen)
                case .failure(let e):
                    self.handleDrop(reason: self.lastCloseWasBusy ? nil : e.localizedDescription, gen: gen)
                }
            }
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didOpenWithProtocol protocol: String?) {
        guard webSocketTask === task else { return }
        isOpen = true
        lastCloseWasBusy = false
        backoff = 0.5
        publish(.connected)
        sendHello()
        let pending = outbox
        outbox.removeAll()
        for s in pending { webSocketTask.send(.string(s)) { _ in } }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        guard webSocketTask === task else { return }
        if closeCode.rawValue == 1013 {
            lastCloseWasBusy = true
            publish(.busy)
        }
        handleDrop(reason: "closed (\(closeCode.rawValue))", gen: generation)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard task === self.task else { return }
        if let e = error { handleDrop(reason: e.localizedDescription, gen: generation) }
    }

    private var reconnectScheduledFor = -1

    private func handleDrop(reason: String?, gen: Int) {
        guard gen == generation, reconnectScheduledFor != gen else { return }
        reconnectScheduledFor = gen
        isOpen = false
        if lastCloseWasBusy {
            publish(.busy)
        } else {
            publish(.offline(Self.friendly(reason)))
        }
        let delay = backoff
        backoff = min(backoff * 2, 8)
        stateQueue.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self, gen == self.generation else { return }
            self.connect()
        }
    }

    private static func friendly(_ reason: String?) -> String {
        guard let r = reason else { return "not running" }
        if r.localizedCaseInsensitiveContains("could not connect")
            || r.localizedCaseInsensitiveContains("refused") {
            return "start it: uv run --project ml brain serve"
        }
        return r
    }

    private var lastPublished: BrainStatus?
    private func publish(_ s: BrainStatus) {
        guard s != lastPublished else { return }
        lastPublished = s
        DispatchQueue.main.async { self.onStatus?(s) }
    }

    // MARK: inbound

    private func onText(_ s: String) {
        guard let data = s.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let t = obj["t"] as? String else { return }
        switch t {
        case "rpc":
            guard let id = obj["id"] as? String, let method = obj["method"] as? String else { return }
            let params = obj["params"] as? [String: Any] ?? [:]
            rpcQueue.async { [weak self] in self?.runRPC(id: id, method: method, params: params) }
        case "ui":
            let mascot = obj["mascot"] as? String
            let bubble = obj["bubble"] as? String
            DispatchQueue.main.async { self.onUI?(mascot, bubble) }
        case "say":
            let text = obj["text"] as? String ?? ""
            DispatchQueue.main.async { self.onSay?(text) }
        case "confirm":
            guard let id = obj["id"] as? String else { return }
            let summary = obj["summary"] as? String ?? "Continue?"
            DispatchQueue.main.async { self.onConfirm?(id, summary) }
        default:
            break
        }
    }

    // MARK: rpc (rpcQueue)

    private func runRPC(id: String, method: String, params: [String: Any]) {
        let t0 = CACurrentMediaTime()
        let (ok, result, error) = handler.handle(method: method, params: params)
        let ms = (CACurrentMediaTime() - t0) * 1000
        var reply: [String: Any] = ["t": "rpc_result", "id": id, "ok": ok]
        if let r = result {
            if JSONSerialization.isValidJSONObject(["r": r]) { reply["result"] = r }
            else { reply["result"] = Self.sanitize(r) }
        }
        if !ok { reply["error"] = error ?? "error" }
        send(reply)
        let summary = Self.summarize(method: method, params: params, result: result, error: error)
        DispatchQueue.main.async { self.onRPC?(method, summary, ms, ok) }
    }

    /// Replace values JSONSerialization can't encode (NaN, inf, custom types).
    static func sanitize(_ v: Any) -> Any {
        switch v {
        case let d as [String: Any]:
            var o: [String: Any] = [:]
            for (k, x) in d { o[k] = sanitize(x) }
            return o
        case let a as [Any]:
            return a.map { sanitize($0) }
        case let n as Double:
            return n.isFinite ? n : NSNull()
        case let n as CGFloat:
            return n.isFinite ? Double(n) : NSNull()
        case is String, is Int, is Bool, is NSNumber, is NSNull:
            return v
        default:
            return "\(v)"
        }
    }

    static func summarize(method: String, params: [String: Any], result: Any?, error: String?) -> String {
        var s: String
        switch method {
        case "act":
            let op = params["op"] as? String ?? "?"
            s = "act \(op)"
            if let r = params["ref"] { s += " #\(r)" }
            if let c = params["combo"] as? String { s += " \(c)" }
            if let n = params["name"] as? String { s += " \"\(n)\"" }
            if let t = params["text"] as? String { s += " \"\(t.prefix(24))\"" }
        case "skill":
            let name = params["name"] as? String ?? "?"
            let args = (params["args"] as? [String: Any] ?? [:])
                .map { "\($0.key)=\($0.value)" }.sorted().joined(separator: " ")
            s = "skill \(name)" + (args.isEmpty ? "" : " \(args)")
        case "observe":
            s = "observe"
            if let r = result as? [String: Any] {
                if let app = r["app"] as? String { s += " \(app)" }
                if let els = r["elements"] as? [Any] { s += " · \(els.count) el" }
            }
        default:
            s = method
        }
        if let e = error, !e.isEmpty { s += " — \(e.prefix(60))" }
        return s
    }
}
