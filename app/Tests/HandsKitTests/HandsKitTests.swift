import Foundation
import XCTest
@testable import HandsKit

// MARK: - Mock element tree (no TCC needed)

final class MockElement: Element {
    var attrs = ElAttrs()
    var actions: [String] = []
    var settable: Set<String> = ["AXFocused"]
    var store: [String: Any?] = [:]
    var failAttrs = false
    var alive = true

    var stableIdOverride: Int = 0
    var stableId: Int { stableIdOverride != 0 ? stableIdOverride
        : ObjectIdentifier(self).hashValue }
    func isAlive() -> Bool { alive }

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
        XCTAssertTrue(Expect.eval(.appears("Sav"), o).0)
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

    func testStaleRefError() {
        let h = Hands()
        let o1 = observe(h, root: tree(), window: "W")
        let anyRef = o1.elements.first!.ref
        XCTAssertNoThrow(try h.element(ref: anyRef))
        XCTAssertThrowsError(try h.element(ref: 9999)) { e in
            XCTAssertTrue("\(e)".contains("stale_ref"))
        }
    }
}

// MARK: - Catalog + skills gating

final class SpyRunner: ScriptRunning {
    var ran: [String] = []
    var respond = ""
    func run(_ source: String) throws -> String { ran.append(source); return respond }
}

final class CatalogTests: XCTestCase {
    func testLoadsRepoCatalog() throws {
        let cat = try Catalog.load()   // walks up to repo skills/catalog.json
        XCTAssertGreaterThan(cat.count, 25)
        XCTAssertEqual(cat["set_volume"]?.risk, "safe")
        XCTAssertEqual(cat["send_message"]?.risk, "confirm")
        XCTAssertEqual(cat["quit_app"]?.risk, "confirm_if_unsaved")
        XCTAssertTrue(cat["set_volume"]?.args.first?.required ?? false)
    }
}

final class SkillGatingTests: XCTestCase {
    func skills() -> Skills {
        Skills(catalog: (try! Catalog.load()), scripts: SpyRunner(),
               events: MockPoster(), apps: MockApps(), hooks: .inert)
    }

    func testConfirmRiskRefusesWithoutConfirmed() {
        let r = skills().execute(name: "send_message",
                                 args: ["to": "mom", "body": "hi"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "needs_confirmation")
        XCTAssertNotNil(r["ms"])
    }

    func testMoveToTrashGate() {
        let r = skills().execute(name: "move_to_trash", args: ["path": "/tmp/x"])
        XCTAssertEqual(r["error"] as? String, "needs_confirmation")
    }

    func testMoveToTrashConfirmed() throws {
        let f = NSTemporaryDirectory() + "hands-test-\(UUID().uuidString)"
        try "x".write(toFile: f, atomically: true, encoding: .utf8)
        let r = skills().execute(name: "move_to_trash",
                                 args: ["path": f, "confirmed": true])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertFalse(FileManager.default.fileExists(atPath: f))
    }

    func testUnimplementedSkill() {
        // executor=brain skills are not implemented by HandsKit
        let r = skills().execute(name: "finance_review", args: [:])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String)?.contains("not_implemented") ?? false)
        XCTAssertEqual(r["error"] as? String,
                       HandsError.notImplemented("finance_review").description)
    }

    func testMissingRequiredArg() {
        let r = skills().execute(name: "set_volume", args: [:])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertTrue((r["error"] as? String)?.contains("missing arg") ?? false)
    }

    func testSetVolumeThroughSpy() {
        let spy = SpyRunner()
        let s = Skills(catalog: try! Catalog.load(), scripts: spy,
                       events: MockPoster(), apps: MockApps(), hooks: .inert)
        let r = s.execute(name: "set_volume", args: ["level": 30])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(spy.ran.first, "set volume output volume 30")
        XCTAssertNotNil(r["ms"])
    }

    func testPathAliases() {
        XCTAssertEqual(PathAlias.resolve("downloads"),
                       NSHomeDirectory() + "/Downloads")
        XCTAssertEqual(PathAlias.resolve("Desktop"),
                       NSHomeDirectory() + "/Desktop")
        XCTAssertEqual(PathAlias.resolve("/tmp"), "/tmp")
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
