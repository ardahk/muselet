import CoreGraphics
import Foundation

/// Procedural geometry for the mascot, a round chubby kitten ("Muse").
/// Body coordinates: bottom-left origin, y up, inside `MascotView.bodySize`
/// (56 x 54; the bubble, pill, ghost cursor and hit areas are laid out from that box).
/// Everything species-specific lives here plus `MascotPalette`: a fox, red panda
/// or otter is a new set of constants and colours, not new layer code.
enum MascotPaths {
    static let outlineWidth: CGFloat = 1

    /// One soft head-body blob, slightly wider than tall, sitting on a flat-ish seat.
    enum Body {
        static let width: CGFloat = 56
        static let height: CGFloat = 50
        static let widestY: CGFloat = 22          // height of the widest point
        static let bottomCorner: CGFloat = 8      // smaller = flatter seat
        static let shoulder: CGFloat = 10         // how far below the crown the sides start to round in
        static let crownCorner: CGFloat = 12      // smaller = flatter crown
        static let sheen = CGRect(x: 8, y: 33, width: 13, height: 8)
        /// Sleeping: curled and lowered (scale about the bottom centre).
        static let curlWidth: CGFloat = 1.04
        static let curlHeight: CGFloat = 0.9
    }

    /// Triangular ears with rounded tips. Pivot = base centre (local origin);
    /// the base tucks under the head, which is drawn on top.
    enum Ear {
        static let halfBase: CGFloat = 8
        static let height: CGFloat = 16
        static let tipRadius: CGFloat = 3
        static let tuck: CGFloat = 3
        static let innerScale: CGFloat = 0.62
        static let innerLift: CGFloat = 1.2
        static let leftBase = CGPoint(x: 14, y: 42)
        static let rightBase = CGPoint(x: 42, y: 42)
        static var bounds: CGRect {
            CGRect(x: -halfBase, y: -tuck, width: halfBase * 2, height: height + tuck)
        }

        // Tilt in radians (+ = tip away from the head's centre) and vertical stretch per pose.
        static let restTilt: CGFloat = 0.24
        static let perkTilt: CGFloat = 0.06       // hover
        static let perkStretch: CGFloat = 1.1
        static let listenTilt: CGFloat = 0.02     // fully up
        static let listenStretch: CGFloat = 1.14
        static let listenTurn: CGFloat = 0.22     // extra tilt toward the screen centre while listening
        static let droopTilt: CGFloat = 0.9       // confused: the left ear folds down
        static let droopStretch: CGFloat = 0.9
        static let sleepTilt: CGFloat = 0.6       // flattened
        static let sleepStretch: CGFloat = 0.82
        static let twitch: CGFloat = 0.26         // idle twitch amplitude
    }

    /// Ginger crown patch with three tabby stripes (clipped by the head).
    enum Crown {
        static let patch = CGRect(x: 13, y: 42, width: 30, height: 16)
        static let stripes: [(CGPoint, CGPoint)] = [
            (CGPoint(x: 22.5, y: 44.5), CGPoint(x: 23.5, y: 49.5)),
            (CGPoint(x: 28, y: 43.5), CGPoint(x: 28, y: 49.8)),
            (CGPoint(x: 33.5, y: 44.5), CGPoint(x: 32.5, y: 49.5)),
        ]
        static let stripeWidth: CGFloat = 1.6
    }

    enum Eye {
        static let leftCenter = CGPoint(x: 18, y: 27)
        static let rightCenter = CGPoint(x: 38, y: 27)
        /// Local to the eye's centre (blinks scale about it).
        static let bounds = CGRect(x: -5, y: -6, width: 10, height: 12)
        /// Two white glints (local rect, alpha): big upper-right, small lower-left.
        static let highlights: [(CGRect, CGFloat)] = [
            (CGRect(x: -0.1, y: 0.9, width: 3.6, height: 3.6), 0.95),
            (CGRect(x: -3.3, y: -3.6, width: 1.8, height: 1.8), 0.75),
        ]
        static let lidWidth: CGFloat = 1.8
        static let lidHalfWidth: CGFloat = 4.2
        static let lidDrop: CGFloat = 1.5         // lids sit a little below the eye centre
        static let happyArch: CGFloat = 4.6       // "^" (success)
        static let sleepSag: CGFloat = -3.6       // closed, bowing down (asleep)
    }

    enum Face {
        static let muzzle = CGRect(x: 16, y: 9.5, width: 24, height: 13)
        static let cheekSize = CGSize(width: 9, height: 5)
        static let cheekL = CGPoint(x: 10.5, y: 17)
        static let cheekR = CGPoint(x: 45.5, y: 17)
        static let nose = CGPoint(x: 28, y: 20)   // centre of the nose triangle
        static let noseSize = CGSize(width: 4.8, height: 3)
        static let mouth = CGPoint(x: 28, y: 16.5) // where the two halves of the "w" meet
        static let mouthLineWidth: CGFloat = 1.3
    }

