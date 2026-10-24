import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import ScreenCaptureKit

public enum ScreenshotError: Error, CustomStringConvertible {
    case noScreenPermission, noWindow, noDisplay, badRegion, captureFailed(String)
    public var description: String {
        switch self {
        case .noScreenPermission: return "screen recording permission missing"
        case .noWindow: return "no capturable window"
        case .noDisplay: return "no display"
        case .badRegion: return "region must be [x,y,w,h] with w,h > 0 on a display"
        case .captureFailed(let s): return "capture failed: \(s)"
        }
    }
}

public struct ShotResult {
    public var path: String
    public var width: Int
    public var height: Int
    /// Global top-left point (AX space) of the image's top-left pixel.
    public var origin: [Double]
    /// Pixels per point: global = origin + px / scale.
    public var scale: Double
}

/// In-memory capture (used by OCR on a region).
public struct ShotImage {
    public var image: CGImage
    public var origin: CGPoint
    public var scale: Double
}

public enum Screenshot {
    // MARK: pure helpers (unit-tested)

    public struct DisplayInfo: Equatable {
        public var id: CGDirectDisplayID
        public var frame: CGRect      // global top-left points (CGDisplayBounds)
        public var backing: Double    // pixels per point
        public init(id: CGDirectDisplayID, frame: CGRect, backing: Double) {
            self.id = id; self.frame = frame; self.backing = backing
        }
    }

    /// Display containing `p`, else the nearest one.
    public static func display(containing p: CGPoint, in displays: [DisplayInfo]) -> DisplayInfo? {
        if let d = displays.first(where: { $0.frame.contains(p) }) { return d }
        func d2(_ r: CGRect) -> CGFloat {
            let dx = max(r.minX - p.x, 0, p.x - r.maxX)
            let dy = max(r.minY - p.y, 0, p.y - r.maxY)
            return dx * dx + dy * dy
        }
        return displays.min { d2($0.frame) < d2($1.frame) }
    }

    /// Output pixel size for `source` points at `backing` px/pt, capped so
    /// width*height <= maxPixels (aspect preserved).
    public static func pixelSize(source: CGRect, backing: Double, maxPixels: Int) -> (Int, Int) {
        let pw = Double(source.width) * backing, ph = Double(source.height) * backing
        let k = min(1.0, sqrt(Double(max(1, maxPixels)) / max(1.0, pw * ph)))
        return (max(1, Int((pw * k).rounded())), max(1, Int((ph * k).rounded())))
    }

