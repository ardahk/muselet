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

/// Template menu-bar glyph: the cork-creature silhouette with eye cut-outs.
enum MenuBarIcon {
    static func make(recording: Bool) -> NSImage {
        let size = NSSize(width: 18, height: 18)
        let img = NSImage(size: size, flipped: false) { _ in
            let body = MascotPaths.bodyPath(width: 13, height: 13.5, bottomRadius: 3.6, topRadius: 6.5)
            let path = NSBezierPath(cgPath: body)
            path.transform(using: AffineTransform(translationByX: 2.5, byY: 1.5))
            NSColor.black.setFill()
            path.fill()
            // cap
            let cap = NSBezierPath(roundedRect: NSRect(x: 6.5, y: 14.2, width: 5, height: 2.2), xRadius: 1.1, yRadius: 1.1)
            cap.fill()
            // eyes (cleared)
            NSGraphicsContext.current?.compositingOperation = .clear
            let eyeH: CGFloat = recording ? 4.2 : 3.4
            NSBezierPath(roundedRect: NSRect(x: 6.2, y: 7.6, width: 1.9, height: eyeH), xRadius: 0.95, yRadius: 0.95).fill()
            NSBezierPath(roundedRect: NSRect(x: 9.9, y: 7.6, width: 1.9, height: eyeH), xRadius: 0.95, yRadius: 0.95).fill()
            if recording {
                NSBezierPath(ovalIn: NSRect(x: 8.0, y: 3.6, width: 2.0, height: 2.2)).fill()
            }
            return true
        }
        img.isTemplate = true
        return img
    }
}
