import AppKit
import HandsKit

/// The app's single HandsDelegate: forwards act hooks to the ghost cursor
/// and hops skill results / timer events to the main thread (HUD, mascot).
final class HandsBridge: HandsDelegate {
    private let ghost: GhostCursor
    /// Main thread: a skill finished (`response` = {ok, result?, error?, ms}).
    var onSkill: ((_ name: String, _ args: [String: Any], _ response: [String: Any]) -> Void)?
    /// Main thread: a start_timer timer fired.
    var onTimer: ((_ label: String?) -> Void)?

    init(ghost: GhostCursor) {
        self.ghost = ghost
    }

    func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval {
        ghost.handsWillAct(op: op, frame: frame, label: label)
    }

    func handsDidAct(op: String, frame: CGRect?, ok: Bool) {
        ghost.handsDidAct(op: op, frame: frame, ok: ok)
    }

    func handsDidRunSkill(name: String, args: [String: Any], result: [String: Any]) {
        DispatchQueue.main.async { self.onSkill?(name, args, result) }
    }

    func handsTimerFired(label: String?) {
        DispatchQueue.main.async { self.onTimer?(label) }
    }
}
