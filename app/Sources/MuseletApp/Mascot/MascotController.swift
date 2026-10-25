import AppKit
import Combine
import HandsKit
import SwiftUI

/// Small non-activating panel that never becomes key or main.
final class FloatingPanel: NSPanel {
    init(size: CGSize, level: NSWindow.Level) {
        super.init(contentRect: NSRect(origin: .zero, size: size),
                   styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        self.level = level
        isFloatingPanel = true
        hidesOnDeactivate = false
        becomesKeyOnlyIfNeeded = true
        isReleasedWhenClosed = false
        isMovable = false
        animationBehavior = .none
        isExcludedFromWindowsMenu = true
        collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

/// Owns the mascot panel + speech bubble panel and maps AppModel state to them.
final class MascotController {
    private let model: AppModel
    let view: MascotView
    private let panel: FloatingPanel
    private let bubblePanel: FloatingPanel
    private let bubbleHost: FirstMouseHostingView<BubbleView>
    private let layout = BubbleLayout()
    /// Capsule under the mascot (keyboard + mic), shown on hover / while listening.
    let pill: PillController
    private var bag = Set<AnyCancellable>()

    var onConfirmReply: ((Bool) -> Void)?
    var onMoved: ((CGPoint) -> Void)?       // global CG anchor

    private var hideBubbleWork: DispatchWorkItem?
    private var orderOutWork: DispatchWorkItem?
    private var revertWork: DispatchWorkItem?
    private var sleepWork: DispatchWorkItem?
    private static let originKey = "muselet.mascot.origin"
    private static let sleepAfter: TimeInterval = 300

    init(model: AppModel) {
        self.model = model
        view = MascotView(frame: NSRect(origin: .zero, size: MascotView.size))
        panel = FloatingPanel(size: MascotView.size, level: .statusBar)
        panel.contentView = view
        pill = PillController(model: model, parent: panel)

        bubblePanel = FloatingPanel(size: CGSize(width: 10, height: 10), level: .statusBar)
        bubblePanel.ignoresMouseEvents = true
        let bubble = BubbleView(model: model, layout: layout, onConfirm: { _ in })
        bubbleHost = FirstMouseHostingView(rootView: bubble)
        bubbleHost.sizingOptions = [.intrinsicContentSize]
        bubbleHost.wantsLayer = true
        bubbleHost.layer?.backgroundColor = .clear
        bubblePanel.contentView = bubbleHost
        bubbleHost.rootView = BubbleView(model: model, layout: layout, onConfirm: { [weak self] yes in
            self?.onConfirmReply?(yes)
        })

        view.onClick = { [weak self] in self?.poked() }
        view.onDragEnded = { [weak self] in self?.dragEnded() }
        view.constrainOrigin = { MascotBounds.clamp($0, visibleFrames: NSScreen.screens.map(\.visibleFrame)) }
        view.onHover = { [weak self] h in
            guard let self else { return }
            if h { self.wake() }
            self.pill.mascotHover(h)
        }

        placeInitially()
        panel.orderFrontRegardless()
        panel.addChildWindow(bubblePanel, ordered: .above)
        bubblePanel.orderOut(nil)

        model.$mood.removeDuplicates().sink { [weak self] m in self?.moodChanged(m) }.store(in: &bag)
        model.levelSubject.sink { [weak self] v in self?.view.setLevel(v) }.store(in: &bag)
        model.$pendingConfirm.sink { [weak self] c in
            self?.bubblePanel.ignoresMouseEvents = (c == nil)
        }.store(in: &bag)
        NotificationCenter.default.publisher(for: NSApplication.didChangeScreenParametersNotification)
            .sink { [weak self] _ in self?.ensureOnScreen() }.store(in: &bag)
        NotificationCenter.default.publisher(for: NSView.frameDidChangeNotification, object: bubbleHost)
            .sink { [weak self] _ in self?.layoutBubble() }.store(in: &bag)
        bubbleHost.postsFrameChangedNotifications = true
        scheduleSleep()
    }

    // MARK: geometry

    /// Body center in global CG (top-left) coordinates.
    func anchorCG() -> CGPoint {
        let f = panel.frame
        let p = CGPoint(x: f.minX + MascotView.bodyBase.x,
                        y: f.minY + MascotView.bodyBase.y + MascotView.bodySize.height / 2)
        return ScreenGeometry.cgPoint(fromAppKit: p)
    }

    private func placeInitially() {
        if let s = UserDefaults.standard.string(forKey: Self.originKey) {
            let p = NSPointFromString(s)
            if NSScreen.screens.contains(where: { $0.visibleFrame.insetBy(dx: -40, dy: -40).contains(p) }) {
                panel.setFrameOrigin(clamped(p))
                onMoved?(anchorCG())
                return
            }
        }
        resetPosition()
    }

    private func clamped(_ origin: NSPoint) -> NSPoint {
        MascotBounds.clamp(origin, visibleFrames: NSScreen.screens.map(\.visibleFrame))
    }

    func resetPosition() {
        guard let s = NSScreen.main ?? NSScreen.screens.first else { return }
        let vf = s.visibleFrame
        panel.setFrameOrigin(clamped(NSPoint(x: vf.maxX - MascotView.size.width - 18, y: vf.minY + 10)))
        onMoved?(anchorCG())
        layoutBubble()
        pill.layout()
    }

    private func ensureOnScreen() {
        let c = NSPoint(x: panel.frame.midX, y: panel.frame.midY)
        if !NSScreen.screens.contains(where: { $0.frame.contains(c) }) { resetPosition() }
        let p = clamped(panel.frame.origin)
        if p != panel.frame.origin { panel.setFrameOrigin(p) }
        onMoved?(anchorCG())
        layoutBubble()
        pill.layout()
    }

    /// Debug hook `mascot_edge`: a drag far past one screen edge, through the drag clamp.
    func debugDrag(toward edge: String) {
        guard let vf = (panel.screen ?? NSScreen.main)?.visibleFrame else { return }
        var p = panel.frame.origin
        switch edge {
        case "right": p.x = vf.maxX + 400
        case "top": p.y = vf.maxY + 400
        case "bottom": p.y = vf.minY - 400
        default: p.x = vf.minX - 400
        }
        panel.setFrameOrigin(view.constrainOrigin?(p) ?? clamped(p))
        dragEnded()
    }

    private func dragEnded() {
        UserDefaults.standard.set(NSStringFromPoint(panel.frame.origin), forKey: Self.originKey)
        onMoved?(anchorCG())
        layoutBubble()
        pill.layout()
    }

    // MARK: moods

    private func moodChanged(_ m: MascotMood) {
        view.apply(mood: m)
        revertWork?.cancel()
        let revertAfter: TimeInterval?
        switch m {
        case .success: revertAfter = 2.2
        case .confused: revertAfter = 4.5
        case .thinking, .acting: revertAfter = 45   // safety net if the brain goes quiet
        default: revertAfter = nil
        }
        if let t = revertAfter {
            let w = DispatchWorkItem { [weak self] in
                guard let self, self.model.mood == m else { return }
                self.model.mood = .idle
            }
            revertWork = w
            DispatchQueue.main.asyncAfter(deadline: .now() + t, execute: w)
        }
        scheduleSleep()
    }

    /// One-shot timer (not a repeating one): fall asleep after 5 idle minutes.
    func scheduleSleep() {
        sleepWork?.cancel()
        guard model.mood == .idle else { return }
        let w = DispatchWorkItem { [weak self] in
            guard let self, self.model.mood == .idle, !self.model.isRecording else { return }
            self.model.mood = .sleeping
        }
        sleepWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.sleepAfter, execute: w)
    }

    func wake() {
        if model.mood == .sleeping { model.mood = .idle }
        scheduleSleep()
    }

    private func poked() {
        let wasSleeping = model.mood == .sleeping
        wake()
        view.hop()
        if model.pendingConfirm == nil && !model.isRecording {
            showBubble(wasSleeping ? "I'm up! Hold right ⌥, or use my mic."
                                   : "Hold right ⌥, or click my mic below.",
                       style: .hint)
        }
    }

    /// Eyes (and lean while acting) toward a global CG point; nil recenters.
    func look(atCG target: CGPoint?) {
        view.look(towardCG: target, fromCG: anchorCG())
    }

    // MARK: bubble

    func showBubble(_ text: String, style: BubbleStyle, autoHide: Bool = true) {
        hideBubbleWork?.cancel()
        orderOutWork?.cancel()
        let content = BubbleContent(text: text, style: style)
        if model.bubble != content { model.bubble = content }
        if !bubblePanel.isVisible {
            layoutBubble()
            bubblePanel.orderFront(nil)
            panel.addChildWindow(bubblePanel, ordered: .above)
        }
        if !model.bubbleVisible { model.bubbleVisible = true }
        DispatchQueue.main.async { [weak self] in self?.layoutBubble() }
        guard autoHide, style != .confirm else { return }
        let words = Double(text.split(separator: " ").count)
        let delay = min(9, max(2.6, 1.6 + words * 0.32))
        let w = DispatchWorkItem { [weak self] in self?.hideBubble() }
        hideBubbleWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: w)
    }

    func hideBubble() {
        hideBubbleWork?.cancel()
        guard model.pendingConfirm == nil else { return }
        model.bubbleVisible = false
        let w = DispatchWorkItem { [weak self] in
            guard let self, !self.model.bubbleVisible else { return }
            self.model.bubble = nil
            // The latency chip outlives the bubble: keep the panel for it.
            if self.model.latencyChip == nil { self.bubblePanel.orderOut(nil) }
            else { self.layoutBubble() }
        }
        orderOutWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35, execute: w)
    }

