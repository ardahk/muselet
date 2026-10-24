import Foundation
import XCTest
@testable import HandsKit

// Clock.app timers via the user's shortcuts (docs/CLOCK_TIMERS.md). No real
// `shortcuts` runs here: FakeShortcuts stands in for /usr/bin/shortcuts.

private func catalog() -> [String: SkillDef] { try! Catalog.load() }

final class FakeShortcuts: ShortcutsRunning {
    var listOutput = ""
    var listResult: ShortcutRun?
    /// Per shortcut name; default: exit 0, no output.
    var results: [String: ShortcutRun] = [:]
    private(set) var listCalls = 0
    /// (name, input path, input file content at run time).
    private(set) var runs: [(name: String, path: String?, input: String?)] = []

    init(installed: [String] = []) { listOutput = installed.joined(separator: "\n") }

    func list() -> ShortcutRun {
        listCalls += 1
        return listResult ?? ShortcutRun(exitCode: 0, stdout: listOutput)
    }

    func run(_ name: String, inputPath: String?) -> ShortcutRun {
        let input = inputPath.flatMap { try? String(contentsOfFile: $0, encoding: .utf8) }
        runs.append((name, inputPath, input))
        return results[name] ?? ShortcutRun(exitCode: 0, ms: 420)
    }
}

private func skills(_ fake: FakeShortcuts, changed: (([TimerRegistry.Info]) -> Void)? = nil) -> Skills {
    var hooks = SystemHooks.inert
    hooks.shortcuts = fake
    if let changed { hooks.timersChanged = changed }
    return Skills(catalog: catalog(), scripts: SpyRunner(), events: MockPoster(), apps: MockApps(), hooks: hooks)
}

private func result(_ r: [String: Any]) -> [String: Any] { r["result"] as? [String: Any] ?? [:] }

final class ShortcutDetectionTests: XCTestCase {
    func testParseListExactNamesOnly() {
        let out = """
            Morning Routine
              Muselet Start Timer  \r
            muselet cancel timer
            Muselet Start Timer 2
            Muselet Timer Status
            """
        XCTAssertEqual(ClockShortcut.parseList(out), [ClockShortcut.start, ClockShortcut.status])
        XCTAssertEqual(ClockShortcut.parseList(""), [])
        XCTAssertEqual(ClockShortcut.parseList("Muselet Cancel Timer\nMuselet Start Timer\n"),
                       [ClockShortcut.start, ClockShortcut.cancel])          // `all` order
    }

    func testCacheSixtySecondsAndRefreshOnMiss() {
        let fake = FakeShortcuts(installed: [ClockShortcut.start])
        let c = ClockTimers(runner: fake)
        var t = Date(timeIntervalSince1970: 1_000)
        c.now = { t }
        XCTAssertTrue(c.has(ClockShortcut.start))
        t += 30
        XCTAssertTrue(c.has(ClockShortcut.start))
        XCTAssertEqual(fake.listCalls, 1)                     // cached
        t += 31
        XCTAssertTrue(c.has(ClockShortcut.start))
        XCTAssertEqual(fake.listCalls, 2)                     // 61 s: expired

        // A miss re-lists (the user just added the shortcut), at most every 2 s.
        fake.listOutput = ClockShortcut.start
        XCTAssertFalse(c.has(ClockShortcut.cancel))
        XCTAssertEqual(fake.listCalls, 2)                     // listed < 2 s ago
        t += 3
        fake.listOutput = "\(ClockShortcut.start)\n\(ClockShortcut.cancel)"
        XCTAssertTrue(c.has(ClockShortcut.cancel))
        XCTAssertEqual(fake.listCalls, 3)
        _ = c.installed(refresh: true)
        XCTAssertEqual(fake.listCalls, 4)
    }

    func testListFailureMeansNothingInstalled() {
        let fake = FakeShortcuts(installed: [ClockShortcut.start])
        fake.listResult = ShortcutRun(exitCode: 1, stdout: ClockShortcut.start)
        XCTAssertEqual(ClockTimers(runner: fake).installed(), [])
        fake.listResult = ShortcutRun(exitCode: 0, stdout: ClockShortcut.start, timedOut: true)
        XCTAssertEqual(ClockTimers(runner: fake).installed(), [])
    }

