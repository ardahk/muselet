import AppKit
import QuartzCore

/// The kitten mascot ("Muse"), drawn procedurally with Core Animation.
/// Looping motion (breathing, tail sway, dot bob, z's, listening pulse) runs
/// in the render server; only the randomized blink / ear twitch / look-around
/// use a cheap one-shot timer every few seconds. Shape constants live in
/// `MascotPaths`, colours in `MascotPalette`.
///
/// Split across files: +Build (layers), +Moods (mood mapping, gaze, mic
/// level), +Life (blinks, look-around, hover perk), +Effects (one-shots).
final class MascotView: NSView {
    static let size = CGSize(width: 108, height: 116)
    static let bodySize = CGSize(width: 56, height: 54)
    static let bodyBase = CGPoint(x: 54, y: 16)   // bottom-center of the body in view coords

    var onClick: (() -> Void)?
    var onDragEnded: (() -> Void)?
    /// Maps a proposed window origin to an allowed one (live, while dragging).
    var constrainOrigin: ((NSPoint) -> NSPoint)?
    /// Pointer entered / left the body (drives the hover pill).
    var onHover: ((Bool) -> Void)?

    // Layers (internal so the extensions in sibling files can reach them).
    let root = CALayer()
    let groundShadow = CAShapeLayer()
    let ring = CAShapeLayer()            // mic-level ring (listening)
    let pulse = CAShapeLayer()           // soft expanding pulse (listening)
    let lean = CALayer()                 // rotation (tilt / lean toward target)
    let perk = CALayer()                 // hover perk-up scale
    let bounce = CALayer()               // hop / squash
    let breath = CALayer()               // idle breathing
    let tail = CALayer()                 // pivot at the tail base: sway / swish / flick / wag
    var tailStrokes: [CAShapeLayer] = [] // outline, fur, ginger tip on one path
    let earL = CAShapeLayer()            // pivot at the base: tilt per mood, idle twitch
    let earR = CAShapeLayer()
    let bodyFill = CAGradientLayer()
    let bodyMask = CAShapeLayer()
    let outline = CAShapeLayer()
    let face = CALayer()
    let eyes = CALayer()
    let eyeL = CAShapeLayer()
    let eyeR = CAShapeLayer()
    let lidL = CAShapeLayer()            // closed eyes: "^" (success) / bowed (asleep)
    let lidR = CAShapeLayer()
    let cheekL = CAShapeLayer()
    let cheekR = CAShapeLayer()
    let whiskers = CAShapeLayer()
    let nose = CAShapeLayer()
    let mouth = CAShapeLayer()           // stroked "w"
    let mouthOpen = CAShapeLayer()       // small "o" (mic level, success)
    let pawL = CAShapeLayer()
    let pawR = CAShapeLayer()            // rises to the chin while thinking
    let tailWrap = CALayer()             // sleeping: tail wrapped over the paws
    var wrapStrokes: [CAShapeLayer] = []
    let dots = CALayer()                 // thinking: three bobbing dots
    var dotLayers: [CAShapeLayer] = []
    let question = CATextLayer()
    var sparkles: [CAShapeLayer] = []
    var zees: [CATextLayer] = []

    var mood: MascotMood = .idle
    var breathKind = -1
    var tailKind = -1
    var lookVector = CGVector(dx: 0, dy: 0)
    var hovered = false
    var blinkWork: DispatchWorkItem?
    var lookAroundWork: DispatchWorkItem?
    var earTwitchWork: DispatchWorkItem?
    var lookingAround = false
    var mouthCenter: CGPoint { MascotPaths.Face.mouth }

    var reduceMotion: Bool { NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }
    private var motionObserver: NSObjectProtocol?

