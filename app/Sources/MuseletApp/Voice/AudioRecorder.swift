import AVFoundation
import Foundation
import QuartzCore

/// Push-to-talk capture: AVAudioEngine input tap converted to 16 kHz mono
/// Float32. The engine only runs while the key is held (mic indicator off
/// otherwise), but it is kept *prepared* between presses (input node, tap,
/// converter and `prepare()` done ahead of time) so a press only pays
/// `engine.start()` (ux-7). Start/stop run on a serial audio queue so the
/// main thread (listening mood, bubble) never waits on Core Audio.
/// Level callbacks (0...1, perceptual) arrive on the main queue.
final class AudioRecorder {
    static let sampleRate: Double = 16_000

    var onLevel: ((Float) -> Void)?
    /// Main queue: first captured buffer of a press, ms after `keyDownAt`.
    var onFirstBuffer: ((_ ms: Double) -> Void)?

    private let queue = DispatchQueue(label: "ai.muselet.audio", qos: .userInteractive)
    // Audio-queue state.
    private var engine = AVAudioEngine()
    private var converter: AVAudioConverter?
    private var tapInstalled = false
    private var prepared = false
    private var running = false
    private var needsRebuild = false
    private var configObserver: NSObjectProtocol?

    private let target = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: AudioRecorder.sampleRate,
                                       channels: 1, interleaved: false)!
    // Shared with the tap thread (lock).
    private let lock = NSLock()
    private var samples: [Float] = []
    private var capturing = false
    private var keyDownAt: CFTimeInterval = 0
    private var firstBufferSeen = true
    private var lastLevelAt: CFTimeInterval = 0

    /// Main-thread view of "a press is capturing".
    private(set) var isRunning = false

    init() {
        observeConfig(engine)
    }

    private func observeConfig(_ e: AVAudioEngine) {
        if let o = configObserver { NotificationCenter.default.removeObserver(o) }
        configObserver = NotificationCenter.default.addObserver(
            forName: .AVAudioEngineConfigurationChange, object: e, queue: nil) { [weak self] _ in
            guard let self else { return }
            self.queue.async {
                self.needsRebuild = true
                // Device changed while idle: re-warm now, off the hot path.
                if !self.running { self.warmLocked() }
            }
        }
    }

    /// Build + prepare the engine ahead of the next press (mic permission
    /// must already be granted). Cheap if already warm.
    func warmUp() {
        queue.async { self.warmLocked() }
    }

    /// Audio queue. Engine graph (input node, converter, tap) + prepare().
    private func warmLocked() {
        if needsRebuild {
            if tapInstalled { engine.inputNode.removeTap(onBus: 0) }
            engine.stop()
            engine = AVAudioEngine()
            tapInstalled = false
            prepared = false
            needsRebuild = false
            let e = engine
            DispatchQueue.main.async { self.observeConfig(e) }
        }
        if !tapInstalled {
            let input = engine.inputNode
            let fmt = input.outputFormat(forBus: 0)
            guard fmt.sampleRate > 0, fmt.channelCount > 0 else { return }
            converter = AVAudioConverter(from: fmt, to: target)
            input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buf, _ in
                self?.process(buf)
            }
            tapInstalled = true
            prepared = false
        }
        if !prepared {
            engine.prepare()
            prepared = true
        }
    }

    /// Start capturing (returns at once; the engine starts on the audio
    /// queue). `completion` runs on main with nil or the start error.
    func start(keyDownAt: CFTimeInterval, completion: @escaping (Error?) -> Void) {
        isRunning = true
        lock.lock()
        samples.removeAll(keepingCapacity: true)
        samples.reserveCapacity(16_000 * 20)
        self.keyDownAt = keyDownAt
        firstBufferSeen = false
        capturing = true
        lock.unlock()
        queue.async {
            var err: Error?
            if !self.running {
                self.warmLocked()
                if !self.tapInstalled {
                    err = NSError(domain: "muselet.audio", code: 1,
                                  userInfo: [NSLocalizedDescriptionKey: "no microphone input available"])
                } else {
                    do {
                        try self.engine.start()
                        self.running = true
                    } catch {
                        err = error
                        // Next press starts from a fresh engine.
                        self.needsRebuild = true
                    }
                }
            }
            if err != nil {
                self.lock.lock(); self.capturing = false; self.lock.unlock()
            }
            DispatchQueue.main.async {
                if err != nil { self.isRunning = false }
                completion(err)
            }
        }
    }

    /// Stop and return everything captured (16 kHz mono). Waits for a
    /// pending start; re-prepares the engine for the next press afterwards.
    func stop() -> [Float] {
        isRunning = false
        queue.sync {
            lock.lock(); capturing = false; lock.unlock()
            if running {
                engine.stop()           // releases prepared resources
                running = false
                prepared = false
            }
        }
        queue.async { self.warmLocked() }   // ready for the next press
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
        lock.lock()
        let live = capturing
        var firstMs: Double?
        if live && !firstBufferSeen {
            firstBufferSeen = true
            firstMs = (CACurrentMediaTime() - keyDownAt) * 1000
        }
        lock.unlock()
        guard live, let converter else { return }
        if let ms = firstMs { DispatchQueue.main.async { [weak self] in self?.onFirstBuffer?(ms) } }
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
        lock.lock()
        if capturing { samples.append(contentsOf: ptr) }
        lock.unlock()

        let now = CACurrentMediaTime()
        guard now - lastLevelAt > 1.0 / 30 else { return }
        lastLevelAt = now
        let rms = sqrt(sum / Float(max(1, n)))
        let db = 20 * log10(max(rms, 1e-6))
        let level = max(0, min(1, (db + 52) / 40))   // -52 dB..-12 dB -> 0..1
        DispatchQueue.main.async { [weak self] in self?.onLevel?(level) }
    }
}
