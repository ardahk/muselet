import AppKit
import ApplicationServices
import Foundation

/// Control Center AX fallback for system toggles (Bluetooth): open the
/// module's own menu extra (or Control Center), flip the switch, close.
/// Best effort; used only when the direct API is missing or ineffective.
enum ControlCenter {
    static let bundleId = "com.apple.controlcenter"

    static func setToggle(named name: String, on: Bool) throws -> Bool {
        guard let cc = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).first
        else { throw HandsError.skillFailed("Control Center is not running") }
        let app = AXNode(AXUIElementCreateApplication(cc.processIdentifier))
        app.setMessagingTimeout(0.5)
        guard let barRef = app.copySingleAttr("AXExtrasMenuBar"),
              CFGetTypeID(barRef as CFTypeRef) == AXUIElementGetTypeID() else {
            throw HandsError.skillFailed("Control Center: no menu extras")
        }
        let items = AXNode(barRef as! AXUIElement).copyAttrs().children
        func matches(_ el: Element, _ s: String) -> Bool {
            let a = el.copyAttrs()
            let ident = el.copySingleAttr("AXIdentifier") as? String ?? ""
            return [a.title, a.desc, ident].compactMap { $0 }
                .contains { $0.localizedCaseInsensitiveContains(s) }
        }
        let opener = items.first { matches($0, name) }
            ?? items.first { matches($0, "controlcenter") || matches($0, "Control Center") }
        guard let opener else { throw HandsError.skillFailed("Control Center: menu extra not found") }

        _ = opener.performAction(kAXPressAction)
        defer {
            // Close whatever we opened (pressing the extra again toggles it).
            if hasWindow(app) { _ = opener.performAction(kAXPressAction) }
        }
        var toggle: Element?
        let deadline = Date().addingTimeInterval(1.5)
        while toggle == nil && Date() < deadline {
            usleep(80_000)
            toggle = findToggle(in: app, named: name)
        }
        guard let toggle else {
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

    private static func hasWindow(_ app: Element) -> Bool {
        ((app.copySingleAttr(kAXWindowsAttribute as String) as? [AXUIElement]) ?? []).isEmpty == false
    }

    private static func value(of el: Element) -> Bool? {
        let v = el.copyAttrs().value
        if let b = v as? Bool { return b }
        if let n = v as? NSNumber { return n.intValue != 0 }
        return nil
    }

    /// BFS over Control Center windows for a checkbox/switch whose title,
    /// description or identifier mentions `name`.
    static func findToggle(in app: Element, named name: String) -> Element? {
        let wins = (app.copySingleAttr(kAXWindowsAttribute as String) as? [AXUIElement]) ?? []
        var queue: [Element] = wins.map { AXNode($0) }
        var qi = 0
        var fallback: Element?
        while qi < queue.count && qi < 600 {
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
}
