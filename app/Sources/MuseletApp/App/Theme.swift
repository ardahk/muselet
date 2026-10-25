import AppKit
import SwiftUI

/// muselet palette: champagne gold accent, cork body, wire silver.
enum Brand {
    static let tint = NSColor(srgbRed: 0.97, green: 0.62, blue: 0.16, alpha: 1)        // champagne gold
    static let tintDeep = NSColor(srgbRed: 0.86, green: 0.45, blue: 0.08, alpha: 1)
    static let corkLight = NSColor(srgbRed: 0.99, green: 0.88, blue: 0.70, alpha: 1)
    static let corkMid = NSColor(srgbRed: 0.93, green: 0.74, blue: 0.48, alpha: 1)
    static let corkDark = NSColor(srgbRed: 0.80, green: 0.57, blue: 0.33, alpha: 1)
    static let speck = NSColor(srgbRed: 0.62, green: 0.40, blue: 0.20, alpha: 1)
    static let wireLight = NSColor(srgbRed: 0.93, green: 0.94, blue: 0.96, alpha: 1)
    static let wireDark = NSColor(srgbRed: 0.58, green: 0.62, blue: 0.68, alpha: 1)
    static let ink = NSColor(srgbRed: 0.18, green: 0.12, blue: 0.10, alpha: 1)
    static let cheek = NSColor(srgbRed: 1.00, green: 0.50, blue: 0.50, alpha: 1)
    static let failure = NSColor.systemRed

    static var tintColor: Color { Color(nsColor: tint) }
}

enum PanelPalette {
    static let ginger = Color(nsColor: MascotPalette.ginger)
    static let accent = dynamic(light: NSColor(srgbRed: 0.80, green: 0.42, blue: 0.14, alpha: 1),
                                dark: MascotPalette.ginger)
    static let ink = dynamic(light: NSColor(srgbRed: 0.30, green: 0.19, blue: 0.13, alpha: 1),
                             dark: MascotPalette.creamLight)
    static let card = dynamic(light: MascotPalette.creamLight.withAlphaComponent(0.62),
                              dark: MascotPalette.cream.withAlphaComponent(0.07))
    static let cardStroke = dynamic(light: MascotPalette.ginger.withAlphaComponent(0.22),
                                   dark: MascotPalette.cream.withAlphaComponent(0.10))
    static let hover = dynamic(light: MascotPalette.ginger.withAlphaComponent(0.14),
                               dark: MascotPalette.ginger.withAlphaComponent(0.16))
    static let wash = dynamic(light: MascotPalette.ginger.withAlphaComponent(0.10),
                              dark: MascotPalette.ginger.withAlphaComponent(0.07))
    static let avatarBack = dynamic(light: MascotPalette.cream.withAlphaComponent(0.9),
                                    dark: MascotPalette.cream.withAlphaComponent(0.16))

    private static func dynamic(light: NSColor, dark: NSColor) -> Color {
        Color(nsColor: NSColor(name: nil) { a in
            a.bestMatch(from: [.darkAqua, .vibrantDark]) != nil ? dark : light
        })
    }
}

/// Template menu-bar glyph: the kitten's head (round head + two ears) with the eyes
/// cut out, from the mascot geometry in `MascotPaths`. Drawn as vectors at 18 pt, so
/// @1x and @2x are crisp; macOS tints it (light/dark/highlighted).
enum MenuBarIcon {
    static let pointSize: CGFloat = 18

    static func make(recording: Bool) -> NSImage {
        let img = NSImage(size: NSSize(width: pointSize, height: pointSize), flipped: false) { rect in
            guard let ctx = NSGraphicsContext.current?.cgContext else { return false }
            let parts = headParts()
            let box = parts.reduce(CGRect.null) { $0.union($1.boundingBoxOfPath) }
            let k = (pointSize - 1) / max(box.width, box.height)
            ctx.translateBy(x: rect.midX, y: rect.midY)
            ctx.scaleBy(x: k, y: k)
            ctx.translateBy(x: -box.midX, y: -box.midY)
            ctx.setFillColor(NSColor.black.cgColor)
            // One fill per part: the ear and head windings may differ.
            for part in parts {
                ctx.addPath(part)
                ctx.fillPath()
            }
            ctx.setBlendMode(.clear)
            let eye = recording ? MascotPaths.Eye.bounds.insetBy(dx: -1, dy: -1.5) : MascotPaths.Eye.bounds
            for c in [MascotPaths.Eye.leftCenter, MascotPaths.Eye.rightCenter] {
                ctx.fillEllipse(in: eye.offsetBy(dx: c.x, dy: c.y))
            }
            return true
        }
        img.isTemplate = true
        img.accessibilityDescription = "Muselet"
        return img
    }

    /// Head blob plus both ears at their resting tilt (tips away from the centre).
    static func headParts() -> [CGPath] {
        let ears = [(MascotPaths.Ear.leftBase, MascotPaths.Ear.restTilt),
                    (MascotPaths.Ear.rightBase, -MascotPaths.Ear.restTilt)].map { base, tilt -> CGPath in
            var t = CGAffineTransform(translationX: base.x, y: base.y).rotated(by: tilt)
            return MascotPaths.ear().copy(using: &t) ?? MascotPaths.ear()
        }
        return ears + [MascotPaths.body()]
    }
}
