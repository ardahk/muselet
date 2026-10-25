import XCTest
@testable import HandsKit

private func rec(_ role: String, _ label: String,
                 value: Any? = nil) -> ElementRecord {
    ElementRecord(ref: 1, role: role, label: label, value: value,
                  enabled: true, selected: false, focused: false,
                  frame: CGRect(x: 0, y: 0, width: 80, height: 24),
                  checked: nil, inWebArea: false,
                  element: MockElement(role: "AXButton"))
}

final class WebLoadSignalTests: XCTestCase {

    // isHotTextButton classification
    func testHotTextClassification() {
        XCTAssertTrue(rec("button", "UI_HotTextNumberT").isHotTextButton)
        XCTAssertTrue(rec("button", "UI_HotText").isHotTextButton)
        XCTAssertTrue(rec("button", "clipSpeed").isHotTextButton)
        XCTAssertFalse(rec("button", "OK").isHotTextButton)
        XCTAssertFalse(rec("link", "clipSpeed").isHotTextButton)
        XCTAssertFalse(rec("button", "Clips").isHotTextButton)
    }

    // Serializer renders values for the custom controls
    func testHotTextButtonValueRendered() {
        XCTAssertTrue(Serializer.line(rec("button", "clipSpeed",
                                          value: "100")).contains(
                                          #"value="100""#))
        XCTAssertTrue(Serializer.line(rec("button", "clipSpeed",
                                          value: NSNumber(value: 200))).contains(
                                          #"value="200""#))
        XCTAssertTrue(Serializer.line(rec("button", "UI_HotTextNumberT",
                                          value: "00:00:11:12")).contains(
                                          #"value="00:00:11:12""#))
        XCTAssertFalse(Serializer.line(rec("button", "OK",
                                           value: "x")).contains("value="))
    }

    // deferred: firstWebArea + webBool via MockElement singles
    func testFirstWebAreaNestedAndMissing() {
        let area = MockElement(role: "AXWebArea")
        area.singles[kAXRoleAttribute as String] = "AXWebArea"
        let group = MockElement(role: "AXGroup")
        group.singles[kAXRoleAttribute as String] = "AXGroup"
        group.singles[kAXChildrenAttribute as String] =
            [area] as [any Element]
        let win = MockElement(role: "AXWindow")
        win.singles[kAXRoleAttribute as String] = "AXWindow"
        win.singles[kAXChildrenAttribute as String] =
            [group] as [any Element]
        XCTAssertTrue(firstWebArea(win) === area)
        let empty = MockElement(role: "AXWindow")
        empty.singles[kAXRoleAttribute as String] = "AXWindow"
        let leaf = MockElement(role: "AXButton")
        leaf.singles[kAXRoleAttribute as String] = "AXButton"
        empty.singles[kAXChildrenAttribute as String] =
            [leaf] as [any Element]
        XCTAssertNil(firstWebArea(empty))
    }

    func testWebBool() {
        let el = MockElement(role: "AXWebArea")
        el.singles[kAXRoleAttribute as String] = "AXWebArea"
        el.singles["AXLoaded"] = true
        XCTAssertEqual(webBool(el, "AXLoaded"), true)
        el.singles["AXLoaded"] = false
        XCTAssertEqual(webBool(el, "AXLoaded"), false)
        XCTAssertNil(webBool(el, "AXElementBusy"))
    }
}
