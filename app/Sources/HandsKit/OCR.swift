import CoreGraphics
import Foundation
import ImageIO
import Vision

public enum OCRError: Error, CustomStringConvertible {
    case badInput(String)
    case failed(String)
    public var description: String {
        switch self {
        case .badInput(let s): return "ocr: \(s)"
        case .failed(let s): return "ocr failed: \(s)"
        }
    }
}

/// Apple Vision text recognition (accurate, en-US, language correction).
public enum OCR {
    public struct Line: Equatable {
        public var text: String
        /// Top-left origin; image pixels for `path`, global points for `region`.
        public var frame: CGRect
        public var confidence: Float
    }

    /// Recognize text lines in `image`; frames in image pixels, top-left
    /// origin, sorted top-to-bottom then left-to-right.
    public static func recognize(_ image: CGImage) throws -> [Line] {
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.recognitionLanguages = ["en-US"]
        req.usesLanguageCorrection = true
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        do { try handler.perform([req]) } catch { throw OCRError.failed("\(error)") }
        let W = CGFloat(image.width), H = CGFloat(image.height)
        var lines: [Line] = []
        for o in req.results ?? [] {
            guard let c = o.topCandidates(1).first else { continue }
            let bb = o.boundingBox     // normalized, bottom-left origin
            let f = CGRect(x: bb.minX * W, y: (1 - bb.maxY) * H,
                           width: bb.width * W, height: bb.height * H)
            lines.append(Line(text: c.string, frame: f, confidence: c.confidence))
        }
        return sortReadingOrder(lines)
    }

    /// Cluster lines into visual rows (vertical centre within half a line
    /// height of the row's first line), rows top-to-bottom, each row
    /// left-to-right.
    static func rows(_ lines: [Line]) -> [[Line]] {
        var rows: [[Line]] = []
        for l in lines.sorted(by: { $0.frame.midY < $1.frame.midY }) {
            if let ref = rows.last?.first,
               abs(ref.frame.midY - l.frame.midY) <= min(ref.frame.height, l.frame.height) * 0.5 {
                rows[rows.count - 1].append(l)
            } else {
                rows.append([l])
            }
        }
        return rows.map { $0.sorted { $0.frame.minX < $1.frame.minX } }
    }

    static func sortReadingOrder(_ lines: [Line]) -> [Line] { rows(lines).flatMap { $0 } }

    /// Join lines into text: segments on the same row are joined with two
    /// spaces ("TOTAL  $41.20"), rows with newlines.
    public static func joinRows(_ lines: [Line]) -> String {
        rows(lines).map { $0.map(\.text).joined(separator: "  ") }.joined(separator: "\n")
    }

    public static func loadImage(path: String) throws -> CGImage {
        let url = URL(fileURLWithPath: (path as NSString).expandingTildeInPath)
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
              let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
            throw OCRError.badInput("cannot read image at \(path)")
        }
        return img
    }

    /// RPC payload: {text, lines:[{text, frame:[x,y,w,h], confidence}], ms, coords}.
    /// `path`: frames in image pixels. `region` (global points): the screen
    /// area is captured first and frames are mapped back to global points.
    public static func run(path: String?, region: CGRect?,
                           excludeBundleId: String?) throws -> [String: Any] {
        let t0 = Date()
        var lines: [Line]
        var coords = "image_px"
        if let path {
            lines = try recognize(try loadImage(path: path))
        } else if let region {
            let shot = try Screenshot.captureImageSync(
                windowOnly: false, region: region, maxPixels: 8_000_000,
                excludeBundleId: excludeBundleId)
            let k = CGFloat(max(shot.scale, 0.0001))
            lines = try recognize(shot.image).map { l in
                var g = l
                g.frame = CGRect(x: shot.origin.x + l.frame.minX / k,
                                 y: shot.origin.y + l.frame.minY / k,
                                 width: l.frame.width / k, height: l.frame.height / k)
                return g
            }
            coords = "screen_pt"
        } else {
            throw OCRError.badInput("needs path or region:[x,y,w,h]")
        }
        func r2(_ v: CGFloat) -> Double { (Double(v) * 10).rounded() / 10 }
        return [
            "text": joinRows(lines),
            "lines": lines.map { l -> [String: Any] in
                ["text": l.text,
                 "frame": [r2(l.frame.minX), r2(l.frame.minY), r2(l.frame.width), r2(l.frame.height)],
                 "confidence": (Double(l.confidence) * 100).rounded() / 100]
            },
            "coords": coords,
            "ms": (Date().timeIntervalSince(t0) * 1000).rounded(to: 1),
        ]
    }
}
