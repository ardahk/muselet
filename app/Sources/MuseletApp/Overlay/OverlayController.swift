import AppKit
import QuartzCore

/// Transparent, click-through, never-key panel covering one screen.
final class OverlayWindow: NSPanel {
    let displayID: CGDirectDisplayID
    let canvas: OverlayCanvas
    /// Screen rect in CG global (top-left) coordinates; canvas-local = global - origin.
    private(set) var cgBounds: CGRect

    init(screen: NSScreen) {
        displayID = ScreenGeometry.displayID(of: screen) ?? 0
        cgBounds = ScreenGeometry.cgBounds(of: screen)
        canvas = OverlayCanvas(frame: NSRect(origin: .zero, size: screen.frame.size))
        super.init(contentRect: screen.frame,
                   styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .screenSaver
        ignoresMouseEvents = true
        isReleasedWhenClosed = false
        hidesOnDeactivate = false
        isFloatingPanel = true
        becomesKeyOnlyIfNeeded = true
        animationBehavior = .none
        collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
        isExcludedFromWindowsMenu = true
        contentView = canvas
        setFrame(screen.frame, display: false)
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    func toLocal(_ cg: CGPoint) -> CGPoint {
        CGPoint(x: cg.x - cgBounds.minX, y: cg.y - cgBounds.minY)
    }

    func toLocal(_ cg: CGRect) -> CGRect {
        CGRect(origin: toLocal(cg.origin), size: cg.size)
    }

    func toGlobal(_ local: CGPoint) -> CGPoint {
        CGPoint(x: local.x + cgBounds.minX, y: local.y + cgBounds.minY)
    }
}

/// Layer-hosting view with a top-left (flipped) geometry so sublayer
/// positions are simply `cgGlobal - screenOrigin`.
final class OverlayCanvas: NSView {
    let root = CALayer()

    override init(frame: NSRect) {
        super.init(frame: frame)
        root.isGeometryFlipped = true
        root.frame = bounds
        root.masksToBounds = false
        layer = root          // layer-hosting: we own the tree
        wantsLayer = true
        layerContentsRedrawPolicy = .never
    }

    required init?(coder: NSCoder) { fatalError() }

    override var isFlipped: Bool { true }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }

    override func layout() {
        super.layout()
        root.frame = bounds
    }

    override func viewDidChangeBackingProperties() {
        super.viewDidChangeBackingProperties()
        let scale = window?.backingScaleFactor ?? 2
        root.contentsScale = scale
        root.sublayers?.forEach { Self.setScale($0, scale) }
    }

    static func setScale(_ l: CALayer, _ s: CGFloat) {
        l.contentsScale = s
        l.sublayers?.forEach { setScale($0, s) }
    }
}

/// One overlay per screen; rebuilt when displays change. Windows are only
/// ordered in while something is drawn, so idle composition cost is zero.
final class OverlayController {
    private(set) var overlays: [OverlayWindow] = []
    var onRebuild: (() -> Void)?
    private var observer: NSObjectProtocol?

    init() {
        rebuild()
        observer = NotificationCenter.default.addObserver(
            forName: NSApplication.didChangeScreenParametersNotification,
            object: nil, queue: .main) { [weak self] _ in
            self?.rebuild()
        }
    }

    deinit { if let o = observer { NotificationCenter.default.removeObserver(o) } }

    func rebuild() {
        overlays.forEach { $0.orderOut(nil); $0.close() }
        overlays = NSScreen.screens.map { OverlayWindow(screen: $0) }
        onRebuild?()
    }

    func overlay(forCG p: CGPoint) -> OverlayWindow? {
        if let s = ScreenGeometry.nearestScreen(toCG: p), let id = ScreenGeometry.displayID(of: s) {
            if let w = overlays.first(where: { $0.displayID == id }) { return w }
        }
        return overlays.first
    }

    func show(_ w: OverlayWindow) {
        if !w.isVisible { w.orderFrontRegardless() }
    }

    func hide(_ w: OverlayWindow) {
        if w.isVisible { w.orderOut(nil) }
    }
}
