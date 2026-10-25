import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Hands core: observe (walker, serializer, differ, stable refs, window
// fallback, label-search scope), act (expect polling, focus guard, shell
// scripts, `type #ref` text targets, media keys), combos / DSL / synthetic
// event tags, screenshot geometry and web AX switches; plus the mocks and
// helpers shared by every test file. Hermetic: mock AX trees, no real
// key/mouse/media events; the shell tests run /bin/zsh with harmless commands.

// MARK: - Mock element tree (no TCC needed)

final class MockElement: Element {
    var attrs = ElAttrs()
    var actions: [String] = []
    var settable: Set<String> = ["AXFocused"]
    var store: [String: Any?] = [:]
    var failAttrs = false
    var alive = true
    /// Values served by copySingleAttr (e.g. AXWindows, AXSelectedRows, AXParent).
    var singles: [String: Any] = [:]

    var stableIdOverride: Int = 0
    var stableId: Int { stableIdOverride != 0 ? stableIdOverride
        : ObjectIdentifier(self).hashValue }
    func isAlive() -> Bool { alive }
    func copySingleAttr(_ name: String) -> Any? { singles[name] }

    init(role: String, title: String? = nil, x: CGFloat = 0, y: CGFloat = 0,
         w: CGFloat = 80, h: CGFloat = 24, children: [MockElement] = []) {
        attrs.role = role
        attrs.title = title
        attrs.position = CGPoint(x: x, y: y)
        attrs.size = CGSize(width: w, height: h)
        attrs.children = children
    }

    func copyAttrs() -> ElAttrs { failAttrs ? ElAttrs() : attrs }
    func performAction(_ name: String) -> Bool { actions.append(name); return true }
    func setAttr(_ name: String, _ value: Any?) -> Bool {
        guard settable.contains(name) else { return false }
        store[name] = value
        if name == "AXFocused" { attrs.focused = (value as? Bool) ?? false }
        if name == "AXValue" { attrs.value = value }
        return true
    }
    func isSettable(_ name: String) -> Bool { settable.contains(name) }
}

private func rec(_ ref: Int, _ role: String, _ label: String,
                 value: Any? = nil, frame: CGRect = CGRect(x: 10, y: 10, width: 80, height: 24),
                 enabled: Bool = true, selected: Bool = false, checked: Bool? = nil) -> ElementRecord {
    ElementRecord(ref: ref, role: role, label: label, value: value, enabled: enabled,
                  selected: selected, focused: false, frame: frame,
                  checked: checked, inWebArea: false,
                  element: MockElement(role: "AXButton"))
}

// MARK: - Shared helpers

func el(_ role: String, _ title: String? = nil, x: CGFloat = 10, y: CGFloat = 10,
        w: CGFloat = 80, h: CGFloat = 24, _ kids: [MockElement] = []) -> MockElement {
    MockElement(role: role, title: title, x: x, y: y, w: w, h: h, children: kids)
}

/// Drive processObservation directly with a mock root.
func observeMock(_ h: Hands, _ root: Element, window: String = "W", pid: pid_t = 1,
                 maxNodes: Int = 150) -> Observation {
    h.processObservation(roots: [root], app: "Mock", window: window, pid: pid,
                         maxNodes: maxNodes, diff: true,
                         deadline: Date().addingTimeInterval(1), appEl: nil, t0: Date())
}

func catalog() -> [String: SkillDef] { try! Catalog.load() }

/// A window of buttons with a fixed identity (same id = same window).
private func window(_ id: Int, _ titles: [String]) -> MockElement {
    let w = MockElement(role: "AXWindow", title: "W", x: 0, y: 0, w: 800, h: 600,
                        children: titles.enumerated().map { i, t in
                            MockElement(role: "AXButton", title: t, x: 10, y: CGFloat(10 + 30 * i))
                        })
    w.stableIdOverride = id
    return w
}

// MARK: - Shared mocks

final class MockPoster: EventPosting {
    var posted: [String] = []
    var typed: [String] = []
    /// Keystroke-app typing (Calculator) and media keys, recorded only.
    var keystrokes: [String] = []
    var mediaKeys: [String] = []
    func post(_ combo: KeyCombo) { posted.append(Combo.describe(combo)) }
    func typeText(_ text: String) { typed.append(text) }
    func typeKeystrokes(_ text: String) { keystrokes.append(text) }
    func postMediaKey(_ key: MediaKey) { mediaKeys.append(key.name) }
}

final class MockApps: AppControlling {
    var frontmost: pid_t
    var activateSucceeds: Bool
    var activated: [pid_t] = []
    var running: [RunningAppInfo]
    /// Lock screen up (screen_locked guard).
    var locked = false

    init(frontmost: pid_t = 1, activateSucceeds: Bool = true, running: [RunningAppInfo] = []) {
        self.frontmost = frontmost
        self.activateSucceeds = activateSucceeds
        self.running = running
    }

    func screenLocked() -> Bool { locked }
    func frontmostPid() -> pid_t { frontmost }
    func activate(pid: pid_t) -> Bool {
        activated.append(pid)
        if activateSucceeds { frontmost = pid }
        return activateSucceeds
    }
    func app(pid: pid_t) -> RunningAppInfo? { running.first { $0.pid == pid } }
    func runningApp(bundlePrefix: String) -> RunningAppInfo? {
        running.first { $0.bundleId.hasPrefix(bundlePrefix) }
    }
}

final class SpyDelegate: HandsDelegate {
    var skills: [(String, [String: Any])] = []
    var timerLabels: [String?] = []
    var onTimer: (() -> Void)?
    func handsWillAct(op: String, frame: CGRect?, label: String?) -> TimeInterval { 0 }
    func handsDidAct(op: String, frame: CGRect?, ok: Bool) {}
    func handsDidRunSkill(name: String, args: [String: Any], result: [String: Any]) {
        skills.append((name, result))
    }
    func handsTimerFired(label: String?) {
        timerLabels.append(label)
        onTimer?()
    }
}

/// Script runner answering the volume read-back script.
final class VolumeSpy: ScriptRunning {
    var ran: [String] = []
    var state = "35,false"
    func run(_ source: String) throws -> String {
        ran.append(source)
        if source.contains("get volume settings") && source.contains("output muted") { return state }
        if source.hasPrefix("output volume of") { return "40" }
        return ""
    }
    /// The volume handlers read the state back (what macOS reports).
    func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String {
        ran.append("\(script.name).\(handler)(\(args.map { "\($0)" }.joined(separator: ",")))")
        return script.name == "volume" ? state : ""
    }
}

/// Records scripts and handler calls; answers `respond`.
final class SpyRunner: ScriptRunning {
    var ran: [String] = []
    var respond = ""
    func run(_ source: String) throws -> String { ran.append(source); return respond }
    /// Handler calls are recorded as `<script>.<handler>(<args>)`.
    func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String {
        ran.append("\(script.name).\(handler)(\(args.map { "\($0)" }.joined(separator: ",")))")
        return respond
    }
}

// MARK: - Serializer

final class SerializerTests: XCTestCase {
    func testFormat() {
        let els = [
            rec(1, "button", "Back"),
            rec(4, "textfield", "Search", value: ""),
            rec(7, "row", "Downloads", selected: true),
            rec(9, "checkbox", "Wi-Fi", checked: true),
            rec(11, "button", "Save", enabled: false),
        ]
        let text = Serializer.text(app: "Finder", window: "Recents",
                                   focusedRef: 4, elements: els)
        let lines = text.components(separatedBy: "\n")
        XCTAssertEqual(lines[0], "app: Finder | window: \"Recents\" | focused: #4")
        XCTAssertEqual(lines[1], "#1 button \"Back\"")
        XCTAssertEqual(lines[2], "#4 textfield \"Search\" value=\"\"")
        XCTAssertEqual(lines[3], "#7 row \"Downloads\" selected")
        XCTAssertEqual(lines[4], "#9 checkbox \"Wi-Fi\" checked")
        XCTAssertEqual(lines[5], "#11 button \"Save\" disabled")
    }

    func testEscapes() {
        let t = Serializer.text(app: "A", window: "a\"b", focusedRef: nil,
                                elements: [rec(1, "button", "x\ny")])
        XCTAssertTrue(t.contains("window: \"a\\\"b\""))
        XCTAssertTrue(t.contains("#1 button \"x\\ny\""))
    }
}

// MARK: - Differ

final class DifferTests: XCTestCase {
    func testAddRemoveChange() {
        let old = [
            rec(1, "button", "Back"),
            rec(4, "textfield", "Search", value: "h"),
            rec(7, "row", "Downloads"),
        ]
        var new = [
            rec(0, "button", "Back"),
            rec(0, "textfield", "Search", value: "hel"),
            rec(0, "button", "Export", frame: CGRect(x: 200, y: 10, width: 80, height: 24)),
        ]
        for i in new.indices { new[i].ref = i + 10 }
        let provM = Differ.match(old: old, new: new)
        // stabilized: Back->1, Search->4; Export stays fresh
        var m: [Int: Int] = [:]
        for i in new.indices {
            let prov = new[i].ref
            if let r = provM[prov] { new[i].ref = r; m[r] = r }
        }
        let d = Differ.diff(old: old, new: new, matched: m)
        XCTAssertTrue(d.contains("+ #12 button \"Export\""), d)
        XCTAssertTrue(d.contains("- #7"), d)
        XCTAssertTrue(d.contains("~ #4 value=\"hel\""), d)
    }

    func testFrameWithin8ptMatches() {
        let old = [rec(1, "button", "A", frame: CGRect(x: 100, y: 100, width: 80, height: 24))]
        var new = [rec(9, "button", "A", frame: CGRect(x: 105, y: 103, width: 80, height: 24))]
        let provM = Differ.match(old: old, new: new)
        XCTAssertEqual(provM[9], 1)
        var m: [Int: Int] = [:]
        for i in new.indices {
            let prov = new[i].ref
            if let r = provM[prov] { new[i].ref = r; m[r] = r }
        }
        XCTAssertEqual(Differ.diff(old: old, new: new, matched: m), "")
    }
}

// MARK: - Combo parser

final class ComboTests: XCTestCase {
    func testMods() throws {
        let c = try Combo.parse("cmd+shift+n")
        XCTAssertTrue(c.flags.contains(.maskCommand))
        XCTAssertTrue(c.flags.contains(.maskShift))
        XCTAssertEqual(c.keyCode, 45)   // n
    }

    func testNamedKeys() throws {
        XCTAssertEqual(try Combo.parse("return").keyCode, 36)
        XCTAssertEqual(try Combo.parse("esc").keyCode, 53)
        XCTAssertEqual(try Combo.parse("tab").keyCode, 48)
        XCTAssertEqual(try Combo.parse("up").keyCode, 126)
        XCTAssertEqual(try Combo.parse("down").keyCode, 125)
        XCTAssertEqual(try Combo.parse("f5").keyCode, 96)
        XCTAssertEqual(try Combo.parse("f12").keyCode, 111)
    }

    func testErrors() {
        XCTAssertThrowsError(try Combo.parse("cmd+"))       // missing key
        XCTAssertThrowsError(try Combo.parse("cmd+wat"))    // unknown key
        XCTAssertThrowsError(try Combo.parse(""))           // empty
    }
}

// MARK: - Expect predicates

final class ExpectTests: XCTestCase {
    func obs() -> Observation {
        var o = Observation()
        o.app = "Finder"; o.window = "Recents"; o.focusedRef = 4
        o.elements = [rec(4, "textfield", "Search", value: "hello"),
                      rec(7, "button", "Save")]
        return o
    }

    func testParseAll() throws {
        XCTAssertEqual(try Expect.parse("title~\"Rec\""), .titleContains("Rec"))
        XCTAssertEqual(try Expect.parse("focused #4"), .focused(4))
        XCTAssertEqual(try Expect.parse("value #2=\"x\""), .valueEquals(2, "x"))
        XCTAssertEqual(try Expect.parse("app \"Finder\""), .appIs("Finder"))
        XCTAssertEqual(try Expect.parse("appears \"Save\""), .appears("Save"))
        XCTAssertEqual(try Expect.parse("gone #7"), .gone(7))
        XCTAssertThrowsError(try Expect.parse("nonsense"))
    }

    func testEval() {
        let o = obs()
        XCTAssertTrue(Expect.eval(.titleContains("cent"), o).0)
        XCTAssertFalse(Expect.eval(.titleContains("Nope"), o).0)
        XCTAssertTrue(Expect.eval(.focused(4), o).0)
        XCTAssertFalse(Expect.eval(.focused(5), o).0)
        XCTAssertTrue(Expect.eval(.valueEquals(4, "hello"), o).0)
        XCTAssertFalse(Expect.eval(.valueEquals(4, "bye"), o).0)
        XCTAssertTrue(Expect.eval(.appIs("Finder"), o).0)
        XCTAssertFalse(Expect.eval(.appIs("Safari"), o).0)
        XCTAssertFalse(Expect.eval(.appears("Sav"), o).0)
        XCTAssertTrue(Expect.eval(.appears("save"), o).0)
        XCTAssertFalse(Expect.eval(.appears(""), o).0)
        XCTAssertFalse(Expect.eval(.appears("Nope"), o).0)
        XCTAssertTrue(Expect.eval(.gone(9), o).0)
        XCTAssertFalse(Expect.eval(.gone(7), o).0)
    }
}

extension ExpectPredicate: Equatable {
    public static func == (a: ExpectPredicate, b: ExpectPredicate) -> Bool {
        switch (a, b) {
        case (.titleContains(let x), .titleContains(let y)): return x == y
        case (.focused(let x), .focused(let y)): return x == y
        case (.valueEquals(let x, let s), .valueEquals(let y, let t)): return x == y && s == t
        case (.appIs(let x), .appIs(let y)): return x == y
        case (.appears(let x), .appears(let y)): return x == y
        case (.gone(let x), .gone(let y)): return x == y
        default: return false
        }
    }
}

// MARK: - Walker (mock tree)

final class WalkerTests: XCTestCase {
    func testWalkEmitsAndPrunes() {
        // screen union will cover typical positions; keep frames on-screen.
        let dead = MockElement(role: "AXButton", title: "Offscreen",
                               x: -99999, y: -99999, w: 10, h: 10)
        let zero = MockElement(role: "AXButton", title: "Zero", w: 0, h: 0)
        let btn = MockElement(role: "AXButton", title: "OK", x: 10, y: 10)
        let txt = MockElement(role: "AXStaticText", title: nil, x: 10, y: 40)
        txt.attrs.value = "some label text"
        let emptyTxt = MockElement(role: "AXStaticText", title: nil, x: 10, y: 60)
        let group = MockElement(role: "AXGroup", x: 0, y: 0, w: 0, h: 0,
                                children: [btn])
        group.attrs.size = .zero   // zero-size container still traverses
        let root = MockElement(role: "AXWindow", title: "W",
                               x: 0, y: 0, w: 800, h: 600,
                               children: [dead, zero, group, txt, emptyTxt])
        let out = Walker.walk(root: root, deadline: Date().addingTimeInterval(2))
        let roles = out.map { $0.role }
        XCTAssertTrue(roles.contains("button"))
        XCTAssertTrue(roles.contains("text"))
        XCTAssertEqual(out.filter { $0.role == "button" }.count, 1)   // OK only
        XCTAssertEqual(out.filter { $0.role == "text" }.count, 1)     // labeled only
        XCTAssertFalse(out.contains { $0.label == "Offscreen" })
        XCTAssertFalse(out.contains { $0.label == "Zero" })
        // interactive first
        XCTAssertEqual(out.first?.role, "button")
        XCTAssertEqual(out.map { $0.ref }, [1, 2])
    }

    func testLabelPriority() {
        let e = MockElement(role: "AXButton", x: 0, y: 0)
        e.attrs.help = "helptext"
        let out = Walker.walk(root: e, deadline: Date().addingTimeInterval(2))
        XCTAssertEqual(out.first?.label, "helptext")
    }
}

// MARK: - Stable refs across epochs

final class StableRefTests: XCTestCase {
    /// Drive processObservation directly with mock roots.
    private func observe(_ h: Hands, root: Element, window: String) -> Observation {
        h.processObservation(roots: [root], app: "Mock", window: window,
                             pid: 1, maxNodes: 150, diff: true,
                             deadline: Date().addingTimeInterval(1),
                             appEl: nil, t0: Date())
    }

    private func tree() -> MockElement {
        MockElement(role: "AXWindow", title: "W", x: 0, y: 0, w: 800, h: 600,
                    children: [
                        MockElement(role: "AXButton", title: "Save", x: 10, y: 10),
                        MockElement(role: "AXButton", title: "Cancel", x: 10, y: 40),
                        MockElement(role: "AXTextField", title: "Name", x: 10, y: 70),
                    ])
    }

    func testStableRefs() {
        let h = Hands()
        let t = tree()
        t.stableIdOverride = 42          // same window identity
        let o1 = observe(h, root: t, window: "W")
        XCTAssertTrue(o1.full)
        let refs1 = Dictionary(uniqueKeysWithValues: o1.elements.map { ($0.label, $0.ref) })

        // mutate: remove "Cancel", add "New", change value on "Name"
        let t2 = tree()
        t2.stableIdOverride = 42         // still the same window
        t2.attrs.children = [
            t2.attrs.children[0],
            MockElement(role: "AXButton", title: "New", x: 10, y: 100),
            t2.attrs.children[2],
        ]
        (t2.attrs.children[2] as! MockElement).attrs.value = "typed"
        let o2 = observe(h, root: t2, window: "W")
        XCTAssertFalse(o2.full)
        let refs2 = Dictionary(uniqueKeysWithValues: o2.elements.map { ($0.label, $0.ref) })
        XCTAssertEqual(refs2["Save"], refs1["Save"])          // stable
        XCTAssertEqual(refs2["Name"], refs1["Name"])          // stable
        XCTAssertNotEqual(refs2["New"], refs1["Cancel"])      // fresh ref, not reused
        XCTAssertTrue((o2.diffText ?? "").contains("- #\(refs1["Cancel"]!)"))
        XCTAssertTrue((o2.diffText ?? "").contains("+ #\(refs2["New"]!)"))
    }

    func testSessionChangeNeverReusesRefs() {
        let h = Hands()
        let o1 = observe(h, root: tree(), window: "W1")
        // a DIFFERENT window element (new stableId) starts a new session,
        // but ref numbers are never reused (process-wide counter)
        let o2 = observe(h, root: tree(), window: "W1")
        XCTAssertTrue(o2.full)
        let max1 = o1.elements.map(\.ref).max()!
        XCTAssertTrue(o2.elements.allSatisfy { $0.ref > max1 })
        XCTAssertEqual(o2.diffText, "")
        XCTAssertEqual(h.sessionStartEpoch, o2.epoch)
    }

    func testTitleChangeKeepsRefs() {
        let h = Hands()
        let t = tree()
        t.stableIdOverride = 7           // same window throughout
        let o1 = observe(h, root: t, window: "My File.txt")
        // same window element, title changed (e.g. "Edited" suffix) — refs hold
        let o2 = observe(h, root: t, window: "My File.txt — Edited")
        XCTAssertFalse(o2.full)
        XCTAssertEqual(o1.elements.first?.ref, o2.elements.first?.ref)
    }
}

// MARK: - hands-1: refs never reused; epoch checked

final class StaleRefAcrossWindowsTests: XCTestCase {
    func testW1RefInW2IsStale() {
        let h = Hands()
        let o1 = observeMock(h, window(101, ["Save", "Cancel", "Name"]), window: "W1")
        let w1Ref = o1.elements.first { $0.label == "Cancel" }!.ref
        let o2 = observeMock(h, window(202, ["A", "B", "C", "D", "E"]), window: "W2")
        XCTAssertTrue(o2.full)
        XCTAssertFalse(o2.elements.contains { $0.ref == w1Ref })   // never re-minted

        // act with a W1 ref (and its epoch) -> stale_ref, nothing executed
        let r = h.act(["op": "press", "ref": w1Ref, "epoch": o1.epoch])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("stale_ref"), "\(r)")
        // even without an epoch
        XCTAssertThrowsError(try h.element(ref: w1Ref))
        // a W2 ref with a pre-session epoch is stale too
        let w2Ref = o2.elements[0].ref
        XCTAssertThrowsError(try h.element(ref: w2Ref, epoch: o1.epoch))
        XCTAssertNoThrow(try h.element(ref: w2Ref, epoch: o2.epoch))
        XCTAssertNoThrow(try h.element(ref: w2Ref))
    }

    func testReturningToWindowResumesItsRefs() {
        let h = Hands()
        let w1 = window(111, ["Save", "Cancel"])
        let o1 = observeMock(h, w1, window: "Doc")
        let cancel = o1.elements.first { $0.label == "Cancel" }!.ref
        let o2 = observeMock(h, window(222, ["Open", "Close"]), window: "Open dialog")
        let w2Ref = o2.elements[0].ref
        XCTAssertThrowsError(try h.element(ref: cancel))
        // dialog closed, back to the same window element: same refs again
        let o3 = observeMock(h, w1, window: "Doc")
        XCTAssertTrue(o3.full)
        XCTAssertEqual(o3.elements.first { $0.label == "Cancel" }?.ref, cancel)
        XCTAssertNoThrow(try h.element(ref: cancel, epoch: o2.epoch))
        XCTAssertThrowsError(try h.element(ref: w2Ref))       // dialog refs are stale now
    }

    func testSameWindowOlderEpochStillValid() {
        let h = Hands()
        let w = window(303, ["Save", "Cancel"])
        let o1 = observeMock(h, w)
        _ = observeMock(h, w)                                         // epoch advances
        let ref = o1.elements[0].ref
        XCTAssertNoThrow(try h.element(ref: ref, epoch: o1.epoch))  // same session
    }
}

