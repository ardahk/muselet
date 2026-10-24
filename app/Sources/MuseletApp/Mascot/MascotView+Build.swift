import AppKit
import QuartzCore

/// Layer tree. Body coordinates: bottom-left origin, y up, `bodySize`.
extension MascotView {
    func build() {
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

        // Listening: soft expanding pulse + mic-level ring
        let rr: CGFloat = 37
        let circle = CGPath(ellipseIn: CGRect(x: -rr, y: -rr, width: rr * 2, height: rr * 2), transform: nil)
        let center = CGPoint(x: Self.bodyBase.x, y: Self.bodyBase.y + s.height / 2)
        pulse.path = circle
        pulse.position = center
        pulse.fillColor = nil
        pulse.strokeColor = Brand.tint.withAlphaComponent(0.6).cgColor
        pulse.lineWidth = 1.5
        pulse.opacity = 0
        root.addSublayer(pulse)
        ring.path = circle
        ring.position = center
        ring.fillColor = Brand.tint.withAlphaComponent(0.07).cgColor
        ring.strokeColor = Brand.tint.cgColor
        ring.lineWidth = 2.2
        ring.opacity = 0
        root.addSublayer(ring)

        // Transform stack: lean (rotation) > perk (hover) > bounce (hop) > breath (idle scale)
        for l in [lean, perk, bounce, breath] {
            l.bounds = bodyRect
            l.anchorPoint = CGPoint(x: 0.5, y: 0)
        }
        lean.position = Self.bodyBase
        for l in [perk, bounce, breath] { l.position = CGPoint(x: s.width / 2, y: 0) }
        root.addSublayer(lean)
        lean.addSublayer(perk)
        perk.addSublayer(bounce)
        bounce.addSublayer(breath)

        // Wire-loop "ears" behind the dome (their base hides under the body)
        let ear = CGMutablePath()
        ear.move(to: .zero)
        ear.addCurve(to: CGPoint(x: 0, y: 11), control1: CGPoint(x: -5.5, y: 3), control2: CGPoint(x: -4.5, y: 11))
        ear.addCurve(to: .zero, control1: CGPoint(x: 4.5, y: 11), control2: CGPoint(x: 5.5, y: 3))
        for (e, x) in [(earL, CGFloat(13)), (earR, s.width - 13)] {
            e.path = ear
            e.bounds = CGRect(x: -6, y: 0, width: 12, height: 12)
            e.anchorPoint = CGPoint(x: 0.5, y: 0)
            e.position = CGPoint(x: x, y: s.height - 9)
            e.fillColor = Brand.corkLight.withAlphaComponent(0.55).cgColor
            e.strokeColor = Brand.wireDark.cgColor
            e.lineWidth = 1.5
            e.lineJoin = .round
            breath.addSublayer(e)
        }

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
        let specks: [(CGFloat, CGFloat, CGFloat)] = [
            (9, 38, 1.1), (47, 41, 1.0), (6, 14, 1.2), (50, 18, 1.0), (14, 6, 0.9),
            (42, 7, 1.1), (28, 47, 0.8), (36, 44, 0.7), (21, 44, 0.9), (52, 30, 0.8), (4, 27, 0.8),
        ]
        for (x, y, r) in specks { sp.addEllipse(in: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)) }
        speck.path = sp
        speck.fillColor = Brand.speck.withAlphaComponent(0.28).cgColor
        bodyFill.addSublayer(speck)

        // Sheen on the dome
        let sheen = CAShapeLayer()
        sheen.path = CGPath(ellipseIn: CGRect(x: 10, y: 36, width: 16, height: 10), transform: nil)
        sheen.fillColor = NSColor.white.withAlphaComponent(0.38).cgColor
        sheen.setAffineTransform(CGAffineTransform(rotationAngle: 0.35))
        bodyFill.addSublayer(sheen)

        // Wire belt near the base
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

