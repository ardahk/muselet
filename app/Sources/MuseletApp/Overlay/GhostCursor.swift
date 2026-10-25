import AppKit
import HandsKit
import QuartzCore

/// Ghost cursor: flies a tinted pointer to the element HandsKit is about to
/// touch, outlines it, then ripples on completion. The real cursor is never
/// moved. Flight is driven by a 120 Hz CADisplayLink that only exists while a
/// flight is in progress; highlight/ripple/fades are Core Animation (render
/// server), so idle CPU stays at zero.
final class GhostCursor: HandsDelegate {
    private let overlays: OverlayController

    /// Global CG point of the mascot (flight origin when there's no last position).
    var mascotAnchor: (() -> CGPoint?)?
    /// Mascot hooks (main thread).
    var onFlightStart: ((_ targetCG: CGPoint) -> Void)?
    var onIdle: (() -> Void)?

    // Cross-thread state (handsWillAct runs on the rpc queue).
    private let lock = NSLock()
    private var lastGlobal: CGPoint?
    private var mascotCache: CGPoint?

    // Main-thread state.
    private weak var host: OverlayWindow?
    private let cursor = CAShapeLayer()
    private let highlight = CAShapeLayer()
    private let chip = CALayer()
    private let chipText = CATextLayer()
    private var link: CADisplayLink?
    private var flight: Flight?
    private var generation = 0
    private var hideWork: DispatchWorkItem?
    private var landed = true

    private struct Flight {
        var from: CGPoint      // local
        var control: CGPoint   // local
        var to: CGPoint        // local
        var start: CFTimeInterval
        var duration: CFTimeInterval
    }

    init(overlays: OverlayController) {
        self.overlays = overlays
        buildLayers()
        overlays.onRebuild = { [weak self] in self?.detach() }
    }

    /// Called on the main thread by the mascot when it moves.
    func updateMascotAnchor(_ p: CGPoint?) {
        lock.lock(); mascotCache = p; lock.unlock()
    }

    // MARK: HandsDelegate (rpc queue)

    func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval {
        guard let frame, frame.minX.isFinite, frame.minY.isFinite,
              frame.width.isFinite, frame.height.isFinite,
              frame.width < 20_000, frame.height < 20_000 else {
            return 0
        }
        let target = CGPoint(x: frame.midX, y: frame.midY)
        lock.lock()
        let start = lastGlobal ?? mascotCache ?? CGPoint(x: target.x + 80, y: target.y + 140)
        lastGlobal = target
        lock.unlock()
        let dist = hypot(target.x - start.x, target.y - start.y)
        let duration = 0.12 + 0.10 * min(1, Double(dist) / 1400)
        DispatchQueue.main.async {
            self.beginFlight(fromCG: start, frame: frame, op: op, label: label, duration: duration)
        }
        return duration
    }

    func handsDidAct(op: String, frame: CGRect?, ok: Bool) {
        DispatchQueue.main.async { self.land(ok: ok) }
    }

    // MARK: layers

