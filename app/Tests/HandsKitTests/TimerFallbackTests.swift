import Foundation
import XCTest
@testable import HandsKit

// start_timer without Clock AX (inert hooks: Accessibility not trusted):
// Muselet's own timer, silently (docs/CLOCK_TIMERS.md).

private func skills() -> Skills {
    Skills(catalog: try! Catalog.load(), scripts: SpyRunner(), events: MockPoster(), hooks: .inert)
}

private func result(_ r: [String: Any]) -> [String: Any] { r["result"] as? [String: Any] ?? [:] }

final class TimerFallbackTests: XCTestCase {
    func testNoClockAXFallsBackToMuseletTimer() {
        let s = skills()
        defer { _ = s.timers.cancel(id: nil) }
        let r = result(s.execute(name: "start_timer", args: ["duration": 600]))
        XCTAssertEqual(r["backend"] as? String, "muselet")
        XCTAssertEqual(r["fallback_reason"] as? String, "clock_ax_unavailable")
        XCTAssertEqual(r["clock_ax_reason"] as? String, "clock_ax_unavailable")
        XCTAssertEqual(s.timerList().first?["backend"] as? String, "muselet")
    }

    func testTimerBackendRPCHasNoShortcutFields() {
        let rpc = RPCHandler(skills: skills(), warmUp: false)
        let (ok, r, _) = rpc.handle(method: "timer_backend", params: ["refresh": true])
        XCTAssertTrue(ok)
        let d = r as? [String: Any] ?? [:]
        XCTAssertEqual(Set(d.keys), ["clock_ax_ready", "backend"])
        XCTAssertEqual(d["backend"] as? String, "muselet")
        XCTAssertEqual(d["clock_ax_ready"] as? Bool, false)
    }

    func testTimersReportAndCancelMuseletTimer() {
        let s = skills()
        let id = result(s.execute(name: "start_timer", args: ["duration": 60]))["timer_id"] as? String ?? ""
        let report = s.timersReport()
        XCTAssertNil(report["clock"])
        XCTAssertNil(report["clock_ax"])
        XCTAssertEqual((report["timers"] as? [[String: Any]])?.first?["id"] as? String, id)
        let rpc = RPCHandler(skills: s, warmUp: false)
        let (ok, r, err) = rpc.handle(method: "timers_cancel", params: [:])
        XCTAssertTrue(ok, err ?? "")
        XCTAssertEqual(((r as? [String: Any])?["cancelled"] as? [[String: Any]])?.first?["id"] as? String, id)
        XCTAssertEqual(s.pendingTimers, 0)
    }

    func testSnapshotRoundTripKeepsBackend() {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("clock-snap-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let now = Date()
        let info = TimerRegistry.Info(id: "timer-c", label: "Tea", total: 600, startedAt: now,
                                      firesAt: now.addingTimeInterval(600), backend: "clock_ax")
        TimerSnapshot.write([info], pid: 111, process: "Muselet", directory: dir, gc: false)
        TimerSnapshot.flush()
        let got = TimerSnapshot.read(directory: dir, now: now, isAlive: { $0 == 111 })
        XCTAssertEqual(got.first?["backend"] as? String, "clock_ax")
        XCTAssertEqual(got.first?["label"] as? String, "Tea")
    }
}