    /// Frontmost matching window from a CGWindowListCopyWindowInfo list
    /// (front-to-back order): owned by `pid`, layer 0, visible, non-trivial.
    /// Prefers the one whose bounds match the AX focused window frame.
    public static func pickWindow(cgList: [[String: Any]], pid: pid_t,
                                  axFrame: CGRect?) -> CGWindowID? {
        var candidates: [(CGWindowID, CGRect)] = []
        for w in cgList {
            guard let owner = (w[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value,
                  owner == pid,
                  ((w[kCGWindowLayer as String] as? NSNumber)?.intValue ?? 0) == 0,
                  let num = (w[kCGWindowNumber as String] as? NSNumber)?.uint32Value,
                  let bd = w[kCGWindowBounds as String] as? NSDictionary,
                  let r = CGRect(dictionaryRepresentation: bd as CFDictionary),
                  r.width > 1, r.height > 1 else { continue }
            if let a = w[kCGWindowAlpha as String] as? NSNumber, a.doubleValue <= 0 { continue }
            candidates.append((num, r))
        }
        if let ax = axFrame, ax.width > 1 {
            if let hit = candidates.first(where: { _, r in
                abs(r.minX - ax.minX) <= 4 && abs(r.minY - ax.minY) <= 4
                    && abs(r.width - ax.width) <= 4 && abs(r.height - ax.height) <= 4
            }) { return hit.0 }
        }
        return candidates.first?.0
    }

    // MARK: live geometry

    public static func activeDisplays() -> [DisplayInfo] {
        var count: UInt32 = 0
        CGGetActiveDisplayList(0, nil, &count)
        guard count > 0 else { return [] }
        var ids = [CGDirectDisplayID](repeating: 0, count: Int(count))
        CGGetActiveDisplayList(count, &ids, &count)
        return ids.prefix(Int(count)).map { id in
            let b = CGDisplayBounds(id)
            var backing = 1.0
            if let mode = CGDisplayCopyDisplayMode(id), b.width > 0 {
                backing = Double(mode.pixelWidth) / Double(b.width)
            }
            return DisplayInfo(id: id, frame: b, backing: backing)
        }
    }

    /// AX focused (else main, else frontmost AXWindows) window frame of
    /// `pid`, global top-left points.
    public static func focusedWindowFrame(pid: pid_t) -> CGRect? {
        guard pid > 0 else { return nil }
        let app = AXNode(AXUIElementCreateApplication(pid))
        app.setMessagingTimeout(0.25)
        guard let w = Hands.pickWindow(app: app)?.window else { return nil }
        let f = w.copyAttrs().frame
        return f.width > 0 ? f : nil
    }

    // MARK: capture

    /// Capture to memory.
    ///  - region (global points): that area of the display containing its
    ///    centre (clamped to it), at the display's backing scale.
    ///  - windowOnly: the target app's frontmost (AX-focused) window.
    ///  - else: the whole display containing the target app's focused window.
    /// Windows owned by `excludeBundleId` (and this process) are excluded.
    public static func captureImage(windowOnly: Bool, region: CGRect? = nil,
                                    maxPixels: Int, excludeBundleId: String?,
                                    targetPid: pid_t? = nil) async throws -> ShotImage {
        guard CGPreflightScreenCaptureAccess() else {
            throw ScreenshotError.noScreenPermission
        }
        let content = try await SCShareableContent.excludingDesktopWindows(
            false, onScreenWindowsOnly: true)
        let me = getpid()
        let own = content.windows.filter {
            guard let app = $0.owningApplication else { return false }
            return app.processID == me
                || (excludeBundleId != nil && app.bundleIdentifier == excludeBundleId)
        }
        let displays = activeDisplays()
        let pid = targetPid ?? NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0

        let filter: SCContentFilter
        let cfg = SCStreamConfiguration()
        cfg.showsCursor = false
        cfg.scalesToFit = true
        var src: CGRect
        var backing = 1.0

        if let region {
            guard region.width > 0, region.height > 0,
                  let d = display(containing: CGPoint(x: region.midX, y: region.midY), in: displays),
                  let scd = content.displays.first(where: { $0.displayID == d.id }) else {
                throw ScreenshotError.badRegion
            }
            src = region.intersection(d.frame)
            guard !src.isNull, src.width >= 1, src.height >= 1 else { throw ScreenshotError.badRegion }
            backing = d.backing
            filter = SCContentFilter(display: scd, excludingWindows: own)
            cfg.sourceRect = CGRect(x: src.minX - d.frame.minX, y: src.minY - d.frame.minY,
                                    width: src.width, height: src.height)
        } else if windowOnly {
            let ax = focusedWindowFrame(pid: pid)
            let list = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                                   kCGNullWindowID) as? [[String: Any]]) ?? []
            let wid = pickWindow(cgList: list, pid: pid, axFrame: ax)
            guard let win = content.windows.first(where: { wid != nil && $0.windowID == wid })
                ?? content.windows.first(where: {
                    $0.owningApplication?.processID == pid && $0.windowLayer == 0
                        && $0.isOnScreen && $0.frame.width > 1 && $0.frame.height > 1
                }) else { throw ScreenshotError.noWindow }
            filter = SCContentFilter(desktopIndependentWindow: win)
            src = win.frame
            backing = display(containing: CGPoint(x: src.midX, y: src.midY), in: displays)?.backing ?? 1
        } else {
            let anchor = focusedWindowFrame(pid: pid).map { CGPoint(x: $0.midX, y: $0.midY) }
                ?? CGDisplayBounds(CGMainDisplayID()).origin
            guard let d = display(containing: anchor, in: displays),
                  let scd = content.displays.first(where: { $0.displayID == d.id })
                    ?? content.displays.first else {
                throw ScreenshotError.noDisplay
            }
            filter = SCContentFilter(display: scd, excludingWindows: own)
            src = CGDisplayBounds(scd.displayID)
            backing = d.backing
        }

        let (w, h) = pixelSize(source: src, backing: backing, maxPixels: maxPixels)
        cfg.width = w
        cfg.height = h
        let img = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: cfg)
        return ShotImage(image: img, origin: src.origin,
                         scale: Double(img.width) / Double(max(1.0, src.width)))
    }

    /// Capture and write a PNG to `outDir`.
    public static func capture(windowOnly: Bool, region: CGRect? = nil, maxPixels: Int,
                               excludeBundleId: String?, targetPid: pid_t? = nil,
                               outDir: URL) async throws -> ShotResult {
        let shot = try await captureImage(windowOnly: windowOnly, region: region,
                                          maxPixels: maxPixels, excludeBundleId: excludeBundleId,
                                          targetPid: targetPid)
        try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
        let path = outDir.appendingPathComponent(
            "hands-shot-\(Int(Date().timeIntervalSince1970 * 1000)).png")
        guard let dest = CGImageDestinationCreateWithURL(
            path as CFURL, "public.png" as CFString, 1, nil) else {
            throw ScreenshotError.captureFailed("image destination")
        }
        CGImageDestinationAddImage(dest, shot.image, nil)
        guard CGImageDestinationFinalize(dest) else {
            throw ScreenshotError.captureFailed("png write")
        }
        return ShotResult(path: path.path, width: shot.image.width, height: shot.image.height,
                          origin: [Double(shot.origin.x), Double(shot.origin.y)],
                          scale: shot.scale)
    }

    /// Blocking wrapper for sync call sites.
    public static func captureSync(windowOnly: Bool, region: CGRect? = nil, maxPixels: Int,
                                   excludeBundleId: String?, targetPid: pid_t? = nil,
                                   outDir: URL) throws -> ShotResult {
        try blocking {
            try await capture(windowOnly: windowOnly, region: region, maxPixels: maxPixels,
                              excludeBundleId: excludeBundleId, targetPid: targetPid,
                              outDir: outDir)
        }
    }

    /// Blocking in-memory capture.
    public static func captureImageSync(windowOnly: Bool, region: CGRect? = nil, maxPixels: Int,
                                        excludeBundleId: String?,
                                        targetPid: pid_t? = nil) throws -> ShotImage {
        try blocking {
            try await captureImage(windowOnly: windowOnly, region: region, maxPixels: maxPixels,
                                   excludeBundleId: excludeBundleId, targetPid: targetPid)
        }
    }

    private final class Box<T>: @unchecked Sendable {
        var r: Result<T, Error>?
    }

    private static func blocking<T>(_ body: @escaping () async throws -> T) throws -> T {
        let box = Box<T>()
        let sem = DispatchSemaphore(value: 0)
        Task {
            do { box.r = .success(try await body()) } catch { box.r = .failure(error) }
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 10)
        guard let r = box.r else { throw ScreenshotError.captureFailed("timeout") }
        return try r.get()
    }
}

/// Parse a JSON `[x,y,w,h]` region (numbers) into a CGRect.
func rectParam(_ p: [String: Any], _ k: String) -> CGRect? {
    guard let a = p[k] as? [Any], a.count == 4 else { return nil }
    let v = a.compactMap { x -> Double? in
        if let n = x as? NSNumber { return n.doubleValue }
        if let s = x as? String { return Double(s) }
        return nil
    }
    guard v.count == 4 else { return nil }
    return CGRect(x: v[0], y: v[1], width: v[2], height: v[3])
}
