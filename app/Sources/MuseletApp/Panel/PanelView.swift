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
    var setLongtermMemory: (Bool) -> Void = { _ in }
    var listMemory: () -> Void = {}
    var searchMemory: (String) -> Void = { _ in }
    var deleteMemory: (Int) -> Void = { _ in }
    var clearMemory: () -> Void = {}
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
        VStack(alignment: .leading, spacing: 12) {
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
        .padding(14)
        .frame(width: 340)
        .animation(reduceMotion ? .easeOut(duration: 0.15) : .snappy(duration: 0.25), value: showSettings)
        .onAppear { actions.panelVisible(true) }
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
                .help("Back")
                Text("Settings").font(.system(size: 15, weight: .semibold))
            } else {
                Image(nsImage: MenuBarIcon.make(recording: model.isRecording))
                    .renderingMode(.template)
                    .resizable()
                    .frame(width: 20, height: 20)
                    .foregroundStyle(Brand.tintColor)
                    .padding(4)
                    .background(Brand.tintColor.opacity(0.14), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                Text("Muselet").font(.system(size: 15, weight: .semibold))
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
                .foregroundStyle(Brand.tintColor)
                .symbolEffect(.variableColor.iterative, isActive: model.isRecording && !reduceMotion)
                .frame(height: 28)
            HStack(spacing: 5) {
                Text("Hold")
                KeyCap(text: "right ⌥")
                Text("to talk")
            }
            .font(.system(size: 13, weight: .medium))
            Text(model.isRecording ? "Listening… release to send" : "or use the mic under the mascot · esc cancels")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
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
            .background(Color.orange.opacity(0.1), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var lastRequestCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            SectionTitle("Last request")
            if let req = model.lastRequest {
                Text("“\(req)”").font(.system(size: 13, weight: .medium)).lineLimit(2)
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
        .frame(maxWidth: .infinity, alignment: .leading)
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
}

// MARK: - home components

struct SectionTitle: View {
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(.secondary)
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
                    .foregroundStyle(Brand.tintColor)
                    .frame(width: 18)
                Text(text).font(.system(size: 13))
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.tertiary)
                    .opacity(hovering ? 1 : 0)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(Color.primary.opacity(hovering ? 0.08 : 0.04),
                        in: RoundedRectangle(cornerRadius: 9, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .help("Run “\(text)”")
    }
}