// MARK: - observe: focused -> main -> AXWindows -> app-scope roots

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

    func testWordBoundedLabelsAndTitles() {
        let a = app()
        XCTAssertFalse(search("get", a))                     // Budget.numbers
        let w = el("AXWindow", "Draft", [el("AXButton", "Autosave"), el("AXButton", "Unsaved")])
        a.singles[kAXFocusedWindowAttribute as String] = w
        XCTAssertFalse(search("Save", a))
        w.attrs.children = [el("AXButton", "SAVE As…")]
        XCTAssertTrue(search("save", a))
        XCTAssertTrue(Expect.labelMatches("Export…", in: "Export…"))
        XCTAssertTrue(Expect.labelMatches("(Save)", in: "Click (SAVE)"))
        XCTAssertFalse(Expect.labelMatches("Save.*", in: "Save As"))
        XCTAssertFalse(Expect.labelMatches("", in: "Save"))
    }

    func testOnlyFocusedWindowAndOwnedOverlays() {
        let a = app(editOpen: true, contextMenu: true)
        let other = el("AXWindow", "Unrelated", [el("AXButton", "Background Only")])
        let focused = el("AXWindow", "Target", [el("AXButton", "Target Only")])
        let sheet = el("AXSheet", "Attached", [el("AXButton", "Sheet Only")])
        let popover = el("AXPopover", nil, [el("AXButton", "Popover Only")])
        popover.singles[kAXParentAttribute as String] = focused
        focused.singles["AXSheets"] = [sheet]
        a.singles[kAXWindowsAttribute as String] = [other, focused]
        a.singles[kAXFocusedWindowAttribute as String] = focused
        a.attrs.children += [other, focused, popover,
                             el("AXSheet", "Unowned", [el("AXButton", "Unowned Only")])]
        for label in ["Target Only", "Sheet Only", "Popover Only", "Paste and Match", "Inspect Element"] {
            XCTAssertTrue(search(label, a), label)
        }
        for label in ["Background Only", "Unrelated", "Unowned Only", "Budget", "Export"] {
            XCTAssertFalse(search(label, a), label)
        }
        a.singles.removeValue(forKey: kAXFocusedWindowAttribute as String)
        a.singles.removeValue(forKey: kAXWindowsAttribute as String)
        XCTAssertFalse(search("Target Only", a))
        XCTAssertTrue(search("Inspect Element", a))
    }
}

