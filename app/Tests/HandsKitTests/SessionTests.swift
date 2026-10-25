import ApplicationServices
import Foundation
import XCTest
@testable import HandsKit

// Session plumbing: hover dwell / pill zone, utterance ctx capture
// (selection, pending ctx), brain frames, the confirm parser and the
// `hands serve` exit rules. Hover dwell is deterministic: ManualScheduler
// advances callbacks without sleeping.

// MARK: - hover dwell / pill

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

// MARK: - training-11: selection includes selected rows/children/cells

final class SelectionCtxTests: XCTestCase {
    /// Per use: XCTest builds every test instance when the run starts, so a
    /// stored deadline had expired by the time a > 5 s suite reached these.
    private var deadline: Date { Date().addingTimeInterval(5) }

    func testFocusedOutlineWithSelectedRows() {
        let row = el("AXRow", "report.pdf")
        let outline = el("AXOutline", w: 400, h: 300, [row])
        outline.singles["AXSelectedRows"] = [row]
        XCTAssertTrue(UtteranceCtx.hasSelection(outline, role: "AXOutline", deadline: deadline))
        outline.singles["AXSelectedRows"] = [MockElement]()
        XCTAssertFalse(UtteranceCtx.hasSelection(outline, role: "AXOutline", deadline: deadline))
    }

    func testSelectedChildrenAndCells() {
        let icon = el("AXImage", "photo.jpg")
        let list = el("AXList", w: 400, h: 300, [icon])
        list.singles["AXSelectedChildren"] = [icon]
        XCTAssertTrue(UtteranceCtx.hasSelection(list, role: "AXList", deadline: deadline))
        let cell = el("AXCell", "42")
        let table = el("AXTable", w: 400, h: 300, [cell])
        table.singles["AXSelectedCells"] = [cell]
        XCTAssertTrue(UtteranceCtx.hasSelection(table, role: "AXTable", deadline: deadline))
    }

    func testFocusedRowUsesItsList() {
        let row = el("AXRow", "notes.txt")
        let outline = el("AXOutline", w: 400, h: 300, [row])
        outline.singles["AXSelectedRows"] = [row]
        row.singles[kAXParentAttribute as String] = outline
        XCTAssertTrue(UtteranceCtx.hasSelection(row, role: "AXRow", deadline: deadline))
    }

    func testFocusedContainerUsesTheListInside() {
        let row = el("AXRow", "a")
        let table = el("AXTable", w: 400, h: 300, [row])
        table.singles["AXSelectedRows"] = [row]
        let scroll = el("AXScrollArea", w: 400, h: 300, [el("AXScrollBar"), table])
        XCTAssertTrue(UtteranceCtx.hasSelection(scroll, role: "AXScrollArea", deadline: deadline))
        table.singles["AXSelectedRows"] = [MockElement]()
        XCTAssertFalse(UtteranceCtx.hasSelection(scroll, role: "AXScrollArea", deadline: deadline))
    }

    func testTextSelectionStillCounts() {
        let area = el("AXTextArea", "Body")
        area.singles[kAXSelectedTextAttribute as String] = "hello"
        XCTAssertTrue(UtteranceCtx.hasSelection(area, role: "AXTextArea", deadline: deadline))
        area.singles[kAXSelectedTextAttribute as String] = ""
        XCTAssertFalse(UtteranceCtx.hasSelection(area, role: "AXTextArea", deadline: deadline))
        var range = CFRange(location: 2, length: 4)
        area.singles[kAXSelectedTextRangeAttribute as String] = AXValueCreate(.cfRange, &range)!
        XCTAssertTrue(UtteranceCtx.hasSelection(area, role: "AXTextArea", deadline: deadline))
    }

    func testMenuBarSelectedChildrenIsNotASelection() {
        let bar = el("AXMenuBar", nil, [el("AXMenuBarItem", "File")])
        bar.singles["AXSelectedChildren"] = bar.attrs.children
        XCTAssertFalse(UtteranceCtx.hasSelection(bar, role: "AXMenuBar", deadline: deadline))
    }

    func testFocusedInfoEndToEnd() {
        let row = el("AXRow", "Q3 receipts")
        let outline = el("AXOutline", "Files", w: 400, h: 300, [row])
        outline.singles["AXSelectedRows"] = [row]
        let app = el("AXApplication")
        app.singles[kAXFocusedUIElementAttribute as String] = outline
        let (focused, sel) = UtteranceCtx.focusedInfo(app: app)
        XCTAssertEqual(focused, "none")                       // outline isn't in the role map
        XCTAssertTrue(sel)
        app.singles[kAXFocusedUIElementAttribute as String] = row
        row.singles[kAXParentAttribute as String] = outline
        let (f2, s2) = UtteranceCtx.focusedInfo(app: app)
        XCTAssertEqual(f2, "row \"Q3 receipts\"")
        XCTAssertTrue(s2)
        XCTAssertEqual(UtteranceCtx.focusedInfo(app: el("AXApplication")).focused, "none")
    }
}

