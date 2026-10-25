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
    /// `ms`: latency of the request, on its final ui message (latency chip).
    var onUI: ((_ mascot: String?, _ bubble: String?, _ ms: Double?) -> Void)?
    var onSay: ((String) -> Void)?
    var onConfirm: ((_ id: String, _ summary: String) -> Void)?
    /// confirm_cancel: the confirm timed out or the task was cancelled
    /// (nil id = whatever is pending).
    var onConfirmCancel: ((_ id: String?) -> Void)?
    var onMemoryItems: (([[String: Any]]) -> Void)?
    var onRPC: ((_ method: String, _ summary: String, _ ms: Double, _ ok: Bool) -> Void)?
    /// A final utterance spoken while offline was dropped (not delivered
    /// within `outboxTTL`); the app shows the "brain offline" bubble.
    var onUtteranceDropped: ((_ id: String) -> Void)?
    /// Socket (re)opened, after hello was queued (main). Send per-connection config here.
    var onOpen: (() -> Void)?
    var onConfigAck: ((ConfigAck) -> Void)?

    /// Max age of a held final utterance; older ones are never replayed
    /// (a stale command must not execute minutes later).
    static let outboxTTL: TimeInterval = 5

    private let stateQueue = DispatchQueue(label: "ai.muselet.brain.state")
    private let rpcQueue = DispatchQueue(label: "ai.muselet.brain.rpc", qos: .userInitiated)
    private var session: URLSession!
    private var task: URLSessionWebSocketTask?
    private var generation = 0
    private var backoff: TimeInterval = 0.5
    private var isOpen = false
    private var lastCloseWasBusy = false
    /// At most one final utterance held while offline, with its timestamp.
    private var outbox: (id: String, frame: String, at: Date)?
    private var offlineSince: Date? = Date()

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

    /// Seconds since the socket was last open (0 while connected).
    var offlineFor: TimeInterval {
        stateQueue.sync { isOpen ? 0 : Date().timeIntervalSince(offlineSince ?? .distantPast) }
    }

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

    func sendUtterance(id: String, text: String, final: Bool,
                       ctx: [String: Any]? = nil) {
        var m: [String: Any] = ["t": "utterance", "id": id, "text": text,
                                "final": final]
        if let ctx { m["ctx"] = ctx }
        send(m)
    }

    func sendCancel() { send(["t": "cancel"]) }

    /// `{"t":"config","escalate_planner":true|false}`; dropped while offline
    /// (onOpen sends it again on every connect).
    func sendConfig(_ frame: [String: Any]) { send(frame) }

    func sendMemoryList() { send(["t": "memory", "op": "list"]) }

    func sendMemorySearch(_ query: String) {
        send(["t": "memory", "op": "search", "q": query])
    }

    func sendMemoryDelete(_ id: Int) {
        send(["t": "memory", "op": "delete", "id": id])
    }

    func sendMemoryClear() { send(["t": "memory", "op": "clear"]) }

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
                if (obj["t"] as? String) == "utterance", obj["final"] as? Bool == true,
                   let id = obj["id"] as? String {
                    // Keep only the latest; drop it if not delivered in time.
                    self.outbox = (id, s, Date())
                    self.stateQueue.asyncAfter(deadline: .now() + Self.outboxTTL) {
                        guard let o = self.outbox, o.id == id else { return }
                        self.outbox = nil
                        DispatchQueue.main.async { self.onUtteranceDropped?(id) }
                    }
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
        if offlineSince == nil { offlineSince = Date() }
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
        offlineSince = nil
        lastCloseWasBusy = false
        backoff = 0.5
        publish(.connected)
        sendHello()
        DispatchQueue.main.async { self.onOpen?() }     // after hello's main hop: frame order kept
        if let o = outbox {
            outbox = nil
            if Date().timeIntervalSince(o.at) <= Self.outboxTTL {
                // hello is queued on main first; keep frame order.
                DispatchQueue.main.async {
                    self.stateQueue.async {
                        guard self.isOpen, let t = self.task else {
                            DispatchQueue.main.async { self.onUtteranceDropped?(o.id) }
                            return
                        }
                        t.send(.string(o.frame)) { _ in }
                    }
                }
            } else {
                DispatchQueue.main.async { self.onUtteranceDropped?(o.id) }
            }
        }
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
        if offlineSince == nil { offlineSince = Date() }
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
        guard let frame = BrainInbound.decode(s) else { return }
        switch frame {
        case .rpc(let id, let method, let params):
            rpcQueue.async { [weak self] in self?.runRPC(id: id, method: method, params: params) }
        case .ui(let mascot, let bubble, let ms):
            DispatchQueue.main.async { self.onUI?(mascot, bubble, ms) }
        case .say(let text):
            DispatchQueue.main.async { self.onSay?(text) }
        case .confirm(let id, let summary):
            DispatchQueue.main.async { self.onConfirm?(id, summary) }
        case .confirmCancel(let id):
            DispatchQueue.main.async { self.onConfirmCancel?(id) }
        case .memory(let items):
            DispatchQueue.main.async { self.onMemoryItems?(items) }
        case .unknown(let t):
            if t == "config_ack", let ack = ConfigAck.parse(s) {
                DispatchQueue.main.async { self.onConfigAck?(ack) }
            }
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
