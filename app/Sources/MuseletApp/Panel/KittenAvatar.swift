import AppKit
import SwiftUI

struct KittenAvatar: View {
    let mood: MascotMood
    var size: CGFloat = 40
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            Circle().fill(PanelPalette.avatarBack)
            Canvas { context, canvasSize in
                KittenAvatarDrawing.draw(&context, size: canvasSize, mood: mood)
            }
            .frame(width: size * 0.8, height: size * 0.8)
            .id(mood)
            .transition(.opacity)
        }
        .frame(width: size, height: size)
        .overlay {
            if mood == .listening {
                Circle().strokeBorder(PanelPalette.ginger, lineWidth: 1.5)
            }
        }
        .animation(.easeOut(duration: reduceMotion ? 0.15 : 0.25), value: mood)
        .accessibilityLabel("Muse, \(mood.rawValue)")
    }
}

private enum KittenAvatarDrawing {
    private static let bounds = CGRect(x: -6, y: -5, width: 76, height: 66)

    static func draw(_ context: inout GraphicsContext, size: CGSize, mood: MascotMood) {
        let scale = min(size.width / bounds.width, size.height / bounds.height)
        guard scale > 0 else { return }

        context.translateBy(x: size.width / 2 - bounds.midX * scale,
                            y: size.height / 2 + bounds.midY * scale)
        context.scaleBy(x: scale, y: -scale)

        drawTail(&context)
        drawEar(&context, mood: mood, left: true)
        drawEar(&context, mood: mood, left: false)

        let body = Path(MascotPaths.body())
        let gradient = Gradient(colors: [
            Color(nsColor: MascotPalette.creamLight),
            Color(nsColor: MascotPalette.cream),
            Color(nsColor: MascotPalette.creamShade),
        ])
        context.fill(body, with: .linearGradient(
            gradient,
            startPoint: CGPoint(x: 28, y: MascotPaths.Body.height),
            endPoint: CGPoint(x: 28, y: 0)
        ))
        context.drawLayer { clipped in
            clipped.clip(to: body)
            clipped.fill(Path(MascotPaths.muzzle()), with: .color(Color(nsColor: MascotPalette.muzzle)))
            clipped.fill(Path(MascotPaths.sheen()), with: .color(Color(nsColor: MascotPalette.sheen)))
            clipped.fill(Path(MascotPaths.crownPatch()), with: .color(Color(nsColor: MascotPalette.ginger)))
            clipped.stroke(Path(MascotPaths.crownStripes()),
                           with: .color(Color(nsColor: MascotPalette.gingerDark)),
                           style: StrokeStyle(lineWidth: MascotPaths.Crown.stripeWidth, lineCap: .round))
        }
        context.stroke(body, with: .color(Color(nsColor: MascotPalette.outline)),
                       style: StrokeStyle(lineWidth: MascotPaths.outlineWidth))

        drawCheeks(&context, mood: mood)
        context.stroke(Path(MascotPaths.whiskers()), with: .color(Color(nsColor: MascotPalette.whisker)),
                       style: StrokeStyle(lineWidth: MascotPaths.Whisker.width, lineCap: .round))
        drawEyes(&context, mood: mood)
        drawMouth(&context, mood: mood)
        context.fill(Path(MascotPaths.nose()), with: .color(Color(nsColor: MascotPalette.nose)))
        context.stroke(Path(MascotPaths.nose()), with: .color(Color(nsColor: MascotPalette.nose)),
                       style: StrokeStyle(lineWidth: 1, lineJoin: .round))
        drawPaws(&context, mood: mood)
    }

    private static func drawTail(_ context: inout GraphicsContext) {
        var tail = context
        tail.translateBy(x: MascotPaths.Tail.base.x, y: MascotPaths.Tail.base.y)
        let path = Path(MascotPaths.tail(.rest))
        tail.stroke(path, with: .color(Color(nsColor: MascotPalette.outline)),
                    style: StrokeStyle(lineWidth: MascotPaths.Tail.width + 2 * MascotPaths.outlineWidth,
                                       lineCap: .round))
        tail.stroke(path, with: .color(Color(nsColor: MascotPalette.cream)),
                    style: StrokeStyle(lineWidth: MascotPaths.Tail.width, lineCap: .round))
        tail.stroke(path.trimmedPath(from: MascotPaths.Tail.tipStart, to: 1),
                    with: .color(Color(nsColor: MascotPalette.ginger)),
                    style: StrokeStyle(lineWidth: MascotPaths.Tail.width, lineCap: .round))
    }

    private static func drawEar(_ context: inout GraphicsContext, mood: MascotMood, left: Bool) {
        let base = left ? MascotPaths.Ear.leftBase : MascotPaths.Ear.rightBase
        let pose = earPose(mood: mood, left: left)
        var ear = context
        ear.translateBy(x: base.x, y: base.y)
        ear.rotate(by: .radians(pose.angle))
        ear.scaleBy(x: 1, y: pose.stretch)
        let path = Path(MascotPaths.ear())
        ear.fill(path, with: .color(Color(nsColor: MascotPalette.ginger)))
        ear.stroke(path, with: .color(Color(nsColor: MascotPalette.outline)),
                   style: StrokeStyle(lineWidth: MascotPaths.outlineWidth, lineJoin: .round))
        ear.fill(Path(MascotPaths.innerEar()), with: .color(Color(nsColor: MascotPalette.innerEar)))
    }

