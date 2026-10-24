import AppKit
import HandsKit
import SwiftUI

/// Actions the panel can trigger; wired up by the AppDelegate.
final class AppActions {
    static let shared = AppActions()
    var requestPermission: (PermissionKind) -> Void = { _ in }
    /// Ask Automation consent for one target app (or open Settings if denied).
    var requestAutomation: (Automation.Target) -> Void = { _ in }
    var reconnect: () -> Void = {}
    var resetMascot: () -> Void = {}
    var panelVisible: (Bool) -> Void = { _ in }
    var testGhost: () -> Void = {}
    /// Run a typed request (example prompts) as a final utterance.
    var runExample: (String) -> Void = { _ in }
    var setEscalatePlanner: (Bool) -> Void = { _ in }
    /// Settings › Timers.
    var setUseClockTimers: (Bool) -> Void = { _ in }
    /// Re-run `timer_backend` (`refresh`: re-list shortcuts now).
    var refreshTimerBackend: (Bool) -> Void = { _ in }
    var openShortcuts: () -> Void = {}
}

/// Menu-bar panel: a simple home page; everything technical lives in Settings (gear).
struct PanelView: View {
    @ObservedObject var model: AppModel
    @State private var showSettings = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let actions = AppActions.shared

    struct Example: Identifiable {
        let symbol: String
        let text: String
        var id: String { text }
    }

    static let examples = [
        Example(symbol: "speaker.wave.2", text: "Set volume to 30"),
        Example(symbol: "timer", text: "Start a 10 minute timer"),
        Example(symbol: "folder", text: "Open my Downloads folder"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header
            if showSettings {
                SettingsView(model: model)
                    .transition(reduceMotion ? .opacity : .move(edge: .trailing).combined(with: .opacity))
            } else {
                home
                    .transition(reduceMotion ? .opacity : .move(edge: .leading).combined(with: .opacity))
            }
        }
        .font(.system(size: 13))
        .padding(16)
        .frame(width: 340)
        .background(alignment: .top) {
            LinearGradient(colors: [PanelPalette.wash, .clear], startPoint: .top, endPoint: .bottom)
                .frame(height: 140)
                .allowsHitTesting(false)
        }
        .tint(PanelPalette.ginger)
        .animation(reduceMotion ? .easeOut(duration: 0.15) : .snappy(duration: 0.25), value: showSettings)
        .onAppear { actions.panelVisible(true) }
        .onReceive(NotificationCenter.default.publisher(for: .museletPanelPage)) { n in
            showSettings = (n.object as? String) == "settings"
        }
        .onDisappear {
            actions.panelVisible(false)
            showSettings = false
        }
    }

    // MARK: header

