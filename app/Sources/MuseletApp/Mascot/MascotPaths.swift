import CoreGraphics
import Foundation

/// Procedural geometry for the cork creature (bottom-left origin, y up).
enum MascotPaths {
    /// Gumdrop/cork body: flat-ish rounded bottom, domed top.
    static func bodyPath(width w: CGFloat, height h: CGFloat,
                         bottomRadius rb: CGFloat, topRadius rt: CGFloat) -> CGPath {
        let p = CGMutablePath()
        p.move(to: CGPoint(x: rb, y: 0))
        p.addLine(to: CGPoint(x: w - rb, y: 0))
        p.addArc(tangent1End: CGPoint(x: w, y: 0), tangent2End: CGPoint(x: w, y: rb), radius: rb)
        p.addLine(to: CGPoint(x: w, y: h - rt))
        p.addArc(tangent1End: CGPoint(x: w, y: h), tangent2End: CGPoint(x: w - rt, y: h), radius: rt)
        p.addLine(to: CGPoint(x: rt, y: h))
        p.addArc(tangent1End: CGPoint(x: 0, y: h), tangent2End: CGPoint(x: 0, y: h - rt), radius: rt)
        p.addLine(to: CGPoint(x: 0, y: rb))
        p.addArc(tangent1End: CGPoint(x: 0, y: 0), tangent2End: CGPoint(x: rb, y: 0), radius: rb)
        p.closeSubpath()
        return p
    }

    /// Mouth shape with a fixed topology (two cubic lips) so CA can
    /// interpolate between expressions.
    struct Mouth {
        var width: CGFloat
        var leftLift: CGFloat
        var rightLift: CGFloat
        var upper: CGFloat     // + bulges up
        var lower: CGFloat     // - bulges down

        static let smile = Mouth(width: 11, leftLift: 1.6, rightLift: 1.6, upper: -1.6, lower: -3.6)
        static let grin = Mouth(width: 14, leftLift: 2.2, rightLift: 2.2, upper: -0.6, lower: -7.5)
        static let flat = Mouth(width: 7, leftLift: 0, rightLift: 0, upper: 0.2, lower: -1.0)
        static let wavy = Mouth(width: 9, leftLift: 1.2, rightLift: -1.0, upper: 0.6, lower: -1.4)
        static let sleepy = Mouth(width: 4.5, leftLift: 0, rightLift: 0, upper: 1.4, lower: -1.6)
        static let attentive = Mouth(width: 7, leftLift: 0.6, rightLift: 0.6, upper: 1.2, lower: -2.6)

        static func open(_ a: CGFloat) -> Mouth {
            let k = max(0, min(1, a))
            return Mouth(width: 6.5 + 2.5 * k, leftLift: 0.4, rightLift: 0.4,
                         upper: 1.2 + 2.6 * k, lower: -2.4 - 4.6 * k)
        }

        func path(center c: CGPoint) -> CGPath {
            let l = CGPoint(x: c.x - width / 2, y: c.y + leftLift)
            let r = CGPoint(x: c.x + width / 2, y: c.y + rightLift)
            let p = CGMutablePath()
            p.move(to: l)
            p.addCurve(to: r,
                       control1: CGPoint(x: l.x + width * 0.25, y: c.y + upper),
                       control2: CGPoint(x: r.x - width * 0.25, y: c.y + upper))
            p.addCurve(to: l,
                       control1: CGPoint(x: r.x - width * 0.2, y: c.y + lower),
                       control2: CGPoint(x: l.x + width * 0.2, y: c.y + lower))
            p.closeSubpath()
            return p
        }
    }

    /// Four-point sparkle star centered at origin.
    static func sparkle(radius r: CGFloat) -> CGPath {
        let p = CGMutablePath()
        let k = r * 0.28
        p.move(to: CGPoint(x: 0, y: r))
        p.addQuadCurve(to: CGPoint(x: r, y: 0), control: CGPoint(x: k, y: k))
        p.addQuadCurve(to: CGPoint(x: 0, y: -r), control: CGPoint(x: k, y: -k))
        p.addQuadCurve(to: CGPoint(x: -r, y: 0), control: CGPoint(x: -k, y: -k))
        p.addQuadCurve(to: CGPoint(x: 0, y: r), control: CGPoint(x: -k, y: k))
        p.closeSubpath()
        return p
    }
}
