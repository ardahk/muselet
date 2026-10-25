import AppKit
import Foundation

/// Headless brain client: connects to ws://127.0.0.1:8765, sends hello,
/// dispatches rpc messages, replies with rpc_result, reconnects with backoff.
/// With utterances (`hands serve --utterance ...`) a `ServeSession` decides
/// when to send the next one and when to exit (0 done, 2 timeout), printing
/// a one-line JSON summary on stdout.
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
    /// Utterance turns, exit rules and the summary.
    public let serve: ServeSession

    public init(url: URL = URL(string: "ws://127.0.0.1:8765")!,
                handler: RPCHandler = RPCHandler(),
                config: ServeSession.Config = ServeSession.Config(utterances: [])) {
        self.url = url
        self.handler = handler
        self.serve = ServeSession(config: config)
        super.init()
        self.session = URLSession(configuration: .default, delegate: self,
                                  delegateQueue: nil)
    }

    public convenience init(url: URL, handler: RPCHandler = RPCHandler(), utterances: [String]) {
        self.init(url: url, handler: handler, config: ServeSession.Config(utterances: utterances))
    }

    /// Run until the session exits (forever without utterances); call on
    /// the main thread.
    public func run() -> Never {
        connect()
        // Exit rules are time based: tick ~10x per second.
        let timer = Timer(timeInterval: 0.1, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.perform(self.serve.tick(now: Date()))
        }
        RunLoop.current.add(timer, forMode: .default)
        // An attached source keeps the run loop from exiting with no input.
        RunLoop.current.add(Port(), forMode: .default)
        while running { RunLoop.current.run(mode: .default, before: .distantFuture) }
        exit(0)
    }

    private func perform(_ step: ServeSession.Step) {
        switch step {
        case .none: break
        case .send(let id, let text):
            // Capture ctx at send time (AGENTS.md contract).
            send(["t": "utterance", "id": id, "text": text,
                  "final": true, "ctx": UtteranceCtx.capture()])
        case .exit(let code):
            running = false
            print(serve.summaryLine())
            fflush(stdout)
            task?.cancel(with: .normalClosure, reason: nil)
            usleep(150_000)             // let the close frame go out
            exit(code)
        }
    }

    private func connect() {
        NSLog("hands: connecting to %@", url.absoluteString)
        task = session.webSocketTask(with: url)
        task?.resume()
        sendHello()
        receive()
    }

    /// The socket is open: the session may send its first utterance.
    public func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                           didOpenWithProtocol protocol: String?) {
        guard webSocketTask === task else { return }
        let step = serve.connected(now: Date())
        DispatchQueue.main.async { [weak self] in self?.perform(step) }
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
        guard let frame = BrainInbound.decode(s) else { return }
        switch frame {
        case .rpc(let id, let method, let params):
            serve.rpcStarted(id: id)
            // Serial hands queue: Hands is stateful, never run RPCs in parallel.
            handsQueue.async { [weak self] in
                guard let self else { return }
                let (ok, result, error) = self.handler.handle(method: method, params: params)
                var reply: [String: Any] = ["t": "rpc_result", "id": id, "ok": ok]
                // Always carry the result payload when the handler produced one.
                if let r = result { reply["result"] = r }
                if !ok { reply["error"] = error ?? "error" }
                self.send(reply)
                self.serve.rpcFinished(id: id, ok: ok)
            }
        case .ui(let mascot, let bubble, let ms):
            serve.ui(mood: mascot, bubble: bubble, ms: ms)
        case .say(let text):
            serve.say(text)
        case .confirm(_, let summary):
            serve.confirm(summary)      // headless: never answered (no auto-yes)
        case .confirmCancel, .memory, .unknown:
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
