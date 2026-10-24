import AppKit
import HandsKit
import QuartzCore

/// Native-style feedback HUD for system skills (volume, brightness, dark
/// mode, Wi-Fi, Bluetooth): glass panel top-right below the menu bar on the
/// screen with the mouse; SF Symbol + level bar or On/Off. Click-through,
/// never key, fades out after ~1.5 s, honors Reduce Motion.
final class SkillHUD {
    enum Style: String { case glass, vibrancy }
    /// glass = NSGlassEffectView (Liquid Glass); vibrancy = NSVisualEffectView .hudWindow.
    static var style: Style = .glass

    static let size = CGSize(width: 300, height: 64)
    static let visibleFor: TimeInterval = 1.5

    private var panel: FloatingPanel?
    private var builtStyle: Style?
    private let content = HUDContentView(frame: NSRect(origin: .zero, size: SkillHUD.size))
    private var generation = 0
    private var hideWork: DispatchWorkItem?

    private var reduceMotion: Bool { NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }

    /// Main thread only.
    func show(_ fb: SkillFeedback) {
        let panel = ensurePanel()
        generation += 1
        let gen = generation
        hideWork?.cancel()

        let wasVisible = panel.isVisible && panel.alphaValue > 0.01
        content.apply(fb, animated: wasVisible && !reduceMotion)

        let target = Self.targetFrame()
        if wasVisible {
            if panel.frame.origin != target.origin { panel.setFrame(target, display: true) }
            panel.alphaValue = 1
        } else {
            var start = target
            if !reduceMotion { start.origin.y += 10 }      // slide down into place
            panel.setFrame(start, display: false)
            panel.alphaValue = 0
            panel.orderFrontRegardless()
            NSAnimationContext.runAnimationGroup { ctx in
                ctx.duration = reduceMotion ? 0.12 : 0.22
                ctx.timingFunction = CAMediaTimingFunction(name: .easeOut)
                panel.animator().alphaValue = 1
                if !reduceMotion { panel.animator().setFrame(target, display: true) }
            }
        }
        NSAccessibility.post(element: panel, notification: .announcementRequested,
                             userInfo: [.announcement: content.spokenSummary,
                                        .priority: NSAccessibilityPriorityLevel.low.rawValue])

        let work = DispatchWorkItem { [weak self] in
            guard let self, self.generation == gen, let p = self.panel else { return }
            NSAnimationContext.runAnimationGroup({ ctx in
                ctx.duration = self.reduceMotion ? 0.15 : 0.3
                ctx.timingFunction = CAMediaTimingFunction(name: .easeIn)
                p.animator().alphaValue = 0
            }, completionHandler: { [weak self] in
                guard let self, self.generation == gen else { return }
                self.panel?.orderOut(nil)
            })
        }
        hideWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.visibleFor, execute: work)
    }

    /// Top-right of the visible frame (below the menu bar) of the screen
    /// containing the mouse.
    static func targetFrame() -> NSRect {
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first { NSMouseInRect(mouse, $0.frame, false) }
            ?? NSScreen.main ?? NSScreen.screens.first
        let vf = screen?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        return NSRect(x: vf.maxX - size.width - 14, y: vf.maxY - size.height - 10,
                      width: size.width, height: size.height).integral
    }

    private func ensurePanel() -> FloatingPanel {
        if let p = panel, builtStyle == Self.style { return p }
        panel?.orderOut(nil)
        let p = FloatingPanel(size: Self.size,
                              level: NSWindow.Level(rawValue: NSWindow.Level.statusBar.rawValue + 1))
        p.ignoresMouseEvents = true
        p.hasShadow = Self.style == .vibrancy
        p.setAccessibilityLabel("muselet status")
        let bounds = NSRect(origin: .zero, size: Self.size)
        content.removeFromSuperview()
        content.frame = bounds
        content.autoresizingMask = [.width, .height]
        switch Self.style {
        case .glass:
            let glass = NSGlassEffectView(frame: bounds)
            glass.cornerRadius = 20
            glass.style = .regular
            glass.contentView = content
            p.contentView = glass
            content.appearanceOverride = nil
        case .vibrancy:
            let fx = NSVisualEffectView(frame: bounds)
            fx.material = .hudWindow
            fx.blendingMode = .behindWindow
            fx.state = .active
            fx.wantsLayer = true
            fx.layer?.cornerRadius = 20
            fx.layer?.cornerCurve = .continuous
            fx.layer?.masksToBounds = true
            fx.addSubview(content)
            p.contentView = fx
            p.appearance = NSAppearance(named: .vibrantDark)
            content.appearanceOverride = NSAppearance(named: .vibrantDark)
        }
        panel = p
        builtStyle = Self.style
        return p
    }
}

/// Icon + title + level bar / value text (flipped, fixed layout).
final class HUDContentView: NSView {
    private let icon = NSImageView()
    private let title = NSTextField(labelWithString: "")
    private let value = NSTextField(labelWithString: "")
    private let bar = LevelBar()
    private(set) var spokenSummary = ""
    var appearanceOverride: NSAppearance? { didSet { appearance = appearanceOverride } }

    override var isFlipped: Bool { true }

