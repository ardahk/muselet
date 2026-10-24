import AVFoundation
import FluidAudio
import Foundation
import Speech

/// Swappable on-device speech-to-text engine. Input is 16 kHz mono Float32.
protocol Transcriber: AnyObject {
    var displayName: String { get }
    /// Download (if needed), load and warm up. progress(fraction, phase).
    func prepare(progress: @escaping @Sendable (Double, String) -> Void) async throws
    func transcribe(_ samples: [Float]) async throws -> String
}

enum TranscriberError: LocalizedError {
    case notReady, unsupportedLocale, noFormat
    var errorDescription: String? {
        switch self {
        case .notReady: return "speech model not ready"
        case .unsupportedLocale: return "en-US not supported by SpeechTranscriber"
        case .noFormat: return "no compatible audio format"
        }
    }
}

// MARK: - FluidAudio Parakeet TDT v2 (Core ML, ANE)

final class ParakeetTranscriber: Transcriber {
    let displayName = "Parakeet TDT v2 · FluidAudio (ANE)"
    private var manager: AsrManager?
    private let version: AsrModelVersion = .v2

    func prepare(progress: @escaping @Sendable (Double, String) -> Void) async throws {
        let models = try await AsrModels.downloadAndLoad(version: version) { p in
            let phase: String
            switch p.phase {
            case .listing: phase = "Preparing download"
            case .downloading(let done, let total): phase = "Downloading model (\(done)/\(total) files)"
            case .compiling(let name): phase = "Compiling \(name)"
            }
            progress(p.fractionCompleted, phase)
        }
        progress(1, "Loading on the Neural Engine")
        let m = AsrManager(config: .default)
        try await m.loadModels(models)
        manager = m
        // Warm-up: first inference builds the ANE plan; keep it off the hot path.
        _ = try? await run(m, [Float](repeating: 0, count: 16_000))
    }

    func transcribe(_ samples: [Float]) async throws -> String {
        guard let m = manager else { throw TranscriberError.notReady }
        return try await run(m, samples)
    }

    private func run(_ m: AsrManager, _ samples: [Float]) async throws -> String {
        var audio = samples
        // Parakeet needs >= 0.3 s; pad short clips (and give the decoder a tail).
        let minCount = 16_000
        if audio.count < minCount { audio.append(contentsOf: [Float](repeating: 0, count: minCount - audio.count)) }
        var state = try TdtDecoderState(decoderLayers: version.decoderLayers)
        let r = try await m.transcribe(audio, decoderState: &state)
        return r.text.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

// MARK: - Apple SpeechAnalyzer / SpeechTranscriber fallback (macOS 26+)

final class AppleSpeechTranscriber: Transcriber {
    let displayName = "Apple SpeechTranscriber (on-device)"
    private var locale: Locale?
    private var format: AVAudioFormat?

    func prepare(progress: @escaping @Sendable (Double, String) -> Void) async throws {
        guard let loc = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: "en-US")) else {
            throw TranscriberError.unsupportedLocale
        }
        locale = loc
        let module = SpeechTranscriber(locale: loc, preset: .transcription)
        if let req = try await AssetInventory.assetInstallationRequest(supporting: [module]) {
            progress(0, "Downloading Apple speech assets")
            let prog = req.progress
            let obs = prog.observe(\.fractionCompleted) { p, _ in
                progress(p.fractionCompleted, "Downloading Apple speech assets")
            }
            try await req.downloadAndInstall()
            obs.invalidate()
        }
        format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [module])
        guard format != nil else { throw TranscriberError.noFormat }
        progress(1, "Ready")
    }

    func transcribe(_ samples: [Float]) async throws -> String {
        guard let loc = locale, let fmt = format else { throw TranscriberError.notReady }
        let module = SpeechTranscriber(locale: loc, preset: .transcription)
        let analyzer = SpeechAnalyzer(modules: [module])
        guard let buffer = Self.buffer(samples, to: fmt) else { throw TranscriberError.noFormat }
        let collector = Task { () -> String in
            var text = ""
            for try await r in module.results where r.isFinal {
                text += String(r.text.characters)
            }
            return text
        }
        let (stream, cont) = AsyncStream<AnalyzerInput>.makeStream()
        try await analyzer.start(inputSequence: stream)
        cont.yield(AnalyzerInput(buffer: buffer))
        cont.finish()
        try await analyzer.finalizeAndFinishThroughEndOfInput()
        return try await collector.value.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// 16 kHz mono Float32 -> the analyzer's preferred format.
    static func buffer(_ samples: [Float], to fmt: AVAudioFormat) -> AVAudioPCMBuffer? {
        guard !samples.isEmpty, let src = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16_000,
                                      channels: 1, interleaved: false),
              let inBuf = AVAudioPCMBuffer(pcmFormat: src, frameCapacity: AVAudioFrameCount(max(1, samples.count)))
        else { return nil }
        inBuf.frameLength = AVAudioFrameCount(samples.count)
        samples.withUnsafeBufferPointer { p in
            inBuf.floatChannelData![0].update(from: p.baseAddress!, count: samples.count)
        }
        if src == fmt { return inBuf }
        guard let conv = AVAudioConverter(from: src, to: fmt) else { return nil }
        let cap = AVAudioFrameCount(Double(samples.count) * fmt.sampleRate / 16_000 + 64)
        guard let out = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: cap) else { return nil }
        var fed = false
        var err: NSError?
        conv.convert(to: out, error: &err) { _, status in
            if fed { status.pointee = .endOfStream; return nil }
            fed = true
            status.pointee = .haveData
            return inBuf
        }
        return err == nil ? out : nil
    }
}