    override init(frame: NSRect) {
        super.init(frame: frame)
        layer = root
        wantsLayer = true
        layerContentsRedrawPolicy = .never
        build()
        apply(mood: .idle, animated: false)
        scheduleBlink()
        scheduleLookAround()
        scheduleEarTwitch()
        motionObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.accessibilityDisplayOptionsDidChangeNotification,
            object: nil, queue: .main) { [weak self] _ in
            guard let self else { return }
            self.breathKind = -1                 // rebuild loops for the new setting
            self.tailKind = -1
            self.apply(mood: self.mood, animated: false)
        }
    }

    required init?(coder: NSCoder) { fatalError() }

    deinit {
        if let o = motionObserver { NSWorkspace.shared.notificationCenter.removeObserver(o) }
        blinkWork?.cancel()
        lookAroundWork?.cancel()
        earTwitchWork?.cancel()
    }

    override var isFlipped: Bool { false }
    override var mouseDownCanMoveWindow: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func viewDidChangeBackingProperties() {
        super.viewDidChangeBackingProperties()
        OverlayCanvas.setScale(root, window?.backingScaleFactor ?? 2)
    }

    /// Body rect (with a little slack) in view coordinates.
    /// The visible kitten (ground shadow, body, ears and their bounce headroom) in
    /// window coordinates; the bubble anchor sits inside it. Kept on screen.
    /// The tail (incl. stroke, outline and wag overshoot) sets the right edge.
    static var kittenRect: CGRect {
        let left = bodyBase.x - bodySize.width / 2
        let tail = MascotPaths.Tail.base.x + MascotPaths.Tail.maxReachX
            + MascotPaths.Tail.width / 2 + MascotPaths.outlineWidth
        let right = left + max(bodySize.width, tail) + 3     // + celebrate squash/stretch
        return CGRect(x: left - 2, y: bodyBase.y - 6, width: right - left + 2,
                      height: MascotPaths.Body.height + MascotPaths.Ear.height + 10)
    }

    var bodyHitRect: CGRect {
        CGRect(x: Self.bodyBase.x - Self.bodySize.width / 2 - 6, y: Self.bodyBase.y - 6,
               width: Self.bodySize.width + 12, height: Self.bodySize.height + 16)
    }

    // MARK: hover

    private var hoverArea: NSTrackingArea?

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let a = hoverArea { removeTrackingArea(a) }
        // activeAlways: the panel is never key and the app is usually inactive.
        let a = NSTrackingArea(rect: bodyHitRect, options: [.mouseEnteredAndExited, .activeAlways],
                               owner: self, userInfo: nil)
        addTrackingArea(a)
        hoverArea = a
    }

    override func mouseEntered(with event: NSEvent) {
        setHovered(true)
        onHover?(true)
    }

    override func mouseExited(with event: NSEvent) {
        setHovered(false)
        onHover?(false)
    }

    // MARK: drag + click

    private var dragStartMouse: NSPoint?
    private var dragStartOrigin: NSPoint?
    private var dragged = false

    override func hitTest(_ point: NSPoint) -> NSView? {
        let p = convert(point, from: superview)
        return bodyHitRect.contains(p) ? self : nil
    }

    override func mouseDown(with event: NSEvent) {
        dragStartMouse = NSEvent.mouseLocation
        dragStartOrigin = window?.frame.origin
        dragged = false
    }

    override func mouseDragged(with event: NSEvent) {
        guard let m0 = dragStartMouse, let o0 = dragStartOrigin, let w = window else { return }
        let m = NSEvent.mouseLocation
        let dx = m.x - m0.x, dy = m.y - m0.y
        if !dragged && hypot(dx, dy) < 3 { return }
        if !dragged {
            dragged = true
            NSCursor.closedHand.push()
        }
        let p = NSPoint(x: o0.x + dx, y: o0.y + dy)
        w.setFrameOrigin(constrainOrigin?(p) ?? p)
    }

    override func mouseUp(with event: NSEvent) {
        if dragged {
            NSCursor.pop()
            onDragEnded?()
        } else {
            onClick?()
        }
        dragStartMouse = nil
        dragStartOrigin = nil
        dragged = false
    }

    override func resetCursorRects() {
        let body = CGRect(x: Self.bodyBase.x - Self.bodySize.width / 2, y: Self.bodyBase.y,
                          width: Self.bodySize.width, height: Self.bodySize.height)
        addCursorRect(body, cursor: .openHand)
    }
}
