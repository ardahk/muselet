import AppKit
import AVFoundation
import QuartzCore

/// Push-to-talk pipeline: Right ⌥ down -> capture (+ live partials) ->
/// release -> final transcript -> utterance (or confirm answer).
final class VoiceController {
    private let model: AppModel
    let recorder = AudioRecorder()
    let ptt = PushToTalkMonitor()

    weak var brain: BrainConnection?
    weak var mascot: MascotController?
    var onConfirmAnswer: ((Bool) -> Void)?

    private(set) var transcriber: Transcriber?
    private let parakeet = ParakeetTranscriber()
    private var apple: AppleSpeechTranscriber?
    private var partialTask: Task<Void, Never>?
    private var counter = 0
    private var currentID: String?
    private var lastPartial = ""
    private var moodBeforeListening: MascotMood = .idle
    /// Keep capturing briefly after release so the last syllable isn't clipped.
    private let releaseTail: TimeInterval = 0.06

    init(model: AppModel) {
        self.model = model
    }

    func start() {
        recorder.onLevel = { [weak self] v in
            guard let self, self.model.isRecording else { return }
            self.model.micLevel = v
            self.model.levelSubject.send(v)
        }
        ptt.onPress = { [weak self] in self?.pressBegan() }
        ptt.onRelease = { [weak self] in self?.pressEnded() }
        ptt.onChord = { [weak self] in self?.abortRecording(hint: nil) }
        ptt.onEscape = { [weak self] in self?.escape() }
        startHotkey()
        prepareSTT()
    }

    /// (Re)try the event tap; called again whenever permissions change.
    func startHotkey() {
        let ok = ptt.start()
        if model.pushToTalkActive != ok { model.pushToTalkActive = ok }
        if !ok {
            FileLog.shared.raw("push-to-talk tap unavailable (needs Input Monitoring or Accessibility)")
        }
    }

    // MARK: STT engine

    private func prepareSTT() {
        model.sttEngine = parakeet.displayName
        model.sttState = .loading("Checking model cache")
        let progress = Self.progressSink(model: model)
        Task.detached(priority: .userInitiated) { [weak self] in
            guard let self else { return }
            let t0 = CACurrentMediaTime()
            do {
                try await self.parakeet.prepare(progress: progress)
                let ms = (CACurrentMediaTime() - t0) * 1000
                await MainActor.run {
                    self.transcriber = self.parakeet
                    self.model.sttState = .ready
                    self.model.log(.stt, "Parakeet TDT v2 ready", ms: ms)
                }
            } catch {
                await MainActor.run {
                    self.model.log(.error, "FluidAudio failed: \(error.localizedDescription) — using Apple Speech")
                }
                await self.prepareApple()
            }
        }
    }

    private func prepareApple() async {
        let a = AppleSpeechTranscriber()
        await MainActor.run {
            self.apple = a
            self.model.sttEngine = a.displayName
            self.model.sttState = .loading("Preparing Apple Speech")
        }
        do {
            try await a.prepare(progress: Self.progressSink(model: model))
            await MainActor.run {
                self.transcriber = a
                self.model.sttState = .ready
                self.model.log(.stt, "Apple SpeechTranscriber ready")
            }
        } catch {
            await MainActor.run {
                self.model.sttState = .failed(error.localizedDescription)
                self.model.log(.error, "speech engine unavailable: \(error.localizedDescription)")
            }
        }
    }

    private static func progressSink(model: AppModel) -> @Sendable (Double, String) -> Void {
        let gate = ProgressGate()
        return { f, phase in
            guard gate.shouldEmit(f, phase) else { return }
            DispatchQueue.main.async {
                if phase.hasPrefix("Downloading") || phase.hasPrefix("Preparing download") {
                    model.sttState = .downloading(f, phase)
                } else {
                    model.sttState = .loading(phase)
                }
            }
        }
    }

    // MARK: push-to-talk