    /// Three thin whiskers per side; the right side mirrors the left about the centre.
    enum Whisker {
        static let width: CGFloat = 0.6
        static let left: [(CGPoint, CGPoint)] = [
            (CGPoint(x: 9, y: 19.5), CGPoint(x: -4, y: 22)),
            (CGPoint(x: 9, y: 17.2), CGPoint(x: -5, y: 17.2)),
            (CGPoint(x: 9, y: 15), CGPoint(x: -4, y: 12.4)),
        ]
    }

    /// Small paws peeking out at the bottom, in front of the body.
    enum Paw {
        static let bounds = CGRect(x: -6, y: -3.5, width: 12, height: 7)
        static let leftCenter = CGPoint(x: 20, y: 2.2)
        static let rightCenter = CGPoint(x: 36, y: 2.2)
        static let toes: [(CGPoint, CGPoint)] = [
            (CGPoint(x: -2, y: -3.3), CGPoint(x: -2, y: -1.1)),
            (CGPoint(x: 2, y: -3.3), CGPoint(x: 2, y: -1.1)),
        ]
        static let toeWidth: CGFloat = 0.8
        /// Thinking: the right paw rises to the chin.
        static let chinCenter = CGPoint(x: 33.5, y: 10.5)
        static let chinTilt: CGFloat = 0.45
    }

    struct Cubic {
        var start: CGPoint = .zero
        var c1: CGPoint
        var c2: CGPoint
        var end: CGPoint

        var path: CGPath {
            let p = CGMutablePath()
            p.move(to: start)
            p.addCurve(to: end, control1: c1, control2: c2)
            return p
        }
    }

    enum TailPose { case rest, up }

    /// Thick stroked tail (outline, fur and a ginger tip share one path so a
    /// pose change animates all three). Poses share one topology so CA interpolates.
    enum Tail {
        static let base = CGPoint(x: 48, y: 9)    // pivot, hidden behind the body
        static let width: CGFloat = 7
        static let tipStart: CGFloat = 0.7        // fraction of the length that is cream
        /// Tail-local (origin = base): curls up around the right side.
        static let rest = Cubic(c1: CGPoint(x: 14, y: -2), c2: CGPoint(x: 19, y: 14), end: CGPoint(x: 14, y: 24))
        /// Tail-local: straight up with the tip curled over (listening, hover).
        static let up = Cubic(c1: CGPoint(x: 16, y: 4), c2: CGPoint(x: 17, y: 36), end: CGPoint(x: 8, y: 34))
        /// Body coordinates: wrapped over the paws, drawn in front (sleeping).
        static let wrap = Cubic(start: CGPoint(x: 54, y: 10), c1: CGPoint(x: 57, y: 0),
                                c2: CGPoint(x: 34, y: -4), end: CGPoint(x: 13, y: 1.5))
        static let sway: CGFloat = 0.14           // ±8°, idle
        static let swayPeriod: CFTimeInterval = 4
        static let swish: CGFloat = 0.24          // acting
        static let swishPeriod: CFTimeInterval = 0.9
    }

    // MARK: paths

    static func body() -> CGPath {
        let w = Body.width, h = Body.height, y = Body.widestY
        let b = Body.bottomCorner, s = Body.shoulder, c = Body.crownCorner
        let p = CGMutablePath()
        p.move(to: CGPoint(x: w / 2, y: 0))
        p.addCurve(to: CGPoint(x: w, y: y), control1: CGPoint(x: w - b, y: 0), control2: CGPoint(x: w, y: b))
        p.addCurve(to: CGPoint(x: w / 2, y: h), control1: CGPoint(x: w, y: h - s), control2: CGPoint(x: w - c, y: h))
        p.addCurve(to: CGPoint(x: 0, y: y), control1: CGPoint(x: c, y: h), control2: CGPoint(x: 0, y: h - s))
        p.addCurve(to: CGPoint(x: w / 2, y: 0), control1: CGPoint(x: 0, y: b), control2: CGPoint(x: b, y: 0))
        p.closeSubpath()
        return p
    }

    /// Ear in its local space (origin = pivot at the base centre).
    static func ear(scale k: CGFloat = 1, lift: CGFloat = 0) -> CGPath {
        let hw = Ear.halfBase * k, h = Ear.height * k, y0 = -Ear.tuck + lift
        let p = CGMutablePath()
        p.move(to: CGPoint(x: -hw, y: y0))
        p.addArc(tangent1End: CGPoint(x: 0, y: h + lift), tangent2End: CGPoint(x: hw, y: y0),
                 radius: Ear.tipRadius * k)
        p.addLine(to: CGPoint(x: hw, y: y0))
        p.closeSubpath()
        return p
    }

    static func innerEar() -> CGPath { ear(scale: Ear.innerScale, lift: Ear.innerLift) }