// MARK: - hands-4: expect polling

final class ExpectPollingTests: XCTestCase {
    func testPollsUntilTitlePasses() {
        let h = Hands()
        let w = window(404, ["Reload"])
        _ = observeMock(h, w, window: "Loading…")
        var calls = 0
        h.settleOverride = { _ in 5 }
        h.observeOverride = {
            calls += 1
            return observeMock(h, w, window: calls >= 3 ? "GitHub · Build software" : "Loading…")
        }
        let t0 = Date()
        let r = h.act(["op": "wait", "ms": 0, "expect": "title~\"GitHub\""])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["expect_ok"] as? Bool, true)
        XCTAssertGreaterThanOrEqual(r["expect_polls"] as? Int ?? 0, 2)
        let settle = r["settle_ms"] as? Double ?? 0
        XCTAssertGreaterThan(settle, 120)              // ~2 polls of 80 ms
        XCTAssertLessThan(Date().timeIntervalSince(t0), 1.0)
    }

    func testTimesOutWithExpectFailed() {
        let h = Hands()
        let w = window(405, ["Reload"])
        _ = observeMock(h, w, window: "Loading…")
        h.settleOverride = { _ in 0 }
        h.observeOverride = { observeMock(h, w, window: "Loading…") }
        let t0 = Date()
        let r = h.act(["op": "wait", "ms": 0, "expect": "title~\"GitHub\"",
                       "expect_timeout_ms": 250])
        let dt = Date().timeIntervalSince(t0)
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("expect_failed"), "\(r)")
        XCTAssertGreaterThanOrEqual(dt, 0.24)
        XCTAssertLessThan(dt, 1.0)
    }

    func testImmediatePassNoPolling() {
        let h = Hands()
        let w = window(406, ["OK"])
        _ = observeMock(h, w, window: "Done")
        h.settleOverride = { _ in 12.5 }
        h.observeOverride = { observeMock(h, w, window: "Done") }
        let r = h.act(["op": "wait", "ms": 0, "expect": "title~\"Done\""])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertNil(r["expect_polls"])
        XCTAssertEqual(r["settle_ms"] as? Double, 12.5)
    }

    func testBadPredicateFailsBeforeActing() {
        let h = Hands()
        let r = h.act(["op": "wait", "ms": 0, "expect": "nonsense"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertNil(r["settle_ms"])                    // never acted/settled
    }
}

// MARK: - hands-6: appears/gone beyond the node cap

final class ExpectBeyondCapTests: XCTestCase {
    func testTruncatedFlag() {
        let h = Hands()
        let o = observeMock(h, window(501, ["A", "B", "C"]), maxNodes: 2)
        XCTAssertTrue(o.truncated)
        XCTAssertEqual(o.elements.count, 2)
        let o2 = observeMock(h, window(502, ["A", "B"]), maxNodes: 150)
        XCTAssertFalse(o2.truncated)
    }

    func testAppearsFallsBackToTargetedSearch() {
        let h = Hands()
        let o = observeMock(h, window(503, ["Open"]))
        var searched: [String] = []
        h.labelSearchOverride = { label, _ in searched.append(label); return label == "Export…" }
        XCTAssertTrue(h.evalExpect(.appears("Open"), o).0)
        XCTAssertTrue(searched.isEmpty)                 // cheap path hit first
        XCTAssertTrue(h.evalExpect(.appears("Export…"), o).0)
        XCTAssertFalse(h.evalExpect(.appears("Nope"), o).0)
        XCTAssertEqual(searched, ["Export…", "Nope"])
    }

    func testGoneUsesLiveness() {
        let h = Hands()
        let w = window(504, ["Keep", "Close"])
        let o = observeMock(h, w)
        let ref = o.elements.first { $0.label == "Close" }!.ref
        // Observation that lacks the ref (e.g. past the cap) but the element lives.
        var capped = o
        capped.elements.removeAll { $0.ref == ref }
        capped.truncated = true
        XCTAssertFalse(h.evalExpect(.gone(ref), capped).0)
        // Element destroyed -> gone, even from a truncated walk.
        (w.attrs.children[1] as! MockElement).alive = false
        XCTAssertTrue(h.evalExpect(.gone(ref), capped).0)
        // Unknown ref: never gone from a truncated walk; gone from a complete one.
        XCTAssertFalse(h.evalExpect(.gone(999_999_999), capped).0)
        var complete = capped
        complete.truncated = false
        XCTAssertTrue(h.evalExpect(.gone(999_999_999), complete).0)
        // Present in the list -> not gone.
        XCTAssertFalse(h.evalExpect(.gone(o.elements[0].ref), o).0)
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

// MARK: - hands-8: input bound to the observed app

final class FocusGuardTests: XCTestCase {
    private func setup(apps: MockApps) -> (Hands, MockElement, Int) {
        let h = Hands()
        h.apps = apps
        let field = MockElement(role: "AXTextField", title: "Name", x: 10, y: 10)
        field.settable = ["AXFocused", "AXValue"]          // AX path: no synthetic typing
        let w = MockElement(role: "AXWindow", title: "W", x: 0, y: 0, w: 800, h: 600,
                            children: [field])
        w.stableIdOverride = 601
        let o = observeMock(h, w, pid: 4242)
        h.settleOverride = { _ in 0 }
        h.observeOverride = { observeMock(h, w, pid: 4242) }
        return (h, field, o.elements[0].ref)
    }

    func testFocusChangedWhenTargetCannotBeActivated() {
        let apps = MockApps(frontmost: 999, activateSucceeds: false)
        let (h, field, ref) = setup(apps: apps)
        let t0 = Date()
        let r = h.act(["op": "type", "ref": ref, "text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String ?? "").hasPrefix("focus_changed"), "\(r)")
        XCTAssertEqual(apps.activated, [4242])
        XCTAssertNil(field.store["AXValue"] ?? nil)        // never typed
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.6)   // <= ~300 ms wait
    }

    func testReactivatesTargetThenTypes() {
        let apps = MockApps(frontmost: 999, activateSucceeds: true)
        let (h, field, ref) = setup(apps: apps)
        let r = h.act(["op": "type", "ref": ref, "text": "hello"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(apps.activated, [4242])
        XCTAssertEqual(field.store["AXValue"] as? String, "hello")
    }

    func testNoActivationWhenAlreadyFrontmost() {
        let apps = MockApps(frontmost: 4242)
        let (h, _, ref) = setup(apps: apps)
        let r = h.act(["op": "type", "ref": ref, "text": "x"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertTrue(apps.activated.isEmpty)
    }

    func testSkillAppSwitchRebindsToFrontmost() {
        let apps = MockApps(frontmost: 999, activateSucceeds: false)
        let (h, field, ref) = setup(apps: apps)
        h.noteExternalFocusChange()                        // e.g. skill open_app ran
        let r = h.act(["op": "type", "ref": ref, "text": "hi"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertTrue(apps.activated.isEmpty)
        XCTAssertEqual(field.store["AXValue"] as? String, "hi")
    }
}

// MARK: - no_text_target: `type #ref` act op

final class NoTextTargetActTests: XCTestCase {
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

// MARK: - DSL line parser (repl)

final class DSLLineTests: XCTestCase {
    func testParse() throws {
        var p = try DSLLine.parse("press #4", epoch: 3)
        XCTAssertEqual(p["op"] as? String, "press")
        XCTAssertEqual(p["ref"] as? Int, 4)
        XCTAssertEqual(p["epoch"] as? Int, 3)

        p = try DSLLine.parse("type #2 \"hello world\" enter", epoch: 1)
        XCTAssertEqual(p["text"] as? String, "hello world")
        XCTAssertEqual(p["enter"] as? Bool, true)

        p = try DSLLine.parse("keys cmd+shift+n", epoch: 1)
        XCTAssertEqual(p["combo"] as? String, "cmd+shift+n")

        p = try DSLLine.parse("scroll #1 down 5", epoch: 1)
        XCTAssertEqual(p["direction"] as? String, "down")
        XCTAssertEqual(p["n"] as? Int, 5)

        p = try DSLLine.parse("click 100,200 double", epoch: 1)
        XCTAssertEqual(p["x"] as? Double, 100)
        XCTAssertEqual(p["double"] as? Bool, true)

        p = try DSLLine.parse("open \"Safari\"", epoch: 1)
        XCTAssertEqual(p["name"] as? String, "Safari")

        p = try DSLLine.parse("wait 500", epoch: 1)
        XCTAssertEqual(p["ms"] as? Int, 500)

        XCTAssertThrowsError(try DSLLine.parse("press x", epoch: 1))
        XCTAssertThrowsError(try DSLLine.parse("bogus", epoch: 1))
    }
}

// MARK: - hands-3: synthetic event tag

final class SyntheticEventTests: XCTestCase {
    func testTagRoundTrip() throws {
        let e = try XCTUnwrap(CGEvent(keyboardEventSource: nil, virtualKey: 53, keyDown: true))
        XCTAssertFalse(SyntheticEvent.isTagged(e))
        SyntheticEvent.tag(e)                       // tag only; never posted
        XCTAssertTrue(SyntheticEvent.isTagged(e))
        XCTAssertEqual(e.getIntegerValueField(.eventSourceUserData), 0x4D55534C)
    }

    func testComboDescribe() throws {
        XCTAssertEqual(Combo.describe(try Combo.parse("cmd+shift+n")), "shift+cmd+n")
        XCTAssertEqual(Combo.describe(try Combo.parse("ctrl+cmd+q")), "ctrl+cmd+q")
        XCTAssertEqual(Combo.describe(try Combo.parse("space")), "space")
    }
}

// MARK: - media keys

final class MediaKeyTests: XCTestCase {
    func testNamesAndCodes() {
        let want: [String: Int32] = [
            "volume_up": 0, "volume_down": 1, "brightness_up": 2, "brightness_down": 3,
            "mute": 7, "play_pause": 16, "next_track": 17, "previous_track": 18,
        ]
        for (n, c) in want { XCTAssertEqual(MediaKey.parse(n)?.code, c, n) }
        XCTAssertEqual(MediaKey.parse(" Volume-Up ")?.name, "volume_up")
        XCTAssertNil(MediaKey.parse("cmd+shift+n"))
        XCTAssertNil(MediaKey.parse("return"))
        XCTAssertEqual(MediaKey.parse("mute")?.kind, .volume)
        XCTAssertEqual(MediaKey.parse("brightness_up")?.kind, .brightness)
        XCTAssertEqual(MediaKey.parse("next_track")?.kind, .playback)
        XCTAssertEqual(MediaKey.forMediaAction("pause")?.code, 16)
        XCTAssertEqual(MediaKey.forMediaAction("previous")?.code, 18)
        XCTAssertNil(MediaKey.forMediaAction("rewind"))
    }

    /// The event shape the hardware keys produce: NX_SYSDEFINED, subtype 8,
    /// data1 = key << 16 | state << 8 (0xA down, 0xB up), tagged as ours.
    func testSystemDefinedEventEncodingAndTag() throws {
        for (name, code) in [("volume_up", Int32(0)), ("brightness_down", 3), ("mute", 7), ("play_pause", 16)] {
            for down in [true, false] {
                let cg = try XCTUnwrap(MediaKey.event(code: code, down: down), name)   // built, never posted
                XCTAssertTrue(SyntheticEvent.isTagged(cg), name)                       // push-to-talk ignores it
                XCTAssertEqual(cg.type.rawValue, 14, name)                              // NX_SYSDEFINED
                let ns = try XCTUnwrap(NSEvent(cgEvent: cg))
                XCTAssertEqual(ns.type, .systemDefined)
                XCTAssertEqual(ns.subtype.rawValue, 8)                                  // aux control buttons
                XCTAssertEqual(ns.data1, (Int(code) << 16) | ((down ? 0xA : 0xB) << 8), name)
                XCTAssertEqual(ns.data1 >> 16, Int(code))
                XCTAssertEqual((ns.data1 >> 8) & 0xFF, down ? 0xA : 0xB)
                XCTAssertEqual(ns.data2, -1)
            }
        }
        XCTAssertEqual(MediaKey.data1(code: 2, down: true), 0x20A00)
        XCTAssertEqual(MediaKey.data1(code: 2, down: false), 0x20B00)
    }

    private func hands(_ apps: MockApps) -> (Hands, Int) {
        let h = Hands()
        h.apps = apps
        let w = el("AXWindow", "W", x: 0, y: 0, w: 400, h: 300, [el("AXButton", "OK")])
        w.stableIdOverride = 77_001
        let o = observeMock(h, w, pid: 4242)
        h.observeOverride = { observeMock(h, w, pid: 4242) }
        return (h, o.elements[0].ref)
    }

    func testKeysPostsMediaKeyWithoutFocusGuardOrSettle() {
        // Another app is frontmost and the observed one can't be activated:
        // an ordinary combo is refused, a media key still goes out.
        let apps = MockApps(frontmost: 999, activateSucceeds: false)
        let (h, _) = hands(apps)
        var posted: [String] = []
        var settles = 0
        var reads = 0
        h.mediaKeyPostOverride = { posted.append($0.name) }
        h.settleOverride = { _ in settles += 1; return 0 }
        h.mediaLevelOverride = { kind in
            XCTAssertEqual(kind, .volume)
            reads += 1
            return reads == 1 ? ["level": 50, "muted": false] : ["level": 56, "muted": false]
        }
        let r = h.act(["op": "keys", "combo": "volume_up"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(posted, ["volume_up"])
        XCTAssertTrue(apps.activated.isEmpty)                 // no focus guard
        XCTAssertEqual(settles, 0)                             // no settle / re-observation
        XCTAssertNil(r["diff_text"])
        XCTAssertEqual(r["media_key"] as? String, "volume_up")
        XCTAssertEqual(r["level_before"] as? Int, 50)
        XCTAssertEqual(r["level"] as? Int, 56)
        XCTAssertEqual(r["muted"] as? Bool, false)
        XCTAssertEqual(r["changed"] as? Bool, true)
        XCTAssertTrue(JSONSerialization.isValidJSONObject(r))

        let combo = h.act(["op": "keys", "combo": "cmd+shift+n"])
        XCTAssertTrue((combo["error"] as? String ?? "").hasPrefix("focus_changed"), "\(combo)")
    }

    func testBrightnessReadBackSettlesAndUnchangedReportsFalse() {
        let (h, _) = hands(MockApps(frontmost: 4242))
        h.mediaKeyPostOverride = { _ in }
        var seq = [50, 47, 44, 44]                             // a ramp, then steady
        h.mediaLevelOverride = { _ in ["level": seq.count > 1 ? seq.removeFirst() : seq[0]] }
        let r = h.act(["op": "keys", "combo": "brightness_down"])
        XCTAssertEqual(r["level_before"] as? Int, 50)
        XCTAssertEqual(r["level"] as? Int, 44)                 // the settled value, not the ramp
        XCTAssertEqual(r["changed"] as? Bool, true)
        // At the limit nothing changes: changed=false after the bounded wait.
        h.mediaLevelOverride = { _ in ["level": 100] }
        h.mediaReadBackTimeout = 0.12
        let t0 = Date()
        let u = h.act(["op": "keys", "combo": "brightness_up"])
        XCTAssertEqual(u["changed"] as? Bool, false)
        XCTAssertEqual(u["level"] as? Int, 100)
        XCTAssertLessThan(Date().timeIntervalSince(t0), 0.5)
        // Playback keys: no read-back.
        h.mediaLevelOverride = { _ in XCTFail("no read-back for playback keys"); return nil }
        let p = h.act(["op": "keys", "combo": "play_pause"])
        XCTAssertEqual(p["ok"] as? Bool, true)
        XCTAssertNil(p["changed"])
    }

    func testMediaKeyWithExpectStillVerifies() {
        let (h, _) = hands(MockApps(frontmost: 4242))
        h.mediaKeyPostOverride = { _ in }
        h.mediaLevelOverride = { _ in nil }
        var settles = 0
        h.settleOverride = { _ in settles += 1; return 0 }
        let r = h.act(["op": "keys", "combo": "mute", "expect": "title~\"W\""])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(r["expect_ok"] as? Bool, true)
        XCTAssertEqual(settles, 1)
    }

    func testLockedScreenAllowsMediaKeysOnly() {
        let apps = MockApps(frontmost: 4242)
        apps.locked = true
        let (h, ref) = hands(apps)
        var posted: [String] = []
        h.mediaKeyPostOverride = { posted.append($0.name) }
        h.mediaLevelOverride = { _ in nil }
        h.settleOverride = { _ in 0 }
        var typed: [String] = []
        h.typeTextOverride = { typed.append($0) }
        XCTAssertEqual(h.act(["op": "keys", "combo": "volume_down"])["ok"] as? Bool, true)
        XCTAssertEqual(posted, ["volume_down"])
        for p: [String: Any] in [["op": "keys", "combo": "return"],
                                 ["op": "type", "ref": ref, "text": "secret"],
                                 ["op": "click", "x": 20, "y": 20]] {
            let r = h.act(p)
            XCTAssertEqual(r["ok"] as? Bool, false, "\(p)")
            XCTAssertEqual(r["error"] as? String, "screen_locked", "\(p)")
            XCTAssertNotNil(r["observed"])
        }
        XCTAssertTrue(typed.isEmpty)
    }

    func testDSLAndMediaControl() throws {
        XCTAssertEqual(try DSLLine.parse("keys volume_up", epoch: 1)["combo"] as? String, "volume_up")
        XCTAssertEqual(try DSLLine.parse("keys brightness-down", epoch: 1)["op"] as? String, "keys")
        XCTAssertThrowsError(try DSLLine.parse("keys volume_upp", epoch: 1))
        let poster = MockPoster()
        let s = Skills(catalog: catalog(), scripts: SpyRunner(), events: poster, apps: MockApps(), hooks: .inert)
        XCTAssertEqual(s.execute(name: "media_control", args: ["action": "next"])["ok"] as? Bool, true)
        XCTAssertEqual(s.execute(name: "media_control", args: ["action": "pause"])["ok"] as? Bool, true)
        XCTAssertEqual(s.execute(name: "media_control", args: ["action": "rewind"])["ok"] as? Bool, false)
        XCTAssertEqual(poster.mediaKeys, ["next_track", "play_pause"])
    }
}

// MARK: - hands-5: screenshot geometry helpers

final class ScreenshotHelperTests: XCTestCase {
    private func win(_ pid: Int32, _ num: UInt32, _ r: CGRect, layer: Int = 0) -> [String: Any] {
        [kCGWindowOwnerPID as String: NSNumber(value: pid),
         kCGWindowNumber as String: NSNumber(value: num),
         kCGWindowLayer as String: NSNumber(value: layer),
         kCGWindowAlpha as String: NSNumber(value: 1.0),
         kCGWindowBounds as String: r.dictionaryRepresentation as NSDictionary]
    }

    func testPickWindowPrefersAXFocusedFrame() {
        let list = [
            win(7, 11, CGRect(x: 0, y: 0, width: 300, height: 20), layer: 25),  // palette/menu
            win(7, 12, CGRect(x: 50, y: 50, width: 200, height: 100)),          // tooltip-ish
            win(7, 13, CGRect(x: 100, y: 80, width: 1200, height: 800)),        // focused doc
            win(8, 14, CGRect(x: 0, y: 0, width: 1500, height: 900)),           // other app
        ]
        XCTAssertEqual(Screenshot.pickWindow(cgList: list, pid: 7,
                                             axFrame: CGRect(x: 101, y: 80, width: 1200, height: 799)), 13)
        // No AX frame: frontmost (list order) layer-0 window of the pid.
        XCTAssertEqual(Screenshot.pickWindow(cgList: list, pid: 7, axFrame: nil), 12)
        XCTAssertNil(Screenshot.pickWindow(cgList: list, pid: 9, axFrame: nil))
    }

    func testDisplayContaining() {
        let a = Screenshot.DisplayInfo(id: 1, frame: CGRect(x: 0, y: 0, width: 1512, height: 982), backing: 2)
        let b = Screenshot.DisplayInfo(id: 2, frame: CGRect(x: 1512, y: -200, width: 2560, height: 1440), backing: 1)
        XCTAssertEqual(Screenshot.display(containing: CGPoint(x: 2000, y: 100), in: [a, b])?.id, 2)
        XCTAssertEqual(Screenshot.display(containing: CGPoint(x: 10, y: 10), in: [a, b])?.id, 1)
        XCTAssertEqual(Screenshot.display(containing: CGPoint(x: 5000, y: 0), in: [a, b])?.id, 2)  // nearest
    }

    func testPixelSizeUsesBackingAndCap() {
        // 300x200 pt region at 2x -> 600x400 px (under the cap)
        let (w, h) = Screenshot.pixelSize(source: CGRect(x: 0, y: 0, width: 300, height: 200),
                                          backing: 2, maxPixels: 1_000_000)
        XCTAssertEqual(w, 600); XCTAssertEqual(h, 400)
        // full 1512x982 display at 2x capped to ~1 MP, aspect kept
        let (w2, h2) = Screenshot.pixelSize(source: CGRect(x: 0, y: 0, width: 1512, height: 982),
                                            backing: 2, maxPixels: 1_000_000)
        XCTAssertLessThanOrEqual(w2 * h2, 1_000_000 + 2_000)
        XCTAssertEqual(Double(w2) / Double(h2), 1512.0 / 982.0, accuracy: 0.01)
    }

    func testRectParam() {
        XCTAssertEqual(rectParam(["region": [1, 2, 3, 4]], "region"), CGRect(x: 1, y: 2, width: 3, height: 4))
        XCTAssertNil(rectParam(["region": [1, 2, 3]], "region"))
        XCTAssertNil(rectParam([:], "region"))
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
