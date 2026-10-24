import AppKit
import HandsKit

/// ctx for typed requests (pill text field, panel examples). Usually the
/// same capture as push-to-talk; if Muselet itself is frontmost (its menu
/// is open), the app falls back to the last other frontmost app.
enum RequestCtx {
    private static var lastOther: String?
    private static var observer: NSObjectProtocol?

    static func startTracking() {
        guard observer == nil else { return }
        if let f = NSWorkspace.shared.frontmostApplication, f.processIdentifier != getpid() {
            lastOther = f.localizedName
        }
        observer = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main) { n in
            guard let app = n.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
                  app.processIdentifier != getpid() else { return }
            lastOther = app.localizedName
        }
    }

    static func capture() -> PendingCtx {
        if let f = NSWorkspace.shared.frontmostApplication, f.processIdentifier != getpid() {
            return UtteranceCtx.begin()
        }
        let base: [String: Any] = ["app": lastOther ?? "none", "focused": "none", "selection": false,
                                   "online": UtteranceCtx.online()]
        return PendingCtx(fallback: base, queue: .global(qos: .userInitiated)) { base }
    }
}
