import AppKit
import CoreGraphics
import Foundation
import ScreenCaptureKit

public enum ScreenshotError: Error, CustomStringConvertible {
    case noScreenPermission, noWindow, noDisplay, captureFailed(String)
    public var description: String {
        switch self {
        case .noScreenPermission: return "screen recording permission missing"
        case .noWindow: return "no capturable window"
        case .noDisplay: return "no display"
        case .captureFailed(let s): return "capture failed: \(s)"
        }
    }
}

public struct ShotResult {
    public var path: String
    public var width: Int
    public var height: Int
    public var origin: [Double]
    public var scale: Double
}

public enum Screenshot {
    /// Capture the focused window (windowOnly=true) or the main display.
    /// Excludes windows owned by `excludeBundleId`. Downscales to maxPixels.
    public static func capture(windowOnly: Bool, maxPixels: Int,
                               excludeBundleId: String?,
                               outDir: URL) async throws -> ShotResult {
        guard CGPreflightScreenCaptureAccess() else {
            throw ScreenshotError.noScreenPermission
        }
        let content = try await SCShareableContent.excludingDesktopWindows(
            false, onScreenWindowsOnly: true)
        let others = content.windows.filter {
            guard let bid = $0.owningApplication?.bundleIdentifier else { return false }
            return bid == excludeBundleId
        }

        let filter: SCContentFilter
        var srcRectPts = CGRect.zero
        if windowOnly {
            // Frontmost app's first on-screen window.
            guard let front = NSWorkspace.shared.frontmostApplication else {
                throw ScreenshotError.noWindow
            }
            guard let win = content.windows.first(where: {
                $0.owningApplication?.processID == front.processIdentifier
                    && $0.isOnScreen && $0.frame.width > 1 && $0.frame.height > 1
            }) else { throw ScreenshotError.noDisplay }
            filter = SCContentFilter(desktopIndependentWindow: win)
            srcRectPts = win.frame
        } else {
            guard let display = content.displays.first else { throw ScreenshotError.noDisplay }
            filter = SCContentFilter(display: display, excludingWindows: others)
            srcRectPts = CGRect(x: 0, y: 0,
                                width: CGFloat(display.width), height: CGFloat(display.height))
        }

        let scale = min(1.0, sqrt(Double(maxPixels) /
                                  Double(max(1.0, srcRectPts.width * srcRectPts.height))))
        let cfg = SCStreamConfiguration()
        cfg.width = Int((srcRectPts.width * scale).rounded())
        cfg.height = Int((srcRectPts.height * scale).rounded())
        cfg.showsCursor = false
        cfg.scalesToFit = true

        let img = try await SCScreenshotManager.captureImage(
            contentFilter: filter, configuration: cfg)
        let w = img.width, h = img.height

        try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
        let path = outDir.appendingPathComponent(
            "hands-shot-\(Int(Date().timeIntervalSince1970 * 1000)).png")
        guard let dest = CGImageDestinationCreateWithURL(
            path as CFURL, "public.png" as CFString, 1, nil) else {
            throw ScreenshotError.captureFailed("image destination")
        }
        CGImageDestinationAddImage(dest, img, nil)
        guard CGImageDestinationFinalize(dest) else {
            throw ScreenshotError.captureFailed("png write")
        }
        return ShotResult(path: path.path, width: w, height: h,
                          origin: [Double(srcRectPts.minX), Double(srcRectPts.minY)],
                          scale: Double(w) / Double(max(1.0, srcRectPts.width)))
    }

    /// Blocking wrapper for sync call sites.
    public static func captureSync(windowOnly: Bool, maxPixels: Int,
                                   excludeBundleId: String?,
                                   outDir: URL) throws -> ShotResult {
        var result: Result<ShotResult, Error>!
        let sem = DispatchSemaphore(value: 0)
        Task {
            do {
                result = .success(try await capture(
                    windowOnly: windowOnly, maxPixels: maxPixels,
                    excludeBundleId: excludeBundleId, outDir: outDir))
            } catch { result = .failure(error) }
            sem.signal()
        }
        _ = sem.wait(timeout: .now() + 10)
        guard let r = result else { throw ScreenshotError.captureFailed("timeout") }
        return try r.get()
    }
}
