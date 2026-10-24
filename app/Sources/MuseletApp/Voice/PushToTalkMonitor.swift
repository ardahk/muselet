import AppKit
import CoreGraphics
import HandsKit
import QuartzCore

/// Global hold-to-talk on Right Option via a listen-only CGEventTap
/// (flagsChanged keycode 61 + the device-dependent right-alt bit), plus Esc.
/// Listen-only: events are never modified or swallowed.
final class PushToTalkMonitor {
    static let rightOptionKeyCode: Int64 = 61
    static let escapeKeyCode: Int64 = 53
    private static let deviceRightAltMask: UInt64 = 0x40   // NX_DEVICERALTKEYMASK

    var onPress: (() -> Void)?
    var onRelease: (() -> Void)?
    /// Another key went down while Right ⌥ was held (user typing a ⌥ chord).
    var onChord: (() -> Void)?
    var onEscape: (() -> Void)?

    private var tap: CFMachPort?
    private var source: CFRunLoopSource?
    private(set) var isHeld = false
    /// CACurrentMediaTime-domain time of the last Right ⌥ key-down event
    /// (from the event timestamp; tap delivery latency included in timings).
    private(set) var pressEventTime: CFTimeInterval = 0
    private var chorded = false
    private var wakeObserver: NSObjectProtocol?

    var isRunning: Bool { tap.map { CGEvent.tapIsEnabled(tap: $0) } ?? false }

    init() {
        wakeObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            self?.ensureEnabled()
        }
    }

    deinit {
        stop()
        if let o = wakeObserver { NSWorkspace.shared.notificationCenter.removeObserver(o) }
    }

    /// Returns false when the tap can't be created (needs Input Monitoring or Accessibility).
    @discardableResult
    func start() -> Bool {
        if tap != nil { ensureEnabled(); return true }
        let mask = (CGEventMask(1) << CGEventType.flagsChanged.rawValue)
            | (CGEventMask(1) << CGEventType.keyDown.rawValue)
        let cb: CGEventTapCallBack = { _, type, event, refcon in
            guard let refcon else { return Unmanaged.passUnretained(event) }
            let me = Unmanaged<PushToTalkMonitor>.fromOpaque(refcon).takeUnretainedValue()
            me.handle(type: type, event: event)
            return Unmanaged.passUnretained(event)
        }
        guard let t = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap,
                                        options: .listenOnly, eventsOfInterest: mask,
                                        callback: cb,
                                        userInfo: Unmanaged.passUnretained(self).toOpaque()) else {
            return false
        }
        guard let src = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, t, 0) else {
            CFMachPortInvalidate(t)
            return false
        }
        tap = t
        source = src
        CFRunLoopAddSource(CFRunLoopGetMain(), src, .commonModes)
        CGEvent.tapEnable(tap: t, enable: true)
        return true
    }

    func stop() {
        if let s = source { CFRunLoopRemoveSource(CFRunLoopGetMain(), s, .commonModes) }
        if let t = tap { CFMachPortInvalidate(t) }
        source = nil
        tap = nil
        isHeld = false
    }

    /// Watchdog: re-enable if the system disabled the tap.
    func ensureEnabled() {
        guard let t = tap else { return }
        if !CGEvent.tapIsEnabled(tap: t) { CGEvent.tapEnable(tap: t, enable: true) }
    }

    private func handle(type: CGEventType, event: CGEvent) {
        // Ignore input HandsKit synthesized (tagged eventSourceUserData):
        // the agent's own `keys esc` must not cancel its task, and its
        // keystrokes (and media keys, should this tap ever listen for
        // system-defined events) must not abort a recording as a ⌥ chord.
        if type != .tapDisabledByTimeout && type != .tapDisabledByUserInput
            && SyntheticEvent.isTagged(event) { return }
        switch type {
        case .tapDisabledByTimeout, .tapDisabledByUserInput:
            ensureEnabled()
            if isHeld {   // we may have missed the release
                isHeld = false
                onRelease?()
            }
        case .flagsChanged:
            guard event.getIntegerValueField(.keyboardEventKeycode) == Self.rightOptionKeyCode else {
                // Another modifier joined the chord while holding (e.g. ⌥⌘): treat as a chord.
                if isHeld && !chorded {
                    chorded = true
                    onChord?()
                }
                return
            }
            let down = (event.flags.rawValue & Self.deviceRightAltMask) != 0
            if down && !isHeld {
                isHeld = true
                chorded = false
                // CGEvent timestamps are mach-time nanoseconds; keep them only
                // if they're plausible (else "now").
                let now = CACurrentMediaTime()
                let t = Double(event.timestamp) / 1e9
                pressEventTime = (t > 0 && t <= now && now - t < 1) ? t : now
                onPress?()
            } else if !down && isHeld {
                isHeld = false
                if chorded { chorded = false } else { onRelease?() }
            }
        case .keyDown:
            let code = event.getIntegerValueField(.keyboardEventKeycode)
            if isHeld && !chorded {
                chorded = true
                onChord?()
                return
            }
            if code == Self.escapeKeyCode && event.getIntegerValueField(.keyboardEventAutorepeat) == 0 {
                onEscape?()
            }
        default:
            break
        }
    }
}
