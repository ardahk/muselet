import ApplicationServices
import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Tests for: hands-12 (scoped appears fallback), planner-11 (shell exit
// codes), hands-13 (act truncated flag), training-11 (item selection ctx),
// confirm_cancel / ui.ms frames, web AX switches, skill ghost targets.
// Hermetic: mock AX trees; the shell tests run /bin/zsh with harmless commands.

private func observeMock(_ h: Hands, _ root: Element, maxNodes: Int = 150, pid: pid_t = 1) -> Observation {
    h.processObservation(roots: [root], app: "Mock", window: "W", pid: pid,
                         maxNodes: maxNodes, diff: true,
                         deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
}

private func el(_ role: String, _ title: String? = nil, x: CGFloat = 10, y: CGFloat = 10,
                w: CGFloat = 80, h: CGFloat = 24, _ kids: [MockElement] = []) -> MockElement {
    MockElement(role: role, title: title, x: x, y: y, w: w, h: h, children: kids)
}

// MARK: - hands-12: appears fallback scope

final class AppearsScopeTests: XCTestCase {
    /// App with a menu bar (File/Format closed, Edit open), one document
    /// window (button OK, sheet Export, popover Share), a context menu.
    private func app(editOpen: Bool = false, contextMenu: Bool = false) -> MockElement {
        let formatMenu = el("AXMenu", w: 0, h: 0, [el("AXMenuItem", "Font", x: 0, y: 0, w: 0, h: 0)])
        let editMenu = editOpen
            ? el("AXMenu", x: 40, y: 24, w: 200, h: 120, [el("AXMenuItem", "Paste and Match Style", x: 44, y: 30)])
            : el("AXMenu", w: 0, h: 0, [el("AXMenuItem", "Paste and Match Style", x: 0, y: 0, w: 0, h: 0)])
        let bar = el("AXMenuBar", x: 0, y: 0, w: 1000, h: 24, [
            el("AXMenuBarItem", "File", x: 10, y: 0),
            el("AXMenuBarItem", "Edit", x: 50, y: 0, [editMenu]),
            el("AXMenuBarItem", "Format", x: 90, y: 0, [formatMenu]),
        ])
        let sheet = el("AXSheet", x: 100, y: 100, w: 300, h: 200, [el("AXButton", "Export", x: 120, y: 120)])
        let popover = el("AXPopover", x: 400, y: 100, w: 200, h: 100, [el("AXButton", "Copy Link", x: 410, y: 110)])
        let win = el("AXWindow", "Budget.numbers", x: 0, y: 30, w: 800, h: 600,
                     [el("AXButton", "OK", x: 20, y: 40), sheet, popover])
        var kids: [MockElement] = [bar, win]
        if contextMenu {
            kids.append(el("AXMenu", x: 300, y: 300, w: 180, h: 80, [el("AXMenuItem", "Inspect Element", x: 305, y: 305)]))
        }
        let a = el("AXApplication", x: 0, y: 0, w: 0, h: 0, kids)
        a.singles[kAXWindowsAttribute as String] = [win]
        a.singles["AXMenuBar"] = bar
        return a
    }

    private func search(_ label: String, _ a: MockElement) -> Bool {
        Hands.searchLabel(label, app: a, deadline: Date().addingTimeInterval(1))
    }

    func testMenuBarTitlesNeverPass() {
        let a = app()
        for t in ["Format", "File", "Edit"] { XCTAssertFalse(search(t, a), t) }
        XCTAssertFalse(search("Font", a))                     // closed menu's item
        XCTAssertFalse(search("Paste and Match Style", a))    // closed menu's item
    }

    func testOpenMenuItemsPass() {
        let a = app(editOpen: true)
        XCTAssertTrue(search("Paste and Match", a))
        XCTAssertFalse(search("Edit", a))                     // the bar title still doesn't
        XCTAssertFalse(search("Format", a))
    }

    func testWindowsSheetsPopoversAndContextMenus() {
        let a = app(contextMenu: true)
        XCTAssertTrue(search("OK", a))
        XCTAssertTrue(search("Export", a))                    // sheet
        XCTAssertTrue(search("Copy Link", a))                 // popover
        XCTAssertTrue(search("Inspect Element", a))           // open context menu
        XCTAssertTrue(search("budget", a))                    // own window title
        XCTAssertFalse(search("Nope", a))
    }

    func testRootsExcludeMenuBar() {
        let roots = Hands.labelSearchRoots(app: app())
        XCTAssertFalse(roots.contains { ($0.el as? MockElement)?.attrs.role == "AXMenuBar" })
        XCTAssertEqual(roots.filter { $0.window }.count, 1)   // window listed once (AXWindows + child)
    }
}

// MARK: - planner-11: shell exit codes

final class ShellScriptTests: XCTestCase {
    private func hands() -> Hands {
        let h = Hands()
        let w = el("AXWindow", "W", x: 0, y: 0, w: 400, h: 300, [el("AXButton", "OK")])
        w.stableIdOverride = 9101
        _ = observeMock(h, w)
        h.settleOverride = { _ in 0 }
        h.observeOverride = { observeMock(h, w) }
        return h
    }

    func testNonZeroExitIsNotOK() {
        let r = hands().act(["op": "script", "lang": "shell",
                             "code": "echo out; echo boom >&2; exit 3"])
        XCTAssertEqual(r["ok"] as? Bool, false, "\(r)")
        XCTAssertEqual(r["exit_code"] as? Int, 3)
        XCTAssertEqual(r["stdout"] as? String, "out\n")
        XCTAssertEqual(r["stderr"] as? String, "boom\n")
        XCTAssertEqual(r["error"] as? String, "script_failed: exit 3: boom")
        XCTAssertNotNil(r["settle_ms"])                       // still re-observed
    }

    func testZeroExitIsOK() {
        let r = hands().act(["op": "script", "lang": "shell", "code": "printf hi"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["exit_code"] as? Int, 0)
        XCTAssertEqual(r["output"] as? String, "hi")
        XCTAssertNil(r["error"])
    }

    func testLargeOutputDoesNotBlock() {
        let t0 = Date()
        let r = hands().act(["op": "script", "lang": "shell",
                             "code": "head -c 300000 /dev/zero | tr '\\0' a"])
        XCTAssertLessThan(Date().timeIntervalSince(t0), 3)    // no 64 KB pipe deadlock
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r["error"] ?? "")")
        XCTAssertTrue((r["stdout"] as? String ?? "").hasPrefix("aaaa"))
        XCTAssertTrue((r["stdout"] as? String ?? "").hasSuffix("[truncated]"))
    }

    func testTimeoutReportsTimedOut() throws {
        let t0 = Date()
        let r = try Hands().runShell("echo started; sleep 5", timeout: 0.3)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 2.5)
        XCTAssertEqual(r["timed_out"] as? Bool, true)
        XCTAssertEqual(r["stdout"] as? String, "started\n")
        XCTAssertNotEqual(r["exit_code"] as? Int, 0)
    }
}

// MARK: - hands-13: truncated fused re-observation

final class ActTruncatedTests: XCTestCase {
    func testActReportsTruncatedReobservation() {
        let h = Hands()
        let w = el("AXWindow", "W", x: 0, y: 0, w: 400, h: 300,
                   [el("AXButton", "A", y: 10), el("AXButton", "B", y: 40), el("AXButton", "C", y: 70)])
        w.stableIdOverride = 9201
        _ = observeMock(h, w)
        h.settleOverride = { _ in 0 }
        h.observeOverride = { observeMock(h, w, maxNodes: 2) }
        let r = h.act(["op": "wait", "ms": 0])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["truncated"] as? Bool, true)
        XCTAssertTrue((r["diff_text"] as? String ?? "").contains("- #"))   // the capped element

        h.observeOverride = { observeMock(h, w, maxNodes: 150) }
        let r2 = h.act(["op": "wait", "ms": 0])
        XCTAssertNil(r2["truncated"], "\(r2)")
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

// MARK: - web AX switches

final class WebAXTests: XCTestCase {
    func testModeMapping() {
        XCTAssertEqual(WebAX.mode(bundleId: "com.google.Chrome", bundleURL: nil), .chromium)
        XCTAssertEqual(WebAX.mode(bundleId: "company.thebrowser.Browser", bundleURL: nil), .chromium)
        XCTAssertEqual(WebAX.mode(bundleId: "com.apple.Safari", bundleURL: nil), .enhanced)
        XCTAssertEqual(WebAX.mode(bundleId: "app.zen-browser.zen", bundleURL: nil), .enhanced)
        XCTAssertEqual(WebAX.mode(bundleId: "org.mozilla.firefox", bundleURL: nil), .enhanced)
        XCTAssertEqual(WebAX.mode(bundleId: "com.tinyspeck.slackmacgap", bundleURL: nil), .manual)
        XCTAssertEqual(WebAX.mode(bundleId: "com.github.Electron.helper.electron", bundleURL: nil), .manual)
        XCTAssertNil(WebAX.mode(bundleId: "com.apple.finder", bundleURL: nil))
        XCTAssertNil(WebAX.mode(bundleId: "com.apple.Notes", bundleURL: nil))
    }

    func testRegistryEnablesOncePerProcess() {
        let reg = WebAX.Registry()
        let app = el("AXApplication")
        app.settable = [WebAX.manualAttribute]
        let launch = Date(timeIntervalSince1970: 1000)
        let r = reg.ensure(pid: 4242, bundleId: "com.tinyspeck.slackmacgap", bundleURL: nil,
                           launchDate: launch, app: app)
        XCTAssertEqual(r?.mode, .manual)
        XCTAssertEqual(r?.manualError, 0)
        XCTAssertNil(r?.enhancedError)                        // Electron: manual only
        XCTAssertEqual(app.store[WebAX.manualAttribute] as? Bool, true)
        XCTAssertFalse(r?.delayed ?? true)
        XCTAssertNil(reg.ensure(pid: 4242, bundleId: "com.tinyspeck.slackmacgap", bundleURL: nil,
                                launchDate: launch, app: app))           // once
        XCTAssertNotNil(reg.enabledAt(pid: 4242))
        // Same pid, new process (other launch date): enabled again.
        XCTAssertNotNil(reg.ensure(pid: 4242, bundleId: "com.tinyspeck.slackmacgap", bundleURL: nil,
                                   launchDate: launch.addingTimeInterval(5), app: app))
        // Not a web app: nothing set, never re-checked.
        let notes = el("AXApplication")
        XCTAssertNil(reg.ensure(pid: 4343, bundleId: "com.apple.Notes", bundleURL: nil, launchDate: launch, app: notes))
        XCTAssertTrue(notes.store.isEmpty)
        // Never our own process; global switch off -> nothing.
        XCTAssertNil(reg.ensure(pid: getpid(), bundleId: "com.google.Chrome", bundleURL: nil, launchDate: nil, app: app))
        reg.isEnabled = false
        XCTAssertNil(reg.ensure(pid: 4444, bundleId: "com.google.Chrome", bundleURL: nil, launchDate: nil, app: app))
    }

    func testChromiumSetsBothAndIsDelayedWhenManualUnsupported() {
        let reg = WebAX.Registry()
        let chrome = el("AXApplication")
        chrome.settable = [WebAX.enhancedAttribute]           // AXManualAccessibility unsupported
        let r = reg.ensure(pid: 5151, bundleId: "com.google.Chrome", bundleURL: nil, launchDate: nil, app: chrome)
        XCTAssertEqual(r?.mode, .chromium)
        XCTAssertNotEqual(r?.manualError, 0)
        XCTAssertEqual(r?.enhancedError, 0)
        XCTAssertEqual(chrome.store[WebAX.enhancedAttribute] as? Bool, true)
        XCTAssertTrue(r?.delayed ?? false)                    // 2 s debounce: skip the populate wait
        XCTAssertTrue(reg.pending(pid: 5151))
        XCTAssertFalse(reg.pending(pid: 5151, now: Date().addingTimeInterval(3)))
    }

    func testPopulateTimeLeftAfterPrewarm() {
        let reg = WebAX.Registry()
        let zen = el("AXApplication")
        zen.settable = [WebAX.enhancedAttribute]
        _ = reg.ensure(pid: 7171, bundleId: "app.zen-browser.zen", bundleURL: nil, launchDate: nil, app: zen)
        let left = reg.populateTimeLeft(pid: 7171) ?? 0
        XCTAssertGreaterThan(left, 0.2)                       // observe waits the rest of the 300 ms
        XCTAssertLessThanOrEqual(left, WebAX.populateTimeout)
        XCTAssertNil(reg.populateTimeLeft(pid: 7171, now: Date().addingTimeInterval(0.5)))
        let chrome = el("AXApplication")
        chrome.settable = [WebAX.enhancedAttribute]
        _ = reg.ensure(pid: 7272, bundleId: "com.google.Chrome", bundleURL: nil, launchDate: nil, app: chrome)
        XCTAssertNil(reg.populateTimeLeft(pid: 7272))         // delayed: no point waiting
        XCTAssertNil(reg.populateTimeLeft(pid: 9999))
    }

    func testEnhancedAlreadyOnIsNotResetAndNotDelayed() {
        let reg = WebAX.Registry()
        let safari = el("AXApplication")
        safari.settable = [WebAX.enhancedAttribute]
        safari.singles[WebAX.enhancedAttribute] = true
        let r = reg.ensure(pid: 6161, bundleId: "com.apple.Safari", bundleURL: nil, launchDate: nil, app: safari)
        XCTAssertEqual(r?.enhancedAlreadyOn, true)
        XCTAssertNil(r?.enhancedError)
        XCTAssertTrue(safari.store.isEmpty)                   // never re-set (Chrome's debounce restarts)
        XCTAssertFalse(r?.delayed ?? true)
    }

    func testWaitForWebAreaReturnsWhenPopulated() {
        let area = el("AXWebArea", w: 400, h: 300, [el("AXLink", "Learn more")])
        let win = el("AXWindow", w: 800, h: 600, [el("AXToolbar", nil, [el("AXButton", "Back")]),
                                                  el("AXGroup", w: 800, h: 500, [area])])
        let w = WebAX.waitForWebArea(root: win)
        XCTAssertTrue(w.populated)
        XCTAssertEqual(w.polls, 1)
        let empty = el("AXWindow", w: 800, h: 600, [el("AXGroup", w: 800, h: 500, [el("AXWebArea", w: 400, h: 300)])])
        let t0 = Date()
        let w2 = WebAX.waitForWebArea(root: empty, timeout: 5)          // clamped to 300 ms
        XCTAssertFalse(w2.populated)
        XCTAssertTrue(w2.foundWebArea)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.6)
    }
}

// MARK: - ux-4: skill ghost targets

final class SkillTargetTests: XCTestCase {
    private let screen = CGRect(x: 0, y: 0, width: 1800, height: 1169)

    private final class Counter { var n = 0 }

    private func targets(dockY: CGFloat = 1080, extras: [SkillTargets.MenuExtra]? = nil,
                         reads: Counter? = nil) -> SkillTargets {
        let t = SkillTargets()
        let y = dockY
        t.readDock = {
            reads?.n += 1
            return [
                .init(title: "Finder", path: "/System/Library/CoreServices/Finder.app",
                      frame: CGRect(x: 112, y: y, width: 77, height: 93)),
                .init(title: "Zen", path: "/Applications/Zen.app", frame: CGRect(x: 420, y: y, width: 77, height: 93)),
                .init(title: "Safari", path: "/System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app",
                      frame: CGRect(x: 1190, y: y, width: 77, height: 93)),
                .init(title: "Numbers", path: "/Applications/Numbers Creator Studio.app",
                      frame: CGRect(x: 1344, y: y, width: 77, height: 93)),
            ]
        }
        t.readExtras = {
            extras ?? [
                .init(ident: "com.apple.menuextra.wifi", frame: CGRect(x: 1614, y: 8, width: 22, height: 24)),
                .init(ident: "com.apple.menuextra.controlcenter", frame: CGRect(x: 1652, y: 8, width: 26, height: 24)),
            ]
        }
        t.screens = { [screen] in screen }
        t.appPath = { name in name == "Safari" ? "/Applications/Safari.app" : nil }
        t.browserPath = { "/Applications/Zen.app" }
        return t
    }

    func testAppSkillsTargetTheDockIcon() {
        let t = targets()
        let s = t.target(skill: "open_app", args: ["app": "Safari"])
        XCTAssertEqual(s?.frame.minX, 1190)                   // matched by bundle name across paths
        XCTAssertEqual(s?.label, "Safari")
        XCTAssertEqual(t.target(skill: "quit_app", args: ["app": "Numbers"])?.frame.minX, 1344)  // title prefix
        XCTAssertEqual(t.target(skill: "hide_app", args: ["app": "zen"])?.frame.minX, 420)
        XCTAssertNil(t.target(skill: "open_app", args: ["app": "Xcode"]))   // not in the Dock
    }

    func testFinderAndBrowserSkills() {
        let t = targets()
        XCTAssertEqual(t.target(skill: "open_folder", args: ["path": "~/Downloads"])?.frame.minX, 112)
        XCTAssertEqual(t.target(skill: "open_folder", args: ["path": "~/Downloads"])?.label, "Downloads")
        XCTAssertEqual(t.target(skill: "find_file", args: ["query": "tax"])?.frame.minX, 112)
        XCTAssertEqual(t.target(skill: "new_folder", args: ["parent": "~", "name": "X"])?.frame.minX, 112)
        XCTAssertEqual(t.target(skill: "web_search", args: ["query": "flights"])?.frame.minX, 420)
        XCTAssertEqual(t.target(skill: "open_url", args: ["url": "github.com/x"])?.label, "github.com")
    }

    func testMenuExtrasWithControlCenterFallback() {
        let t = targets()
        XCTAssertEqual(t.target(skill: "wifi", args: ["on": false])?.frame.minX, 1614)
        XCTAssertEqual(t.target(skill: "wifi", args: ["on": false])?.label, "Off")
        XCTAssertEqual(t.target(skill: "set_volume", args: ["level": 30])?.frame.minX, 1652)  // no Sound extra
        XCTAssertEqual(t.target(skill: "set_volume", args: ["level": 30])?.label, "30%")
        for s in ["mute", "set_brightness", "dark_mode", "bluetooth", "change_volume"] {
            XCTAssertEqual(t.target(skill: s, args: [:])?.frame.minX, 1652, s)
        }
        let withSound = targets(extras: [
            .init(ident: "com.apple.menuextra.sound", frame: CGRect(x: 1500, y: 8, width: 22, height: 24)),
            .init(ident: "com.apple.menuextra.controlcenter", frame: CGRect(x: 1652, y: 8, width: 26, height: 24)),
        ])
        XCTAssertEqual(withSound.target(skill: "mute", args: ["on": true])?.frame.minX, 1500)
    }

    func testHiddenDockAndUntargetedSkills() {
        let hidden = targets(dockY: 1174)                     // auto-hidden Dock parks icons below the edge
        XCTAssertNil(hidden.target(skill: "open_app", args: ["app": "Safari"]))
        XCTAssertNil(hidden.target(skill: "open_folder", args: ["path": "~"]))
        XCTAssertFalse(SkillTargets.hasTarget("start_timer"))
        XCTAssertNil(targets().target(skill: "start_timer", args: ["duration": 60]))
        XCTAssertNil(targets(extras: []).target(skill: "wifi", args: ["on": true]))
    }

    func testFramesAreCachedForFiveSeconds() {
        let reads = Counter()
        var clock = Date(timeIntervalSince1970: 0)
        let t = targets(reads: reads)
        t.now = { clock }
        _ = t.target(skill: "open_app", args: ["app": "Safari"])
        _ = t.target(skill: "open_folder", args: ["path": "~"])
        clock = clock.addingTimeInterval(4.9)
        _ = t.target(skill: "open_app", args: ["app": "Zen"])
        XCTAssertEqual(reads.n, 1)
        clock = clock.addingTimeInterval(0.2)
        _ = t.target(skill: "open_app", args: ["app": "Zen"])
        XCTAssertEqual(reads.n, 2)
    }

    func testRPCSkillFliesGhostWithinLead() {
        final class GhostSpy: HandsDelegate {
            var frames: [CGRect?] = []
            var labels: [String?] = []
            func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval {
                frames.append(frame); labels.append(label)
                return 1.0                                     // a slow flight must not delay the skill > 120 ms
            }
            func handsDidAct(op: String, frame: CGRect?, ok: Bool) {}
        }
        let skills = Skills(catalog: try! Catalog.load(), scripts: VolumeSpy(), events: MockPoster(),
                            apps: MockApps(), hooks: .inert)
        let rpc = RPCHandler(skills: skills, skillTargets: targets(), warmUp: false)
        let spy = GhostSpy()
        rpc.delegate = spy
        let t0 = Date()
        let (ok, _, _) = rpc.handle(method: "skill", params: ["name": "set_volume", "args": ["level": 30]])
        XCTAssertTrue(ok)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.4)
        XCTAssertEqual(spy.frames.first??.minX, 1652)
        XCTAssertEqual(spy.labels.first ?? nil, "30%")
        // Skills without a natural target: no frame (ghost stays put, no wait).
        let t1 = Date()
        _ = rpc.handle(method: "skill", params: ["name": "battery_status", "args": [:]])
        XCTAssertEqual(spy.frames.count, 2)
        XCTAssertNil(spy.frames.last ?? nil)
        XCTAssertLessThan(Date().timeIntervalSince(t1), 0.2)
    }
}
