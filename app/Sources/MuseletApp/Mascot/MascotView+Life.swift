import AppKit
import QuartzCore

/// Idle life: randomized blinks (3-6 s), ear twitches (6-12 s), an occasional
/// look-around (8-15 s), and the hover perk-up. Timers are one-shot work items
/// rescheduled after each run.
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

    // MARK: ear twitch

    func scheduleEarTwitch() {
        earTwitchWork?.cancel()
        let w = DispatchWorkItem { [weak self] in
            guard let self else { return }
            if self.mood == .idle, !self.hovered, !self.reduceMotion, self.window?.isVisible ?? false {
                self.twitchEar()
            }
            self.scheduleEarTwitch()
        }
        earTwitchWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + Double.random(in: 6...12), execute: w)
    }

    private func twitchEar() {
        let left = Bool.random()
        let a = MascotPaths.Ear.twitch * (left ? 1 : -1)   // + = tip outward for the left ear
        let t = CAKeyframeAnimation(keyPath: "transform.rotation.z")
        t.values = [0, a, -a * 0.25, a * 0.45, 0]
        t.keyTimes = [0, 0.3, 0.55, 0.78, 1]
        t.duration = 0.34
        t.isAdditive = true
        (left ? earL : earR).add(t, forKey: "twitch")
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
        if h, mood != .sleeping, mood != .listening { flickTail() }
    }

    /// Pose of ears, tail and paws plus the hover perk / sleeping curl.
    /// Call inside a CATransaction.
    func applyPerk() {
        let awake = mood != .sleeping
        earL.transform = earTransform(left: true)
        earR.transform = earTransform(left: false)

        let k: CGFloat = (hovered && awake && !reduceMotion) ? 1.06 : 1
        perk.transform = awake
            ? CATransform3DMakeScale(k, k, 1)
            : CATransform3DMakeScale(MascotPaths.Body.curlWidth, MascotPaths.Body.curlHeight, 1)

        let up = mood == .listening || (hovered && awake)
        let tailPath = MascotPaths.tail(up ? .up : .rest)
        tailStrokes.forEach { $0.path = tailPath }
        tail.opacity = awake ? 1 : 0
        tailWrap.opacity = awake ? 0 : 1

        let chin = mood == .thinking
        pawR.position = chin ? MascotPaths.Paw.chinCenter : MascotPaths.Paw.rightCenter
        pawR.transform = chin ? CATransform3DMakeRotation(MascotPaths.Paw.chinTilt, 0, 0, 1) : CATransform3DIdentity
    }

    /// Rest: tilted out a little. Hover: perked. Listening: fully up and turned
    /// toward the screen centre. Confused: the left ear folds down. Asleep: flat.
    func earTransform(left: Bool) -> CATransform3D {
        typealias E = MascotPaths.Ear
        var tilt = E.restTilt, stretch: CGFloat = 1, turn: CGFloat = 0
        if mood == .sleeping {
            tilt = E.sleepTilt
            stretch = E.sleepStretch
        } else if mood == .listening {
            tilt = E.listenTilt
            stretch = E.listenStretch
            turn = -screenCentreDX * E.listenTurn             // + rotation = tip to the left
        } else if mood == .confused && left {
            tilt = E.droopTilt
            stretch = E.droopStretch
        } else if hovered {
            tilt = E.perkTilt
            stretch = E.perkStretch
        }
        let angle = (left ? tilt : -tilt) + turn
        return CATransform3DScale(CATransform3DMakeRotation(angle, 0, 0, 1), 1, stretch, 1)
    }

    /// -1...1: where the screen centre is horizontally relative to the mascot (+ = to the right).
    var screenCentreDX: CGFloat {
        guard let w = window, let s = w.screen else { return 0 }
        let half = max(1, s.frame.width / 2)
        return max(-1, min(1, (s.frame.midX - w.frame.midX) / half))
    }
}
