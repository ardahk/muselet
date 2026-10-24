import AppKit
import SwiftUI

/// Which side of the bubble the tail sits on (toward the mascot).
final class BubbleLayout: ObservableObject {
    @Published var tailOnRight = true
}

struct BubbleView: View {
    @ObservedObject var model: AppModel
    @ObservedObject var layout: BubbleLayout
    var onConfirm: (Bool) -> Void

    var body: some View {
        // The latency chip sits beside the bubble's lower edge, on the side
        // away from the mascot (the panel grows away from the mascot).
        HStack(alignment: .bottom, spacing: 6) {
            if layout.tailOnRight { latency }
            if let b = model.bubble {
                content(b)
                    .padding(.horizontal, 14)
                    .padding(.top, 10)
                    .padding(.bottom, 10 + BubbleShape.tail)
                    .frame(minWidth: 44, maxWidth: 280, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .background(VibrancyBackground(shape: BubbleShape(tailOnRight: layout.tailOnRight)))
                    .overlay(BubbleShape(tailOnRight: layout.tailOnRight)
                        .stroke(Color.primary.opacity(0.1), lineWidth: 0.5))
                    .shadow(color: .black.opacity(0.18), radius: 10, x: 0, y: 4)
                    .scaleEffect(model.bubbleVisible ? 1 : 0.55,
                                 anchor: layout.tailOnRight ? .bottomTrailing : .bottomLeading)
                    .opacity(model.bubbleVisible ? 1 : 0)
                    .animation(.spring(response: 0.34, dampingFraction: 0.7), value: model.bubbleVisible)
                    .animation(.spring(response: 0.3, dampingFraction: 0.85), value: b)
            }
            if !layout.tailOnRight { latency }
        }
        .padding(14)
        .fixedSize()
    }

    /// "0.21 s" in SF Mono, secondary color; fades in/out (MascotController
    /// drops it ~2 s after the final ui message).
    @ViewBuilder
    private var latency: some View {
        if let chip = model.latencyChip {
            Text(chip.text)
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .glassEffect(.regular, in: Capsule())
                .padding(.bottom, model.bubble != nil && model.bubbleVisible ? BubbleShape.tail + 3 : 0)
                .opacity(model.latencyVisible ? 1 : 0)
                .animation(.easeOut(duration: 0.3), value: model.latencyVisible)
                .accessibilityLabel("took \(chip.text)")
        }
    }

    static let maxWords = 12

    /// Replies and hints: at most 12 words (AGENTS.md), ellipsis if cut.
    static func clip(_ text: String, words n: Int = maxWords) -> String {
        let w = text.split(whereSeparator: \.isWhitespace)
        return w.count <= n ? text : w.prefix(n).joined(separator: " ") + "…"
    }

    /// Live transcript: the latest 12 words.
    static func tail(_ text: String, words n: Int = maxWords) -> String {
        let w = text.split(whereSeparator: \.isWhitespace)
        return w.count <= n ? text : "…" + w.suffix(n).joined(separator: " ")
    }

    @ViewBuilder
    private func content(_ b: BubbleContent) -> some View {
        switch b.style {
        case .transcript:
            HStack(alignment: .center, spacing: 9) {
                if model.isRecording {
                    LiveWave(level: model.micLevel)
                }
                Text(b.text.isEmpty ? "Listening…" : Self.tail(b.text))
                    .font(.system(size: 13, weight: .regular))
                    .italic(b.text.isEmpty)
                    .foregroundStyle(b.text.isEmpty ? .secondary : .primary)
                    .lineLimit(5)
                    .multilineTextAlignment(.leading)
            }
        case .say, .hint:
            Text(Self.clip(b.text))
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(b.style == .hint ? .secondary : .primary)
                .lineLimit(6)
                .multilineTextAlignment(.leading)
        case .confirm:
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.shield.fill")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Brand.tintColor)
                    Text(b.text)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(5)
                        .multilineTextAlignment(.leading)
                }
                HStack(spacing: 8) {
                    Button { onConfirm(false) } label: {
                        Text("Cancel").frame(minWidth: 64)
                    }
                    .buttonStyle(.glass)
                    .controlSize(.regular)
                    Button { onConfirm(true) } label: {
                        Text("Confirm").frame(minWidth: 64)
                    }
                    .buttonStyle(.glassProminent)
                    .tint(Brand.tintColor)
                    .controlSize(.regular)
                }
                Text("or hold right ⌥ and say “yes” or “no”")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
        }
    }
}

/// Rounded bubble with a small tail at the bottom corner nearest the mascot.
struct BubbleShape: Shape {
    static let tail: CGFloat = 7
    var tailOnRight: Bool

    func path(in rect: CGRect) -> Path {
        let r: CGFloat = 16
        let body = CGRect(x: rect.minX, y: rect.minY, width: rect.width, height: rect.height - Self.tail)
        let p = Path(roundedRect: body, cornerRadius: r, style: .continuous)
        let tx = tailOnRight ? body.maxX - 26 : body.minX + 26
        let dir: CGFloat = tailOnRight ? 1 : -1
        var t = Path()
        t.move(to: CGPoint(x: tx - 8 * dir, y: body.maxY - 1))
        t.addQuadCurve(to: CGPoint(x: tx + 12 * dir, y: rect.maxY),
                       control: CGPoint(x: tx + 2 * dir, y: body.maxY + 2))
        t.addQuadCurve(to: CGPoint(x: tx + 6 * dir, y: body.maxY - 1),
                       control: CGPoint(x: tx + 6 * dir, y: body.maxY + 3))
        t.closeSubpath()
        return p.union(t)
    }
}

/// Five bars driven by the live mic level (re-rendered only while recording).
struct LiveWave: View {
    var level: Float
    private let weights: [CGFloat] = [0.45, 0.8, 1.0, 0.75, 0.5]

    var body: some View {
        HStack(alignment: .center, spacing: 2.5) {
            ForEach(0..<5, id: \.self) { i in
                Capsule()
                    .fill(Brand.tintColor)
                    .frame(width: 3, height: 4 + CGFloat(level) * 15 * weights[i])
            }
        }
        .frame(height: 20)
        .animation(.linear(duration: 0.08), value: level)
    }
}

/// Hosting view that takes the first click (buttons work without
/// activating the app or making the panel key).
final class FirstMouseHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}