    override init(frame: NSRect) {
        super.init(frame: frame)
        icon.imageScaling = .scaleProportionallyUpOrDown
        title.font = .systemFont(ofSize: 13, weight: .semibold)
        title.textColor = .labelColor
        title.lineBreakMode = .byTruncatingTail
        value.font = .monospacedDigitSystemFont(ofSize: 12, weight: .medium)
        value.textColor = .secondaryLabelColor
        value.alignment = .right
        [icon, title, value, bar].forEach(addSubview)
    }

    required init?(coder: NSCoder) { fatalError() }

    func apply(_ fb: SkillFeedback, animated: Bool) {
        let w = bounds.width, h = bounds.height
        var symbol = "questionmark", tint = NSColor.labelColor
        switch fb {
        case .level(let kind, let level, let muted):
            let frac = CGFloat(level) / 100
            if kind == .volume {
                title.stringValue = muted ? "Muted" : "Volume"
                symbol = muted ? "speaker.slash.fill"
                    : level == 0 ? "speaker.fill"
                    : level < 34 ? "speaker.wave.1.fill"
                    : level < 67 ? "speaker.wave.2.fill" : "speaker.wave.3.fill"
                tint = muted ? .secondaryLabelColor : .labelColor
                value.stringValue = muted ? "Off" : "\(level)%"
                bar.set(fraction: muted ? 0 : frac, animated: animated)
                spokenSummary = muted ? "Sound muted" : "Volume \(level) percent"
            } else {
                title.stringValue = "Brightness"
                symbol = level < 50 ? "sun.min.fill" : "sun.max.fill"
                value.stringValue = "\(level)%"
                bar.set(fraction: frac, animated: animated)
                spokenSummary = "Brightness \(level) percent"
            }
            bar.isHidden = false
            title.frame = NSRect(x: 58, y: 12, width: w - 58 - 64, height: 18)
            bar.frame = NSRect(x: 58, y: 38, width: w - 58 - 64, height: 6)
            value.frame = NSRect(x: w - 56, y: 31, width: 42, height: 18)
        case .toggle(let kind, let on):
            switch kind {
            case .darkMode:
                title.stringValue = "Dark Mode"
                symbol = on ? "moon.fill" : "sun.max.fill"
            case .wifi:
                title.stringValue = "Wi-Fi"
                symbol = on ? "wifi" : "wifi.slash"
            case .bluetooth:
                title.stringValue = "Bluetooth"
                symbol = on ? "antenna.radiowaves.left.and.right"
                    : "antenna.radiowaves.left.and.right.slash"
            default:
                title.stringValue = kind.rawValue.capitalized
            }
            tint = on ? .controlAccentColor : .secondaryLabelColor
            value.stringValue = on ? "On" : "Off"
            value.textColor = on ? .labelColor : .secondaryLabelColor
            bar.isHidden = true
            title.frame = NSRect(x: 58, y: (h - 18) / 2, width: w - 58 - 76, height: 18)
            value.frame = NSRect(x: w - 70, y: (h - 18) / 2, width: 56, height: 18)
            spokenSummary = "\(title.stringValue) \(on ? "on" : "off")"
        }
        if case .level = fb { value.textColor = .secondaryLabelColor }
        let cfg = NSImage.SymbolConfiguration(pointSize: 20, weight: .semibold)
        icon.image = (NSImage(systemSymbolName: symbol, accessibilityDescription: title.stringValue)
            ?? NSImage(systemSymbolName: "circle.fill", accessibilityDescription: nil))?
            .withSymbolConfiguration(cfg)
        icon.contentTintColor = tint
        icon.frame = NSRect(x: 16, y: (h - 28) / 2, width: 30, height: 28)
    }
}

/// Rounded track + fill (Core Animation; fill animates unless told not to).
final class LevelBar: NSView {
    private let track = CALayer()
    private let fill = CALayer()
    private var fraction: CGFloat = 0

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.addSublayer(track)
        track.addSublayer(fill)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layout() {
        super.layout()
        redraw(animated: false)
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        redraw(animated: false)
    }

    func set(fraction f: CGFloat, animated: Bool) {
        fraction = max(0, min(1, f))
        redraw(animated: animated)
    }

    private func redraw(animated: Bool) {
        var track = NSColor.labelColor.withAlphaComponent(0.18).cgColor
        var fillC = NSColor.labelColor.withAlphaComponent(0.92).cgColor
        effectiveAppearance.performAsCurrentDrawingAppearance {
            track = NSColor.labelColor.withAlphaComponent(0.18).cgColor
            fillC = NSColor.labelColor.withAlphaComponent(0.92).cgColor
        }
        CATransaction.begin()
        CATransaction.setDisableActions(!animated)
        CATransaction.setAnimationDuration(0.18)
        self.track.frame = bounds
        self.track.cornerRadius = bounds.height / 2
        self.track.backgroundColor = track
        self.track.masksToBounds = true
        fill.backgroundColor = fillC
        fill.cornerRadius = bounds.height / 2
        fill.frame = CGRect(x: 0, y: 0, width: bounds.width * fraction, height: bounds.height)
        CATransaction.commit()
    }
}
