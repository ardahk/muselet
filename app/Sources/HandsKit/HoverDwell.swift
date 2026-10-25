import Foundation

/// One cancellable delayed call.
public final class ScheduledWork {
    private var cancelImpl: (() -> Void)?

    public init(cancel: @escaping () -> Void) {
        cancelImpl = cancel
    }

    public func cancel() {
        cancelImpl?()
        cancelImpl = nil
    }
}

/// Runs work after a delay; injectable so tests don't sleep.
public protocol DelayScheduler: AnyObject {
    @discardableResult func after(_ delay: TimeInterval, _ work: @escaping () -> Void) -> ScheduledWork
}

public final class MainQueueScheduler: DelayScheduler {
    public init() {}

    @discardableResult
    public func after(_ delay: TimeInterval, _ work: @escaping () -> Void) -> ScheduledWork {
        let item = DispatchWorkItem(block: work)
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: item)
        return ScheduledWork { item.cancel() }
    }
}

/// Mascot hover that counts only after the pointer has rested `dwell` seconds; leaving first cancels it.
public final class HoverDwell {
    public let dwell: TimeInterval
    public private(set) var hovering = false
    public private(set) var settled = false
    public var onChange: (() -> Void)?

    private let scheduler: DelayScheduler
    private var pending: ScheduledWork?

    public init(dwell: TimeInterval, scheduler: DelayScheduler = MainQueueScheduler()) {
        self.dwell = dwell
        self.scheduler = scheduler
    }

    public func set(_ h: Bool) {
        guard h != hovering else { return }
        hovering = h
        if h {
            pending?.cancel()
            pending = scheduler.after(dwell) { [weak self] in
                guard let self, self.hovering else { return }
                self.pending = nil
                guard !self.settled else { return }
                self.settled = true
                self.onChange?()
            }
        } else {
            pending?.cancel()
            pending = nil
            if settled {
                settled = false
                onChange?()
            }
        }
    }

    public func reset() {
        pending?.cancel()
        pending = nil
        hovering = false
        settled = false
    }
}

/// Whether the pill under the mascot should be visible.
public enum PillPolicy {
    public static func wantsShow(mascotSettled: Bool, mascotHovering: Bool, pillShown: Bool,
                                 pillHover: Bool, recording: Bool, typing: Bool) -> Bool {
        mascotSettled || (mascotHovering && pillShown) || pillHover || recording || typing
    }
}