    private static func earPose(mood: MascotMood, left: Bool) -> (angle: CGFloat, stretch: CGFloat) {
        typealias Ear = MascotPaths.Ear
        let tilt: CGFloat
        let stretch: CGFloat
        switch mood {
        case .listening:
            tilt = Ear.listenTilt
            stretch = Ear.listenStretch
        case .confused where left:
            tilt = Ear.droopTilt
            stretch = Ear.droopStretch
        case .sleeping:
            tilt = Ear.sleepTilt
            stretch = Ear.sleepStretch
        default:
            tilt = Ear.restTilt
            stretch = 1
        }
        return (left ? tilt : -tilt, stretch)
    }

    private static func drawCheeks(_ context: inout GraphicsContext, mood: MascotMood) {
        let alpha: CGFloat = mood == .success ? 0.62 : (mood == .sleeping ? 0.45 : 0.36)
        let blush = Color(nsColor: MascotPalette.blush.withAlphaComponent(alpha))
        for center in [MascotPaths.Face.cheekL, MascotPaths.Face.cheekR] {
            context.fill(Path(MascotPaths.cheek()).applying(
                CGAffineTransform(translationX: center.x, y: center.y)
            ), with: .color(blush))
        }
    }

    private static func drawEyes(_ context: inout GraphicsContext, mood: MascotMood) {
        if mood == .success || mood == .sleeping {
            let lid: MascotPaths.Lid = mood == .success ? .happy : .asleep
            for center in [MascotPaths.Eye.leftCenter, MascotPaths.Eye.rightCenter] {
                context.stroke(Path(MascotPaths.lid(lid, center: center)),
                               with: .color(Color(nsColor: MascotPalette.ink)),
                               style: StrokeStyle(lineWidth: MascotPaths.Eye.lidWidth, lineCap: .round))
            }
            return
        }

        let look = lookVector(mood: mood)
        let offset = CGPoint(x: look.dx * 3.2, y: look.dy * 2.6)
        for origin in [MascotPaths.Eye.leftCenter, MascotPaths.Eye.rightCenter] {
            let center = CGPoint(x: origin.x + offset.x, y: origin.y + offset.y)
            let eye = MascotPaths.Eye.bounds.offsetBy(dx: center.x, dy: center.y)
            context.fill(Path(ellipseIn: eye), with: .color(Color(nsColor: MascotPalette.ink)))
            for (rect, alpha) in MascotPaths.Eye.highlights {
                context.fill(Path(ellipseIn: rect.offsetBy(dx: center.x, dy: center.y)),
                             with: .color(Color.white.opacity(alpha)))
            }
        }
    }

    private static func drawMouth(_ context: inout GraphicsContext, mood: MascotMood) {
        if mood == .success {
            let scale: CGFloat = 0.6
            let center = MascotPaths.Mouth.openCenter
            let bounds = MascotPaths.Mouth.openBounds
            let open = CGRect(x: center.x + bounds.minX * scale, y: center.y + bounds.minY * scale,
                              width: bounds.width * scale, height: bounds.height * scale)
            context.fill(Path(ellipseIn: open), with: .color(Color(nsColor: MascotPalette.mouthInside)))
        }
        context.stroke(Path(mouthShape(mood: mood).path(center: MascotPaths.Face.mouth)),
                       with: .color(Color(nsColor: MascotPalette.ink)),
                       style: StrokeStyle(lineWidth: MascotPaths.Face.mouthLineWidth,
                                          lineCap: .round, lineJoin: .round))
    }

    private static func mouthShape(mood: MascotMood) -> MascotPaths.Mouth {
        switch mood {
        case .idle: return .smile
        case .listening, .acting: return .attentive
        case .thinking: return .flat
        case .success: return .grin
        case .confused: return .wavy
        case .sleeping: return .sleepy
        }
    }

    private static func lookVector(mood: MascotMood) -> CGVector {
        switch mood {
        case .thinking: return CGVector(dx: -0.55, dy: 0.85)
        case .listening: return CGVector(dx: 0, dy: 0.5)
        case .sleeping: return CGVector(dx: 0, dy: -0.3)
        default: return .zero
        }
    }

    private static func drawPaws(_ context: inout GraphicsContext, mood: MascotMood) {
        drawPaw(&context, center: MascotPaths.Paw.leftCenter, angle: 0)
        drawPaw(&context, center: mood == .thinking ? MascotPaths.Paw.chinCenter : MascotPaths.Paw.rightCenter,
                angle: mood == .thinking ? MascotPaths.Paw.chinTilt : 0)
    }

    private static func drawPaw(_ context: inout GraphicsContext, center: CGPoint, angle: CGFloat) {
        var paw = context
        paw.translateBy(x: center.x, y: center.y)
        paw.rotate(by: .radians(angle))
        let path = Path(MascotPaths.paw())
        paw.fill(path, with: .color(Color(nsColor: MascotPalette.paw)))
        paw.stroke(path, with: .color(Color(nsColor: MascotPalette.outline)),
                   style: StrokeStyle(lineWidth: MascotPaths.outlineWidth))
        paw.stroke(Path(MascotPaths.toes()), with: .color(Color(nsColor: MascotPalette.toe)),
                   style: StrokeStyle(lineWidth: MascotPaths.Paw.toeWidth, lineCap: .round))
    }
}