    static func crownPatch() -> CGPath { CGPath(ellipseIn: Crown.patch, transform: nil) }

    static func crownStripes() -> CGPath { segments(Crown.stripes) }

    static func muzzle() -> CGPath { CGPath(ellipseIn: Face.muzzle, transform: nil) }

    static func sheen() -> CGPath { CGPath(ellipseIn: Body.sheen, transform: nil) }

    static func cheek() -> CGPath {
        let s = Face.cheekSize
        return CGPath(ellipseIn: CGRect(x: -s.width / 2, y: -s.height / 2, width: s.width, height: s.height),
                      transform: nil)
    }

    static func whiskers() -> CGPath {
        let mirrored = Whisker.left.map { a, b in
            (CGPoint(x: Body.width - a.x, y: a.y), CGPoint(x: Body.width - b.x, y: b.y))
        }
        return segments(Whisker.left + mirrored)
    }

    /// Tiny downward triangle (stroke it with round joins for soft corners).
    static func nose() -> CGPath {
        let c = Face.nose, w = Face.noseSize.width / 2, h = Face.noseSize.height / 2
        let p = CGMutablePath()
        p.move(to: CGPoint(x: c.x - w, y: c.y + h))
        p.addLine(to: CGPoint(x: c.x + w, y: c.y + h))
        p.addLine(to: CGPoint(x: c.x, y: c.y - h))
        p.closeSubpath()
        return p
    }

    enum Lid { case happy, asleep }

    /// Closed eye in body coordinates: "^" (happy) or a soft downward bow (asleep).
    static func lid(_ kind: Lid, center c: CGPoint) -> CGPath {
        let y = c.y - Eye.lidDrop, hw = Eye.lidHalfWidth
        let bend = kind == .happy ? Eye.happyArch : Eye.sleepSag
        let p = CGMutablePath()
        p.move(to: CGPoint(x: c.x - hw, y: y))
        p.addQuadCurve(to: CGPoint(x: c.x + hw, y: y), control: CGPoint(x: c.x, y: y + bend))
        return p
    }

    static func paw() -> CGPath { CGPath(ellipseIn: Paw.bounds, transform: nil) }

    static func toes() -> CGPath { segments(Paw.toes) }

    static func tail(_ pose: TailPose) -> CGPath { (pose == .up ? Tail.up : Tail.rest).path }

    static func tailWrap() -> CGPath { Tail.wrap.path }

    /// Stroked "w" mouth (plus the short line up to the nose). Fixed topology
    /// (philtrum + two cubic halves) so CA can interpolate between expressions.
    struct Mouth {
        var width: CGFloat
        var dipL: CGFloat      // + bows the left half down, - up
        var dipR: CGFloat
        var edgeLift: CGFloat  // + lifts the outer corners

        static let smile = Mouth(width: 10, dipL: 2.4, dipR: 2.4, edgeLift: 0.8)
        static let grin = Mouth(width: 12, dipL: 3.2, dipR: 3.2, edgeLift: 1.4)
        static let flat = Mouth(width: 7, dipL: 0.7, dipR: 0.7, edgeLift: 0)
        static let wavy = Mouth(width: 9, dipL: 1.6, dipR: -1.6, edgeLift: 0)
        static let sleepy = Mouth(width: 6, dipL: 1.2, dipR: 1.2, edgeLift: 0.3)
        static let attentive = Mouth(width: 8, dipL: 1.8, dipR: 1.8, edgeLift: 0.4)

        static let philtrum: CGFloat = 2
        /// The small "o" under the "w" (listening level, success); local to its centre.
        static let openCenter = CGPoint(x: 28, y: 13.6)
        static let openBounds = CGRect(x: -2.6, y: -2.9, width: 5.2, height: 5.8)
        static let tongue = CGRect(x: -1.7, y: -2.6, width: 3.4, height: 2.4)

        func path(center c: CGPoint) -> CGPath {
            let l = CGPoint(x: c.x - width / 2, y: c.y + edgeLift)
            let r = CGPoint(x: c.x + width / 2, y: c.y + edgeLift)
            let k = width * 0.06
            let p = CGMutablePath()
            p.move(to: CGPoint(x: c.x, y: c.y + Self.philtrum))
            p.addLine(to: c)
            p.move(to: l)
            p.addCurve(to: c, control1: CGPoint(x: l.x + k, y: l.y - dipL), control2: CGPoint(x: c.x - k, y: c.y - dipL))
            p.addCurve(to: r, control1: CGPoint(x: c.x + k, y: c.y - dipR), control2: CGPoint(x: r.x - k, y: r.y - dipR))
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

    private static func segments(_ s: [(CGPoint, CGPoint)]) -> CGPath {
        let p = CGMutablePath()
        for (a, b) in s {
            p.move(to: a)
            p.addLine(to: b)
        }
        return p
    }
}