    /// Confirm mode ended (confirm_cancel / disconnect): drop the confirm
    /// bubble if it is the one showing.
    func clearConfirmBubble() {
        guard model.pendingConfirm == nil else { return }
        if model.bubble?.style == .confirm { hideBubble() }
    }

    // MARK: latency chip

    private var latencyWork: DispatchWorkItem?
    static let latencyChipSeconds: TimeInterval = 2.0

    /// Subtle "0.21 s" chip beside the bubble for ~2 s, then fade out.
    func showLatency(ms: Double) {
        latencyWork?.cancel()
        model.latencyVisible = false
        model.latencyChip = LatencyChip(text: LatencyFormat.seconds(ms))
        if !bubblePanel.isVisible {
            layoutBubble()
            bubblePanel.orderFront(nil)
            panel.addChildWindow(bubblePanel, ordered: .above)
        }
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.layoutBubble()
            self.model.latencyVisible = true          // next turn: fades in
        }
        let w = DispatchWorkItem { [weak self] in
            guard let self else { return }
            self.model.latencyVisible = false
            let chip = self.model.latencyChip
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                guard let self, !self.model.latencyVisible, self.model.latencyChip == chip else { return }
                self.model.latencyChip = nil
                if self.model.bubble == nil || !self.model.bubbleVisible {
                    self.bubblePanel.orderOut(nil)
                    self.model.bubble = nil
                } else {
                    DispatchQueue.main.async { [weak self] in self?.layoutBubble() }
                }
            }
        }
        latencyWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.latencyChipSeconds, execute: w)
    }

    /// Size the bubble panel to its SwiftUI content and anchor it beside the mascot.
    private func layoutBubble() {
        let size = bubbleHost.fittingSize
        guard size.width > 1, size.height > 1 else { return }
        let m = panel.frame
        let screen = panel.screen ?? NSScreen.main
        let vf = screen?.visibleFrame ?? m
        // Bubble's tail corner sits just above-left of the mascot's head.
        let headLeft = m.minX + MascotView.bodyBase.x - MascotView.bodySize.width / 2
        let headRight = m.minX + MascotView.bodyBase.x + MascotView.bodySize.width / 2
        // The hosting view has 14 pt of transparent padding around the bubble.
        let baseY = m.minY + MascotView.bodyBase.y + MascotView.bodySize.height - 30
        let fitsLeft = headLeft + 22 - size.width >= vf.minX
        layout.tailOnRight = fitsLeft
        var x = fitsLeft ? headLeft + 22 - size.width : headRight - 22
        x = max(vf.minX, min(x, vf.maxX - size.width))
        var y = baseY
        y = max(vf.minY, min(y, vf.maxY - size.height))
        let frame = NSRect(x: x, y: y, width: size.width, height: size.height).integral
        if bubblePanel.frame != frame { bubblePanel.setFrame(frame, display: true) }
    }
}