// MARK: - utterance ctx capture

final class PendingCtxTests: XCTestCase {
    func testDeliversValueWhenFast() {
        let p = PendingCtx(fallback: ["focused": "none"], queue: DispatchQueue.global()) {
            ["focused": "textarea \"Body\""]
        }
        let e = expectation(description: "ctx")
        p.whenReady(timeout: 0.2, queue: .global()) { v in
            XCTAssertEqual(v["focused"] as? String, "textarea \"Body\"")
            e.fulfill()
        }
        wait(for: [e], timeout: 1)
        XCTAssertNotNil(p.ready)
    }

    func testFallbackAfterTimeoutWhenAppHangs() {
        let p = PendingCtx(fallback: ["app": "Hung", "focused": "none"], queue: DispatchQueue.global()) {
            usleep(800_000)                                  // a beachballing app
            return ["app": "Hung", "focused": "button \"x\""]
        }
        XCTAssertNil(p.ready)                                // partials omit ctx
        let t0 = Date()
        let e = expectation(description: "fallback")
        var calls = 0
        p.whenReady(timeout: 0.2, queue: .main) { v in
            calls += 1
            XCTAssertEqual(v["focused"] as? String, "none")
            XCTAssertEqual(v["app"] as? String, "Hung")
            e.fulfill()
        }
        wait(for: [e], timeout: 1)
        let dt = Date().timeIntervalSince(t0)
        XCTAssertGreaterThanOrEqual(dt, 0.19)
        XCTAssertLessThan(dt, 0.6)
        // the late real value must not trigger a second delivery
        let settle = expectation(description: "settle")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { settle.fulfill() }
        wait(for: [settle], timeout: 2)
        XCTAssertEqual(calls, 1)
    }

    func testBeginReturnsImmediately() {
        let t0 = Date()
        let p = UtteranceCtx.begin()
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.05)
        XCTAssertNotNil(p.fallback["app"])
        XCTAssertEqual(p.fallback["focused"] as? String, "none")
    }
}

// MARK: - confirm_cancel / ui.ms / latency chip

final class BrainFramesTests: XCTestCase {
    func testDecodeConfirmCancel() {
        guard case .confirmCancel(let id)? = BrainInbound.decode(#"{"t":"confirm_cancel","id":"c1"}"#) else {
            return XCTFail("not decoded")
        }
        XCTAssertEqual(id, "c1")
        guard case .confirmCancel(let none)? = BrainInbound.decode(#"{"t":"confirm_cancel"}"#) else {
            return XCTFail("not decoded")
        }
        XCTAssertNil(none)
    }

