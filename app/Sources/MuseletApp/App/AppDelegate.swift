import AppKit
import HandsKit

/// Wires brain <-> HandsKit <-> overlay/mascot/voice.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let model = AppModel.shared
    private let rpc = RPCHandler()
    private var brain: BrainConnection!
    private var overlays: OverlayController!
    private var ghost: GhostCursor!
    private var mascot: MascotController!
    private var voice: VoiceController!
    private let permissionWatcher = PermissionWatcher()
    private var debugHooks: DebugHooks?

    func applicationDidFinishLaunching(_ notification: Notification) {
        if terminateIfAlreadyRunning() { return }
        NSApp.setActivationPolicy(.accessory)
        FileLog.shared.raw("launch pid=\(getpid()) bundle=\(Bundle.main.bundleIdentifier ?? "nil")")

        // Screenshots exclude windows owned by this bundle id.
        rpc.ownBundleId = Bundle.main.bundleIdentifier ?? "ai.muselet.app"

        overlays = OverlayController()
        ghost = GhostCursor(overlays: overlays)
        mascot = MascotController(model: model)
        rpc.delegate = ghost

        // Ghost <-> mascot choreography.
        mascot.onMoved = { [weak self] p in self?.ghost.updateMascotAnchor(p) }
        ghost.updateMascotAnchor(mascot.anchorCG())
        ghost.onFlightStart = { [weak self] target in
            guard let self else { return }
            if [.idle, .thinking, .sleeping].contains(self.model.mood) { self.model.mood = .acting }
            self.mascot.look(atCG: target)
        }
        ghost.onIdle = { [weak self] in self?.mascot.look(atCG: nil) }

        brain = BrainConnection(handler: rpc)
        wireBrain()

        voice = VoiceController(model: model)
        voice.brain = brain
        voice.mascot = mascot
        voice.onConfirmAnswer = { [weak self] yes in self?.replyConfirm(yes: yes) }
        mascot.onConfirmReply = { [weak self] yes in self?.replyConfirm(yes: yes) }

        permissionWatcher.onChange = { [weak self] _ in self?.voice.startHotkey() }
        permissionWatcher.refreshNow()
        wireActions()

        debugHooks = DebugHooks(model: model, ghost: ghost, mascot: mascot, brain: brain, rpc: rpc)

        voice.start()
        brain.start()

        model.log(.system, "muselet started")
        if !model.permissions.allGranted {
            permissionWatcher.watch(for: 20)
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
            guard let self else { return }
            self.mascot.view.hop(height: 12)
            self.mascot.showBubble(self.model.pushToTalkActive
                                   ? "Hi! Hold right ⌥ and tell me what to do."
                                   : "Hi! Open my menu to grant permissions.",
                                   style: .say)
        }
    }

    private func terminateIfAlreadyRunning() -> Bool {
        guard let bid = Bundle.main.bundleIdentifier else { return false }
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: bid)
            .filter { $0.processIdentifier != getpid() }
        if !others.isEmpty {
            NSLog("muselet: already running (pid %d); exiting", others[0].processIdentifier)
            NSApp.terminate(nil)
            return true
        }
        return false
    }

    // MARK: brain

    private func wireBrain() {
        brain.onStatus = { [weak self] s in
            guard let self else { return }
            let was = self.model.brainStatus
            self.model.brainStatus = s
            switch s {
            case .connected: self.model.log(.system, "brain connected")
            case .busy where was != .busy: self.model.log(.error, "brain rejected us: another client is connected")
            case .offline where was == .connected:
                self.model.log(.error, "brain disconnected")
                if self.model.pendingConfirm != nil {
                    self.model.pendingConfirm = nil
                    self.mascot.hideBubble()
                }
            default: break
            }
        }
        brain.onUI = { [weak self] mascotState, bubble in
            guard let self else { return }
            if let m = mascotState.flatMap(MascotMood.init(rawValue:)) {
                if !(self.model.isRecording && m != .listening) { self.model.mood = m }
            }
            if let b = bubble, !b.isEmpty, self.model.pendingConfirm == nil, !self.model.isRecording {
                self.mascot.showBubble(b, style: .say)
            }
            self.model.log(.ui, (mascotState ?? "ui") + (bubble.map { " · \($0)" } ?? ""))
        }
        brain.onSay = { [weak self] text in
            guard let self, !text.isEmpty else { return }
            self.model.log(.say, text)
            if !self.model.isRecording && self.model.pendingConfirm == nil {
                self.mascot.showBubble(text, style: .say)
            }
        }
        brain.onConfirm = { [weak self] id, summary in
            guard let self else { return }
            self.model.pendingConfirm = PendingConfirm(id: id, summary: summary)
            self.model.log(.confirm, summary)
            self.mascot.wake()
            if !self.model.isRecording {
                self.mascot.showBubble(summary, style: .confirm, autoHide: false)
            }
        }
        brain.onRPC = { [weak self] method, summary, ms, ok in
            self?.model.log(.rpc, summary, ms: ms, ok: ok)
        }
    }

    private func replyConfirm(yes: Bool) {
        guard let c = model.pendingConfirm else { return }
        brain.sendConfirmReply(id: c.id, yes: yes)
        model.pendingConfirm = nil
        model.log(.confirm, yes ? "confirmed" : "declined")
        mascot.showBubble(yes ? "On it." : "Okay, cancelled.", style: .hint)
        model.mood = yes ? .thinking : .idle
    }

    // MARK: panel actions

    private func wireActions() {
        let a = AppActions.shared
        a.requestPermission = { [weak self] k in
            Permissions.request(k) { self?.permissionWatcher.watch(for: 60) }
            self?.permissionWatcher.watch(for: 60)
        }
        a.reconnect = { [weak self] in self?.brain.reconnectNow() }
        a.resetMascot = { [weak self] in self?.mascot.resetPosition() }
        a.panelVisible = { [weak self] visible in
            guard let self else { return }
            if visible { self.permissionWatcher.watch(for: 3600) } else { self.permissionWatcher.stop() }
            self.voice.ptt.ensureEnabled()
        }
    }
}