    func testTimerBackendRPC() {
        let fake = FakeShortcuts(installed: [ClockShortcut.start, ClockShortcut.status])
        let rpc = RPCHandler(skills: skills(fake), warmUp: false)
        let (ok, r, err) = rpc.handle(method: "timer_backend", params: [:])
        XCTAssertTrue(ok, err ?? "")
        let d = r as? [String: Any] ?? [:]
        XCTAssertEqual(d["clock_ready"] as? Bool, true)
        XCTAssertEqual(d["shortcuts"] as? [String], [ClockShortcut.start, ClockShortcut.status])
        XCTAssertEqual(d["backend"] as? String, "clock")
        XCTAssertEqual(d["cancel_ready"] as? Bool, false)
        XCTAssertTrue(JSONSerialization.isValidJSONObject(d))

        let none = RPCHandler(skills: skills(FakeShortcuts()), warmUp: false)
        let d2 = none.handle(method: "timer_backend", params: [:]).1 as? [String: Any] ?? [:]
        XCTAssertEqual(d2["clock_ready"] as? Bool, false)
        XCTAssertEqual(d2["shortcuts"] as? [String], [])
        XCTAssertEqual(d2["backend"] as? String, "muselet")
    }
}

final class ClockStartTests: XCTestCase {
    func testInputText() {
        XCTAssertEqual(ClockShortcut.inputText(seconds: 600), "600")
        XCTAssertEqual(ClockShortcut.inputText(seconds: 89.6), "90")
        XCTAssertEqual(ClockShortcut.inputText(seconds: 0.2), "1")
        XCTAssertEqual(ClockShortcut.inputText(seconds: 86_400), "86400")
    }

    func testFailureReasons() {
        XCTAssertNil(ClockShortcut.failureReason(ShortcutRun(exitCode: 0)))
        XCTAssertEqual(ClockShortcut.failureReason(ShortcutRun(exitCode: 1)), "shortcut_exit_1")
        XCTAssertEqual(ClockShortcut.failureReason(ShortcutRun(exitCode: 0, timedOut: true)), "shortcut_timeout")
        XCTAssertEqual(ClockShortcut.failureReason(ShortcutRun(exitCode: 15, timedOut: true)), "shortcut_timeout")
        XCTAssertEqual(ClockShortcut.failureReason(ShortcutRun(exitCode: -1)), "shortcuts_unavailable")
    }