        // Metal cap (plaque) + knob, grouped so they can lift together
        capGroup.frame = bodyRect
        breath.addSublayer(capGroup)
        cap.frame = CGRect(x: s.width / 2 - 12, y: s.height - 3, width: 24, height: 7)
        cap.cornerRadius = 3.5
        cap.colors = [Brand.wireLight.cgColor, Brand.wireDark.cgColor]
        cap.startPoint = CGPoint(x: 0.5, y: 1)
        cap.endPoint = CGPoint(x: 0.5, y: 0)
        cap.borderColor = Brand.wireDark.withAlphaComponent(0.8).cgColor
        cap.borderWidth = 0.6
        capGroup.addSublayer(cap)
        capKnob.frame = CGRect(x: s.width / 2 - 3, y: s.height + 3, width: 6, height: 4.5)
        capKnob.cornerRadius = 2.25
        capKnob.colors = cap.colors
        capKnob.startPoint = cap.startPoint
        capKnob.endPoint = cap.endPoint
        capGroup.addSublayer(capKnob)

        // Face group (moves slightly with gaze)
        face.frame = bodyRect
        breath.addSublayer(face)

        for (c, x) in [(cheekL, CGFloat(11.5)), (cheekR, s.width - 11.5)] {
            c.path = CGPath(ellipseIn: CGRect(x: -5, y: -2.8, width: 10, height: 5.6), transform: nil)
            c.position = CGPoint(x: x, y: 20.5)
            c.fillColor = Brand.cheek.withAlphaComponent(0.36).cgColor
            face.addSublayer(c)
        }

        // Big glossy eyes (two glints each)
        eyes.frame = bodyRect
        face.addSublayer(eyes)
        for (e, x) in [(eyeL, CGFloat(19.5)), (eyeR, s.width - 19.5)] {
            e.bounds = CGRect(x: 0, y: 0, width: 8.2, height: 11.4)
            e.path = CGPath(roundedRect: e.bounds, cornerWidth: 4.1, cornerHeight: 4.1, transform: nil)
            e.position = CGPoint(x: x, y: 29.5)
            e.fillColor = Brand.ink.cgColor
            let glint = CAShapeLayer()
            glint.path = CGPath(ellipseIn: CGRect(x: 4.3, y: 6.6, width: 2.9, height: 2.9), transform: nil)
            glint.fillColor = NSColor.white.withAlphaComponent(0.95).cgColor
            e.addSublayer(glint)
            let glint2 = CAShapeLayer()
            glint2.path = CGPath(ellipseIn: CGRect(x: 1.6, y: 2.2, width: 1.5, height: 1.5), transform: nil)
            glint2.fillColor = NSColor.white.withAlphaComponent(0.7).cgColor
            e.addSublayer(glint2)
            eyes.addSublayer(e)
        }

        mouth.path = MascotPaths.Mouth.smile.path(center: mouthCenter)
        mouth.fillColor = Brand.ink.cgColor
        mouth.strokeColor = Brand.ink.cgColor
        mouth.lineWidth = 1.6
        mouth.lineJoin = .round
        mouth.lineCap = .round
        face.addSublayer(mouth)

        // Thinking: three dots in a row above the head
        dots.bounds = CGRect(x: -14, y: -5, width: 28, height: 10)
        dots.position = CGPoint(x: Self.bodyBase.x, y: Self.bodyBase.y + s.height + 17)
        dots.opacity = 0
        for i in 0..<3 {
            let d = CAShapeLayer()
            let r: CGFloat = 2.7
            d.path = CGPath(ellipseIn: CGRect(x: -r, y: -r, width: r * 2, height: r * 2), transform: nil)
            d.position = CGPoint(x: CGFloat(i - 1) * 8.5, y: 0)
            d.fillColor = Brand.tint.cgColor
            dots.addSublayer(d)
            dotLayers.append(d)
        }
        root.addSublayer(dots)

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
            let l = CAShapeLayer()
            l.path = MascotPaths.sparkle(radius: i % 2 == 0 ? 6.5 : 5)
            l.position = p
            l.fillColor = (i % 2 == 0 ? Brand.tint : NSColor(srgbRed: 1, green: 0.85, blue: 0.4, alpha: 1)).cgColor
            l.opacity = 0
            root.addSublayer(l)
            sparkles.append(l)
        }

        // z, z, Z for sleeping
        for i in 0..<3 {
            let z = CATextLayer()
            z.string = i == 2 ? "Z" : "z"
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
}
