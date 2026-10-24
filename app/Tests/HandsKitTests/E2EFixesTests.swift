import ApplicationServices
import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Tests for the live-E2E fixes: observe window fallback (TextEdit blind),
// no_text_target for type_text / type, `hands serve` exit rules, skill
// AppleScripts compiled once as handlers, Automation status mapping,
// Control Center lookups in MenuBarAgent. Hermetic: mock AX trees, mock
// script compilers; the one real NSAppleScript test targets no app.

private func el(_ role: String, _ title: String? = nil, x: CGFloat = 10, y: CGFloat = 10,
                w: CGFloat = 80, h: CGFloat = 24, _ kids: [MockElement] = []) -> MockElement {
    MockElement(role: role, title: title, x: x, y: y, w: w, h: h, children: kids)
}

private func catalog() -> [String: SkillDef] { try! Catalog.load() }

// MARK: - 1. observe: focused -> main -> AXWindows -> app-scope roots

final class ObserveWindowFallbackTests: XCTestCase {
    /// TextEdit after open_app / after its key window closed: AXWindows has
    /// the document, but no focused or main window.
    private func textEditApp(focused: Bool = false, main: Bool = false,
                             minimizedFirst: Bool = false) -> (MockElement, MockElement) {
        let area = el("AXTextArea", x: 200, y: 130, w: 600, h: 380)
        let doc = el("AXWindow", "Untitled", x: 195, y: 92, w: 673, h: 439, [
            el("AXScrollArea", x: 195, y: 124, w: 673, h: 407, [area]),
            el("AXButton", "close button", x: 203, y: 100, w: 16, h: 16),
        ])
        let mini = el("AXWindow", "Minimized doc", x: 100, y: 100, w: 500, h: 400,
                      [el("AXButton", "Hidden", x: 110, y: 110)])
        mini.singles[kAXMinimizedAttribute as String] = true
        let bar = el("AXMenuBar", x: 0, y: 0, w: 1000, h: 24, [el("AXMenuBarItem", "File", x: 10, y: 0)])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0, [doc, bar])
        app.singles[kAXWindowsAttribute as String] = minimizedFirst ? [mini, doc] : [doc]
        app.singles["AXMenuBar"] = bar
        if focused { app.singles[kAXFocusedWindowAttribute as String] = doc }
        if main { app.singles[kAXMainWindowAttribute as String] = doc }
        return (app, doc)
    }

    func testFocusedThenMainThenWindows() {
        XCTAssertEqual(Hands.pickWindow(app: textEditApp(focused: true).0)?.source, "focused")
        XCTAssertEqual(Hands.pickWindow(app: textEditApp(main: true).0)?.source, "main")
        let (app, doc) = textEditApp()
        let p = Hands.pickWindow(app: app)
        XCTAssertEqual(p?.source, "windows")
        XCTAssertTrue(p?.window === doc)
    }

    func testMinimizedWindowsAreSkipped() {
        let (app, doc) = textEditApp(minimizedFirst: true)
        XCTAssertTrue(Hands.pickWindow(app: app)?.window === doc)
    }

    func testBlindAppNowYieldsTheDocument() {
        // The live bug: no focused/main window -> the app element was walked
        // and the zero-size AXApplication root pruned everything.
        let (app, _) = textEditApp()
        let r = Hands.observationRoots(app: app, scope: "focused_window")
        XCTAssertEqual(r.source, "windows")
        XCTAssertEqual(r.window, "Untitled")
        let h = Hands()
        let obs = h.processObservation(roots: r.roots, app: "TextEdit", window: r.window, pid: 1,
                                       maxNodes: 150, diff: true,
                                       deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
        XCTAssertTrue(obs.elements.contains { $0.role == "textarea" }, obs.text)
        XCTAssertTrue(obs.text.hasPrefix("app: TextEdit | window: \"Untitled\""))
    }

    func testAppRootIsTraversedNotPruned() {
        let (app, _) = textEditApp()
        let recs = Walker.walk(root: app, deadline: Date().addingTimeInterval(1))
        XCTAssertTrue(recs.contains { $0.role == "textarea" })
    }

    func testAppScopeFallbackForWindowLikeChildrenAndNoneWithoutWindows() {
        // A floating panel that isn't in AXWindows (window-like app child).
        let panel = el("AXSheet", "Open", x: 300, y: 200, w: 400, h: 300, [el("AXButton", "Cancel", x: 320, y: 460)])
        let bar = el("AXMenuBar", x: 0, y: 0, w: 1000, h: 24, [el("AXMenuBarItem", "File", x: 10, y: 0)])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0, [bar, panel])
        app.singles["AXMenuBar"] = bar
        let r = Hands.observationRoots(app: app, scope: "focused_window")
        XCTAssertEqual(r.source, "app")
        XCTAssertEqual(r.roots.count, 1)
        XCTAssertEqual(r.window, "Open")
        // No windows at all: nothing to walk; the menu bar is never a fallback
        // (its titles would satisfy `appears "File"`).
        let bare = el("AXApplication", x: 0, y: 0, w: 0, h: 0, [bar])
        bare.singles["AXMenuBar"] = bar
        let n = Hands.observationRoots(app: bare, scope: "focused_window")
        XCTAssertEqual(n.source, "none")
        XCTAssertTrue(n.roots.isEmpty)
    }

    func testScopeAppWalksAllWindows() {
        let w1 = el("AXWindow", "A", x: 0, y: 30, w: 400, h: 300, [el("AXButton", "One", x: 10, y: 40)])
        let w2 = el("AXWindow", "B", x: 420, y: 30, w: 400, h: 300, [el("AXButton", "Two", x: 430, y: 40)])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0, [w1, w2])
        app.singles[kAXWindowsAttribute as String] = [w1, w2]
        app.singles[kAXFocusedWindowAttribute as String] = w1
        let r = Hands.observationRoots(app: app, scope: "app")
        XCTAssertEqual(r.source, "all_windows")
        XCTAssertEqual(r.roots.count, 2)
        XCTAssertEqual(r.window, "A")
    }

    /// App whose focused window appears only at `readyAt` (just launched).
    private final class LateWindowApp: Element {
        let window: Element
        let readyAt: Date
        init(window: Element, readyAt: Date) { self.window = window; self.readyAt = readyAt }
        func copyAttrs() -> ElAttrs { var a = ElAttrs(); a.role = "AXApplication"; return a }
        func performAction(_ name: String) -> Bool { false }
        func setAttr(_ name: String, _ value: Any?) -> Bool { false }
        func isSettable(_ name: String) -> Bool { false }
        func copySingleAttr(_ name: String) -> Any? {
            name == kAXFocusedWindowAttribute as String && Date() >= readyAt ? window : nil
        }
    }

    func testWaitsForAWindowAfterLaunch() {
        let doc = el("AXWindow", "Untitled", x: 100, y: 100, w: 400, h: 300)
        let app = LateWindowApp(window: doc, readyAt: Date().addingTimeInterval(0.15))
        let r = Hands.observationRoots(app: app, scope: "focused_window",
                                       waitForWindowUntil: Date().addingTimeInterval(1))
        XCTAssertEqual(r.source, "focused")
        XCTAssertEqual(r.window, "Untitled")
        // Without the launch wait it falls through at once.
        let late = LateWindowApp(window: doc, readyAt: Date().addingTimeInterval(10))
        XCTAssertEqual(Hands.observationRoots(app: late, scope: "focused_window").source, "none")
    }

    func testSidebarRowsTakeTheirTextLabel() {
        // Open panel / Finder sidebar: row > cell > {image "move", text value "Recents"}.
        let txt = el("AXStaticText", x: 470, y: 222)
        txt.attrs.value = "Recents"
        let img = el("AXImage", x: 462, y: 222, w: 16, h: 16)
        img.attrs.desc = "clock"
        let cell = el("AXCell", x: 460, y: 220, w: 139, h: 32, [img, txt])
        let row = el("AXRow", x: 460, y: 220, w: 139, h: 32, [cell])
        let win = el("AXWindow", "Open", x: 400, y: 200, w: 800, h: 500,
                     [el("AXOutline", x: 460, y: 210, w: 141, h: 400, [row])])
        let recs = Walker.walk(root: win, deadline: Date().addingTimeInterval(1))
        XCTAssertEqual(recs.first { $0.role == "row" }?.label, "Recents")
        XCTAssertEqual(recs.first { $0.role == "cell" }?.label, "Recents")
    }

    func testFinderListRowsTakeTheNameNotTheDate() {
        // Finder list view: row > [cell > {image, textfield value=name}, cell > text "Today"].
        let name = el("AXTextField", x: 700, y: 362, w: 200, h: 18)
        name.attrs.value = "report.pdf"
        let date = el("AXStaticText", x: 950, y: 362, w: 120, h: 18)
        date.attrs.value = "Today at 9:41"
        let row = el("AXRow", x: 661, y: 360, w: 741, h: 22, [
            el("AXCell", x: 661, y: 360, w: 280, h: 22, [el("AXImage", x: 680, y: 362, w: 16, h: 16), name]),
            el("AXCell", x: 941, y: 360, w: 160, h: 22, [date]),
        ])
        let win = el("AXWindow", "Downloads", x: 498, y: 271, w: 920, h: 436,
                     [el("AXOutline", x: 661, y: 350, w: 741, h: 300, [row])])
        let recs = Walker.walk(root: win, deadline: Date().addingTimeInterval(1))
        XCTAssertEqual(recs.first { $0.role == "row" }?.label, "report.pdf")
    }
}

