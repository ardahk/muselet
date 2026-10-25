import Foundation
import XCTest
@testable import HandsKit

// Hover dwell is deterministic: ManualScheduler advances callbacks without sleeping.

private final class ManualScheduler: DelayScheduler {
    private struct Entry {
        let due: TimeInterval
        let work: () -> Void
        var cancelled = false
        var fired = false
    }

    private(set) var now: TimeInterval = 0
    private var entries: [Entry] = []

    @discardableResult
    func after(_ delay: TimeInterval, _ work: @escaping () -> Void) -> ScheduledWork {
        let index = entries.count
        entries.append(Entry(due: now + delay, work: work))
        return ScheduledWork { [weak self] in
            guard self?.entries.indices.contains(index) == true else { return }
            self?.entries[index].cancelled = true
        }
    }

    func advance(by interval: TimeInterval) {
        let target = now + interval
        while let index = entries.indices
            .filter({ entries[$0].due <= target && !entries[$0].cancelled && !entries[$0].fired })
            .min(by: { entries[$0].due < entries[$1].due }) {
            now = entries[index].due
            entries[index].fired = true
            entries[index].work()
        }
        now = target
    }
}

final class HoverDwellTests: XCTestCase {
    func testSettlesAfterFullDwell() {
        let scheduler = ManualScheduler()
        let hover = HoverDwell(dwell: 1, scheduler: scheduler)
        var changes = 0
        hover.onChange = { changes += 1 }

        hover.set(true)
        scheduler.advance(by: 0.99)
        XCTAssertFalse(hover.settled)
        scheduler.advance(by: 0.01)
        XCTAssertTrue(hover.settled)
        XCTAssertEqual(changes, 1)
    }

    func testLeavingBeforeDwellCancels() {
        let scheduler = ManualScheduler()
        let hover = HoverDwell(dwell: 1, scheduler: scheduler)
        var changes = 0
        hover.onChange = { changes += 1 }

        hover.set(true)
        scheduler.advance(by: 0.5)
        hover.set(false)
        scheduler.advance(by: 2)
        XCTAssertFalse(hover.settled)
        XCTAssertEqual(changes, 0)
    }

    func testReenteringStartsFreshDwell() {
        let scheduler = ManualScheduler()
        let hover = HoverDwell(dwell: 1, scheduler: scheduler)

        hover.set(true)
        scheduler.advance(by: 0.6)
        hover.set(false)
        hover.set(true)
        scheduler.advance(by: 0.4)
        XCTAssertFalse(hover.settled)
        scheduler.advance(by: 0.6)
        XCTAssertTrue(hover.settled)
    }

    func testLeavingSettledHoverNotifiesAgain() {
        let scheduler = ManualScheduler()
        let hover = HoverDwell(dwell: 1, scheduler: scheduler)
        var changes = 0
        hover.onChange = { changes += 1 }

        hover.set(true)
        scheduler.advance(by: 1)
        XCTAssertTrue(hover.settled)
        hover.set(false)
        XCTAssertFalse(hover.settled)
        XCTAssertEqual(changes, 2)
    }

    func testDuplicateEnterDoesNotRestartDwell() {
        let scheduler = ManualScheduler()
        let hover = HoverDwell(dwell: 1, scheduler: scheduler)

        hover.set(true)
        scheduler.advance(by: 0.6)
        hover.set(true)
        scheduler.advance(by: 0.4)
        XCTAssertTrue(hover.settled)
    }

    func testPillPolicy() {
        XCTAssertFalse(PillPolicy.wantsShow(mascotSettled: false, mascotHovering: true, pillShown: false,
                                            pillHover: false, recording: false, typing: false))
        XCTAssertTrue(PillPolicy.wantsShow(mascotSettled: true, mascotHovering: false, pillShown: false,
                                           pillHover: false, recording: false, typing: false))
        XCTAssertTrue(PillPolicy.wantsShow(mascotSettled: false, mascotHovering: true, pillShown: true,
                                           pillHover: false, recording: false, typing: false))
        XCTAssertTrue(PillPolicy.wantsShow(mascotSettled: false, mascotHovering: false, pillShown: false,
                                           pillHover: true, recording: false, typing: false))
        XCTAssertTrue(PillPolicy.wantsShow(mascotSettled: false, mascotHovering: false, pillShown: false,
                                           pillHover: false, recording: true, typing: false))
        XCTAssertTrue(PillPolicy.wantsShow(mascotSettled: false, mascotHovering: false, pillShown: false,
                                           pillHover: false, recording: false, typing: true))
        XCTAssertFalse(PillPolicy.wantsShow(mascotSettled: false, mascotHovering: false, pillShown: false,
                                            pillHover: false, recording: false, typing: false))
    }

    func testPillZoneBridgesTheGapOnly() {
        let kitten = CGRect(x: 100, y: 100, width: 60, height: 70)   // AppKit: pill sits below
        let pill = CGRect(x: 95, y: 70, width: 70, height: 26)
        XCTAssertTrue(PillZone.contains(CGPoint(x: 130, y: 140), kitten: kitten, pill: pill))
        XCTAssertTrue(PillZone.contains(CGPoint(x: 100, y: 80), kitten: kitten, pill: pill))
        XCTAssertTrue(PillZone.contains(CGPoint(x: 130, y: 98), kitten: kitten, pill: pill))    // gap
        XCTAssertFalse(PillZone.contains(CGPoint(x: 170, y: 98), kitten: kitten, pill: pill))   // beside gap
        XCTAssertFalse(PillZone.contains(CGPoint(x: 130, y: 60), kitten: kitten, pill: pill))
        XCTAssertFalse(PillZone.contains(CGPoint(x: 130, y: 200), kitten: kitten, pill: pill))
    }
}
