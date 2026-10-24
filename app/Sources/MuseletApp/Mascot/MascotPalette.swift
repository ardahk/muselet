import AppKit

/// Kitten colours: warm cream fur, ginger patches (ears, crown, tail tip), pink
/// nose and inner ears, soft blush. Pairs with `MascotPaths`; swap both to
/// change the animal.
enum MascotPalette {
    static let creamLight = NSColor(srgbRed: 1.00, green: 0.97, blue: 0.91, alpha: 1)
    static let cream = NSColor(srgbRed: 0.99, green: 0.92, blue: 0.80, alpha: 1)
    static let creamShade = NSColor(srgbRed: 0.95, green: 0.83, blue: 0.68, alpha: 1)
    static let muzzle = NSColor(srgbRed: 1.00, green: 0.98, blue: 0.95, alpha: 0.85)
    static let paw = NSColor(srgbRed: 1.00, green: 0.96, blue: 0.89, alpha: 1)
    static let sheen = NSColor.white.withAlphaComponent(0.32)
    static let ginger = NSColor(srgbRed: 0.96, green: 0.62, blue: 0.30, alpha: 1)
    static let gingerDark = NSColor(srgbRed: 0.84, green: 0.46, blue: 0.19, alpha: 0.85)
    static let innerEar = NSColor(srgbRed: 1.00, green: 0.72, blue: 0.75, alpha: 1)
    static let nose = NSColor(srgbRed: 0.95, green: 0.50, blue: 0.58, alpha: 1)
    static let blush = NSColor(srgbRed: 1.00, green: 0.55, blue: 0.58, alpha: 1)
    /// 1 pt warm-brown outline at low alpha: reads on light and dark wallpapers.
    static let outline = NSColor(srgbRed: 0.45, green: 0.27, blue: 0.14, alpha: 0.45)
    static let whisker = NSColor(srgbRed: 0.45, green: 0.27, blue: 0.14, alpha: 0.55)
    static let toe = NSColor(srgbRed: 0.45, green: 0.27, blue: 0.14, alpha: 0.35)
    /// Eyes, "w" mouth and closed-eye lids.
    static let ink = NSColor(srgbRed: 0.16, green: 0.11, blue: 0.10, alpha: 1)
    static let mouthInside = NSColor(srgbRed: 0.40, green: 0.15, blue: 0.15, alpha: 1)
    static let tongue = NSColor(srgbRed: 1.00, green: 0.56, blue: 0.62, alpha: 1)
}