// MARK: - 2. no_text_target

final class NoTextTargetTests: XCTestCase {
    private let textEdit = RunningAppInfo(pid: 77, name: "TextEdit", bundleId: "com.apple.TextEdit")

    private func skills(app: MockElement, poster: MockPoster,
                        info: RunningAppInfo? = nil) -> Skills {
        let apps = MockApps(frontmost: (info ?? textEdit).pid, running: [info ?? textEdit])
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster, apps: apps, hooks: .inert)
        s.axApp = { _ in app }
        return s
    }

    private func window(_ kids: [MockElement]) -> MockElement {
        el("AXWindow", "Untitled", x: 100, y: 100, w: 600, h: 400, kids)
    }

    func testTypesIntoAFocusedTextField() {
        let field = el("AXTextField", "To", x: 120, y: 120)
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = field
        app.singles[kAXFocusedWindowAttribute as String] = window([field])
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(poster.typed, ["hello"])
        XCTAssertEqual((r["result"] as? [String: Any])?["target"] as? String, "focused")
    }

    func testNoTextTargetWhenNothingTakesText() {
        let bold = el("AXCheckBox", "bold", x: 120, y: 110)
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = bold
        app.singles[kAXFocusedWindowAttribute as String] = window([bold])
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "no_text_target")
        let observed = r["observed"] as? String ?? ""
        XCTAssertTrue(observed.contains("TextEdit"), observed)
        XCTAssertTrue(observed.contains("window \"Untitled\""), observed)
        XCTAssertTrue(observed.contains("checkbox \"bold\""), observed)
        XCTAssertTrue(poster.typed.isEmpty)                       // never typed
    }

    func testNoWindowNoFocusIsNoTextTarget() {
        // The live E2E: TextEdit with no window / nothing focused.
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "hi"])
        XCTAssertEqual(r["error"] as? String, "no_text_target")
        XCTAssertEqual(r["observed"] as? String, "app \"TextEdit\" window none focused none")
        XCTAssertTrue(poster.typed.isEmpty)
    }

    func testWindowTextAreaFallbackFocusesItFirst() {
        // Focus on the window itself (clicked the chrome): the document's
        // text area takes the text, focused first.
        let area = el("AXTextArea", x: 110, y: 140, w: 560, h: 340)
        area.settable = ["AXFocused"]
        let small = el("AXTextArea", x: 110, y: 110, w: 100, h: 20)
        let win = window([el("AXScrollArea", x: 100, y: 130, w: 600, h: 360, [area]), small])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = win
        app.singles[kAXFocusedWindowAttribute as String] = win
        let poster = MockPoster()
        let r = skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "notes"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["target"] as? String, "window_textarea")
        XCTAssertEqual(area.store["AXFocused"] as? Bool, true)    // the larger one
        XCTAssertEqual(poster.typed, ["notes"])
    }

    func testWebEditableAndSpreadsheetCellsAccept() {
        let group = el("AXGroup", x: 120, y: 120)
        group.singles["AXEditableAncestor"] = el("AXTextArea")   // contenteditable
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = group
        let poster = MockPoster()
        XCTAssertEqual(skills(app: app, poster: poster).execute(name: "type_text", args: ["text": "a"])["ok"] as? Bool, true)

        let table = el("AXTable", x: 100, y: 100, w: 500, h: 300)
        let numbers = RunningAppInfo(pid: 88, name: "Numbers", bundleId: "com.apple.iWork.Numbers")
        let app2 = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app2.singles[kAXFocusedUIElementAttribute as String] = table
        XCTAssertEqual(skills(app: app2, poster: poster, info: numbers)
            .execute(name: "type_text", args: ["text": "42"])["ok"] as? Bool, true)
        // A table elsewhere (Finder list) is not a text target.
        let finder = RunningAppInfo(pid: 89, name: "Finder", bundleId: "com.apple.finder")
        XCTAssertEqual(skills(app: app2, poster: poster, info: finder)
            .execute(name: "type_text", args: ["text": "42"])["error"] as? String, "no_text_target")
        XCTAssertEqual(poster.typed, ["a", "42"])
    }

    // `type #ref "text"` act op.
    private func handsWith(_ win: MockElement, app: MockElement) -> (Hands, Observation, [String]) {
        let h = Hands()
        h.apps = MockApps(frontmost: 4242, running: [RunningAppInfo(pid: 4242, name: "Mock", bundleId: "x.mock")])
        win.stableIdOverride = 901
        let o = h.processObservation(roots: [win], app: "Mock", window: "W", pid: 4242, maxNodes: 150,
                                     diff: true, deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
        h.settleOverride = { _ in 0 }
        h.observeOverride = {
            h.processObservation(roots: [win], app: "Mock", window: "W", pid: 4242, maxNodes: 150,
                                 diff: true, deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
        }
        h.axAppOverride = { _ in app }
        return (h, o, [])
    }

    func testTypeOnAButtonRefIsNoTextTarget() {
        let button = el("AXButton", "Share", x: 20, y: 20)
        let win = el("AXWindow", "W", x: 0, y: 0, w: 800, h: 600, [button])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = button
        let (h, o, _) = handsWith(win, app: app)
        var typed: [String] = []
        h.typeTextOverride = { typed.append($0) }
        let ref = o.elements.first { $0.label == "Share" }!.ref
        let r = h.act(["op": "type", "ref": ref, "text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "no_text_target")
        XCTAssertTrue((r["observed"] as? String ?? "").contains("button \"Share\""), "\(r)")
        XCTAssertTrue(typed.isEmpty)
    }

    func testTypeOnATextFieldStillWorks() {
        let field = el("AXTextField", "Name", x: 20, y: 20)
        field.settable = ["AXFocused", "AXValue"]
        let win = el("AXWindow", "W", x: 0, y: 0, w: 800, h: 600, [field])
        let (h, o, _) = handsWith(win, app: el("AXApplication", x: 0, y: 0, w: 0, h: 0))
        let r = h.act(["op": "type", "ref": o.elements[0].ref, "text": "Ada"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(field.store["AXValue"] as? String, "Ada")
    }

    func testTypeOnACellThatFocusesAnEditorIsAllowed() {
        // Clicking/focusing a cell leaves an editable focus (Numbers editor).
        let cell = el("AXCell", "B2", x: 20, y: 20)
        let editor = el("AXTextArea", x: 20, y: 20)
        let win = el("AXWindow", "W", x: 0, y: 0, w: 800, h: 600, [cell])
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles[kAXFocusedUIElementAttribute as String] = editor
        let (h, o, _) = handsWith(win, app: app)
        var typed: [String] = []
        h.typeTextOverride = { typed.append($0) }
        let r = h.act(["op": "type", "ref": o.elements.first { $0.role == "cell" }!.ref, "text": "12"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(typed, ["12"])
    }
}

// MARK: - 3. hands serve: arguments + exit rules

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

// MARK: - 4. skill AppleScripts: handlers compiled once

final class MockCompiled: CompiledAppleScript {
    let source: String
    var executes = 0
    var calls: [(String, [Any])] = []
    init(_ source: String) { self.source = source }
    func execute() throws -> String { executes += 1; return "ok" }
    func callHandler(_ name: String, args: [Any]) throws -> String {
        calls.append((name, args))
        return name == "set_level" ? "\(args.first ?? 0),false" : "ok"
    }
}

final class MockCompiler {
    var compiled: [String: MockCompiled] = [:]
    var compiles: [String] = []
    func compile(_ s: String) throws -> CompiledAppleScript {
        compiles.append(s)
        let c = MockCompiled(s)
        compiled[s] = c
        return c
    }
}

final class AppleScriptHandlerTests: XCTestCase {
    func testHandlerCompiledOnceAcrossDifferentArgs() throws {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        _ = try r.call(SkillScripts.notes, "new_note", ["Groceries", "<h1>Groceries</h1>"])
        _ = try r.call(SkillScripts.notes, "new_note", ["Ideas", "<h1>Ideas</h1>"])
        XCTAssertEqual(mc.compiles, [SkillScripts.notes.source])        // ONE compile
        XCTAssertEqual(r.compileCount, 1)
        let calls = mc.compiled[SkillScripts.notes.source]!.calls
        XCTAssertEqual(calls.map(\.0), ["new_note", "new_note"])
        XCTAssertEqual(calls.map { $0.1.first as? String }, ["Groceries", "Ideas"])
    }

    func testWarmUpCompilesEverySkillScriptAndRunsNothing() {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        r.warmUp()
        let expected = SkillScripts.all.map(\.source) + SkillScripts.fixedSources
        XCTAssertEqual(mc.compiles, expected)
        XCTAssertTrue(mc.compiled.values.allSatisfy { $0.executes == 0 && $0.calls.isEmpty })
        for s in expected { XCTAssertTrue(r.isCompiled(s)) }
        // Real calls afterwards compile nothing new.
        _ = try? r.call(SkillScripts.volume, "set_level", [30])
        _ = try? r.run("output volume of (get volume settings)")
        XCTAssertEqual(mc.compiles.count, expected.count)
    }

    func testAdHocScriptsAreCachedBySourceInAnLRU() throws {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        _ = try r.run("return 1")
        _ = try r.run("return 1")
        XCTAssertEqual(mc.compiles, ["return 1"])
        for i in 0..<70 { _ = try r.run("return \(i + 2)") }        // evicts "return 1"
        _ = try r.run("return 1")
        XCTAssertEqual(mc.compiles.filter { $0 == "return 1" }.count, 2)
        // pinned skill scripts survive any number of ad-hoc scripts
        _ = try r.call(SkillScripts.volume, "set_level", [10])
        for i in 0..<70 { _ = try r.run("return \(i + 200)") }
        _ = try r.call(SkillScripts.volume, "set_level", [20])
        XCTAssertEqual(mc.compiles.filter { $0 == SkillScripts.volume.source }.count, 1)
    }

    func testSkillsUseHandlersNotSplicedSource() {
        let mc = MockCompiler()
        let r = AppleScriptRunner(compiler: mc.compile)
        let s = Skills(catalog: catalog(), scripts: r, events: MockPoster(), apps: MockApps(), hooks: .inert)
        let a = s.execute(name: "new_note", args: ["title": "Q\"4\" <plan>", "body": "line 1\nline 2 & more"])
        let b = s.execute(name: "new_note", args: ["body": "buy oat milk"])
        XCTAssertEqual(a["ok"] as? Bool, true, "\(a)")
        XCTAssertEqual(b["ok"] as? Bool, true, "\(b)")
        XCTAssertEqual(mc.compiles, [SkillScripts.notes.source])
        let calls = mc.compiled[SkillScripts.notes.source]!.calls
        XCTAssertEqual(calls[0].1.first as? String, "Q\"4\" <plan>")        // verbatim name
        XCTAssertEqual(calls[0].1.last as? String,
                       "<h1>Q\"4\" &lt;plan&gt;</h1><br>line 1<br>line 2 &amp; more")
        let v = s.execute(name: "set_volume", args: ["level": 30])
        XCTAssertEqual((v["result"] as? [String: Any])?["level"] as? Int, 30)
        XCTAssertEqual(mc.compiles.count, 2)                              // + volume script
    }

    func testRealHandlerCallPassesParameters() throws {
        // Real NSAppleScript, no app targeted: verifies the subroutine-event
        // encoding (name, positional args, types) end to end.
        let script = SkillScript(name: "math", source: """
            on add_two(a, b)
                return (a + b) as text
            end add_two
            on greet(who, loud)
                if loud then return "HI " & who
                return "hi " & who
            end greet
            """)
        let r = AppleScriptRunner()
        XCTAssertEqual(try r.call(script, "add_two", [2, 3]), "5")
        XCTAssertEqual(try r.call(script, "add_two", [40, 2]), "42")
        XCTAssertEqual(try r.call(script, "greet", ["Ada \"Lovelace\"", true]), "HI Ada \"Lovelace\"")
        XCTAssertEqual(try r.call(script, "GREET", ["x", false]), "hi x")   // case-insensitive
        XCTAssertEqual(r.compileCount, 1)
        XCTAssertThrowsError(try r.call(script, "missing_handler", []))
    }

    func testAllSkillScriptsCompile() throws {
        // Compile only (nothing runs, no app is launched).
        let r = AppleScriptRunner()
        let res = r.precompile(SkillScripts.all.map(\.source) + SkillScripts.fixedSources)
        for x in res { XCTAssertTrue(x.ok, "failed to compile:\n\(x.source)") }
    }
}

// MARK: - 5. Automation status mapping

final class AutomationTests: XCTestCase {
    func testStatusMapping() {
        XCTAssertEqual(Automation.status(from: 0), .granted)
        XCTAssertEqual(Automation.status(from: -1743), .denied)
        XCTAssertEqual(Automation.status(from: -1744), .notDetermined)
        XCTAssertEqual(Automation.status(from: -600), .notRunning)
        XCTAssertEqual(Automation.status(from: -50), .unknown(-50))
    }

    func testTargetsAndSummary() {
        XCTAssertEqual(Automation.targets.map(\.name),
                       ["Notes", "Calendar", "Reminders", "Numbers", "Finder", "System Events"])
        XCTAssertEqual(Automation.targets.map(\.bundleId),
                       ["com.apple.Notes", "com.apple.iCal", "com.apple.reminders",
                        "com.apple.iWork.Numbers", "com.apple.finder", "com.apple.systemevents"])
        let line = Automation.summaryLine([(Automation.targets[0], .granted),
                                           (Automation.targets[5], .notRunning)])
        XCTAssertEqual(line, "Notes=granted SystemEvents=not_running")
        XCTAssertTrue(Automation.targets[4].persistent)          // Finder is never quit
        XCTAssertFalse(Automation.targets[3].persistent)         // Numbers launched hidden is quit
    }
}

// MARK: - 6. Control Center via MenuBarAgent

final class ControlCenterLookupTests: XCTestCase {
    /// macOS 27 MenuBarAgent: AXExtrasMenuBar > AXHostingView groups > AXMenuExtra.
    private func menuBarAgent(withBluetooth: Bool) -> MockElement {
        func extra(_ ident: String, _ desc: String, x: CGFloat) -> MockElement {
            let e = el("AXMenuBarItem", x: x, y: 8, w: 26, h: 22)
            e.attrs.subrole = "AXMenuExtra"
            e.attrs.desc = desc
            e.singles["AXIdentifier"] = ident
            let host = el("AXGroup", x: x, y: 0, w: 26, h: 39, [e])
            host.attrs.subrole = "AXHostingView"
            return host
        }
        var hosts = [extra("com.apple.menuextra.wifi", "Wi‑Fi, connected", x: 1614),
                     extra("com.apple.menuextra.controlcenter", "Control Center", x: 1652)]
        if withBluetooth { hosts.insert(extra("com.apple.menuextra.bluetooth", "Bluetooth", x: 1580), at: 0) }
        let bar = el("AXMenuBar", x: 1420, y: 0, w: 359, h: 39, hosts)
        let app = el("AXApplication", x: 0, y: 0, w: 0, h: 0)
        app.singles["AXExtrasMenuBar"] = bar
        return app
    }

    func testExtrasInsideHostingGroups() {
        let items = ControlCenter.extras(in: menuBarAgent(withBluetooth: false))
        XCTAssertEqual(items.map(\.ident), ["com.apple.menuextra.wifi", "com.apple.menuextra.controlcenter"])
        XCTAssertEqual(items.last?.frame, CGRect(x: 1652, y: 8, width: 26, height: 22))
        XCTAssertTrue(ControlCenter.extras(in: el("AXApplication", x: 0, y: 0, w: 0, h: 0)).isEmpty)
    }

    func testOpenerPrefersTheModuleExtraElseControlCenter() {
        let own = ControlCenter.pickOpener(ControlCenter.extras(in: menuBarAgent(withBluetooth: true)),
                                           named: "Bluetooth")
        XCTAssertEqual(own?.ident, "com.apple.menuextra.bluetooth")
        let cc = ControlCenter.pickOpener(ControlCenter.extras(in: menuBarAgent(withBluetooth: false)),
                                          named: "Bluetooth")
        XCTAssertEqual(cc?.ident, "com.apple.menuextra.controlcenter")
        XCTAssertNil(ControlCenter.pickOpener([], named: "Bluetooth"))
    }

    func testFindToggleInPanelWindows() {
        let tile = el("AXCheckBox", x: 1500, y: 60, w: 150, h: 60)
        tile.attrs.desc = "Bluetooth"
        tile.attrs.value = NSNumber(value: 1)
        let wifi = el("AXCheckBox", x: 1340, y: 60, w: 150, h: 60)
        wifi.attrs.desc = "Wi‑Fi"
        let panel = el("AXWindow", x: 1330, y: 40, w: 340, h: 500,
                       [el("AXGroup", x: 1330, y: 40, w: 340, h: 500, [wifi, tile])])
        let found = ControlCenter.findToggle(in: [panel], named: "Bluetooth")
        XCTAssertTrue(found === tile)
        XCTAssertEqual(ControlCenter.value(of: tile), true)
        XCTAssertNil(ControlCenter.findToggle(in: [panel], named: "AirDrop"))
    }
}
