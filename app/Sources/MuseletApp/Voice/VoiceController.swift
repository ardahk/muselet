import AppKit
import AVFoundation
import QuartzCore
import HandsKit

/// Push-to-talk pipeline: Right ⌥ down -> capture (+ live partials) ->
/// release -> final transcript -> utterance (or confirm answer).
final class VoiceController {
    private let model: AppModel
    let recorder = AudioRecorder()
    let ptt = PushToTalkMonitor()

    weak var brain: BrainConnection?
    weak var mascot: MascotController?
    var onConfirmAnswer: ((Bool) -> Void)?
    /// Key-down of a real recording (prefetch work the request will need).
    var onPressBegan: (() -> Void)?

    private(set) var transcriber: Transcriber?
    private let parakeet = ParakeetTranscriber()
    private var apple: AppleSpeechTranscriber?
    private var partialTask: Task<Void, Never>?
    private var counter = 0
    private var currentID: String?
    private var lastPartial = ""
    /// ctx capture started at key-down (AX off the main thread).
    private var pressCtx: PendingCtx?
    private var moodBeforeListening: MascotMood = .idle
    /// Keep capturing briefly after release so the last syllable isn't clipped.
    private let releaseTail: TimeInterval = 0.06
    /// The confirm that was pending at key-down (a yes/no answer to a
    /// confirm the brain cancelled meanwhile must not become a command).
    private var confirmAtPress: String?
    /// Key-down -> listening mood / first mic buffer (ux-7), logged per press.
    private struct ListenTiming { var moodMs: Double?; var firstBufferMs: Double?; var logged = false }
    private var listenTiming = ListenTiming()

    init(model: AppModel) {
        self.model = model
    }

