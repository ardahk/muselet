import AppKit
import ApplicationServices
import Foundation

/// Control Center AX fallback for system toggles (Bluetooth): open the
/// module's own menu extra (or Control Center), flip the switch, close.
/// Best effort; used only when the direct API is missing or ineffective.
///
/// macOS 27 moved the menu extras into MenuBarAgent: its AXExtrasMenuBar
/// holds AXHostingView groups, each with one AXMenuBarItem/AXMenuExtra
/// (`com.apple.menuextra.controlcenter`, `.wifi`, `.battery`, ...).
/// ControlCenter no longer has an AXExtrasMenuBar; the opened module window
/// may belong to either process, so both are searched.
enum ControlCenter {
    static let bundleId = "com.apple.controlcenter"
    /// Processes whose AXExtrasMenuBar may hold the menu extras (newest first).
    static let extrasOwners = ["com.apple.MenuBarAgent", "com.apple.controlcenter",
                               "com.apple.systemuiserver"]
    /// Processes whose windows may host an opened module / Control Center.
    static let panelOwners = ["com.apple.controlcenter", "com.apple.MenuBarAgent"]

    struct Extra {
        var el: Element
        var ident: String
        var label: String          // AXDescription / AXTitle, e.g. "Control Center"
        var frame: CGRect
    }

    // MARK: lookups

