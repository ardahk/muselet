import AVFoundation
import Foundation
import QuartzCore

/// Push-to-talk capture: AVAudioEngine input tap converted to 16 kHz mono
/// Float32. The engine only runs while the key is held (mic indicator off
/// otherwise). Level callbacks (0...1, perceptual) arrive on the main queue.
final class AudioRecorder {
    static let sampleRate: Double = 16_000

    var onLevel: ((Float) -> Void)?

    private var engine = AVAudioEngine()
    private var converter: AVAudioConverter?
    private let target = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: AudioRecorder.sampleRate,
                                       channels: 1, interleaved: false)!
    private let lock = NSLock()
    private var samples: [Float] = []
    private(set) var isRunning = false
    private var configObserver: NSObjectProtocol?
    private var needsRebuild = false
    private var lastLevelAt: CFTimeInterval = 0

    init() {
        observeConfig()
    }

    private func observeConfig() {
        if let o = configObserver { NotificationCenter.default.removeObserver(o) }
        configObserver = NotificationCenter.default.addObserver(
            forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main) { [weak self] _ in
            self?.needsRebuild = true
        }
    }

    func start() throws {
        guard !isRunning else { return }
        if needsRebuild {
            engine = AVAudioEngine()
            observeConfig()
            needsRebuild = false
        }
        lock.lock(); samples.removeAll(keepingCapacity: true); samples.reserveCapacity(16_000 * 20); lock.unlock()
        let input = engine.inputNode
        let fmt = input.outputFormat(forBus: 0)
        guard fmt.sampleRate > 0, fmt.channelCount > 0 else {
            throw NSError(domain: "muselet.audio", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "no microphone input available"])
        }
        converter = AVAudioConverter(from: fmt, to: target)
        input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buf, _ in
            self?.process(buf)
        }
        engine.prepare()
        do {
            try engine.start()
        } catch {
            input.removeTap(onBus: 0)
            throw error
        }
        isRunning = true
    }

    /// Stop and return everything captured (16 kHz mono).
    func stop() -> [Float] {
        if isRunning {
            engine.inputNode.removeTap(onBus: 0)
            engine.stop()
            isRunning = false
        }
        lock.lock(); defer { lock.unlock() }
        return samples
    }

    func snapshot() -> [Float] {
        lock.lock(); defer { lock.unlock() }
        return samples
    }

    var capturedSeconds: Double {
        lock.lock(); defer { lock.unlock() }
        return Double(samples.count) / Self.sampleRate
    }

    private func process(_ buf: AVAudioPCMBuffer) {
        guard let converter else { return }
        let ratio = target.sampleRate / buf.format.sampleRate
        let cap = AVAudioFrameCount(Double(buf.frameLength) * ratio + 32)
        guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: cap) else { return }
        var fed = false
        var err: NSError?
        converter.convert(to: out, error: &err) { _, status in
            if fed { status.pointee = .noDataNow; return nil }
            fed = true
            status.pointee = .haveData
            return buf
        }
        guard err == nil, let ch = out.floatChannelData else { return }
        let n = Int(out.frameLength)
        let ptr = UnsafeBufferPointer(start: ch[0], count: n)
        var sum: Float = 0
        for v in ptr { sum += v * v }
        lock.lock(); samples.append(contentsOf: ptr); lock.unlock()

        let now = CACurrentMediaTime()
        guard now - lastLevelAt > 1.0 / 30 else { return }
        lastLevelAt = now
        let rms = sqrt(sum / Float(max(1, n)))
        let db = 20 * log10(max(rms, 1e-6))
        let level = max(0, min(1, (db + 52) / 40))   // -52 dB..-12 dB -> 0..1
        DispatchQueue.main.async { [weak self] in self?.onLevel?(level) }
    }
}
