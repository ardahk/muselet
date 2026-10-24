import AppKit
import QuartzCore

/// The cork creature, drawn procedurally with Core Animation. All looping
/// motion (breathing, blinking, orbiting dots, z's) is CA animations that run
/// in the render server, so the app process stays idle.
final class MascotView: NSView {
    static let size = CGSize(width: 108, height: 116)
    static let bodySize = CGSize(width: 56, height: 54)
    static let bodyBase = CGPoint(x: 54, y: 16)   // bottom-center of the body in view coords

    var onClick: (() -> Void)?
    var onDragEnded: (() -> Void)?

    private let root = CALayer()
    private let groundShadow = CAShapeLayer()
    private let ring = CAShapeLayer()
    private let lean = CALayer()
    private let bounce = CALayer()
    private let breath = CALayer()
    private let bodyFill = CAGradientLayer()
    private let bodyMask = CAShapeLayer()
    private let outline = CAShapeLayer()
    private let wires = CAShapeLayer()
    private let cap = CAGradientLayer()
    private let capKnob = CAGradientLayer()
    private let face = CALayer()
    private let eyes = CALayer()
    private let eyeL = CAShapeLayer()
    private let eyeR = CAShapeLayer()
    private let cheekL = CAShapeLayer()
    private let cheekR = CAShapeLayer()
    private let mouth = CAShapeLayer()
    private let orbit = CALayer()
    private let question = CATextLayer()
    private var sparkles: [CAShapeLayer] = []
    private var zees: [CATextLayer] = []

    private(set) var mood: MascotMood = .idle
    private var breathKind = -1
    private var lookVector = CGVector(dx: 0, dy: 0)
    private var mouthCenter: CGPoint { CGPoint(x: Self.bodySize.width / 2, y: 18.5) }

    override init(frame: NSRect) {
        super.init(frame: frame)
        layer = root
        wantsLayer = true
        layerContentsRedrawPolicy = .never
        build()
        apply(mood: .idle, animated: false)
    }

    required init?(coder: NSCoder) { fatalError() }

    override var isFlipped: Bool { false }
    override var mouseDownCanMoveWindow: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func viewDidChangeBackingProperties() {
        super.viewDidChangeBackingProperties()
        OverlayCanvas.setScale(root, window?.backingScaleFactor ?? 2)
    }

    // MARK: build

    private func build() {
        let s = Self.bodySize
        let bodyRect = CGRect(origin: .zero, size: s)
        let bodyPath = MascotPaths.bodyPath(width: s.width, height: s.height, bottomRadius: 15, topRadius: 27)
        root.frame = CGRect(origin: .zero, size: Self.size)

        // Ground shadow
        groundShadow.path = CGPath(ellipseIn: CGRect(x: -20, y: -3.5, width: 40, height: 7), transform: nil)
        groundShadow.position = CGPoint(x: Self.bodyBase.x, y: Self.bodyBase.y - 3)
        groundShadow.fillColor = NSColor.black.withAlphaComponent(0.22).cgColor
        groundShadow.shadowColor = NSColor.black.cgColor
        groundShadow.shadowOpacity = 0.25
        groundShadow.shadowRadius = 3
        groundShadow.shadowOffset = .zero
        root.addSublayer(groundShadow)

        // Listening ring
        let rr: CGFloat = 37
        ring.path = CGPath(ellipseIn: CGRect(x: -rr, y: -rr, width: rr * 2, height: rr * 2), transform: nil)
        ring.position = CGPoint(x: Self.bodyBase.x, y: Self.bodyBase.y + s.height / 2)
        ring.fillColor = Brand.tint.withAlphaComponent(0.07).cgColor
        ring.strokeColor = Brand.tint.cgColor
        ring.lineWidth = 2.2
        ring.opacity = 0
        root.addSublayer(ring)

        // Transform stack: lean (rotation) > bounce (hop/squash) > breath (idle scale)
        for l in [lean, bounce, breath] {
            l.bounds = bodyRect
            l.anchorPoint = CGPoint(x: 0.5, y: 0)
        }
        lean.position = Self.bodyBase
        bounce.position = CGPoint(x: s.width / 2, y: 0)
        breath.position = CGPoint(x: s.width / 2, y: 0)
        root.addSublayer(lean)
        lean.addSublayer(bounce)
        bounce.addSublayer(breath)

        // Body: cork gradient masked by the gumdrop path
        bodyFill.frame = bodyRect
        bodyFill.colors = [Brand.corkLight.cgColor, Brand.corkMid.cgColor, Brand.corkDark.cgColor]
        bodyFill.locations = [0, 0.55, 1]
        bodyFill.startPoint = CGPoint(x: 0.3, y: 1)
        bodyFill.endPoint = CGPoint(x: 0.7, y: 0)
        bodyMask.path = bodyPath
        bodyFill.mask = bodyMask
        breath.addSublayer(bodyFill)

        // Cork speckles
        let speck = CAShapeLayer()
        let sp = CGMutablePath()
        let dots: [(CGFloat, CGFloat, CGFloat)] = [
            (9, 38, 1.1), (47, 41, 1.0), (6, 14, 1.2), (50, 18, 1.0), (14, 6, 0.9),
            (42, 7, 1.1), (28, 47, 0.8), (36, 44, 0.7), (21, 44, 0.9), (52, 30, 0.8), (4, 27, 0.8),
        ]
        for (x, y, r) in dots { sp.addEllipse(in: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)) }
        speck.path = sp
        speck.fillColor = Brand.speck.withAlphaComponent(0.28).cgColor
        bodyFill.addSublayer(speck)

