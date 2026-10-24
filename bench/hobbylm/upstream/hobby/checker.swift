// Independent completion checker: reads System Settings' selected sidebar row straight from the macOS
// Accessibility API (not from macos-use, not from the model's observation). Read-only: performs no actions.
// Output: one JSON line {"running": bool, "selected": [labels], "window_title": string|null}
import AppKit
import ApplicationServices

func attr(_ e: AXUIElement, _ a: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(e, a as CFString, &v) == .success ? v : nil
}
func children(_ e: AXUIElement) -> [AXUIElement] { (attr(e, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }
func role(_ e: AXUIElement) -> String { (attr(e, kAXRoleAttribute) as? String) ?? "" }
func texts(_ e: AXUIElement, depth: Int = 0) -> [String] {
    if depth > 6 { return [] }
    var out: [String] = []
    if role(e) == "AXStaticText", let v = attr(e, kAXValueAttribute) as? String, !v.isEmpty { out.append(v) }
    for c in children(e) { out += texts(c, depth: depth + 1) }
    return out
}
func outlines(_ e: AXUIElement, depth: Int = 0) -> [AXUIElement] {
    if depth > 12 { return [] }
    if role(e) == "AXOutline" { return [e] }
    return children(e).flatMap { outlines($0, depth: depth + 1) }
}
func esc(_ s: String) -> String {
    let d = try! JSONSerialization.data(withJSONObject: [s])
    let j = String(data: d, encoding: .utf8)!
    return String(j.dropFirst().dropLast())
}

guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.systempreferences").first else {
    print("{\"running\": false, \"selected\": [], \"window_title\": null}"); exit(0)
}
let ax = AXUIElementCreateApplication(app.processIdentifier)
let windows = (attr(ax, kAXWindowsAttribute) as? [AXUIElement]) ?? []
let title = windows.first.flatMap { attr($0, kAXTitleAttribute) as? String }
var selected: [String] = []
for w in windows {
    for o in outlines(w) {
        for row in (attr(o, kAXSelectedRowsAttribute) as? [AXUIElement]) ?? [] { selected += texts(row) }
    }
}
print("{\"running\": true, \"selected\": [\(selected.map(esc).joined(separator: ", "))], \"window_title\": \(title.map(esc) ?? "null")}")
