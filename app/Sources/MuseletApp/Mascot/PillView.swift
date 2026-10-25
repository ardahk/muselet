import SwiftUI

/// Pill state shared by PillController (AppKit) and PillView (SwiftUI).
final class PillState: ObservableObject {
    @Published var shown = false
    @Published var typing = false
    @Published var text = ""
}

/// Floating capsule under the mascot: keyboard (type a request) + mic
/// (click to start / stop listening). Typing swaps the buttons for a field.
struct PillView: View {
    @ObservedObject var model: AppModel
    @ObservedObject var state: PillState
    var onMic: () -> Void
    var onKeyboard: () -> Void
    var onSubmit: (String) -> Void
    var onCancel: () -> Void

    @FocusState private var fieldFocused: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Fade-out when the pointer leaves the kitten + pill zone.
    static let hideFade: TimeInterval = 0.12

    /// Debug hook `pill_slow`: stretch the typing open/close so the lead can screenshot it mid-way.
    static var slowMotion = false

    static func typingAnimation(reduceMotion: Bool) -> Animation {
        if slowMotion { return .easeInOut(duration: 2.0) }
        return reduceMotion ? .easeOut(duration: 0.15) : .spring(response: 0.3, dampingFraction: 0.78)
    }

    private var spring: Animation { Self.typingAnimation(reduceMotion: reduceMotion) }

    var body: some View {
        HStack(spacing: 2) {
            if state.typing { field } else { buttons }
        }
        .padding(.horizontal, 5)
        .padding(.vertical, 4)
        .background(VibrancyBackground(shape: Capsule(), material: .popover))
        .overlay(Capsule().strokeBorder(Color.primary.opacity(0.12), lineWidth: 0.5))
        .shadow(color: .black.opacity(0.2), radius: 7, x: 0, y: 3)
        .scaleEffect(state.shown ? 1 : (reduceMotion ? 1 : 0.85), anchor: .top)
        .opacity(state.shown ? 1 : 0)
        .animation(state.shown ? spring : .easeOut(duration: Self.hideFade), value: state.shown)
        .animation(spring, value: state.typing)
        .animation(spring, value: model.isRecording)
        .padding(10)            // transparent margin for the shadow
        .fixedSize()
    }

    private var buttons: some View {
        HStack(spacing: 2) {
            PillButton(symbol: "keyboard", help: "Type a request", action: onKeyboard)
                .disabled(model.isRecording)
            if model.isRecording {
                LiveWave(level: model.micLevel)
                    .scaleEffect(0.8)
                    .padding(.horizontal, 2)
                    .transition(.opacity)
            }
            PillButton(symbol: model.isRecording ? "stop.fill" : "waveform",
                       help: model.isRecording ? "Stop and send" : "Click to talk (or hold right ⌥)",
                       tint: model.isRecording ? Brand.tintColor : nil,
                       action: onMic)
        }
        .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.96)))
    }

    private var field: some View {
        HStack(spacing: 4) {
            Image(systemName: "keyboard")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.secondary)
                .padding(.leading, 7)
            TextField("Ask Muselet…", text: $state.text)
                .textFieldStyle(.plain)
                .font(.system(size: 13))
                .frame(width: 210)
                .focused($fieldFocused)
                .onSubmit { onSubmit(state.text) }
                .onExitCommand { onCancel() }
                .onAppear { DispatchQueue.main.async { fieldFocused = true } }
            PillButton(symbol: "arrow.up.circle.fill", help: "Send (return)",
                       tint: Brand.tintColor) { onSubmit(state.text) }
                .disabled(state.text.trimmingCharacters(in: .whitespaces).isEmpty)
            PillButton(symbol: "xmark", help: "Cancel (esc)", action: onCancel)
        }
        .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.96)))
    }
}

private struct PillButton: View {
    let symbol: String
    let help: String
    var tint: Color?
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(tint ?? Color.primary.opacity(0.8))
                .frame(width: 30, height: 26)
                .background(Color.primary.opacity(hovering ? 0.1 : 0), in: Capsule())
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .help(help)
        .accessibilityLabel(help)
    }
}
