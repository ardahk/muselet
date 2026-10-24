import AppKit
import Foundation

/// Headless brain client: connects to ws://127.0.0.1:8765, sends hello,
/// dispatches rpc messages, replies with rpc_result, reconnects with backoff.
public final class BrainClient: NSObject, URLSessionWebSocketDelegate {
    private let url: URL
    private let handler: RPCHandler
    private var session: URLSession!
    private var task: URLSessionWebSocketTask?
    private var backoff: TimeInterval = 0.5
    private var running = true
    private var reconnectScheduled = false
    /// Hands is stateful — every RPC executes on this one serial queue.
    private let handsQueue = DispatchQueue(label: "hands.serial")
    /// Utterances queued for `hands serve --utterance`.
    private var pendingUtterances: [String]
    private var uttSeq = 0
    private var waitingForOutcome = false

    public init(url: URL = URL(string: "ws://127.0.0.1:8765")!,
                handler: RPCHandler = RPCHandler(),
                utterances: [String] = []) {
        self.url = url
        self.handler = handler
        self.pendingUtterances = utterances
        super.init()
        self.session = URLSession(configuration: .default, delegate: self,
                                  delegateQueue: nil)
    }

    /// Run forever; call on the main thread or a dedicated run loop.
    public func run() -> Never {
        connect()
        // An attached source keeps the run loop from exiting with no input.
        RunLoop.current.add(Port(), forMode: .default)
        while running { RunLoop.current.run(mode: .default, before: .distantFuture) }
        exit(0)
    }

    private func connect() {
        NSLog("hands: connecting to %@", url.absoluteString)
        task = session.webSocketTask(with: url)
        task?.resume()
        sendHello()
        receive()
        waitingForOutcome = false
        sendNextUtteranceIfAny()
    }

    private func sendHello() {
        var screens: [[String: Any]] = []
        for (i, s) in NSScreen.screens.enumerated() {
            screens.append([
                "id": i + 1,
                "frame": [s.frame.minX, s.frame.minY, s.frame.width, s.frame.height],
                "scale": s.backingScaleFactor,
            ])
        }
        send(["t": "hello", "screens": screens])
    }

    private func sendNextUtteranceIfAny() {
        guard !pendingUtterances.isEmpty, !waitingForOutcome else { return }
        waitingForOutcome = true
        uttSeq += 1
        let text = pendingUtterances.removeFirst()
        // Capture ctx at send time (AGENTS.md contract).
        send(["t": "utterance", "id": "u\(uttSeq)", "text": text,
              "final": true, "ctx": UtteranceCtx.capture()])
    }

    private func receive() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let msg):
                self.backoff = 0.5          // reset on successful receive
                switch msg {
                case .string(let s): self.onText(s)
                case .data(let d):
                    if let s = String(data: d, encoding: .utf8) { self.onText(s) }
                @unknown default: break
                }
                self.receive()
            case .failure(let e):
                NSLog("hands: ws error: %@", e.localizedDescription)
                self.scheduleReconnect()
            }
        }
    }

    private func onText(_ s: String) {
        guard let data = s.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let t = obj["t"] as? String else { return }
        switch t {
        case "rpc":
            guard let id = obj["id"] as? String,
                  let method = obj["method"] as? String else { return }
            let params = obj["params"] as? [String: Any] ?? [:]
            // Serial hands queue: Hands is stateful, never run RPCs in parallel.
            handsQueue.async { [weak self] in
                guard let self else { return }
                let (ok, result, error) = self.handler.handle(method: method, params: params)
                var reply: [String: Any] = ["t": "rpc_result", "id": id, "ok": ok]
                // Always carry the result payload when the handler produced one.
                if let r = result { reply["result"] = r }
                if !ok { reply["error"] = error ?? "error" }
                self.send(reply)
            }
        case "ui":
            // utterance finished when the mascot reports an outcome
            if let m = obj["mascot"] as? String,
               m == "success" || m == "confused" || m == "sleeping" {
                waitingForOutcome = false
                sendNextUtteranceIfAny()
            }
        case "say", "confirm":
            break   // headless: no UI to drive yet
        default:
            break
        }
    }

    private func send(_ obj: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: obj),
              let s = String(data: data, encoding: .utf8) else { return }
        task?.send(.string(s)) { err in
            if let e = err { NSLog("hands: send failed: %@", e.localizedDescription) }
        }
    }

    public func urlSession(_ session: URLSession,
                           webSocketTask: URLSessionWebSocketTask,
                           didCloseWith closeCode: URLSessionWebSocketTask.CloseCode,
                           reason: Data?) {
        NSLog("hands: ws closed (%d)", closeCode.rawValue)
        scheduleReconnect()
    }

    private func scheduleReconnect() {
        guard running, !reconnectScheduled else { return }
        reconnectScheduled = true
        let delay = min(backoff, 8)
        backoff = min(backoff * 2, 8)
        DispatchQueue.global().asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self, self.running else { return }
            self.reconnectScheduled = false
            self.connect()
        }
    }
}