    private func pressBegan() {
        guard !model.isRecording else { return }
        mascot?.wake()
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    self.model.permissions = Permissions.snapshot()
                    self.mascot?.showBubble(granted ? "Mic is on. Hold right ⌥ again and talk to me."
                                                    : "I need the microphone to hear you.",
                                            style: .hint)
                }
            }
            return
        case .denied, .restricted:
            model.mood = .confused
            mascot?.showBubble("Microphone access is off. Open muselet in the menu bar to grant it.", style: .hint)
            return
        default:
            break
        }
        do {
            try recorder.start()
        } catch {
            model.mood = .confused
            mascot?.showBubble("Mic error: \(error.localizedDescription)", style: .hint)
            model.log(.error, "mic start failed: \(error.localizedDescription)")
            return
        }
        counter += 1
        currentID = "u\(counter)-\(Int(Date().timeIntervalSince1970) % 100_000)"
        lastPartial = ""
        model.isRecording = true
        model.micLevel = 0
        if model.mood != .listening { moodBeforeListening = model.mood }
        model.mood = .listening
        mascot?.showBubble("", style: .transcript, autoHide: false)
        startPartials()
    }

    private func pressEnded() {
        guard model.isRecording else { return }
        let releasedAt = CACurrentMediaTime()
        DispatchQueue.main.asyncAfter(deadline: .now() + releaseTail) { [weak self] in
            self?.finish(releasedAt: releasedAt)
        }
    }

    private func startPartials() {
        partialTask?.cancel()
        guard let tr = transcriber, tr is ParakeetTranscriber else { return }
        let id = currentID
        partialTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 450_000_000)
                guard let self, !Task.isCancelled, self.model.isRecording, self.currentID == id else { return }
                let snap = self.recorder.snapshot()
                guard snap.count >= 9_600 else { continue }   // >= 0.6 s
                guard let text = try? await tr.transcribe(snap), !Task.isCancelled else { continue }
                guard self.model.isRecording, self.currentID == id, !text.isEmpty, text != self.lastPartial else { continue }
                self.lastPartial = text
                self.mascot?.showBubble(text, style: .transcript, autoHide: false)
                if self.model.pendingConfirm == nil, let id {
                    self.brain?.sendUtterance(id: id, text: text, final: false)
                }
            }
        }
    }

    private func finish(releasedAt: CFTimeInterval) {
        partialTask?.cancel()
        partialTask = nil
        let samples = recorder.stop()
        model.isRecording = false
        model.micLevel = 0
        let seconds = Double(samples.count) / AudioRecorder.sampleRate
        guard seconds >= 0.3 else {
            model.mood = moodBeforeListening == .listening ? .idle : moodBeforeListening
            restoreBubbleAfterVoice(hint: "Hold right ⌥ while you speak.")
            return
        }
        guard let tr = transcriber else {
            model.mood = .idle
            restoreBubbleAfterVoice(hint: sttNotReadyHint())
            return
        }
        let id = currentID ?? "u\(counter)"
        model.mood = .thinking
        Task { @MainActor [weak self] in
            let t0 = CACurrentMediaTime()
            let result: Result<String, Error>
            do { result = .success(try await tr.transcribe(samples)) } catch { result = .failure(error) }
            let t1 = CACurrentMediaTime()
            guard let self else { return }
            let latency = (t1 - releasedAt) * 1000
            let infer = (t1 - t0) * 1000
            switch result {
            case .failure(let failure):
                self.model.mood = .confused
                self.restoreBubbleAfterVoice(hint: "Speech error: \(failure.localizedDescription)")
                self.model.log(.error, "stt failed: \(failure.localizedDescription)")
            case .success(let text):
                self.model.lastSTTms = latency
                self.model.log(.stt, String(format: "release→text %.0f ms · infer %.0f ms · %.1f s audio",
                                            latency, infer, seconds), ms: latency)
                FileLog.shared.raw(String(format: "stt_latency release_to_final_ms=%.1f infer_ms=%.1f audio_s=%.2f engine=%@ text=%@",
                                          latency, infer, seconds, tr.displayName, text))
                self.handleFinal(text, id: id)
            }
        }
    }

    private func handleFinal(_ text: String, id: String) {
        if model.pendingConfirm != nil {
            if let yes = Self.parseYesNo(text) {
                model.log(.utterance, "“\(text)” → \(yes ? "yes" : "no")")
                onConfirmAnswer?(yes)
            } else {
                model.mood = .confused
                restoreBubbleAfterVoice(hint: nil)
            }
            return
        }
        guard !text.isEmpty else {
            model.mood = .confused
            mascot?.showBubble("I didn't catch that.", style: .hint)
            return
        }
        model.log(.utterance, text)
        guard let brain, brain.connected else {
            model.mood = .confused
            mascot?.showBubble("My brain is offline. Start it with: uv run --project ml brain serve", style: .hint)
            brain?.sendUtterance(id: id, text: text, final: true)   // queued for reconnect
            return
        }
        brain.sendUtterance(id: id, text: text, final: true)
        mascot?.showBubble(text, style: .transcript)
    }

    private func restoreBubbleAfterVoice(hint: String?) {
        if let c = model.pendingConfirm {
            mascot?.showBubble(c.summary, style: .confirm, autoHide: false)
        } else if let h = hint {
            mascot?.showBubble(h, style: .hint)
        } else {
            mascot?.hideBubble()
        }
    }

    private func sttNotReadyHint() -> String {
        switch model.sttState {
        case .downloading(let f, _): return String(format: "Still downloading my ears (%.0f%%)…", f * 100)
        case .loading(let p): return "Almost ready: \(p.lowercased())…"
        case .failed(let e): return "Speech engine failed: \(e)"
        default: return "Speech model is still loading…"
        }
    }

    // MARK: cancel paths

    func abortRecording(hint: String?) {
        guard model.isRecording else { return }
        partialTask?.cancel()
        _ = recorder.stop()
        model.isRecording = false
        model.micLevel = 0
        model.mood = moodBeforeListening == .listening ? .idle : moodBeforeListening
        restoreBubbleAfterVoice(hint: hint)
    }

    private func escape() {
        if model.isRecording {
            abortRecording(hint: "Cancelled.")
            return
        }
        if model.pendingConfirm != nil {
            onConfirmAnswer?(false)
            return
        }
        if model.mood == .thinking || model.mood == .acting {
            brain?.sendCancel()
            model.log(.system, "cancel sent (Esc)")
            model.mood = .idle
            mascot?.showBubble("Stopped.", style: .hint)
        }
    }

    // MARK: yes / no

    static func parseYesNo(_ text: String) -> Bool? {
        let t = text.lowercased()
            .replacingOccurrences(of: "[^a-z' ]", with: " ", options: .regularExpression)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespaces)
        let noPhrases = ["don't", "do not", "never mind", "nevermind", "not now", "hold on"]
        let yesPhrases = ["go ahead", "do it", "send it", "please do", "sounds good", "of course"]
        for p in noPhrases where t.contains(p) { return false }
        for p in yesPhrases where t.contains(p) { return true }
        let yes: Set<String> = ["yes", "yeah", "yep", "yup", "sure", "confirm", "confirmed", "ok", "okay",
                                "affirmative", "absolutely", "correct", "right", "ya", "yah"]
        let no: Set<String> = ["no", "nope", "nah", "cancel", "stop", "abort", "negative", "wait"]
        for w in t.split(separator: " ").map(String.init) {
            if yes.contains(w) { return true }
            if no.contains(w) { return false }
        }
        return nil
    }
}

/// Throttles progress callbacks (called from arbitrary queues).
private final class ProgressGate: @unchecked Sendable {
    private let lock = NSLock()
    private var lastFraction = -1.0
    private var lastPhase = ""

    func shouldEmit(_ f: Double, _ phase: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        if phase != lastPhase || abs(f - lastFraction) >= 0.004 || f >= 1 {
            lastFraction = f
            lastPhase = phase
            return true
        }
        return false
    }
}
