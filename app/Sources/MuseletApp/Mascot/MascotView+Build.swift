import AppKit
import QuartzCore

private typealias Geo = MascotPaths
private typealias Ink = MascotPalette

/// Layer tree. Body coordinates: bottom-left origin, y up, `bodySize`.
/// Geometry comes from `MascotPaths`, colours from `MascotPalette`.
extension MascotView {
    func build() {
        let s = Self.bodySize
        let bodyRect = CGRect(origin: .zero, size: s)
        let bodyPath = Geo.body()
        root.frame = CGRect(origin: .zero, size: Self.size)

        // Ground shadow
        groundShadow.path = CGPath(ellipseIn: CGRect(x: -23, y: -3.5, width: 46, height: 7), transform: nil)
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

        // Transform stack: lean (rotation) > perk (hover / curl) > bounce (hop) > breath (idle scale)
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

        // Tail, curling up around the right side (behind the body)
        tail.position = Geo.Tail.base
        breath.addSublayer(tail)
        tailStrokes = makeTailStrokes(in: tail)
        tailStrokes.forEach { $0.path = Geo.tail(.rest) }

        // Ears: ginger with pink insides; the base tucks under the head
        for (e, base) in [(earL, Geo.Ear.leftBase), (earR, Geo.Ear.rightBase)] {
            pin(e, bounds: Geo.Ear.bounds, at: base)
            e.path = Geo.ear()
            e.fillColor = Ink.ginger.cgColor
            e.strokeColor = Ink.outline.cgColor
            e.lineWidth = Geo.outlineWidth
            e.lineJoin = .round
            let inner = CAShapeLayer()
            inner.path = Geo.innerEar()
            inner.fillColor = Ink.innerEar.cgColor
            e.addSublayer(inner)
            breath.addSublayer(e)
        }

        // Head-body blob: cream gradient masked by the body path
        bodyFill.frame = bodyRect
        bodyFill.colors = [Ink.creamLight.cgColor, Ink.cream.cgColor, Ink.creamShade.cgColor]
        bodyFill.locations = [0, 0.5, 1]
        bodyFill.startPoint = CGPoint(x: 0.3, y: 1)
        bodyFill.endPoint = CGPoint(x: 0.7, y: 0)
        bodyMask.path = bodyPath
        bodyFill.mask = bodyMask
        breath.addSublayer(bodyFill)

        let muzzle = CAShapeLayer()
        muzzle.path = Geo.muzzle()
        muzzle.fillColor = Ink.muzzle.cgColor
        bodyFill.addSublayer(muzzle)

        let sheen = CAShapeLayer()
        sheen.path = Geo.sheen()
        sheen.fillColor = Ink.sheen.cgColor
        bodyFill.addSublayer(sheen)

        let crown = CAShapeLayer()
        crown.path = Geo.crownPatch()
        crown.fillColor = Ink.ginger.cgColor
        bodyFill.addSublayer(crown)
        let stripes = CAShapeLayer()
        stripes.path = Geo.crownStripes()
        stripes.fillColor = nil
        stripes.strokeColor = Ink.gingerDark.cgColor
        stripes.lineWidth = Geo.Crown.stripeWidth
        stripes.lineCap = .round
        bodyFill.addSublayer(stripes)

        outline.path = bodyPath
        outline.fillColor = nil
        outline.strokeColor = Ink.outline.cgColor
        outline.lineWidth = Geo.outlineWidth
        breath.addSublayer(outline)

        // Face group (moves slightly with gaze)
        face.frame = bodyRect
        breath.addSublayer(face)

        for (c, p) in [(cheekL, Geo.Face.cheekL), (cheekR, Geo.Face.cheekR)] {
            c.path = Geo.cheek()
            c.position = p
            c.fillColor = Ink.blush.withAlphaComponent(0.36).cgColor
            face.addSublayer(c)
        }

        whiskers.path = Geo.whiskers()
        whiskers.fillColor = nil
        whiskers.strokeColor = Ink.whisker.cgColor
        whiskers.lineWidth = Geo.Whisker.width
        whiskers.lineCap = .round
        face.addSublayer(whiskers)

        // Big glossy eyes (two glints each) + closed-eye lids
        eyes.frame = bodyRect
        face.addSublayer(eyes)
        for (e, c) in [(eyeL, Geo.Eye.leftCenter), (eyeR, Geo.Eye.rightCenter)] {
            pin(e, bounds: Geo.Eye.bounds, at: c)
            e.path = CGPath(ellipseIn: Geo.Eye.bounds, transform: nil)
            e.fillColor = Ink.ink.cgColor
            for (rect, alpha) in Geo.Eye.highlights {
                let glint = CAShapeLayer()
                glint.path = CGPath(ellipseIn: rect, transform: nil)
                glint.fillColor = NSColor.white.withAlphaComponent(alpha).cgColor
                e.addSublayer(glint)
            }
            eyes.addSublayer(e)
        }
        for (l, c) in [(lidL, Geo.Eye.leftCenter), (lidR, Geo.Eye.rightCenter)] {
            l.path = Geo.lid(.happy, center: c)
            l.fillColor = nil
            l.strokeColor = Ink.ink.cgColor
            l.lineWidth = Geo.Eye.lidWidth
            l.lineCap = .round
            l.opacity = 0
            eyes.addSublayer(l)
        }

        // Mouth: small "o" under a stroked "w"; nose on top
        pin(mouthOpen, bounds: Geo.Mouth.openBounds, at: Geo.Mouth.openCenter)
        mouthOpen.path = CGPath(ellipseIn: Geo.Mouth.openBounds, transform: nil)
        mouthOpen.fillColor = Ink.mouthInside.cgColor
        let tongue = CAShapeLayer()
        tongue.path = CGPath(ellipseIn: Geo.Mouth.tongue, transform: nil)
        tongue.fillColor = Ink.tongue.cgColor
        mouthOpen.addSublayer(tongue)
        mouthOpen.transform = CATransform3DMakeScale(0.01, 0.01, 1)
        mouthOpen.opacity = 0
        face.addSublayer(mouthOpen)

        mouth.path = Geo.Mouth.smile.path(center: mouthCenter)
        mouth.fillColor = nil
        mouth.strokeColor = Ink.ink.cgColor
        mouth.lineWidth = Geo.Face.mouthLineWidth
        mouth.lineJoin = .round
        mouth.lineCap = .round
        face.addSublayer(mouth)

        nose.path = Geo.nose()
        nose.fillColor = Ink.nose.cgColor
        nose.strokeColor = Ink.nose.cgColor
        nose.lineWidth = 1
        nose.lineJoin = .round
        face.addSublayer(nose)

        // Paws peeking out at the bottom (in front of the body)
        for (p, c) in [(pawL, Geo.Paw.leftCenter), (pawR, Geo.Paw.rightCenter)] {
            pin(p, bounds: Geo.Paw.bounds, at: c)
            p.path = Geo.paw()
            p.fillColor = Ink.paw.cgColor
            p.strokeColor = Ink.outline.cgColor
            p.lineWidth = Geo.outlineWidth
            let toes = CAShapeLayer()
            toes.path = Geo.toes()
            toes.fillColor = nil
            toes.strokeColor = Ink.toe.cgColor
            toes.lineWidth = Geo.Paw.toeWidth
            toes.lineCap = .round
            p.addSublayer(toes)
            breath.addSublayer(p)
        }

        // Sleeping: tail wrapped over the paws (in front, shown only while asleep)
        tailWrap.frame = bodyRect
        tailWrap.opacity = 0
        breath.addSublayer(tailWrap)
        wrapStrokes = makeTailStrokes(in: tailWrap)
        wrapStrokes.forEach { $0.path = Geo.tailWrap() }

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

    /// Bounds plus an anchor at the local origin, placed at `p`, so the layer
    /// rotates / scales about its pivot (ear base, eye centre, paw centre).
    private func pin(_ l: CALayer, bounds b: CGRect, at p: CGPoint) {
        l.bounds = b
        l.anchorPoint = CGPoint(x: b.width > 0 ? -b.minX / b.width : 0.5,
                                y: b.height > 0 ? -b.minY / b.height : 0.5)
        l.position = p
    }

    /// Outline, fur and ginger tip stroked along one path, so a single path
    /// change re-poses all three.
    private func makeTailStrokes(in parent: CALayer) -> [CAShapeLayer] {
        let specs: [(NSColor, CGFloat, CGFloat)] = [
            (Ink.outline, Geo.Tail.width + 2 * Geo.outlineWidth, 0),
            (Ink.cream, Geo.Tail.width, 0),
            (Ink.ginger, Geo.Tail.width, Geo.Tail.tipStart),
        ]
        return specs.map { color, width, start in
            let l = CAShapeLayer()
            l.fillColor = nil
            l.strokeColor = color.cgColor
            l.lineWidth = width
            l.lineCap = .round
            l.strokeStart = start
            parent.addSublayer(l)
            return l
        }
    }
}