        // Sheen on the dome
        let sheen = CAShapeLayer()
        sheen.path = CGPath(ellipseIn: CGRect(x: 10, y: 36, width: 16, height: 10), transform: nil)
        sheen.fillColor = NSColor.white.withAlphaComponent(0.38).cgColor
        sheen.setAffineTransform(CGAffineTransform(rotationAngle: 0.35))
        bodyFill.addSublayer(sheen)

        // Wire belt (the muselet's ring) near the base
        let belt = CAShapeLayer()
        let bp = CGMutablePath()
        bp.move(to: CGPoint(x: 0, y: 9.5))
        bp.addQuadCurve(to: CGPoint(x: s.width, y: 9.5), control: CGPoint(x: s.width / 2, y: 6.5))
        belt.path = bp
        belt.strokeColor = Brand.wireDark.cgColor
        belt.fillColor = nil
        belt.lineWidth = 1.8
        bodyFill.addSublayer(belt)

        outline.path = bodyPath
        outline.fillColor = nil
        outline.strokeColor = Brand.corkDark.withAlphaComponent(0.55).cgColor
        outline.lineWidth = 1
        breath.addSublayer(outline)

        // Side wires from the cap down to the belt
        let wp = CGMutablePath()
        wp.move(to: CGPoint(x: s.width / 2 - 9, y: s.height + 1))
        wp.addCurve(to: CGPoint(x: 3.2, y: 9.5), control1: CGPoint(x: 4, y: s.height - 4),
                    control2: CGPoint(x: 1.5, y: 28))
        wp.move(to: CGPoint(x: s.width / 2 + 9, y: s.height + 1))
        wp.addCurve(to: CGPoint(x: s.width - 3.2, y: 9.5), control1: CGPoint(x: s.width - 4, y: s.height - 4),
                    control2: CGPoint(x: s.width - 1.5, y: 28))
        wires.path = wp
        wires.strokeColor = Brand.wireDark.withAlphaComponent(0.9).cgColor
        wires.fillColor = nil
        wires.lineWidth = 1.3
        wires.lineCap = .round
        breath.addSublayer(wires)

        // Metal cap (plaque) + knob
        cap.frame = CGRect(x: s.width / 2 - 12, y: s.height - 3, width: 24, height: 7)
        cap.cornerRadius = 3.5
        cap.colors = [Brand.wireLight.cgColor, Brand.wireDark.cgColor]
        cap.startPoint = CGPoint(x: 0.5, y: 1)
        cap.endPoint = CGPoint(x: 0.5, y: 0)
        cap.borderColor = Brand.wireDark.withAlphaComponent(0.8).cgColor
        cap.borderWidth = 0.6
        breath.addSublayer(cap)
        capKnob.frame = CGRect(x: s.width / 2 - 3, y: s.height + 3, width: 6, height: 4.5)
        capKnob.cornerRadius = 2.25
        capKnob.colors = cap.colors
        capKnob.startPoint = cap.startPoint
        capKnob.endPoint = cap.endPoint
        breath.addSublayer(capKnob)

