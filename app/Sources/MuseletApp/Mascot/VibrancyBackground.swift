import AppKit
import SwiftUI

/// Behind-window vibrancy (NSVisualEffectView) clipped to a SwiftUI shape.
/// Adapts to light/dark mode on its own.
struct VibrancyBackground<S: Shape>: NSViewRepresentable {
    var shape: S
    var material: NSVisualEffectView.Material = .popover

    func makeNSView(context: Context) -> ShapedEffectView {
        let v = ShapedEffectView()
        v.blendingMode = .behindWindow
        v.state = .active
        update(v)
        return v
    }

    func updateNSView(_ v: ShapedEffectView, context: Context) {
        update(v)
    }

    private func update(_ v: ShapedEffectView) {
        v.material = material
        let s = shape
        v.makePath = { rect in s.path(in: rect).cgPath }
        v.refreshMask()
    }
}

/// NSVisualEffectView whose maskImage follows `makePath` (top-left origin).
final class ShapedEffectView: NSVisualEffectView {
    var makePath: ((CGRect) -> CGPath)?

    override func layout() {
        super.layout()
        refreshMask()
    }

    func refreshMask() {
        guard let make = makePath, bounds.width > 0, bounds.height > 0 else { return }
        let size = bounds.size
        let path = make(CGRect(origin: .zero, size: size))
        maskImage = NSImage(size: size, flipped: true) { _ in
            NSColor.black.setFill()
            NSBezierPath(cgPath: path).fill()
            return true
        }
    }
}
