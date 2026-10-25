import AppKit
import Combine
import Foundation
import HandsKit

/// Mascot moods driven by brain `ui.mascot` (plus local voice states).
enum MascotMood: String, CaseIterable {
    case idle, listening, thinking, acting, success, confused, sleeping
}

enum BrainStatus: Equatable {
    case connecting
    case connected
    case offline(String)
    case busy          // brain rejected us: another app client is connected

    var title: String {
        switch self {
        case .connecting: return "Connecting…"
        case .connected: return "Connected"
        case .offline: return "Brain offline"
        case .busy: return "Brain busy"
        }
    }

    var detail: String {
        switch self {
        case .connecting: return "ws://127.0.0.1:8765"
        case .connected: return "ws://127.0.0.1:8765"
        case .offline(let why): return why
        case .busy: return "another client is connected"
        }
    }
}

enum STTState: Equatable {
    case idle
    case downloading(Double, String)
    case loading(String)
    case ready
    case failed(String)
}

enum ActivityKind {
    case utterance, say, ui, rpc, confirm, system, error, stt

    var symbol: String {
        switch self {
        case .utterance: return "waveform"
        case .say: return "text.bubble"
        case .ui: return "face.smiling"
        case .rpc: return "cursorarrow.rays"
        case .confirm: return "checkmark.shield"
        case .system: return "bolt.horizontal"
        case .error: return "exclamationmark.triangle"
        case .stt: return "mic"
        }
    }
}

struct ActivityEntry: Identifiable, Equatable {
    let id = UUID()
    let date = Date()
    let kind: ActivityKind
    let text: String
    let ms: Double?
    let ok: Bool?
}

struct PendingConfirm: Equatable {
    let id: String
    let summary: String
}

struct MemoryItem: Identifiable, Equatable {
    let id: Int
    let type: String
    let key: String
    let value: String
    let created: Double

    init?(_ raw: [String: Any]) {
        guard let id = raw["id"] as? Int,
              let type = raw["type"] as? String,
              let key = raw["key"] as? String,
              let value = raw["value"] as? String else { return nil }
        self.id = id
        self.type = type
        self.key = key
        self.value = value
        self.created = raw["created"] as? Double ?? 0
    }
}

enum BubbleStyle: Equatable {
    case say          // brain reply
    case transcript   // live transcript while the user talks
    case confirm      // pending confirmation with buttons
    case hint         // local status / hints
}

struct BubbleContent: Equatable {
    var text: String
    var style: BubbleStyle
}

/// Latency chip next to the bubble ("0.21 s"), from `ui.ms`.
struct LatencyChip: Equatable {
    let id = UUID()
    let text: String
}

/// The panel's "last request" card: the brain's latest reply and outcome.
struct LastResult: Equatable {
    enum Outcome { case working, done, failed }
    var text: String?
    var outcome: Outcome
}

/// Single source of truth for UI state. Main-thread only.
final class AppModel: ObservableObject {
    static let shared = AppModel()

    @Published var brainStatus: BrainStatus = .connecting
    @Published var mood: MascotMood = .idle
    @Published var bubble: BubbleContent?
    @Published var bubbleVisible = false
    @Published var latencyChip: LatencyChip?
    @Published var latencyVisible = false
    @Published var pendingConfirm: PendingConfirm?
    @Published var activity: [ActivityEntry] = []
    @Published var sttState: STTState = .idle
    @Published var sttEngine: String = "Parakeet TDT v2 (FluidAudio)"
    @Published var lastSTTms: Double?
    @Published var isRecording = false
    @Published var permissions = PermissionSnapshot()
    /// Automation consent per target app (bundle id -> status).
    @Published var automation: [String: Automation.Status] = [:]
    @Published var pushToTalkActive = false
    /// Live mic level 0...1 while recording (drives the bubble waveform).
    @Published var micLevel: Float = 0

    /// Fan-out for the high-rate mic level so SwiftUI isn't invalidated
    /// for the mascot (which renders with Core Animation).
    let levelSubject = PassthroughSubject<Float, Never>()

    @Published var lastRequest: String?
    @Published var lastResult: LastResult?
    /// Settings › Models (persisted by PlannerSettings) and the brain's config_ack.
    @Published var escalatePlanner = PlannerSettings.escalate
    @Published var configAck: ConfigAck?
    /// Settings › Timers (persisted by TimerSettings) and the last `timer_backend` result.
    @Published var useClockTimers = TimerSettings.useClock
    @Published var clockTimers: ClockTimerStatus?
    @Published var longtermMemoryEnabled = MemorySettings.enabled
    @Published var memoryItems: [MemoryItem] = []

    func noteRequest(_ text: String) {
        lastRequest = text
        lastResult = LastResult(text: nil, outcome: .working)
    }

    func noteReply(_ text: String) {
        guard lastRequest != nil, !text.isEmpty else { return }
        lastResult = LastResult(text: text, outcome: lastResult?.outcome ?? .working)
    }

    func noteMood(_ m: MascotMood) {
        guard var r = lastResult, r.outcome == .working else { return }
        switch m {
        case .success: r.outcome = .done
        case .confused: r.outcome = .failed
        case .idle where r.text != nil: r.outcome = .done
        default: return
        }
        lastResult = r
    }

    private init() {}

    func log(_ kind: ActivityKind, _ text: String, ms: Double? = nil, ok: Bool? = nil) {
        let e = ActivityEntry(kind: kind, text: text, ms: ms, ok: ok)
        activity.insert(e, at: 0)
        if activity.count > 200 { activity.removeLast(activity.count - 200) }
        FileLog.shared.write(kind: kind, text: text, ms: ms, ok: ok)
    }
}

/// Append-only log at ~/Library/Logs/Muselet/muselet.log (for debugging and evidence).
final class FileLog {
    static let shared = FileLog()
    private let queue = DispatchQueue(label: "ai.muselet.filelog", qos: .utility)
    private var handle: FileHandle?
    private let formatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private init() {
        let dir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/Muselet", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent("muselet.log")
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        handle = try? FileHandle(forWritingTo: url)
        _ = try? handle?.seekToEnd()
    }

    func write(kind: ActivityKind, text: String, ms: Double?, ok: Bool?) {
        let line = "\(formatter.string(from: Date())) [\(kind)] \(text)"
            + (ms.map { String(format: " (%.1f ms)", $0) } ?? "")
            + (ok.map { $0 ? " ok" : " FAIL" } ?? "") + "\n"
        queue.async { [weak self] in
            self?.handle?.write(line.data(using: .utf8)!)
        }
    }

    func raw(_ s: String) {
        let line = "\(formatter.string(from: Date())) \(s)\n"
        queue.async { [weak self] in self?.handle?.write(line.data(using: .utf8)!) }
    }
}
