import AppKit
import ApplicationServices
import Foundation

/// `hands probe windows`: per-app window inventory over AX only
/// (AXWindows/AXTitle/AXDocument/AXSubrole/AXMinimized). Never sends
/// Apple Events — no Automation prompts, no hangs. 0.5 s messaging
/// timeout per app; the whole probe must stay under ~2 s for 24 ids.
public enum WindowsProbe {

    /// One window record from an AX window element (mockable).
    public static func windowDict(_ el: Element) -> [String: Any] {
        el.setMessagingTimeout(0.5)
        let a = el.copyAttrs()
        var d: [String: Any] = ["title": a.title ?? ""]
        // AXDocument / AXMinimized aren't in the batched attrs.
        if let doc = el.copySingleAttr("AXDocument") as? String,
           !doc.isEmpty {
            d["document"] = doc
        }
        if let s = a.subrole { d["subrole"] = s }
        d["minimized"] = (el.copySingleAttr("AXMinimized") as? Bool) ?? false
        return d
    }

    /// A running app's window list; AX failures -> error for this app.
    static func appDict(pid: pid_t) -> [String: Any] {
        let app = AXNode(AXUIElementCreateApplication(pid))
        app.setMessagingTimeout(0.5)
        var v: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(
            app.el, kAXWindowsAttribute as CFString, &v)
        guard err == .success else {
            return ["running": true, "pid": Int(pid),
                    "error": "\(err.rawValue)"]
        }
        return ["running": true, "pid": Int(pid),
                "windows": axElements(v).map(windowDict)]
    }

    /// All requested bundle ids. Not running -> running:false, windows:[].
    public static func probe(bundleIds: [String]) -> [String: Any] {
        let running = NSWorkspace.shared.runningApplications
        var out: [String: Any] = [:]
        for bid in bundleIds {
            guard let app = running.first(where: {
                $0.bundleIdentifier == bid && !$0.isTerminated
            }) else {
                out[bid] = ["running": false,
                            "windows": [[String: Any]]()]
                continue
            }
            out[bid] = appDict(pid: app.processIdentifier)
        }
        return out
    }
}
