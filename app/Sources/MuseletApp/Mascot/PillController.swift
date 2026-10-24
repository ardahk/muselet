import AppKit
import Combine
import HandsKit
import SwiftUI

/// Panel for the pill. Becomes key only while the text field is open
/// (non-activating: the frontmost app stays frontmost).
final class PillPanel: NSPanel {
    var acceptsKey = false

    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: 10, height: 10),
                   styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .statusBar
        isFloatingPanel = true
        hidesOnDeactivate = false
        becomesKeyOnlyIfNeeded = false
        isReleasedWhenClosed = false
        isMovable = false
        animationBehavior = .none
        isExcludedFromWindowsMenu = true
        collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
    }

    override var canBecomeKey: Bool { acceptsKey }
    override var canBecomeMain: Bool { false }
}

/// Hosting view that takes the first click and reports pointer enter/exit.
final class HoverHostingView<Content: View>: NSHostingView<Content> {
    var onHover: ((Bool) -> Void)?
    private var hoverArea: NSTrackingArea?

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let a = hoverArea { removeTrackingArea(a) }
        let a = NSTrackingArea(rect: .zero, options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
                               owner: self, userInfo: nil)
        addTrackingArea(a)
        hoverArea = a
    }

    override func mouseEntered(with event: NSEvent) {
        super.mouseEntered(with: event)
        onHover?(true)
    }

    override func mouseExited(with event: NSEvent) {
        super.mouseExited(with: event)
        onHover?(false)
    }
}

/// The capsule under the mascot: shown while the pointer is over the
/// mascot or the pill, while listening, and while typing.
final class PillController {
    let state = PillState()
    private let model: AppModel
    private let panel = PillPanel()
    private var host: HoverHostingView<PillView>!
    private weak var parent: NSWindow?
    private var bag = Set<AnyCancellable>()
    private var hoverMascot = false
    private var hoverPill = false
    private var hideWork: DispatchWorkItem?
    private var typingCtx: PendingCtx?

    var onMic: (() -> Void)?
    var onTyped: ((String, PendingCtx) -> Void)?

    init(model: AppModel, parent: NSWindow) {
        self.model = model
        self.parent = parent
        host = HoverHostingView(rootView: makeView())
        host.sizingOptions = [.intrinsicContentSize]
        host.wantsLayer = true
        host.layer?.backgroundColor = .clear
        host.onHover = { [weak self] h in
            self?.hoverPill = h
            self?.update()
        }
        panel.contentView = host
        host.postsFrameChangedNotifications = true
        NotificationCenter.default.publisher(for: NSView.frameDidChangeNotification, object: host)
            .sink { [weak self] _ in self?.layout() }.store(in: &bag)
        NotificationCenter.default.publisher(for: NSWindow.didResignKeyNotification, object: panel)
            .sink { [weak self] _ in self?.resignedKey() }.store(in: &bag)
        model.$isRecording.removeDuplicates().dropFirst()
            .sink { [weak self] _ in DispatchQueue.main.async { self?.update() } }.store(in: &bag)
    }

    private func makeView() -> PillView {
        PillView(model: model, state: state,
                 onMic: { [weak self] in self?.onMic?() },
                 onKeyboard: { [weak self] in self?.beginTyping() },
                 onSubmit: { [weak self] t in self?.submit(t) },
                 onCancel: { [weak self] in self?.endTyping() })
    }

    func mascotHover(_ h: Bool) {
        hoverMascot = h
        update()
    }

    private var wantsShow: Bool { hoverMascot || hoverPill || model.isRecording || state.typing }

    func update() {
        hideWork?.cancel()
        if wantsShow {
            show()
            return
        }
        // Grace period so the pointer can travel from the mascot to the pill.
        let w = DispatchWorkItem { [weak self] in
            guard let self, !self.wantsShow else { return }
            self.hide()
        }
        hideWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6, execute: w)
    }

    private func show() {
        if !panel.isVisible {
            layout()
            panel.orderFrontRegardless()
            parent?.addChildWindow(panel, ordered: .above)
        }
        if !state.shown { state.shown = true }
        DispatchQueue.main.async { [weak self] in self?.layout() }
    }

    private func hide() {
        state.shown = false
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
            guard let self, !self.state.shown else { return }
            self.panel.orderOut(nil)
        }
    }

    // MARK: typing

    private func beginTyping() {
        typingCtx = RequestCtx.capture()       // before the pill takes key focus
        state.text = ""
        state.typing = true
        panel.acceptsKey = true
        show()
        panel.makeKey()
    }

    private func submit(_ raw: String) {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        let ctx = typingCtx ?? RequestCtx.capture()
        endTyping()
        onTyped?(text, ctx)
    }

    func endTyping() {
        guard state.typing else { return }
        state.typing = false
        state.text = ""
        typingCtx = nil
        panel.acceptsKey = false
        if panel.isKeyWindow {
            // Ordering out gives keyboard focus back to the frontmost app.
            panel.orderOut(nil)
            if wantsShow {
                panel.orderFrontRegardless()
                parent?.addChildWindow(panel, ordered: .above)
            }
        }
        update()
    }

    /// Clicked elsewhere: close an empty field, keep a draft.
    private func resignedKey() {
        if state.typing && state.text.trimmingCharacters(in: .whitespaces).isEmpty { endTyping() }
    }

    // MARK: geometry

    /// Centered under the mascot's body (the host has a 10 pt transparent margin).
    func layout() {
        guard let m = parent?.frame else { return }
        let size = host.fittingSize
        guard size.width > 1, size.height > 1 else { return }
        let vf = (parent?.screen ?? NSScreen.main)?.visibleFrame ?? m
        let cx = m.minX + MascotView.bodyBase.x
        var x = cx - size.width / 2
        x = max(vf.minX - 10, min(x, vf.maxX - size.width + 10))
        let pillTop = m.minY + MascotView.bodyBase.y - 7
        var y = pillTop + 10 - size.height
        y = max(vf.minY - 8, y)
        let frame = NSRect(x: x, y: y, width: size.width, height: size.height).integral
        if panel.frame != frame { panel.setFrame(frame, display: true) }
    }
}