    private func buildLayers() {
        let tint = Brand.tint.cgColor
        // Classic arrow pointer, tip at (0,0), drawn in flipped (y-down) space.
        let p = CGMutablePath()
        p.move(to: .zero)
        p.addLine(to: CGPoint(x: 0, y: 17.5))
        p.addLine(to: CGPoint(x: 4.3, y: 13.6))
        p.addLine(to: CGPoint(x: 7.2, y: 20.2))
        p.addLine(to: CGPoint(x: 10.3, y: 18.9))
        p.addLine(to: CGPoint(x: 7.5, y: 12.4))
        p.addLine(to: CGPoint(x: 13.0, y: 12.4))
        p.closeSubpath()
        var scale = CGAffineTransform(scaleX: 1.15, y: 1.15)
        cursor.path = p.copy(using: &scale)
        cursor.bounds = CGRect(x: 0, y: 0, width: 16, height: 24)
        cursor.anchorPoint = CGPoint(x: 0, y: 0)
        cursor.fillColor = tint
        cursor.strokeColor = NSColor.white.cgColor
        cursor.lineWidth = 1.6
        cursor.lineJoin = .round
        cursor.shadowColor = NSColor.black.cgColor
        cursor.shadowOpacity = 0.35
        cursor.shadowRadius = 3
        cursor.shadowOffset = CGSize(width: 0, height: 1.5)
        cursor.opacity = 0
        cursor.zPosition = 10

        highlight.fillColor = Brand.tint.withAlphaComponent(0.10).cgColor
        highlight.strokeColor = tint
        highlight.lineWidth = 2.5
        highlight.shadowColor = tint
        highlight.shadowOpacity = 0.55
        highlight.shadowRadius = 9
        highlight.shadowOffset = .zero
        highlight.opacity = 0
        highlight.zPosition = 1

        chip.backgroundColor = Brand.tintDeep.withAlphaComponent(0.94).cgColor
        chip.cornerRadius = 9
        chip.cornerCurve = .continuous
        chip.shadowColor = NSColor.black.cgColor
        chip.shadowOpacity = 0.25
        chip.shadowRadius = 4
        chip.shadowOffset = CGSize(width: 0, height: 1)
        chip.opacity = 0
        chip.zPosition = 5
        chipText.font = NSFont.systemFont(ofSize: 11, weight: .semibold)
        chipText.fontSize = 11
        chipText.foregroundColor = NSColor.white.cgColor
        chipText.alignmentMode = .center
        chipText.truncationMode = .end
        chip.addSublayer(chipText)
    }

    private func attach(to w: OverlayWindow) {
        guard host !== w else { return }
        if let old = host { overlays.hide(old) }
        let root = w.canvas.root
        for l in [highlight, chip, cursor] as [CALayer] {
            l.removeFromSuperlayer()
            root.addSublayer(l)
        }
        OverlayCanvas.setScale(highlight, w.backingScaleFactor)
        OverlayCanvas.setScale(chip, w.backingScaleFactor)
        OverlayCanvas.setScale(cursor, w.backingScaleFactor)
        host = w
    }

    private func detach() {
        stopLink()
        [highlight, chip, cursor].forEach { $0.removeFromSuperlayer() }
        host = nil
    }

    // MARK: flight (main)

    private func beginFlight(fromCG startCG: CGPoint, frame: CGRect, op: String,
                             label: String?, duration: TimeInterval) {
        let targetCG = CGPoint(x: frame.midX, y: frame.midY)
        guard let w = overlays.overlay(forCG: targetCG) else { return }
        generation += 1
        hideWork?.cancel()
        landed = false
        attach(to: w)
        overlays.show(w)

        let to = w.toLocal(targetCG)
        // If the cursor is already visible on this overlay, start from where it is.
        var from = w.toLocal(startCG)
        if cursor.opacity > 0.01, cursor.superlayer === w.canvas.root {
            from = cursor.presentation()?.position ?? cursor.position
        }
        let dx = to.x - from.x, dy = to.y - from.y
        let dist = max(1, hypot(dx, dy))
        let mid = CGPoint(x: (from.x + to.x) / 2, y: (from.y + to.y) / 2)
        // Perpendicular bow; pick the side that arcs upward on screen.
        var nx = -dy / dist, ny = dx / dist
        if ny > 0 { nx = -nx; ny = -ny }
        let bow = min(dist * 0.22, 90)
        let control = CGPoint(x: mid.x + nx * bow, y: mid.y + ny * bow)

        CATransaction.begin()
        CATransaction.setDisableActions(true)
        cursor.position = from
        CATransaction.commit()
        if cursor.opacity < 0.99 { fade(cursor, to: 1, duration: 0.08) }

        showHighlight(localRect: w.toLocal(frame), op: op, label: label, bounds: w.canvas.bounds)

        flight = Flight(from: from, control: control, to: to,
                        start: CACurrentMediaTime(), duration: duration)
        startLink(on: w.canvas)
        onFlightStart?(targetCG)
    }