    func testDecodeUIWithMs() {
        guard case .ui(let m, let b, let ms)? = BrainInbound.decode(
            #"{"t":"ui","mascot":"success","bubble":"Opened Safari","ms":212}"#) else { return XCTFail() }
        XCTAssertEqual(m, "success"); XCTAssertEqual(b, "Opened Safari"); XCTAssertEqual(ms, 212)
        guard case .ui(_, _, let none)? = BrainInbound.decode(#"{"t":"ui","mascot":"thinking"}"#) else {
            return XCTFail()
        }
        XCTAssertNil(none)
    }

    func testDecodeOthers() {
        guard case .confirm(let id, let s)? = BrainInbound.decode(
            #"{"t":"confirm","id":"c2","summary":"Send it?"}"#) else { return XCTFail() }
        XCTAssertEqual(id, "c2"); XCTAssertEqual(s, "Send it?")
        guard case .rpc(let rid, let method, let p)? = BrainInbound.decode(
            #"{"t":"rpc","id":"r1","method":"observe","params":{"max_nodes":5}}"#) else { return XCTFail() }
        XCTAssertEqual(rid, "r1"); XCTAssertEqual(method, "observe"); XCTAssertEqual(p["max_nodes"] as? Int, 5)
        XCTAssertNil(BrainInbound.decode("not json"))
        XCTAssertNil(BrainInbound.decode(#"{"t":"confirm"}"#))
    }

    func testDecodeMemoryItems() {
        guard case .memory(let items)? = BrainInbound.decode(
            #"{"t":"memory","items":[{"id":4,"type":"person","key":"mom","value":"Jane","created":12.5}]}"#)
        else { return XCTFail("not decoded") }
        XCTAssertEqual(items.first?["id"] as? Int, 4)
        XCTAssertEqual(items.first?["value"] as? String, "Jane")
    }

    func testConfirmCancelClearsOnlyTheMatchingConfirm() {
        XCTAssertTrue(ConfirmCancel.clears(pendingId: "c1", cancelId: "c1"))
        XCTAssertFalse(ConfirmCancel.clears(pendingId: "c2", cancelId: "c1"))   // stale cancel
        XCTAssertTrue(ConfirmCancel.clears(pendingId: "c2", cancelId: nil))
        XCTAssertFalse(ConfirmCancel.clears(pendingId: nil, cancelId: "c1"))
    }

    func testLatencyFormat() {
        XCTAssertEqual(LatencyFormat.seconds(212), "0.21 s")
        XCTAssertEqual(LatencyFormat.seconds(1530), "1.53 s")
        XCTAssertEqual(LatencyFormat.seconds(12_400), "12.4 s")
        XCTAssertEqual(LatencyFormat.seconds(-5), "0.00 s")
    }
}

// MARK: - hands-2: confirm parser

final class YesNoTests: XCTestCase {
    func testRefusals() {
        for s in ["not right now", "okay cancel that", "that's not correct", "no", "nope",
                  "Don't do it", "not sure", "never mind", "hold on", "stop", "wait",
                  "No.", "nah", "please don't send it", "that\u{2019}s not right",
                  "ok cancel", "no, don't send it"] {
            XCTAssertEqual(YesNo.parse(s), false, s)
        }
    }

    func testAmbiguousIsNotYes() {
        let r = YesNo.parse("yes no wait")
        XCTAssertTrue(r == nil || r == false)
        XCTAssertNotEqual(YesNo.parse("yes, don't"), true)
    }

    func testYes() {
        for s in ["yes", "Yes.", "yeah do it", "go ahead", "sure", "okay", "yep, send it",
                  "Sure, go ahead!", "absolutely", "yes please", "sure no problem"] {
            XCTAssertEqual(YesNo.parse(s), true, s)
        }
    }

    func testRightCorrectNoLongerYes() {
        XCTAssertNil(YesNo.parse("right"))
        XCTAssertNil(YesNo.parse("correct"))
        XCTAssertNil(YesNo.parse("hmm"))
        XCTAssertNil(YesNo.parse(""))
    }
}

// MARK: - hands serve: arguments + exit rules

final class ServeSessionTests: XCTestCase {
    private let t0 = Date(timeIntervalSince1970: 1_000_000)
    private func at(_ s: Double) -> Date { t0.addingTimeInterval(s) }

    func testConfigValidation() {
        XCTAssertThrowsError(try ServeSession.Config.make(utterances: ["hi"], timeout: -1))
        XCTAssertThrowsError(try ServeSession.Config.make(utterances: ["  "], timeout: 90))
        XCTAssertThrowsError(try ServeSession.Config.make(utterances: ["hi"], timeout: .infinity))
        let c = try! ServeSession.Config.make(utterances: [" set volume to 30 "], timeout: 0)
        XCTAssertEqual(c.utterances, ["set volume to 30"])
        XCTAssertEqual(c.timeout, 0)
        XCTAssertEqual(c.quiet, 1.5)
        XCTAssertTrue(c.exitsWhenDone)
        XCTAssertFalse(ServeSession.Config(utterances: []).exitsWhenDone)
        XCTAssertEqual(ServeSession.Config(utterances: ["x"]).timeout, 90)   // default cap
    }

    func testExitsZeroAfterOutcomeAndQuiet() {
        let s = ServeSession(config: .init(utterances: ["set volume to 30"]), now: t0)
        XCTAssertEqual(s.tick(now: at(0.1)), .none)                       // not connected yet
        XCTAssertEqual(s.connected(now: at(0.2)), .send(id: "u1", text: "set volume to 30"))
        s.rpcStarted(id: "r1", now: at(0.4))
        s.rpcFinished(id: "r1", ok: true, now: at(0.5))
        s.say("Volume set to 30", now: at(0.6))
        s.ui(mood: "success", bubble: nil, ms: 212, now: at(0.6))
        XCTAssertEqual(s.tick(now: at(2.0)), .none)                       // 1.4 s quiet
        XCTAssertEqual(s.tick(now: at(2.15)), .exit(code: 0))
        XCTAssertEqual(s.tick(now: at(3.0)), .none)                       // exits once
        let sum = s.summary(now: at(2.15))
        XCTAssertEqual(sum["exit"] as? Int, 0)
        XCTAssertEqual(sum["reason"] as? String, "done")
        let u = (sum["utterances"] as? [[String: Any]])?.first
        XCTAssertEqual(u?["mood"] as? String, "success")
        XCTAssertEqual(u?["say"] as? String, "Volume set to 30")
        XCTAssertEqual(u?["rpcs"] as? Int, 1)
        XCTAssertEqual(u?["ms"] as? Double, 212)
        XCTAssertTrue(s.summaryLine(now: at(2.15)).hasPrefix("{"))
        XCTAssertFalse(s.summaryLine(now: at(2.15)).contains("\n"))      // one line
    }

    func testPendingRPCBlocksExitAndLateFramesResetQuiet() {
        let s = ServeSession(config: .init(utterances: ["open notes"]), now: t0)
        _ = s.connected(now: at(0))
        s.say("Opening Notes", now: at(1))                               // outcome
        s.rpcStarted(id: "r9", now: at(1.2))                              // a late verify
        XCTAssertEqual(s.tick(now: at(5)), .none)                         // pending
        s.rpcFinished(id: "r9", ok: false, now: at(5.5))
        XCTAssertEqual(s.tick(now: at(6.9)), .none)                       // 1.4 s since the RPC
        s.ui(mood: "confused", bubble: nil, ms: nil, now: at(6.95))       // late final ui
        XCTAssertEqual(s.tick(now: at(8.3)), .none)
        XCTAssertEqual(s.tick(now: at(8.5)), .exit(code: 0))
        let u = (s.summary()["utterances"] as? [[String: Any]])?.first
        XCTAssertEqual(u?["mood"] as? String, "confused")
        XCTAssertEqual(u?["rpc_errors"] as? Int, 1)
    }

    func testIdleCountsAndThinkingDoesNot() {
        let s = ServeSession(config: .init(utterances: ["cancel"]), now: t0)
        _ = s.connected(now: at(0))
        s.ui(mood: "thinking", bubble: nil, ms: nil, now: at(0.1))
        XCTAssertEqual(s.tick(now: at(5)), .none)
        s.ui(mood: "idle", bubble: nil, ms: nil, now: at(5))
        XCTAssertEqual(s.tick(now: at(6.6)), .exit(code: 0))
    }

    func testUtterancesRunInSequence() {
        let s = ServeSession(config: .init(utterances: ["set a timer", "10 minutes"]), now: t0)
        XCTAssertEqual(s.connected(now: at(0)), .send(id: "u1", text: "set a timer"))
        s.say("For how long?", now: at(1))                                // ASK
        s.ui(mood: "listening", bubble: nil, ms: nil, now: at(1))
        XCTAssertEqual(s.tick(now: at(2.6)), .send(id: "u2", text: "10 minutes"))
        XCTAssertEqual(s.tick(now: at(5)), .none)                         // u2 has no outcome yet
        s.say("Timer set", now: at(5))
        XCTAssertEqual(s.tick(now: at(6.6)), .exit(code: 0))
        XCTAssertEqual((s.summary()["utterances"] as? [[String: Any]])?.count, 2)
    }

    func testTimeoutExitsTwo() {
        let s = ServeSession(config: .init(utterances: ["hang"], timeout: 90), now: t0)
        _ = s.connected(now: at(0))
        s.rpcStarted(id: "r1", now: at(1))
        XCTAssertEqual(s.tick(now: at(89.9)), .none)
        XCTAssertEqual(s.tick(now: at(90.01)), .exit(code: 2))
        XCTAssertEqual(s.summary()["reason"] as? String, "timeout")
        XCTAssertEqual(s.summary()["pending_rpcs"] as? Int, 1)
        // Never connected: still capped.
        let n = ServeSession(config: .init(utterances: ["x"], timeout: 5), now: t0)
        XCTAssertEqual(n.tick(now: at(5.01)), .exit(code: 2))
        XCTAssertEqual(n.summary()["connected"] as? Bool, false)
    }

    func testNoUtterancesServesForeverAndZeroTimeoutHasNoCap() {
        let s = ServeSession(config: .init(utterances: []), now: t0)
        XCTAssertEqual(s.connected(now: at(0)), .none)
        XCTAssertEqual(s.tick(now: at(10_000)), .none)
        let c = ServeSession(config: .init(utterances: ["x"], timeout: 0), now: t0)
        _ = c.connected(now: at(0))
        XCTAssertEqual(c.tick(now: at(10_000)), .none)
    }

    func testDisconnectMidTurnClosesItAndExitsOne() {
        let s = ServeSession(config: .init(utterances: ["open notes"]), now: t0)
        _ = s.connected(now: at(0))
        XCTAssertEqual(s.connected(now: at(3)), .none)                    // reconnect: never re-sent
        XCTAssertEqual(s.tick(now: at(4.6)), .exit(code: 1))
        XCTAssertEqual(s.summary()["reason"] as? String, "disconnected")
    }
}