    private var header: some View {
        HStack(spacing: 9) {
            if showSettings {
                Button { showSettings = false } label: {
                    Image(systemName: "chevron.left").font(.system(size: 13, weight: .semibold))
                        .frame(width: 26, height: 26)
                }
                .buttonStyle(.plain)
                .foregroundStyle(PanelPalette.accent)
                .help("Back")
                Text("Settings").font(.system(size: 15, weight: .semibold)).foregroundStyle(PanelPalette.ink)
            } else {
                KittenAvatar(mood: model.isRecording ? .listening : model.mood, size: 40)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Muselet")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(PanelPalette.ink)
                    Text(Self.statusLine(mood: model.mood, recording: model.isRecording, brain: model.brainStatus))
                        .font(.system(size: 11.5))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            Spacer()
            StatusDot(status: model.brainStatus)
            if !showSettings {
                Button { showSettings = true } label: {
                    Image(systemName: "gearshape").font(.system(size: 14, weight: .medium))
                        .frame(width: 26, height: 26)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .help("Settings")
                .accessibilityLabel("Settings")
            }
        }
    }

    // MARK: home

    private var home: some View {
        VStack(alignment: .leading, spacing: 12) {
            talkHero
            if needsAttention { attentionRow }
            lastRequestCard
            examplesSection
        }
    }

    private var talkHero: some View {
        VStack(spacing: 6) {
            Image(systemName: model.isRecording ? "waveform" : "mic.fill")
                .font(.system(size: 22, weight: .medium))
                .foregroundStyle(PanelPalette.accent)
                .symbolEffect(.variableColor.iterative, isActive: model.isRecording && !reduceMotion)
                .frame(width: 40, height: 40)
                .background(PanelPalette.ginger.opacity(0.18), in: Circle())
            HStack(spacing: 5) {
                Text("Hold")
                KeyCap(text: "right ⌥")
                Text("to talk")
            }
            .font(.system(size: 13, weight: .medium))
            Text(model.isRecording ? "Listening… release to send" : "or rest the pointer on me for mic & keyboard · esc cancels")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(PanelPalette.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
            .strokeBorder(PanelPalette.cardStroke, lineWidth: 0.5))
    }

    private var needsAttention: Bool { !model.permissions.allGranted || !model.pushToTalkActive }

    private var attentionRow: some View {
        Button { showSettings = true } label: {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                Text(model.pushToTalkActive ? "Some permissions are missing" : "Push-to-talk needs permissions")
                Spacer()
                Text("Review").foregroundStyle(.secondary)
                Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold)).foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(Color.orange.opacity(0.1), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var lastRequestCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            SectionTitle("Last request")
            if let req = model.lastRequest {
                Text("“\(req)”")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(PanelPalette.ink)
                    .lineLimit(2)
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    outcomeIcon
                    Text(resultText).foregroundStyle(.secondary).lineLimit(2)
                }
                .font(.system(size: 12))
            } else {
                Text("Nothing yet. Try one of these:")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(PanelPalette.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
            .strokeBorder(PanelPalette.cardStroke, lineWidth: 0.5))
    }

    private var resultText: String {
        guard let r = model.lastResult else { return "" }
        if let t = r.text { return t }
        switch r.outcome {
        case .working: return "Working on it…"
        case .done: return "Done"
        case .failed: return "Didn't work"
        }
    }

    @ViewBuilder private var outcomeIcon: some View {
        switch model.lastResult?.outcome {
        case .working?: ProgressView().controlSize(.mini)
        case .done?: Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
        case .failed?: Image(systemName: "questionmark.circle.fill").foregroundStyle(.orange)
        case nil: EmptyView()
        }
    }

    private var examplesSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            if model.lastRequest != nil { SectionTitle("Try") }
            ForEach(Self.examples) { ex in
                ExampleRow(symbol: ex.symbol, text: ex.text) { actions.runExample(ex.text) }
                    .disabled(model.isRecording)
            }
        }
    }

    static func statusLine(mood: MascotMood, recording: Bool, brain: BrainStatus) -> String {
        if recording { return "I'm listening…" }
        switch brain {
        case .connecting: return "Waking up my brain…"
        case .offline: return "Can't reach my brain yet"
        case .busy: return "Another app has my brain"
        case .connected: break
        }
        switch mood {
        case .idle: return "Ready when you are"
        case .thinking: return "Thinking it over…"
        case .acting: return "On it!"
        case .success: return "Done! What's next?"
        case .confused: return "Hmm, I didn't catch that"
        case .sleeping: return "Napping. Hover me to wake me"
        case .listening: return "I'm listening…"
        }
    }
}

// MARK: - home components

struct SectionTitle: View {
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(PanelPalette.accent.opacity(0.9))
    }
}

private struct KeyCap: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.system(size: 12, weight: .semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(.background, in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.18), lineWidth: 0.5))
            .shadow(color: .black.opacity(0.12), radius: 0.5, x: 0, y: 1)
    }
}

private struct ExampleRow: View {
    let symbol: String
    let text: String
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) {
                Image(systemName: symbol)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(PanelPalette.accent)
                    .frame(width: 22, height: 22)
                    .background(PanelPalette.ginger.opacity(0.16),
                                in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                Text(text).font(.system(size: 13))
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.tertiary)
                    .opacity(hovering ? 1 : 0)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(hovering ? PanelPalette.hover : PanelPalette.card,
                        in: RoundedRectangle(cornerRadius: 11, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .help("Run “\(text)”")
    }
}

extension Notification.Name {
    static let museletPanelPage = Notification.Name("ai.muselet.panelPage")
}