        // Face group (moves slightly with gaze)
        face.frame = bodyRect
        breath.addSublayer(face)

        for (c, x) in [(cheekL, CGFloat(11.5)), (cheekR, s.width - 11.5)] {
            c.path = CGPath(ellipseIn: CGRect(x: -4.5, y: -2.6, width: 9, height: 5.2), transform: nil)
            c.position = CGPoint(x: x, y: 21)
            c.fillColor = Brand.cheek.withAlphaComponent(0.33).cgColor
            face.addSublayer(c)
        }

        eyes.frame = bodyRect
        face.addSublayer(eyes)
        for (e, x) in [(eyeL, CGFloat(20)), (eyeR, s.width - 20)] {
            e.bounds = CGRect(x: 0, y: 0, width: 7.4, height: 10.4)
            e.path = CGPath(roundedRect: e.bounds, cornerWidth: 3.7, cornerHeight: 3.7, transform: nil)
            e.position = CGPoint(x: x, y: 29.5)
            e.fillColor = Brand.ink.cgColor
            let glint = CAShapeLayer()
            glint.path = CGPath(ellipseIn: CGRect(x: 3.9, y: 6.0, width: 2.6, height: 2.6), transform: nil)
            glint.fillColor = NSColor.white.withAlphaComponent(0.95).cgColor
            e.addSublayer(glint)
            eyes.addSublayer(e)
        }

        mouth.path = MascotPaths.Mouth.smile.path(center: mouthCenter)
        mouth.fillColor = Brand.ink.cgColor
        mouth.strokeColor = Brand.ink.cgColor
        mouth.lineWidth = 1.6
        mouth.lineJoin = .round
        mouth.lineCap = .round
        face.addSublayer(mouth)

        // Thinking dots orbiting above the head
        orbit.bounds = CGRect(x: -12, y: -12, width: 24, height: 24)
        orbit.position = CGPoint(x: Self.bodyBase.x + 2, y: Self.bodyBase.y + s.height + 21)
        orbit.opacity = 0
        for i in 0..<3 {
            let d = CAShapeLayer()
            let r: CGFloat = [3.0, 2.4, 1.8][i]
            d.path = CGPath(ellipseIn: CGRect(x: -r, y: -r, width: r * 2, height: r * 2), transform: nil)
            let a = CGFloat(i) * 2 * .pi / 3
            d.position = CGPoint(x: cos(a) * 9, y: sin(a) * 9)
            d.fillColor = Brand.tint.cgColor
            orbit.addSublayer(d)
        }
        root.addSublayer(orbit)

        // "?" for confused
        question.string = "?"
        question.font = NSFont.systemFont(ofSize: 22, weight: .heavy)
        question.fontSize = 22
        question.foregroundColor = Brand.tint.cgColor
        question.alignmentMode = .center
        question.bounds = CGRect(x: 0, y: 0, width: 20, height: 28)
        question.position = CGPoint(x: Self.bodyBase.x + 33, y: Self.bodyBase.y + s.height + 6)
        question.opacity = 0
        question.shadowColor = NSColor.black.cgColor
        question.shadowOpacity = 0.2
        question.shadowRadius = 1.5
        question.shadowOffset = CGSize(width: 0, height: -1)
        root.addSublayer(question)

        // Sparkles for success
        let spots: [CGPoint] = [
            CGPoint(x: 16, y: 82), CGPoint(x: 92, y: 78), CGPoint(x: 9, y: 44), CGPoint(x: 99, y: 40),
            CGPoint(x: 54, y: 104),
        ]
        for (i, p) in spots.enumerated() {
            let sp = CAShapeLayer()
            sp.path = MascotPaths.sparkle(radius: i % 2 == 0 ? 6.5 : 5)
            sp.position = p
            sp.fillColor = (i % 2 == 0 ? Brand.tint : NSColor(srgbRed: 1, green: 0.85, blue: 0.4, alpha: 1)).cgColor
            sp.opacity = 0
            root.addSublayer(sp)
            sparkles.append(sp)
        }