    static func appElement(bundleId: String) -> Element? {
        guard let ra = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).first
        else { return nil }
        let app = AXNode(AXUIElementCreateApplication(ra.processIdentifier))
        app.setMessagingTimeout(0.5)
        return app
    }

    /// Menu extras of the first owner that has any.
    static func liveExtras() -> [Extra] {
        for bid in extrasOwners {
            guard let app = appElement(bundleId: bid) else { continue }
            let found = extras(in: app)
            if !found.isEmpty { return found }
        }
        return []
    }

    /// Items under `app`'s AXExtrasMenuBar: directly under the bar, or one
    /// level down inside hosting groups (MenuBarAgent). Testable (mocks).
    static func extras(in app: Element) -> [Extra] {
        guard let bar = axElement(app.copySingleAttr("AXExtrasMenuBar")) else { return [] }
        var out: [Extra] = []
        var queue: [(Element, Int)] = bar.copyAttrs().children.map { ($0, 0) }
        var qi = 0
        while qi < queue.count && qi < 80 {
            let (el, depth) = queue[qi]; qi += 1
            let a = el.copyAttrs()
            let ident = el.copySingleAttr("AXIdentifier") as? String ?? ""
            if a.role == "AXMenuBarItem" || ident.hasPrefix("com.apple.menuextra.") {
                let label = [a.desc, a.title].compactMap { $0 }.first { !$0.isEmpty } ?? ""
                out.append(Extra(el: el, ident: ident, label: label, frame: a.frame))
                continue
            }
            if depth < 2 { queue.append(contentsOf: a.children.map { ($0, depth + 1) }) }
        }
        return out
    }

    /// The module's own extra (`com.apple.menuextra.<name>` or a label
    /// mentioning it), else the Control Center extra.
    static func pickOpener(_ items: [Extra], named name: String) -> Extra? {
        let key = name.lowercased().replacingOccurrences(of: " ", with: "")
        func own(_ e: Extra) -> Bool {
            e.ident.lowercased().hasSuffix("." + key) || e.label.localizedCaseInsensitiveContains(name)
        }
        func cc(_ e: Extra) -> Bool {
            e.ident.lowercased().hasSuffix(".controlcenter")
                || e.label.localizedCaseInsensitiveContains("Control Center")
        }
        return items.first(where: own) ?? items.first(where: cc)
    }

    static func panelWindows() -> [Element] {
        panelOwners.compactMap { appElement(bundleId: $0) }
            .flatMap { axElements($0.copySingleAttr(kAXWindowsAttribute as String)) }
    }

    static func value(of el: Element) -> Bool? {
        let v = el.copyAttrs().value
        if let b = v as? Bool { return b }
        if let n = v as? NSNumber { return n.intValue != 0 }
        return nil
    }

    /// BFS over `roots` (module / Control Center windows) for a
    /// checkbox/switch whose title, description or identifier mentions
    /// `name`; a named AXButton with a boolean value is the fallback.
    static func findToggle(in roots: [Element], named name: String) -> Element? {
        var queue = roots
        var qi = 0
        var fallback: Element?
        while qi < queue.count && qi < 800 {
            let el = queue[qi]; qi += 1
            let a = el.copyAttrs()
            let ident = el.copySingleAttr("AXIdentifier") as? String ?? ""
            let named = [a.title, a.desc, ident].compactMap { $0 }
                .contains { $0.localizedCaseInsensitiveContains(name) }
            if named {
                if a.role == "AXCheckBox" || a.subrole == "AXSwitch" || a.subrole == "AXToggle" {
                    return el
                }
                if fallback == nil, a.role == "AXButton", value(of: el) != nil { fallback = el }
            }
            queue.append(contentsOf: a.children)
        }
        return fallback
    }

    // MARK: open / close

    /// Press `opener` and poll (<= 1.5 s) for the `name` toggle. Returns
    /// the toggle and whether a panel opened (the caller closes it).
    private static func open(_ opener: Extra, findToggle name: String) -> (Element?, opened: Bool) {
        let before = panelWindows().count
        _ = opener.el.performAction(kAXPressAction)
        var toggle: Element?
        let deadline = Date().addingTimeInterval(1.5)
        while toggle == nil && Date() < deadline {
            usleep(80_000)
            toggle = findToggle(in: panelWindows(), named: name)
        }
        return (toggle, toggle != nil || panelWindows().count > before)
    }

    /// Close what `open` opened: pressing the extra again toggles it shut.
    private static func close(_ opener: Extra) {
        _ = opener.el.performAction(kAXPressAction)
    }

    // MARK: entry points

    static func setToggle(named name: String, on: Bool) throws -> Bool {
        let items = liveExtras()
        guard !items.isEmpty else {
            throw HandsError.skillFailed("Control Center: no menu extras (MenuBarAgent / ControlCenter)")
        }
        guard let opener = pickOpener(items, named: name) else {
            throw HandsError.skillFailed("Control Center: menu extra not found")
        }
        let (found, opened) = open(opener, findToggle: name)
        defer { if opened { close(opener) } }
        guard let toggle = found else {
            throw HandsError.skillFailed("Control Center: \(name) switch not found")
        }
        let before = value(of: toggle)
        if before != on {
            _ = toggle.performAction(kAXPressAction)
            let end = Date().addingTimeInterval(1.0)
            while Date() < end, value(of: toggle) != on { usleep(60_000) }
        }
        return value(of: toggle) ?? on
    }

    /// Read-only probe: the extras, the opener for `name` and (only with
    /// `open`) the toggle's frame/value after opening the panel. The toggle
    /// is never pressed; the panel is closed again.
    static func locate(named name: String, open doOpen: Bool) -> [String: Any] {
        func f(_ r: CGRect) -> [Double] { [r.minX, r.minY, r.width, r.height].map { Double($0) } }
        let items = liveExtras()
        var d: [String: Any] = [
            "extras": items.map { ["ident": $0.ident, "label": $0.label, "frame": f($0.frame)] as [String: Any] },
        ]
        guard let opener = pickOpener(items, named: name) else {
            d["opener"] = NSNull()
            return d
        }
        d["opener"] = ["ident": opener.ident, "label": opener.label, "frame": f(opener.frame)] as [String: Any]
        guard doOpen else { return d }
        let t0 = Date()
        let (toggle, opened) = open(opener, findToggle: name)
        if let t = toggle {
            let a = t.copyAttrs()
            d["toggle"] = ["role": a.role ?? "", "subrole": a.subrole ?? "",
                           "label": a.desc ?? a.title ?? "", "frame": f(a.frame),
                           "on": value(of: t).map { $0 as Any } ?? NSNull()] as [String: Any]
        } else {
            d["toggle"] = NSNull()
        }
        d["find_ms"] = (Date().timeIntervalSince(t0) * 1000).rounded(to: 1)
        d["panel_opened"] = opened
        if opened { close(opener) }
        return d
    }
}

/// Public read-only entry for `hands probe control-center`.
public enum ControlCenterProbe {
    public static func locate(named name: String, open: Bool) -> [String: Any] {
        ControlCenter.locate(named: name, open: open)
    }
}