    private func startLink(on view: NSView) {
        if let link { link.isPaused = false; return }
        let l = view.displayLink(target: self, selector: #selector(step(_:)))
        l.preferredFrameRateRange = CAFrameRateRange(minimum: 60, maximum: 120, preferred: 120)
        l.add(to: .main, forMode: .common)
        link = l
    }

    private func stopLink() {
        link?.invalidate()
        link = nil
    }

    @objc private func step(_ l: CADisplayLink) {
        guard let f = flight else { stopLink(); return }
        let now = max(CACurrentMediaTime(), l.timestamp)
        let t = min(1, (now - f.start) / f.duration)
        let e = CGFloat(Self.spring(t))
        let u = 1 - e
        let x = u * u * f.from.x + 2 * u * e * f.control.x + e * e * f.to.x
        let y = u * u * f.from.y + 2 * u * e * f.control.y + e * e * f.to.y
        // Slight swoop scale mid-flight.
        let s = 1 + 0.18 * CGFloat(sin(Double.pi * min(1, t * 1.6)))
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        cursor.position = CGPoint(x: x, y: y)
        cursor.setAffineTransform(CGAffineTransform(scaleX: s, y: s))
        CATransaction.commit()
        if t >= 1 {
            CATransaction.begin()
            CATransaction.setDisableActions(true)
            cursor.position = f.to
            cursor.setAffineTransform(.identity)
            CATransaction.commit()
            flight = nil
            stopLink()
        }
    }

    /// Under-damped spring step response on t∈[0,1] (ζ≈0.78, ~2% overshoot).
    static func spring(_ t: Double) -> Double {
        if t >= 1 { return 1 }
        let zeta = 0.78, omega = 9.0
        let wd = omega * sqrt(1 - zeta * zeta)
        let env = exp(-zeta * omega * t)
        return 1 - env * (cos(wd * t) + (zeta * omega / wd) * sin(wd * t))
    }

    // MARK: highlight + chip

    private func showHighlight(localRect r: CGRect, op: String, label: String?, bounds: CGRect) {
        let isPoint = r.width < 4 || r.height < 4
        let rect: CGRect
        if isPoint {
            rect = CGRect(x: r.midX - 14, y: r.midY - 14, width: 28, height: 28)
        } else {
            rect = r.insetBy(dx: -5, dy: -5)
        }
        let radius = isPoint ? 14 : min(10, rect.height / 2)
        _ = radius
        // user preference: no box highlight around the target — cursor only
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        highlight.removeAllAnimations()
        highlight.frame = rect
        highlight.path = CGPath(roundedRect: CGRect(origin: .zero, size: rect.size),
                                cornerWidth: radius, cornerHeight: radius, transform: nil)
        highlight.opacity = 0
        CATransaction.commit()

        // Chip: "press · Back"
        let verb = Self.verb(op)
        let text: String
        if let l = label?.trimmingCharacters(in: .whitespacesAndNewlines), !l.isEmpty {
            text = "\(verb) · \(l.count > 40 ? String(l.prefix(39)) + "…" : l)"
        } else {
            text = verb
        }
        let font = NSFont.systemFont(ofSize: 11, weight: .semibold)
        let tw = ceil((text as NSString).size(withAttributes: [.font: font]).width)
        let size = CGSize(width: min(tw + 18, 300), height: 20)
        var origin = CGPoint(x: rect.minX, y: rect.minY - size.height - 6)
        if origin.y < 4 { origin.y = rect.maxY + 6 }
        origin.x = max(4, min(origin.x, bounds.width - size.width - 4))
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        chip.removeAllAnimations()
        chip.backgroundColor = Brand.tintDeep.withAlphaComponent(0.94).cgColor
        chip.frame = CGRect(origin: origin, size: size)
        chipText.string = text
        chipText.frame = CGRect(x: 9, y: 3, width: size.width - 18, height: 15)
        chip.opacity = 1
        CATransaction.commit()
        let chipIn = CABasicAnimation(keyPath: "opacity")
        chipIn.fromValue = 0
        chipIn.toValue = 1
        chipIn.duration = 0.15
        chip.add(chipIn, forKey: "fadeIn")
    }

    static func verb(_ op: String) -> String {
        switch op {
        case "press": return "Click"
        case "type": return "Type"
        case "scroll": return "Scroll"
        case "click": return "Click"
        case "keys": return "Keys"
        case "open", "open_app", "open_file", "open_url": return "Open"
        // Skills (ux-4): the ghost flies to the Dock icon / menu extra.
        case "quit_app": return "Quit"
        case "hide_app": return "Hide"
        case "open_folder": return "Open folder"
        case "find_file": return "Find"
        case "new_folder": return "New folder"
        case "web_search": return "Search"
        case "set_volume", "change_volume": return "Volume"
        case "mute": return "Mute"
        case "set_brightness": return "Brightness"
        case "dark_mode": return "Dark mode"
        case "wifi": return "Wi‑Fi"
        case "bluetooth": return "Bluetooth"
        default: return op.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    // MARK: landing

    private func land(ok: Bool) {
        guard !landed, let w = host else { return }
        landed = true
        let gen = generation
        let center = CGPoint(x: highlight.frame.midX, y: highlight.frame.midY)
        ripple(at: center, in: w.canvas.root, ok: ok)
        if !ok {
            CATransaction.begin()
            CATransaction.setAnimationDuration(0.15)
            highlight.strokeColor = Brand.failure.cgColor
            highlight.shadowColor = Brand.failure.cgColor
            highlight.fillColor = Brand.failure.withAlphaComponent(0.10).cgColor
            chip.backgroundColor = Brand.failure.withAlphaComponent(0.94).cgColor
            CATransaction.commit()
            let shake = CAKeyframeAnimation(keyPath: "transform.translation.x")
            shake.values = [0, -6, 6, -4, 4, -2, 0]
            shake.duration = 0.35
            highlight.add(shake, forKey: "shake")
        }
        // Fade highlight + chip shortly after; cursor lingers a bit longer.
        DispatchQueue.main.asyncAfter(deadline: .now() + (ok ? 0.35 : 0.8)) { [weak self] in
            guard let self, self.generation == gen else { return }
            self.fade(self.highlight, to: 0, duration: 0.3)
            self.fade(self.chip, to: 0, duration: 0.3)
        }
        let work = DispatchWorkItem { [weak self] in
            guard let self, self.generation == gen else { return }
            self.fade(self.cursor, to: 0, duration: 0.35) { [weak self] in
                guard let self, self.generation == gen, let w = self.host else { return }
                self.overlays.hide(w)
                self.lock.lock(); self.lastGlobal = nil; self.lock.unlock()
                self.onIdle?()
            }
        }
        hideWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.4, execute: work)
    }

    private func ripple(at p: CGPoint, in root: CALayer, ok: Bool) {
        let color = ok ? Brand.tint : Brand.failure
        let d: CGFloat = 40
        let ring = CAShapeLayer()
        ring.contentsScale = root.contentsScale
        ring.frame = CGRect(x: p.x - d / 2, y: p.y - d / 2, width: d, height: d)
        ring.path = CGPath(ellipseIn: CGRect(x: 0, y: 0, width: d, height: d), transform: nil)
        ring.fillColor = color.withAlphaComponent(0.18).cgColor
        ring.strokeColor = color.cgColor
        ring.lineWidth = 2.5
        ring.opacity = 0
        ring.zPosition = 8
        root.addSublayer(ring)
        let scale = CABasicAnimation(keyPath: "transform.scale")
        scale.fromValue = 0.25
        scale.toValue = 1.7
        let alpha = CAKeyframeAnimation(keyPath: "opacity")
        alpha.values = [0.0, 1.0, 0.0]
        alpha.keyTimes = [0, 0.15, 1]
        let g = CAAnimationGroup()
        g.animations = [scale, alpha]
        g.duration = 0.5
        g.timingFunction = CAMediaTimingFunction(name: .easeOut)
        CATransaction.begin()
        CATransaction.setCompletionBlock { ring.removeFromSuperlayer() }
        ring.add(g, forKey: "ripple")
        CATransaction.commit()
    }

    private func fade(_ l: CALayer, to value: Float, duration: CFTimeInterval,
                      completion: (() -> Void)? = nil) {
        let from = l.presentation()?.opacity ?? l.opacity
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        CATransaction.setCompletionBlock(completion)
        l.opacity = value
        let a = CABasicAnimation(keyPath: "opacity")
        a.fromValue = from
        a.toValue = value
        a.duration = duration
        a.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        l.add(a, forKey: "fade")
        CATransaction.commit()
    }
}
