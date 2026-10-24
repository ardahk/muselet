import AppKit
import QuartzCore

/// Idle life: randomized blinks (3-6 s), an occasional look-around, and the
/// hover perk-up. Timers are one-shot work items rescheduled after each run.
extension MascotView {
    // MARK: blinks

    func scheduleBlink() {
        blinkWork?.cancel()
        guard mood != .sleeping else { return }
        let w = DispatchWorkItem { [weak self] in
            guard let self else { return }
            self.blinkOnce(double: Double.random(in: 0..<1) < 0.15)
            self.scheduleBlink()
        }
        blinkWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + Double.random(in: 3...6), execute: w)
    }

    func blinkOnce(double: Bool = false) {
        guard mood != .sleeping, window?.isVisible ?? false else { return }
        let b = CAKeyframeAnimation(keyPath: "transform.scale.y")
        if double {
            b.values = [1, 0.1, 1, 0.1, 1]
            b.keyTimes = [0, 0.22, 0.5, 0.72, 1]
            b.duration = 0.38
        } else {
            b.values = [1, 0.1, 1]
            b.keyTimes = [0, 0.45, 1]
            b.duration = 0.17
        }
        for e in [eyeL, eyeR] { e.add(b, forKey: "blink") }
    }

    // MARK: look-around

    func scheduleLookAround() {
        lookAroundWork?.cancel()
        let w = DispatchWorkItem { [weak self] in
            guard let self else { return }
            if self.mood == .idle, !self.hovered, !self.reduceMotion, self.window?.isVisible ?? false {
                self.lookAround()
            }
            self.scheduleLookAround()
        }
        lookAroundWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + Double.random(in: 8...15), execute: w)
    }

    private func lookAround() {
        let options: [CGVector] = [
            CGVector(dx: -0.9, dy: 0.1), CGVector(dx: 0.9, dy: 0.1), CGVector(dx: -0.6, dy: 0.6),
            CGVector(dx: 0.6, dy: 0.6), CGVector(dx: 0, dy: -0.4),
        ]
        guard let v = options.randomElement() else { return }
        lookingAround = true
        lookVector = v
        animateLook(duration: 0.35)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.1) { [weak self] in
            guard let self, self.lookingAround, self.mood == .idle else { return }
            self.lookingAround = false
            self.lookVector = .zero
            self.animateLook(duration: 0.4)
        }
    }

    private func animateLook(duration: CFTimeInterval) {
        CATransaction.begin()
        CATransaction.setAnimationDuration(duration)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(name: .easeInEaseOut))
        applyLook()
        CATransaction.commit()
    }

    // MARK: hover perk

    func setHovered(_ h: Bool) {
        guard h != hovered else { return }
        hovered = h
        CATransaction.begin()
        CATransaction.setAnimationDuration(reduceMotion ? 0.15 : 0.3)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(controlPoints: 0.3, 1.45, 0.55, 1))
        applyPerk()
        applyLook()
        CATransaction.commit()
        if h, mood == .idle { hop(height: 4) }
    }

    /// Ears droop at rest, stand up when listening or hovered; the cap lifts
    /// while listening; hover scales the body up a touch. Call inside a CATransaction.
    func applyPerk() {
        let awake = mood != .sleeping
        let alert = mood == .listening || (hovered && awake)
        let earAngle: CGFloat = awake ? (alert ? 0.12 : 0.5) : 0.85
        earL.transform = CATransform3DMakeRotation(earAngle, 0, 0, 1)
        earR.transform = CATransform3DMakeRotation(-earAngle, 0, 0, 1)
        capGroup.transform = CATransform3DMakeTranslation(0, mood == .listening ? 2.5 : 0, 0)
        let k: CGFloat = (hovered && awake && !reduceMotion) ? 1.06 : 1
        perk.transform = CATransform3DMakeScale(k, k, 1)
    }
}
