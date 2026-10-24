import AppKit
import ApplicationServices
import Foundation

/// Is there something to type into? `type_text` / `type` must never report
/// ok while the keystrokes land nowhere (live E2E: TextEdit with no focused
/// window "typed" fine). Read-only apart from `focusTarget`, which the
/// caller focuses before typing.
public enum TextTarget {
    public struct Check {
        public var ok: Bool
        /// "focused" (the focused element takes text) | "window_textarea"
        /// (nothing specific focused; the window's text area takes it).
        public var via: String?
        /// Short hint of what is focused, e.g.
        /// `app "TextEdit" window "Untitled" focused button "Bold"`.
        public var observed: String
        /// Focus this before typing (window_textarea fallback).
        public var focusTarget: Element?
    }

    static let textRoles: Set<String> = ["AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"]
    static let textSubroles: Set<String> = ["AXSearchField", "AXSecureTextField"]
    /// Focus that means "nothing in particular": the focused window's text
    /// area may take the text (TextEdit / Notes after a click on the chrome).
    static let neutralRoles: Set<String> = [
        "AXWindow", "AXSheet", "AXGroup", "AXScrollArea", "AXSplitGroup", "AXLayoutArea",
        "AXApplication", "AXUnknown",
    ]
    /// Spreadsheets: typing into a selected cell edits it (focus is the table/cell).
    static let spreadsheetBundles: Set<String> = ["com.apple.iWork.Numbers", "com.microsoft.Excel"]
    static let gridRoles: Set<String> = ["AXTable", "AXGrid", "AXCell"]

    /// Does `el` (attributes `a`) accept typed text? Text fields/areas,
    /// combo/search/secure fields, anything inside a web editable region
    /// (contenteditable, ARIA textbox: AXEditableAncestor), and spreadsheet
    /// grids/cells.
    static func acceptsText(_ el: Element, _ a: ElAttrs, bundleId: String?) -> Bool {
        let role = a.role ?? ""
        if textRoles.contains(role) { return true }
        if let s = a.subrole, textSubroles.contains(s) { return true }
        if el.copySingleAttr("AXEditableAncestor") != nil { return true }
        if let b = bundleId, spreadsheetBundles.contains(b), gridRoles.contains(role) { return true }
        return false
    }

    /// `<role> "<label>"` in the observation role names (or the raw AX role).
    static func describe(_ a: ElAttrs) -> String {
        let axRole = a.role ?? "?"
        let role = kRoleMap[axRole] ?? axRole
        let label = Walker.label(of: a, role: role)
        return label.isEmpty ? role : "\(role) \"\(String(label.prefix(40)))\""
    }

    /// Check the keyboard focus of `app` (the frontmost app's AX element).
    /// windowFallback: when nothing specific is focused, accept the focused
    /// window's largest visible AXTextArea (outside web areas) and return it
    /// as `focusTarget`.
    public static func check(app: Element, appName: String, bundleId: String?,
                             windowFallback: Bool = true,
                             deadline: Date = Date().addingTimeInterval(0.3)) -> Check {
        let focused = axElement(app.copySingleAttr(kAXFocusedUIElementAttribute as String))
        let fa = focused?.copyAttrs()
        if let f = focused, let a = fa, acceptsText(f, a, bundleId: bundleId) {
            // Hot path: no window lookup.
            return Check(ok: true, via: "focused",
                         observed: "app \"\(appName)\" focused \(describe(a))", focusTarget: nil)
        }
        let win = Hands.pickWindow(app: app)?.window
        let winTitle = win.map { Hands.windowTitle($0) }
        var observed = "app \"\(appName)\" window " + (winTitle.map { "\"\(String($0.prefix(40)))\"" } ?? "none")
        observed += " focused " + (fa.map(describe) ?? "none")
        let neutral = fa.map { neutralRoles.contains($0.role ?? "") } ?? true
        if windowFallback, neutral, let w = win, let area = largestTextArea(in: w, deadline: deadline) {
            return Check(ok: true, via: "window_textarea", observed: observed, focusTarget: area)
        }
        return Check(ok: false, via: nil, observed: observed, focusTarget: nil)
    }

    /// Largest visible AXTextArea in `window` (BFS <= 400 nodes, depth <= 10,
    /// never inside an AXWebArea: a page's comment box is not "the document").
    static func largestTextArea(in window: Element, deadline: Date) -> Element? {
        var queue: [(Element, Int)] = [(window, 0)]
        var qi = 0
        var best: (Element, CGFloat)?
        while qi < queue.count && qi < 400 && Date() < deadline {
            let (el, depth) = queue[qi]; qi += 1
            let a = el.copyAttrs()
            let role = a.role ?? ""
            if role == "AXWebArea" { continue }
            if role == "AXTextArea", a.size.width > 0, a.size.height > 0, a.enabled {
                let area = a.size.width * a.size.height
                if best == nil || area > best!.1 { best = (el, area) }
                continue
            }
            if depth < 10 { queue.append(contentsOf: a.children.map { ($0, depth + 1) }) }
        }
        return best?.0
    }
}
