import AppKit
import CoreGraphics

/// Conversions between the two global coordinate spaces:
///  - CG / AX: origin top-left of the primary display, y down (points)
///  - AppKit:  origin bottom-left of the primary display, y up (points)
/// Done per screen via NSScreenNumber -> CGDirectDisplayID -> CGDisplayBounds,
/// so arrangements with displays above/below the primary convert correctly.
enum ScreenGeometry {
    static func displayID(of screen: NSScreen) -> CGDirectDisplayID? {
        let key = NSDeviceDescriptionKey("NSScreenNumber")
        return (screen.deviceDescription[key] as? NSNumber).map { CGDirectDisplayID($0.uint32Value) }
    }

    /// The screen's rect in CG global (top-left) coordinates.
    static func cgBounds(of screen: NSScreen) -> CGRect {
        if let id = displayID(of: screen) {
            let b = CGDisplayBounds(id)
            if b.width > 0 { return b }
        }
        // Fallback: flip around the primary screen height.
        let primaryH = NSScreen.screens.first?.frame.height ?? screen.frame.height
        let f = screen.frame
        return CGRect(x: f.minX, y: primaryH - f.maxY, width: f.width, height: f.height)
    }

    static func screen(containingCG p: CGPoint) -> NSScreen? {
        NSScreen.screens.first { cgBounds(of: $0).contains(p) }
    }

    static func screen(containingAppKit p: CGPoint) -> NSScreen? {
        NSScreen.screens.first { NSMouseInRect(p, $0.frame, false) }
    }

    /// Nearest screen to a CG point (for points slightly off any display).
    static func nearestScreen(toCG p: CGPoint) -> NSScreen? {
        if let s = screen(containingCG: p) { return s }
        return NSScreen.screens.min { a, b in
            dist2(cgBounds(of: a), p) < dist2(cgBounds(of: b), p)
        }
    }

    private static func dist2(_ r: CGRect, _ p: CGPoint) -> CGFloat {
        let dx = max(r.minX - p.x, 0, p.x - r.maxX)
        let dy = max(r.minY - p.y, 0, p.y - r.maxY)
        return dx * dx + dy * dy
    }

    static func appKitPoint(fromCG p: CGPoint) -> CGPoint {
        guard let s = nearestScreen(toCG: p) else { return p }
        let b = cgBounds(of: s)
        let f = s.frame
        return CGPoint(x: f.minX + (p.x - b.minX), y: f.maxY - (p.y - b.minY))
    }

    static func cgPoint(fromAppKit p: CGPoint) -> CGPoint {
        guard let s = screen(containingAppKit: p) ?? NSScreen.main ?? NSScreen.screens.first else { return p }
        let b = cgBounds(of: s)
        let f = s.frame
        return CGPoint(x: b.minX + (p.x - f.minX), y: b.minY + (f.maxY - p.y))
    }

    static func appKitRect(fromCG r: CGRect) -> CGRect {
        let tl = appKitPoint(fromCG: CGPoint(x: r.minX, y: r.minY))
        return CGRect(x: tl.x, y: tl.y - r.height, width: r.width, height: r.height)
    }

    static func cgRect(fromAppKit r: CGRect) -> CGRect {
        let tl = cgPoint(fromAppKit: CGPoint(x: r.minX, y: r.maxY))
        return CGRect(x: tl.x, y: tl.y, width: r.width, height: r.height)
    }
}