/// Keeps the whole kitten (`MascotView.kittenRect`, incl. the bubble anchor) inside a
/// screen's `visibleFrame`: on drag (live), launch from the saved origin and screen changes.
enum MascotBounds {
    /// Window origin moved the least so the kitten fits the visible frame it overlaps
    /// most (else the nearest one). No screens: unchanged.
    static func clamp(_ origin: NSPoint, visibleFrames: [NSRect],
                      kitten: CGRect = MascotView.kittenRect) -> NSPoint {
        let k = kitten.offsetBy(dx: origin.x, dy: origin.y)
        func area(_ r: NSRect) -> CGFloat {
            let i = r.intersection(k)
            return i.isNull ? 0 : i.width * i.height
        }
        func distance(_ r: NSRect) -> CGFloat {
            hypot(max(r.minX - k.midX, 0, k.midX - r.maxX), max(r.minY - k.midY, 0, k.midY - r.maxY))
        }
        guard let vf = visibleFrames.max(by: { a, b in
            let (aa, ab) = (area(a), area(b))
            return aa == ab ? distance(a) > distance(b) : aa < ab
        }) else { return origin }
        let x = min(max(k.minX, vf.minX), vf.maxX - k.width)
        let y = min(max(k.minY, vf.minY), vf.maxY - k.height)
        return NSPoint(x: origin.x + (x - k.minX), y: origin.y + (y - k.minY))
    }
}
