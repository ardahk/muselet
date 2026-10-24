import AppKit
import QuartzCore

/// One-shot and looping accessories. Every motion has a Reduce Motion
/// variant (fades instead of hops / spins / floats).
extension MascotView {
    func hop(height: CGFloat = 9) {
        guard !reduceMotion else { return }
        let y = CAKeyframeAnimation(keyPath: "position.y")
        y.values = [0, height, 0, height * 0.25, 0]
        y.keyTimes = [0, 0.35, 0.65, 0.82, 1]
        y.isAdditive = true
        y.duration = 0.5
        y.timingFunctions = [CAMediaTimingFunction(name: .easeOut), CAMediaTimingFunction(name: .easeIn),
                             CAMediaTimingFunction(name: .easeOut), CAMediaTimingFunction(name: .easeIn)]
        bounce.add(y, forKey: "hop")
    }

    func celebrate() {
        let rm = reduceMotion
        if !rm {
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
        }

        let now = CACurrentMediaTime()
        for (i, sp) in sparkles.enumerated() {
            let o = CAKeyframeAnimation(keyPath: "opacity")
            o.values = [0, 1, 0]
            o.keyTimes = [0, 0.3, 1]
            var parts: [CAAnimation] = [o]
            if !rm {
                let s = CAKeyframeAnimation(keyPath: "transform.scale")
                s.values = [0.0, 1.25, 0.0]
                s.keyTimes = [0, 0.4, 1]
                let r = CABasicAnimation(keyPath: "transform.rotation.z")
                r.fromValue = 0
                r.toValue = Double.pi / 2
                parts += [s, r]
            }
            let g = CAAnimationGroup()
            g.animations = parts
            g.duration = rm ? 1.0 : 0.8
            g.beginTime = now + 0.12 + Double(i) * 0.07
            g.fillMode = .backwards
            sp.add(g, forKey: "sparkle")
        }
    }

    func popQuestion() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        question.opacity = 1
        CATransaction.commit()
        let o = CABasicAnimation(keyPath: "opacity")
        o.fromValue = 0
        o.toValue = 1
        o.duration = reduceMotion ? 0.2 : 0.12
        question.add(o, forKey: "fade")
        guard !reduceMotion else { return }
        let s = CASpringAnimation(keyPath: "transform.scale")
        s.fromValue = 0.2
        s.toValue = 1
        s.damping = 9
        s.stiffness = 260
        s.duration = s.settlingDuration
        let wob = CAKeyframeAnimation(keyPath: "transform.rotation.z")
        wob.values = [0, 0.25, -0.18, 0.1, 0]
        wob.duration = 0.9
        wob.beginTime = CACurrentMediaTime() + 0.25
        question.add(s, forKey: "pop")
        question.add(wob, forKey: "wobble")
    }

    func hideQuestion() {
        guard question.opacity > 0 else { return }
        CATransaction.begin()
        CATransaction.setAnimationDuration(0.2)
        question.opacity = 0
        CATransaction.commit()
    }

    // MARK: listening pulse

    func startPulse() {
        guard pulse.animation(forKey: "pulse") == nil else { return }
        let s = CABasicAnimation(keyPath: "transform.scale")
        s.fromValue = 0.92
        s.toValue = 1.38
        let o = CABasicAnimation(keyPath: "opacity")
        o.fromValue = 0.6
        o.toValue = 0
        let g = CAAnimationGroup()
        g.animations = [s, o]
        g.duration = 1.5
        g.repeatCount = .infinity
        g.timingFunction = CAMediaTimingFunction(name: .easeOut)
        pulse.add(g, forKey: "pulse")
    }

    func stopPulse() {
        pulse.removeAnimation(forKey: "pulse")
    }

    // MARK: thinking dots

    func startDots() {
        let now = CACurrentMediaTime()
        for (i, d) in dotLayers.enumerated() {
            guard d.animation(forKey: "bob") == nil else { continue }
            let a: CAAnimation
            if reduceMotion {
                let o = CAKeyframeAnimation(keyPath: "opacity")
                o.values = [0.35, 1, 0.35]
                o.keyTimes = [0, 0.5, 1]
                o.duration = 1.2
                a = o
            } else {
                let y = CAKeyframeAnimation(keyPath: "position.y")
                y.values = [0, 4.5, 0, 0]
                y.keyTimes = [0, 0.3, 0.6, 1]
                y.isAdditive = true
                y.duration = 0.95
                y.timingFunctions = [CAMediaTimingFunction(name: .easeOut), CAMediaTimingFunction(name: .easeIn),
                                     CAMediaTimingFunction(name: .linear)]
                a = y
            }
            a.repeatCount = .infinity
            a.beginTime = now + Double(i) * 0.15
            d.add(a, forKey: "bob")
        }
    }

    func stopDots() {
        dotLayers.forEach { $0.removeAnimation(forKey: "bob") }
    }

    // MARK: sleeping z's

    func startZees() {
        if reduceMotion {
            CATransaction.begin()
            CATransaction.setDisableActions(true)
            for (i, z) in zees.enumerated() {
                z.removeAnimation(forKey: "float")
                z.opacity = i == 1 ? 0 : 0.8
                z.transform = CATransform3DMakeTranslation(CGFloat(i) * 5, CGFloat(i) * 8, 0)
            }
            CATransaction.commit()
            return
        }
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

    func stopZees() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        for z in zees {
            z.removeAnimation(forKey: "float")
            z.opacity = 0
            z.transform = CATransform3DIdentity
        }
        CATransaction.commit()
    }
}
