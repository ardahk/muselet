// Independent Calculator checker: reads the display straight from the Accessibility API. Read-only.
// Output: {"running": bool, "display": string|null}
import AppKit
import ApplicationServices

func attr(_ e: AXUIElement, _ a: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(e, a as CFString, &v) == .success ? v : nil
}
func children(_ e: AXUIElement) -> [AXUIElement] { (attr(e, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }
func find(_ e: AXUIElement, depth: Int = 0) -> String? {
    if depth > 10 { return nil }
    if (attr(e, kAXRoleAttribute) as? String) == "AXScrollArea", (attr(e, kAXDescriptionAttribute) as? String) == "Input" {
        for c in children(e) where (attr(c, kAXRoleAttribute) as? String) == "AXStaticText" {
            return attr(c, kAXValueAttribute) as? String
        }
    }
    for c in children(e) { if let v = find(c, depth: depth + 1) { return v } }
    return nil
}
guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.calculator").first else {
    print("{\"running\": false, \"display\": null}"); exit(0)
}
let ax = AXUIElementCreateApplication(app.processIdentifier)
let v = ((attr(ax, kAXWindowsAttribute) as? [AXUIElement]) ?? []).compactMap { find($0) }.first
let d = try! JSONSerialization.data(withJSONObject: [v.map { $0 as Any } ?? NSNull()])
let s = String(data: d, encoding: .utf8)!
let inner = String(s.dropFirst().dropLast()); print("{\"running\": true, \"display\": " + inner + "}")