        // Z's for sleeping
        for i in 0..<3 {
            let z = CATextLayer()
            z.string = "z"
            let fs: CGFloat = [11, 13, 15][i]
            z.font = NSFont.systemFont(ofSize: fs, weight: .bold)
            z.fontSize = fs
            z.foregroundColor = NSColor.secondaryLabelColor.cgColor
            z.alignmentMode = .center
            z.bounds = CGRect(x: 0, y: 0, width: 14, height: 18)
            z.position = CGPoint(x: Self.bodyBase.x + 26, y: Self.bodyBase.y + s.height - 2)
            z.opacity = 0
            root.addSublayer(z)
            zees.append(z)
        }
    }

    // MARK: moods

    func apply(mood m: MascotMood, animated: Bool = true) {
        let previous = mood
        mood = m
        CATransaction.begin()
        CATransaction.setAnimationDuration(animated ? 0.38 : 0)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(controlPoints: 0.3, 1.45, 0.55, 1))

        // Breathing (only restarted when its tempo changes) + blink
        let kind = m == .sleeping ? 2 : (m == .listening ? 1 : 0)
        if kind != breathKind || breath.animation(forKey: "breath") == nil {
            breathKind = kind
            breath.removeAnimation(forKey: "breath")
            breath.add(breathing(sleeping: kind == 2, fast: kind == 1), forKey: "breath")
        }
        if m == .sleeping {
            [eyeL, eyeR].forEach { $0.removeAnimation(forKey: "blink") }
        } else if eyeL.animation(forKey: "blink") == nil {
            addBlink()
        }

        // Eyes
        let eyeScaleY: CGFloat = m == .sleeping ? 0.16 : 1
        for e in [eyeL, eyeR] { e.transform = CATransform3DMakeScale(1, eyeScaleY, 1) }
        let eyeBoost: CGFloat = (m == .listening || m == .success) ? 1.12 : 1
        switch m {
        case .thinking: lookVector = CGVector(dx: 0.55, dy: 0.85)
        case .acting: break                 // set by look(towardCG:)
        case .sleeping: lookVector = CGVector(dx: 0, dy: -0.3)
        default: lookVector = .zero
        }
        applyLook(eyeBoost: eyeBoost)

        // Mouth
        let mouthShape: MascotPaths.Mouth
        switch m {
        case .idle: mouthShape = .smile
        case .listening: mouthShape = .attentive
        case .thinking: mouthShape = .flat
        case .acting: mouthShape = .attentive
        case .success: mouthShape = .grin
        case .confused: mouthShape = .wavy
        case .sleeping: mouthShape = .sleepy
        }
        mouth.path = mouthShape.path(center: mouthCenter)

        // Cheeks glow on success
        let cheekAlpha: CGFloat = m == .success ? 0.6 : (m == .sleeping ? 0.45 : 0.33)
        [cheekL, cheekR].forEach { $0.fillColor = Brand.cheek.withAlphaComponent(cheekAlpha).cgColor }

        // Lean / tilt
        let tilt: CGFloat
        switch m {
        case .confused: tilt = 0.2
        case .acting: tilt = -lookVector.dx * 0.14
        case .sleeping: tilt = 0.06
        default: tilt = 0
        }
        lean.transform = CATransform3DMakeRotation(tilt, 0, 0, 1)

        // Accessories
        ring.opacity = m == .listening ? 0.55 : 0
        ring.transform = CATransform3DIdentity
        orbit.opacity = m == .thinking ? 1 : 0
        CATransaction.commit()

        if m == .thinking {
            if orbit.animation(forKey: "spin") == nil {
                let spin = CABasicAnimation(keyPath: "transform.rotation.z")
                spin.fromValue = 0
                spin.toValue = -2 * Double.pi
                spin.duration = 1.1
                spin.repeatCount = .infinity
                orbit.add(spin, forKey: "spin")
            }
        } else {
            orbit.removeAnimation(forKey: "spin")
        }

        if m == .confused { popQuestion() } else { hideQuestion() }
        if m == .sleeping { startZees() } else { stopZees() }
        if m == .success && previous != .success { celebrate() }
    }

    private func breathing(sleeping: Bool, fast: Bool) -> CAAnimation {
        let y = CABasicAnimation(keyPath: "transform.scale.y")
        y.fromValue = 1.0
        y.toValue = sleeping ? 1.05 : 1.035
        let x = CABasicAnimation(keyPath: "transform.scale.x")
        x.fromValue = 1.0
        x.toValue = sleeping ? 1.02 : 0.985
        let g = CAAnimationGroup()
        g.animations = [y, x]
        g.duration = sleeping ? 2.6 : (fast ? 0.9 : 1.7)
        g.autoreverses = true
        g.repeatCount = .infinity
        g.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        return g
    }

    private func addBlink() {
        let b = CAKeyframeAnimation(keyPath: "transform.scale.y")
        b.values = [1, 1, 0.1, 1, 1, 0.1, 1, 1]
        b.keyTimes = [0, 0.46, 0.48, 0.50, 0.93, 0.95, 0.97, 1]
        b.duration = 7.4
        b.repeatCount = .infinity
        b.isAdditive = false
        let start = CACurrentMediaTime() + 1.2
        for e in [eyeL, eyeR] {
            b.beginTime = start
            e.add(b, forKey: "blink")
        }
    }

    // MARK: gaze

    /// Point the eyes (and the lean, while acting) toward a global CG point.
    func look(towardCG target: CGPoint?, fromCG origin: CGPoint) {
        if let t = target {
            let dx = t.x - origin.x, dy = origin.y - t.y   // y up
            let d = max(1, hypot(dx, dy))
            lookVector = CGVector(dx: dx / d, dy: dy / d)
        } else {
            lookVector = .zero
        }
        CATransaction.begin()
        CATransaction.setAnimationDuration(0.3)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(controlPoints: 0.3, 1.4, 0.55, 1))
        applyLook(eyeBoost: mood == .listening ? 1.12 : 1)
        if mood == .acting {
            lean.transform = CATransform3DMakeRotation(-lookVector.dx * 0.14, 0, 0, 1)
        }
        CATransaction.commit()
    }

    private func applyLook(eyeBoost: CGFloat) {
        let ex = lookVector.dx * 3.2, ey = lookVector.dy * 2.6
        var t = CATransform3DMakeTranslation(ex, ey, 0)
        t = CATransform3DScale(t, eyeBoost, eyeBoost, 1)
        eyes.transform = t
        face.transform = CATransform3DMakeTranslation(ex * 0.35, ey * 0.35, 0)
    }

    // MARK: live mic level

    func setLevel(_ v: Float) {
        guard mood == .listening else { return }
        let k = CGFloat(max(0, min(1, v)))
        CATransaction.begin()
        CATransaction.setAnimationDuration(0.09)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(name: .linear))
        ring.transform = CATransform3DMakeScale(1 + 0.16 * k, 1 + 0.16 * k, 1)
        ring.opacity = Float(0.35 + 0.6 * k)
        mouth.path = MascotPaths.Mouth.open(k).path(center: mouthCenter)
        CATransaction.commit()
    }

    // MARK: one-shots

    func hop(height: CGFloat = 9) {
        let y = CAKeyframeAnimation(keyPath: "position.y")
        y.values = [0, height, 0, height * 0.25, 0]
        y.keyTimes = [0, 0.35, 0.65, 0.82, 1]
        y.isAdditive = true
        y.duration = 0.5
        y.timingFunctions = [CAMediaTimingFunction(name: .easeOut), CAMediaTimingFunction(name: .easeIn),
                             CAMediaTimingFunction(name: .easeOut), CAMediaTimingFunction(name: .easeIn)]
        bounce.add(y, forKey: "hop")
    }

    private func celebrate() {
        let y = CAKeyframeAnimation(keyPath: "position.y")
        y.values = [0, -1, 16, 0, 5, 0]
        y.keyTimes = [0, 0.12, 0.42, 0.68, 0.84, 1]
        y.isAdditive = true
        let sx = CAKeyframeAnimation(keyPath: "transform.scale.x")
        sx.values = [1, 1.12, 0.92, 1.1, 0.97, 1]
        sx.keyTimes = y.keyTimes
        let sy = CAKeyframeAnimation(keyPath: "transform.scale.y")
        sy.values = [1, 0.86, 1.1, 0.88, 1.03, 1]
        sy.keyTimes = y.keyTimes
        let g = CAAnimationGroup()
        g.animations = [y, sx, sy]
        g.duration = 0.75
        bounce.add(g, forKey: "celebrate")

        let now = CACurrentMediaTime()
        for (i, sp) in sparkles.enumerated() {
            let s = CAKeyframeAnimation(keyPath: "transform.scale")
            s.values = [0.0, 1.25, 0.0]
            s.keyTimes = [0, 0.4, 1]
            let r = CABasicAnimation(keyPath: "transform.rotation.z")
            r.fromValue = 0
            r.toValue = Double.pi / 2
            let o = CAKeyframeAnimation(keyPath: "opacity")
            o.values = [0, 1, 0]
            o.keyTimes = [0, 0.3, 1]
            let g = CAAnimationGroup()
            g.animations = [s, r, o]
            g.duration = 0.8
            g.beginTime = now + 0.12 + Double(i) * 0.07
            g.fillMode = .backwards
            sp.add(g, forKey: "sparkle")
        }
    }

    private func popQuestion() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        question.opacity = 1
        CATransaction.commit()
        let s = CASpringAnimation(keyPath: "transform.scale")
        s.fromValue = 0.2
        s.toValue = 1
        s.damping = 9
        s.stiffness = 260
        s.duration = s.settlingDuration
        let o = CABasicAnimation(keyPath: "opacity")
        o.fromValue = 0
        o.toValue = 1
        o.duration = 0.12
        let wob = CAKeyframeAnimation(keyPath: "transform.rotation.z")
        wob.values = [0, 0.25, -0.18, 0.1, 0]
        wob.duration = 0.9
        wob.beginTime = CACurrentMediaTime() + 0.25
        question.add(s, forKey: "pop")
        question.add(o, forKey: "fade")
        question.add(wob, forKey: "wobble")
    }

    private func hideQuestion() {
        guard question.opacity > 0 else { return }
        CATransaction.begin()
        CATransaction.setAnimationDuration(0.2)
        question.opacity = 0
        CATransaction.commit()
    }

    private func startZees() {
        let now = CACurrentMediaTime()
        for (i, z) in zees.enumerated() {
            guard z.animation(forKey: "float") == nil else { continue }
            let y = CABasicAnimation(keyPath: "position.y")
            y.fromValue = 0
            y.toValue = 24
            y.isAdditive = true
            let x = CABasicAnimation(keyPath: "position.x")
            x.fromValue = 0
            x.toValue = 10
            x.isAdditive = true
            let o = CAKeyframeAnimation(keyPath: "opacity")
            o.values = [0, 0.9, 0]
            o.keyTimes = [0, 0.3, 1]
            let s = CABasicAnimation(keyPath: "transform.scale")
            s.fromValue = 0.6
            s.toValue = 1.1
            let g = CAAnimationGroup()
            g.animations = [y, x, o, s]
            g.duration = 2.7
            g.repeatCount = .infinity
            g.beginTime = now + Double(i) * 0.9
            z.add(g, forKey: "float")
        }
    }

    private func stopZees() {
        zees.forEach { $0.removeAnimation(forKey: "float") }
    }

    // MARK: drag + click

    private var dragStartMouse: NSPoint?
    private var dragStartOrigin: NSPoint?
    private var dragged = false

    override func hitTest(_ point: NSPoint) -> NSView? {
        let p = convert(point, from: superview)
        let body = CGRect(x: Self.bodyBase.x - Self.bodySize.width / 2 - 6, y: Self.bodyBase.y - 6,
                          width: Self.bodySize.width + 12, height: Self.bodySize.height + 16)
        return body.contains(p) ? self : nil
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
        w.setFrameOrigin(NSPoint(x: o0.x + dx, y: o0.y + dy))
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
