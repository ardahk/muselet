import AppKit
import QuartzCore

/// Mood -> pose mapping, gaze and the live mic level.
extension MascotView {
    func apply(mood m: MascotMood, animated: Bool = true) {
        let previous = mood
        mood = m
        let rm = reduceMotion
        CATransaction.begin()
        CATransaction.setAnimationDuration(animated ? (rm ? 0.2 : 0.38) : 0)
        CATransaction.setAnimationTimingFunction(rm ? CAMediaTimingFunction(name: .easeInEaseOut)
                                                    : CAMediaTimingFunction(controlPoints: 0.3, 1.45, 0.55, 1))

        // Breathing (restarted only when its tempo changes; none with Reduce Motion)
        let kind = rm ? 3 : (m == .sleeping ? 2 : (m == .listening ? 1 : 0))
        if kind != breathKind || (!rm && breath.animation(forKey: "breath") == nil) {
            breathKind = kind
            breath.removeAnimation(forKey: "breath")
            if !rm { breath.add(breathing(sleeping: kind == 2, fast: kind == 1), forKey: "breath") }
        }

        // Tail: slow sway at rest, swish while acting; still while listening, asleep or with Reduce Motion
        let tk = (rm || m == .sleeping || m == .listening) ? 2 : (m == .acting ? 1 : 0)
        if tk != tailKind || (tk != 2 && tail.animation(forKey: "sway") == nil) {
            tailKind = tk
            tail.removeAnimation(forKey: "sway")
            if tk != 2 { tail.add(tailSway(fast: tk == 1), forKey: "sway") }
        }

        // Eyes: open and glossy, or closed lids ("^ ^" on success, bowed while asleep)
        let closed = m == .success || m == .sleeping
        for e in [eyeL, eyeR] {
            if m == .sleeping { e.removeAnimation(forKey: "blink") }
            e.transform = CATransform3DIdentity
            e.opacity = closed ? 0 : 1
        }
        let lid: MascotPaths.Lid = m == .sleeping ? .asleep : .happy
        lidL.path = MascotPaths.lid(lid, center: MascotPaths.Eye.leftCenter)
        lidR.path = MascotPaths.lid(lid, center: MascotPaths.Eye.rightCenter)
        [lidL, lidR].forEach { $0.opacity = closed ? 1 : 0 }
        switch m {
        case .thinking: lookVector = CGVector(dx: -0.55, dy: 0.85)  // eyes up-left
        case .listening: lookVector = CGVector(dx: 0, dy: 0.5)      // attentive, eyes up a bit
        case .acting: break                                          // set by look(towardCG:)
        case .sleeping: lookVector = CGVector(dx: 0, dy: -0.3)
        default: lookVector = .zero
        }
        lookingAround = false
        applyLook()

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
        mouth.opacity = 1
        setMouthOpen(m == .success ? 0.6 : 0)

        // Cheeks glow on success
        let cheekAlpha: CGFloat = m == .success ? 0.62 : (m == .sleeping ? 0.45 : 0.36)
        [cheekL, cheekR].forEach { $0.fillColor = MascotPalette.blush.withAlphaComponent(cheekAlpha).cgColor }

        // Lean / tilt
        let tilt: CGFloat
        switch m {
        case .confused: tilt = 0.2
        case .acting: tilt = -lookVector.dx * 0.14
        case .sleeping: tilt = 0.06
        default: tilt = 0
        }
        lean.transform = CATransform3DMakeRotation(tilt, 0, 0, 1)

        // Ears, tail pose, paw, hover perk / sleeping curl
        applyPerk()

        // Accessories
        ring.opacity = m == .listening ? 0.55 : 0
        ring.transform = CATransform3DIdentity
        CATransaction.commit()
        refreshDots()

        if m == .listening && !rm { startPulse() } else { stopPulse() }
        if m == .confused { popQuestion() } else { hideQuestion() }
        if m == .sleeping { startZees() } else { stopZees() }
        if m == .success && previous != .success { celebrate() }
        if previous == .sleeping && m != .sleeping {
            scheduleBlink()
            if hovered { hop(height: 4) }                       // woken by hover
        }
    }

    /// One breath = 1.00 -> 1.03 -> 1.00 over 3 s at rest (autoreversed half-cycles).
    func breathing(sleeping: Bool, fast: Bool) -> CAAnimation {
        let y = CABasicAnimation(keyPath: "transform.scale.y")
        y.fromValue = 1.0
        y.toValue = sleeping ? 1.04 : 1.03
        let x = CABasicAnimation(keyPath: "transform.scale.x")
        x.fromValue = 1.0
        x.toValue = sleeping ? 1.02 : 1.015
        let g = CAAnimationGroup()
        g.animations = [y, x]
        g.duration = sleeping ? 2.2 : (fast ? 0.8 : 1.5)
        g.autoreverses = true
        g.repeatCount = .infinity
        g.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        return g
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
        lookingAround = false
        CATransaction.begin()
        CATransaction.setAnimationDuration(reduceMotion ? 0.15 : 0.3)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(controlPoints: 0.3, 1.4, 0.55, 1))
        applyLook()
        if mood == .acting {
            lean.transform = CATransform3DMakeRotation(-lookVector.dx * 0.14, 0, 0, 1)
        }
        CATransaction.commit()
    }

    var eyeBoost: CGFloat {
        if mood == .sleeping { return 1 }
        return (mood == .listening || mood == .success || hovered) ? 1.12 : 1
    }

    /// Call inside a CATransaction.
    func applyLook() {
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
        let grow: CGFloat = reduceMotion ? 0 : 0.16 * k
        ring.transform = CATransform3DMakeScale(1 + grow, 1 + grow, 1)
        ring.opacity = Float(0.35 + 0.6 * k)
        setMouthOpen(k)
        mouth.opacity = Float(1 - 0.6 * k)
        CATransaction.commit()
    }

    /// The small "o" under the "w": 0 = closed, 1 = fully open. Call inside a CATransaction.
    func setMouthOpen(_ k: CGFloat) {
        let s = max(0.01, min(1, k))
        mouthOpen.transform = CATransform3DMakeScale(s, s, 1)
        mouthOpen.opacity = k > 0.05 ? 1 : 0
    }
}