    func start() {
        recorder.onLevel = { [weak self] v in
            guard let self, self.model.isRecording else { return }
            self.model.micLevel = v
            self.model.levelSubject.send(v)
        }
        recorder.onFirstBuffer = { [weak self] ms in
            guard let self else { return }
            self.listenTiming.firstBufferMs = ms
            self.logListenTiming()
        }
        // Keep the engine prepared so key-down only pays engine.start().
        if AVCaptureDevice.authorizationStatus(for: .audio) == .authorized { recorder.warmUp() }
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

    private func pressBegan(at explicitKeyDown: CFTimeInterval? = nil) {
        guard !model.isRecording else { return }
        let keyDown = explicitKeyDown ?? (ptt.pressEventTime > 0 ? ptt.pressEventTime : CACurrentMediaTime())
        mascot?.wake()
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    self.model.permissions = Permissions.snapshot()
                    if granted { self.recorder.warmUp() }
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
        counter += 1
        let id = "u\(counter)-\(Int(Date().timeIntervalSince1970) % 100_000)"
        currentID = id
        lastPartial = ""
        // Capture ctx at push-to-talk key-down (AGENTS.md contract). App
        // name is read now; the AX part runs off the main thread with a
        // 0.15 s timeout so a hung frontmost app can't stall listening.
        pressCtx = UtteranceCtx.begin()
        confirmAtPress = model.pendingConfirm?.id
        // ux-7: feedback first. The listening mood and bubble never wait on
        // Core Audio; the (prepared) engine starts on the audio queue.
        model.isRecording = true
        model.micLevel = 0
        if model.mood != .listening { moodBeforeListening = model.mood }
        model.mood = .listening
        mascot?.showBubble("", style: .transcript, autoHide: false)
        onPressBegan?()
        listenTiming = ListenTiming()
        DispatchQueue.main.async { [weak self] in
            // Next main-loop turn: the mood change has been committed to the render server.
            guard let self, self.currentID == id else { return }
            self.listenTiming.moodMs = (CACurrentMediaTime() - keyDown) * 1000
            self.logListenTiming()
        }
        recorder.start(keyDownAt: keyDown) { [weak self] error in
            guard let self, let error else { return }
            self.model.log(.error, "mic start failed: \(error.localizedDescription)")
            guard self.model.isRecording, self.currentID == id else { return }
            self.partialTask?.cancel()
            self.model.isRecording = false
            self.model.micLevel = 0
            self.model.mood = .confused
            self.mascot?.showBubble("Mic error: \(error.localizedDescription)", style: .hint)
        }
        startPartials()
    }

    /// One line per press once both numbers are in (FileLog, next to stt_latency).
    private func logListenTiming() {
        guard !listenTiming.logged, let mood = listenTiming.moodMs,
              let first = listenTiming.firstBufferMs else { return }
        listenTiming.logged = true
        FileLog.shared.raw(String(format: "listen_latency keydown_to_mood_ms=%.1f keydown_to_first_buffer_ms=%.1f",
                                  mood, first))
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
                    // Partials carry ctx only once the capture is ready.
                    self.brain?.sendUtterance(id: id, text: text, final: false,
                                              ctx: self.pressCtx?.ready)
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

    static let offlineHint = "My brain is offline. Start it with: uv run --project ml brain serve"

    private func handleFinal(_ text: String, id: String) {
        if model.pendingConfirm != nil {
            if let yes = Self.parseYesNo(text) {
                model.log(.utterance, "“\(text)” → \(yes ? "yes" : "no")")
                onConfirmAnswer?(yes)
            } else {
                model.mood = .confused
                restoreBubbleAfterVoice(hint: nil)
                if !text.isEmpty, let brain, brain.connected {
                    // The brain cancels the confirm and runs this only if it's a new command.
                    let ctx = pressCtx
                    if let ctx {
                        ctx.whenReady(timeout: 0.2) { [weak brain] c in
                            brain?.sendUtterance(id: id, text: text, final: true, ctx: c)
                        }
                    } else {
                        brain.sendUtterance(id: id, text: text, final: true, ctx: UtteranceCtx.begin().fallback)
                    }
                }
            }
            return
        }
        // The brain cancelled the confirm while the user was answering it:
        // a bare yes/no must not go out as a new command.
        if confirmAtPress != nil, Self.parseYesNo(text) != nil {
            model.log(.utterance, "“\(text)” dropped: the confirmation was cancelled")
            model.mood = .idle
            mascot?.showBubble("That question was cancelled.", style: .hint)
            return
        }
        guard !text.isEmpty else {
            model.mood = .confused
            mascot?.showBubble("I didn't catch that.", style: .hint)
            return
        }
        model.log(.utterance, text)
        model.noteRequest(text)
        guard let brain else {
            model.mood = .confused
            mascot?.showBubble(Self.offlineHint, style: .hint)
            return
        }
        if !brain.connected {
            // A brief drop (brain restarting) may recover: BrainConnection
            // holds the latest final utterance for <= 5 s, then drops it and
            // reports back (offline bubble). Never replay stale commands.
            if brain.offlineFor > BrainConnection.outboxTTL || model.brainStatus == .busy {
                model.mood = .confused
                mascot?.showBubble(Self.offlineHint, style: .hint)
                return
            }
            mascot?.showBubble("Reconnecting to my brain…", style: .hint)
        } else {
            mascot?.showBubble(text, style: .transcript)
        }
        // The final frame always carries ctx: wait <= 200 ms for the
        // key-down capture, else send the fallback (app + online).
        let ctx = pressCtx
        if let ctx {
            ctx.whenReady(timeout: 0.2) { [weak brain] c in
                brain?.sendUtterance(id: id, text: text, final: true, ctx: c)
            }
        } else {
            brain.sendUtterance(id: id, text: text, final: true, ctx: UtteranceCtx.begin().fallback)
        }
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

    // MARK: pill (click to talk, typed requests)

    /// Mascot pill mic button: first click starts listening, second click sends.
    func toggleListening() {
        if model.isRecording { pressEnded() } else { pressBegan(at: CACurrentMediaTime()) }
    }

    /// Typed request (pill text field, panel example): the same final
    /// utterance frame as voice; `ctx` was captured before Muselet took focus.
    func sendTyped(_ raw: String, ctx: PendingCtx) {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !model.isRecording else { return }
        mascot?.wake()
        counter += 1
        let id = "t\(counter)-\(Int(Date().timeIntervalSince1970) % 100_000)"
        currentID = id
        pressCtx = ctx
        confirmAtPress = model.pendingConfirm?.id
        model.mood = .thinking
        handleFinal(text, id: id)
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

    /// Confirm-gate parser; lives in HandsKit (`YesNo`) so it's unit-tested.
    static func parseYesNo(_ text: String) -> Bool? { YesNo.parse(text) }
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