    func testClockSuccessWritesInputFileAndKeepsRecord() {
        let fake = FakeShortcuts(installed: [ClockShortcut.start])
        var snaps: [[TimerRegistry.Info]] = []
        let s = skills(fake) { snaps.append($0) }
        defer { _ = s.timers.cancel(id: nil) }
        let r = s.execute(name: "start_timer", args: ["duration": "10 minutes", "label": "Tea"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let d = result(r)
        XCTAssertEqual(d["backend"] as? String, "clock")
        XCTAssertEqual(d["seconds"] as? Double, 600)
        XCTAssertEqual(d["label"] as? String, "Tea")
        XCTAssertEqual(d["ms"] as? Double, 420)
        XCTAssertNil(d["fallback_reason"])
        XCTAssertEqual(fake.runs.count, 1)
        XCTAssertEqual(fake.runs[0].name, ClockShortcut.start)
        XCTAssertEqual(fake.runs[0].input, "600")
        let path = try! XCTUnwrap(fake.runs[0].path)
        XCTAssertFalse(FileManager.default.fileExists(atPath: path))      // temp file removed
        // Muselet's own record (timers RPC + snapshot for bench/hobbylm).
        let list = s.timerList()
        XCTAssertEqual(list.count, 1)
        XCTAssertEqual(list[0]["backend"] as? String, "clock")
        XCTAssertEqual(list[0]["label"] as? String, "Tea")
        XCTAssertEqual(list[0]["id"] as? String, d["timer_id"] as? String)
        XCTAssertEqual(snaps.last?.map(\.backend), ["clock"])
    }

    private func fallback(_ fake: FakeShortcuts, enabled: Bool = true) -> (Skills, [String: Any]) {
        let s = skills(fake)
        s.clock.enabled = enabled
        let r = s.execute(name: "start_timer", args: ["duration": 600])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        return (s, result(r))
    }

    func testFallbackShortcutMissing() {
        let fake = FakeShortcuts(installed: ["Something Else"])
        let (s, d) = fallback(fake)
        defer { _ = s.cancelTimers(id: nil) }
        XCTAssertEqual(d["backend"] as? String, "muselet")
        XCTAssertEqual(d["fallback_reason"] as? String, "shortcut_missing")
        XCTAssertTrue(fake.runs.isEmpty)
        XCTAssertEqual(s.pendingTimers, 1)
        XCTAssertEqual(s.timerList().first?["backend"] as? String, "muselet")
    }

    func testFallbackNonZeroExitAndTimeout() {
        for (run, reason) in [(ShortcutRun(exitCode: 1, stderr: "no timer"), "shortcut_exit_1"),
                              (ShortcutRun(exitCode: 15, timedOut: true, ms: 10_000), "shortcut_timeout")] {
            let fake = FakeShortcuts(installed: [ClockShortcut.start])
            fake.results[ClockShortcut.start] = run
            let (s, d) = fallback(fake)
            XCTAssertEqual(d["backend"] as? String, "muselet", reason)
            XCTAssertEqual(d["fallback_reason"] as? String, reason)
            XCTAssertNotNil(d["timer_id"] as? String)
            XCTAssertEqual(s.timerList().map { $0["backend"] as? String }, ["muselet"])
            _ = s.cancelTimers(id: nil)
            // A failed run drops the cache: the next timer re-lists.
            let before = fake.listCalls
            _ = s.clock.installed(need: nil)
            XCTAssertEqual(fake.listCalls, before + 1)
        }
    }

    func testToggleOffNeverRunsShortcuts() {
        let fake = FakeShortcuts(installed: [ClockShortcut.start])
        let (s, d) = fallback(fake, enabled: false)
        defer { _ = s.cancelTimers(id: nil) }
        XCTAssertEqual(d["fallback_reason"] as? String, "clock_off")
        XCTAssertEqual(fake.listCalls, 0)
        XCTAssertTrue(fake.runs.isEmpty)
    }

    func testSnapshotRoundTripKeepsBackend() {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("clock-snap-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let now = Date()
        let info = TimerRegistry.Info(id: "timer-c", label: "Tea", total: 600, startedAt: now,
                                      firesAt: now.addingTimeInterval(600), backend: "clock")
        TimerSnapshot.write([info], pid: 111, process: "Muselet", directory: dir, gc: false)
        TimerSnapshot.flush()
        let got = TimerSnapshot.read(directory: dir, now: now, isAlive: { $0 == 111 })
        XCTAssertEqual(got.first?["backend"] as? String, "clock")
        XCTAssertEqual(got.first?["label"] as? String, "Tea")
    }
}

final class ClockCancelAndMergeTests: XCTestCase {
    private func clockSkills(_ installed: [String]) -> (Skills, FakeShortcuts, String) {
        let fake = FakeShortcuts(installed: installed)
        let s = skills(fake)
        let id = result(s.execute(name: "start_timer", args: ["duration": 600]))["timer_id"] as? String ?? ""
        return (s, fake, id)
    }

    func testCancelClockWithoutShortcutIsUnsupported() {
        let (s, _, id) = clockSkills([ClockShortcut.start])
        defer { _ = s.timers.cancel(id: nil) }
        let rpc = RPCHandler(skills: s, warmUp: false)
        let (ok, r, err) = rpc.handle(method: "timers_cancel", params: ["id": id])
        XCTAssertFalse(ok)
        XCTAssertTrue(err?.hasPrefix("unsupported") ?? false, err ?? "")
        let d = r as? [String: Any] ?? [:]
        XCTAssertEqual(d["unsupported"] as? [String], [id])
        XCTAssertEqual((d["cancelled"] as? [[String: Any]])?.count, 0)
        XCTAssertEqual(s.pendingTimers, 1)                                   // record kept
        XCTAssertTrue(JSONSerialization.isValidJSONObject(d))
    }

    func testCancelClockRunsCancelShortcut() {
        let (s, fake, id) = clockSkills([ClockShortcut.start, ClockShortcut.cancel])
        let rpc = RPCHandler(skills: s, warmUp: false)
        let (ok, r, err) = rpc.handle(method: "timers_cancel", params: [:])
        XCTAssertTrue(ok, err ?? "")
        XCTAssertEqual(fake.runs.last?.name, ClockShortcut.cancel)
        XCTAssertNil(fake.runs.last?.path)
        let d = r as? [String: Any] ?? [:]
        XCTAssertEqual((d["cancelled"] as? [[String: Any]])?.first?["id"] as? String, id)
        XCTAssertEqual(s.pendingTimers, 0)
    }

    func testCancelClockShortcutFailureKeepsRecord() {
        let (s, fake, id) = clockSkills([ClockShortcut.start, ClockShortcut.cancel])
        defer { _ = s.timers.cancel(id: nil) }
        fake.results[ClockShortcut.cancel] = ShortcutRun(exitCode: 0, timedOut: true)
        let rpc = RPCHandler(skills: s, warmUp: false)
        let (ok, r, err) = rpc.handle(method: "timers_cancel", params: ["id": id])
        XCTAssertFalse(ok)
        XCTAssertEqual(err, "clock_cancel_failed: shortcut_timeout")
        XCTAssertEqual(((r as? [String: Any])?["failed"] as? [[String: Any]])?.first?["id"] as? String, id)
        XCTAssertEqual(s.pendingTimers, 1)
    }

    func testCancelMixedMuseletTimerStillCancelled() {
        let fake = FakeShortcuts()                                           // Muselet timer
        let s = skills(fake)
        _ = s.execute(name: "start_timer", args: ["duration": 60])
        fake.listOutput = ClockShortcut.start
        s.clock.invalidate()
        _ = s.execute(name: "start_timer", args: ["duration": 600])           // Clock timer
        defer { _ = s.timers.cancel(id: nil) }
        let c = s.cancelTimersDetailed(id: nil)
        XCTAssertEqual(c.cancelled.map { $0["backend"] as? String }, ["muselet"])
        XCTAssertEqual(c.unsupported.count, 1)
        XCTAssertEqual(s.timerList().map { $0["backend"] as? String }, ["clock"])
    }

    func testParseStatus() {
        XCTAssertEqual(ClockShortcut.parseStatus(""), ClockShortcut.Status.none)
        XCTAssertEqual(ClockShortcut.parseStatus("0\n"), ClockShortcut.Status.none)
        XCTAssertEqual(ClockShortcut.parseStatus("598\n"), .running(left: 598))
        XCTAssertEqual(ClockShortcut.parseStatus("9:58"), .running(left: 598))
        XCTAssertEqual(ClockShortcut.parseStatus("1:00:00"), .running(left: 3600))
        XCTAssertEqual(ClockShortcut.parseStatus("9 minutes 58 seconds"), .running(left: 598))
        XCTAssertEqual(ClockShortcut.parseStatus("Timer"), .unknown("Timer"))
    }

    private let records: [[String: Any]] = [
        ["id": "timer-m", "label": NSNull(), "left_s": 50.0, "backend": "muselet"],
        ["id": "timer-a", "label": "Tea", "left_s": 300.0, "backend": "clock"],
        ["id": "timer-b", "label": NSNull(), "left_s": 598.0, "backend": "clock"],
    ]

    func testMergeMatchesClockTimerWithinTolerance() {
        let m = TimerMerge.merge(records, status: .running(left: 596))
        XCTAssertEqual(m.timers.count, 3)                                    // nothing dropped
        XCTAssertEqual(m.timers.map { $0["id"] as? String }, ["timer-m", "timer-a", "timer-b"])
        XCTAssertEqual(m.timers[2]["clock_seen"] as? Bool, true)
        XCTAssertEqual(m.timers[2]["clock_left_s"] as? Double, 596)
        XCTAssertNil(m.timers[1]["clock_seen"])                              // Clock reports one timer
        XCTAssertNil(m.timers[0]["clock_seen"])                              // Muselet timers untouched
        XCTAssertEqual(m.clock["status"] as? String, "running")
        XCTAssertEqual(m.clock["matched_id"] as? String, "timer-b")
    }

    func testMergeUnmatchedNoneUnknownAndUnavailable() {
        let far = TimerMerge.merge(records, status: .running(left: 1200))
        XCTAssertEqual(far.clock["unmatched"] as? Bool, true)
        XCTAssertFalse(far.timers.contains { $0["clock_seen"] != nil })

        let none = TimerMerge.merge(records, status: ClockShortcut.Status.none)
        XCTAssertEqual(none.clock["status"] as? String, "none")
        XCTAssertEqual(none.timers.map { $0["clock_seen"] as? Bool }, [nil, false, false])

        let unknown = TimerMerge.merge(records, status: .unknown("shortcut_timeout"))
        XCTAssertEqual(unknown.clock["status"] as? String, "unknown")
        XCTAssertEqual(unknown.clock["raw"] as? String, "shortcut_timeout")

        let un = TimerMerge.merge(records, status: nil)
        XCTAssertEqual(un.clock["status"] as? String, "unavailable")
        XCTAssertEqual(un.timers.count, 3)
    }

    func testTimersRPCAsksStatusOnlyWithClockTimers() {
        let fake = FakeShortcuts(installed: [ClockShortcut.start, ClockShortcut.status])
        fake.results[ClockShortcut.status] = ShortcutRun(exitCode: 0, stdout: "599\n")
        let s = skills(fake)
        defer { _ = s.timers.cancel(id: nil) }
        let rpc = RPCHandler(skills: s, warmUp: false)
        var d = rpc.handle(method: "timers", params: [:]).1 as? [String: Any] ?? [:]
        XCTAssertEqual((d["clock"] as? [String: Any])?["status"] as? String, "unavailable")
        XCTAssertFalse(fake.runs.contains { $0.name == ClockShortcut.status })

        _ = s.execute(name: "start_timer", args: ["duration": 600])
        d = rpc.handle(method: "timers", params: [:]).1 as? [String: Any] ?? [:]
        let timers = d["timers"] as? [[String: Any]] ?? []
        XCTAssertEqual(timers.count, 1)
        XCTAssertEqual(timers[0]["clock_seen"] as? Bool, true)
        XCTAssertEqual((d["clock"] as? [String: Any])?["status"] as? String, "running")
        XCTAssertEqual((d["backend"] as? [String: Any])?["clock_ready"] as? Bool, true)
        XCTAssertTrue(JSONSerialization.isValidJSONObject(d))
    }
}
