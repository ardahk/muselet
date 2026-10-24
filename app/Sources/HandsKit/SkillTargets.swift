import AppKit
import ApplicationServices
import Foundation

/// Natural on-screen targets for skills, so the ghost cursor can fly
/// somewhere meaningful before a skill runs (ux-4): the app's Dock icon,
/// the Control Center / Wi-Fi / Sound menu extra, the Finder Dock icon, the
/// default browser's Dock icon. Frames are global top-left points, read
/// from the Dock and menu-extra processes over AX (read-only) and cached
/// for `cacheTTL`. Hidden (auto-hide Dock) or absent targets give nil.
public final class SkillTargets {
    public struct Target: Equatable {
        public var frame: CGRect
        public var label: String?
    }

    struct DockItem: Equatable {
        var title: String
        var path: String?      // app bundle path (AXURL)
        var frame: CGRect
    }

    struct MenuExtra: Equatable {
        var ident: String      // e.g. com.apple.menuextra.wifi
        var frame: CGRect
    }

    public static let cacheTTL: TimeInterval = 5
    static let finderPath = "/System/Library/CoreServices/Finder.app"

    static let appSkills: Set<String> = ["open_app", "quit_app", "hide_app"]
    static let finderSkills: Set<String> = ["open_folder", "open_file", "find_file", "new_folder"]
    static let browserSkills: Set<String> = ["open_url", "web_search"]
    /// Skill -> preferred menu extra (identifier suffix); Control Center is the fallback.
    static let extraSkills: [String: String] = [
        "set_volume": "sound", "change_volume": "sound", "mute": "sound",
        "set_brightness": "display", "dark_mode": "controlcenter",
        "wifi": "wifi", "bluetooth": "bluetooth",
    ]

    // Sources (injectable for tests).
    var readDock: () -> [DockItem] = SkillTargets.liveDock
    var readExtras: () -> [MenuExtra] = SkillTargets.liveExtras
    var screens: () -> CGRect = Walker.screenUnion
    var appPath: (String) -> String? = SkillTargets.liveAppPath
    var browserPath: () -> String? = {
        NSWorkspace.shared.urlForApplication(toOpen: URL(string: "https://example.com")!)?
            .resolvingSymlinksInPath().path
    }
    var now: () -> Date = Date.init

    private let lock = NSLock()
    private var dockCache: (at: Date, items: [DockItem])?
    private var extrasCache: (at: Date, items: [MenuExtra])?

    public init() {}

    private let prefetchQueue = DispatchQueue(label: "hands.skilltargets", qos: .utility)

    /// Refresh stale caches in the background (the app calls this at
    /// push-to-talk key-down, so the skill RPC a second later hits a warm
    /// cache instead of a ~30-60 ms Dock / menu-bar AX read).
    public func prefetch() {
        prefetchQueue.async { [self] in
            _ = dockItems()
            _ = extras()
        }
    }

    /// Does this skill have a natural target at all (cheap, no AX)?
    public static func hasTarget(_ skill: String) -> Bool {
        appSkills.contains(skill) || finderSkills.contains(skill)
            || browserSkills.contains(skill) || extraSkills[skill] != nil
    }

    /// Target for `skill`, or nil (no natural target / not visible).
    public func target(skill: String, args: [String: Any]) -> Target? {
        guard Self.hasTarget(skill) else { return nil }
        let label = Self.label(skill: skill, args: args)
        let frame: CGRect?
        if Self.appSkills.contains(skill) {
            guard let name = (args["app"] as? String)?.trimmingCharacters(in: .whitespaces),
                  !name.isEmpty else { return nil }
            frame = dockFrame(path: appPath(name), title: name)
        } else if Self.finderSkills.contains(skill) {
            frame = dockFrame(path: Self.finderPath, title: "Finder")
        } else if Self.browserSkills.contains(skill) {
            guard let p = browserPath() else { return nil }
            frame = dockFrame(path: p, title: Self.appName(fromPath: p))
        } else if let want = Self.extraSkills[skill] {
            frame = extraFrame(want) ?? extraFrame("controlcenter")
        } else {
            frame = nil
        }
        return frame.map { Target(frame: $0, label: label) }
    }

    // MARK: lookups (cached)

    func dockItems() -> [DockItem] {
        lock.lock()
        if let c = dockCache, now().timeIntervalSince(c.at) < Self.cacheTTL {
            lock.unlock(); return c.items
        }
        lock.unlock()
        let items = readDock()
        lock.lock(); dockCache = (now(), items); lock.unlock()
        return items
    }

    func extras() -> [MenuExtra] {
        lock.lock()
        if let c = extrasCache, now().timeIntervalSince(c.at) < Self.cacheTTL {
            lock.unlock(); return c.items
        }
        lock.unlock()
        let items = readExtras()
        lock.lock(); extrasCache = (now(), items); lock.unlock()
        return items
    }

    func visible(_ r: CGRect) -> Bool {
        let s = screens()
        guard r.width > 0, r.height > 0, r.minX.isFinite, r.minY.isFinite else { return false }
        if s.isNull || s.isEmpty { return true }
        // Mostly on screen: an auto-hidden Dock parks its icons just below the edge.
        let inter = r.intersection(s)
        return !inter.isNull && inter.width * inter.height >= 0.5 * r.width * r.height
    }

    /// Dock icon by bundle path (exact), else title (exact, then prefix).
    func dockFrame(path: String?, title: String) -> CGRect? {
        let items = dockItems()
        let norm = { (p: String) in (p as NSString).standardizingPath.lowercased() }
        var hit: DockItem?
        if let path {
            let want = norm(path)
            hit = items.first { $0.path.map(norm) == want }
                ?? items.first { ($0.path.map { ($0 as NSString).lastPathComponent.lowercased() })
                    == (want as NSString).lastPathComponent }
        }
        let t = title.lowercased()
        if hit == nil { hit = items.first { $0.title.lowercased() == t } }
        if hit == nil, t.count >= 3 {
            hit = items.first { $0.title.lowercased().hasPrefix(t) || t.hasPrefix($0.title.lowercased()) }
        }
        guard let f = hit?.frame, visible(f) else { return nil }
        return f
    }

    /// Menu extra whose identifier ends with `.<suffix>` (or contains it).
    func extraFrame(_ suffix: String) -> CGRect? {
        let items = extras()
        let hit = items.first { $0.ident.lowercased().hasSuffix("." + suffix) }
            ?? items.first { $0.ident.lowercased().contains(suffix) }
        guard let f = hit?.frame, visible(f) else { return nil }
        return f
    }

    // MARK: labels

    /// Short chip label: app name, folder name, query, host, level.
    static func label(skill: String, args: [String: Any]) -> String? {
        func s(_ k: String) -> String? {
            if let v = args[k] as? String, !v.isEmpty { return v }
            if let n = args[k] as? NSNumber { return n.stringValue }
            return nil
        }
        switch skill {
        case "open_app", "quit_app", "hide_app": return s("app")
        case "open_folder", "open_file": return s("path").map { ($0 as NSString).lastPathComponent }
        case "new_folder": return s("name")
        case "find_file", "web_search": return s("query")
        case "open_url":
            guard let u = s("url") else { return nil }
            return URL(string: u.contains("://") ? u : "https://" + u)?.host ?? u
        case "set_volume", "set_brightness": return s("level").map { "\($0)%" }
        case "change_volume": return s("delta").map { $0.hasPrefix("-") ? $0 : "+\($0)" }
        case "mute", "dark_mode", "wifi", "bluetooth":
            guard let on = args["on"] else { return nil }
            let b = (on as? Bool) ?? ["true", "1", "on", "yes"].contains("\(on)".lowercased())
            return b ? "On" : "Off"
        default: return nil
        }
    }

    static func appName(fromPath p: String) -> String {
        ((p as NSString).lastPathComponent as NSString).deletingPathExtension
    }

    // MARK: live AX readers (read-only)

    static func liveAppPath(_ name: String) -> String? {
        if let r = NSWorkspace.shared.runningApplications.first(where: {
            ($0.localizedName ?? "").localizedCaseInsensitiveCompare(name) == .orderedSame
        }), let u = r.bundleURL { return u.resolvingSymlinksInPath().path }
        return AppResolver.url(forAppNamed: name)?.resolvingSymlinksInPath().path
    }

    private static func attr(_ e: AXUIElement, _ n: String) -> CFTypeRef? {
        var v: CFTypeRef?
        return AXUIElementCopyAttributeValue(e, n as CFString, &v) == .success ? v : nil
    }

    private static func frame(_ e: AXUIElement) -> CGRect {
        var p = CGPoint.zero, s = CGSize.zero
        if let v = attr(e, kAXPositionAttribute as String), CFGetTypeID(v) == AXValueGetTypeID() {
            AXValueGetValue(v as! AXValue, .cgPoint, &p)
        }
        if let v = attr(e, kAXSizeAttribute as String), CFGetTypeID(v) == AXValueGetTypeID() {
            AXValueGetValue(v as! AXValue, .cgSize, &s)
        }
        return CGRect(origin: p, size: s)
    }

    /// Dock auto-hide is on: its icons sit off screen, so never pay the AX read.
    static func dockAutoHides() -> Bool {
        CFPreferencesAppSynchronize("com.apple.dock" as CFString)
        return (CFPreferencesCopyAppValue("autohide" as CFString, "com.apple.dock" as CFString) as? Bool) ?? false
    }

    /// Dock process: AXList > AXDockItem (title, AXURL, frame).
    static func liveDock() -> [DockItem] {
        if dockAutoHides() { return [] }
        guard let dock = NSRunningApplication.runningApplications(
            withBundleIdentifier: "com.apple.dock").first else { return [] }
        let app = AXUIElementCreateApplication(dock.processIdentifier)
        AXUIElementSetMessagingTimeout(app, 0.1)
        var out: [DockItem] = []
        for list in (attr(app, kAXChildrenAttribute as String) as? [AXUIElement]) ?? [] {
            AXUIElementSetMessagingTimeout(list, 0.1)
            guard (attr(list, kAXRoleAttribute as String) as? String) == "AXList" else { continue }
            for it in (attr(list, kAXChildrenAttribute as String) as? [AXUIElement]) ?? [] {
                AXUIElementSetMessagingTimeout(it, 0.1)
                guard (attr(it, kAXSubroleAttribute as String) as? String) == "AXApplicationDockItem"
                else { continue }
                let title = attr(it, kAXTitleAttribute as String) as? String ?? ""
                var path: String?
                if let u = attr(it, kAXURLAttribute as String) {
                    path = ((u as? URL) ?? (u as? NSURL).map { $0 as URL })?.resolvingSymlinksInPath().path
                }
                out.append(DockItem(title: title, path: path, frame: frame(it)))
            }
        }
        return out
    }

    /// System menu extras (Control Center, Wi-Fi, Sound, ...): the
    /// AXExtrasMenuBar of MenuBarAgent (macOS 27) / ControlCenter /
    /// SystemUIServer, items with an `com.apple.menuextra.*` identifier.
    static func liveExtras() -> [MenuExtra] {
        var out: [MenuExtra] = []
        for bid in ["com.apple.MenuBarAgent", "com.apple.controlcenter", "com.apple.systemuiserver"] {
            guard let ra = NSRunningApplication.runningApplications(withBundleIdentifier: bid).first
            else { continue }
            let app = AXUIElementCreateApplication(ra.processIdentifier)
            AXUIElementSetMessagingTimeout(app, 0.1)
            guard let barRef = attr(app, "AXExtrasMenuBar"),
                  CFGetTypeID(barRef) == AXUIElementGetTypeID() else { continue }
            // Items sit directly under the bar, or one level down inside
            // hosting groups (MenuBarAgent).
            var queue: [(AXUIElement, Int)] = ((attr(barRef as! AXUIElement, kAXChildrenAttribute as String)
                as? [AXUIElement]) ?? []).map { ($0, 0) }
            var qi = 0
            while qi < queue.count && qi < 80 {
                let (el, depth) = queue[qi]; qi += 1
                AXUIElementSetMessagingTimeout(el, 0.1)
                if let ident = attr(el, "AXIdentifier") as? String, ident.hasPrefix("com.apple.menuextra.") {
                    out.append(MenuExtra(ident: ident, frame: frame(el)))
                    continue
                }
                if depth < 2 {
                    queue.append(contentsOf: ((attr(el, kAXChildrenAttribute as String) as? [AXUIElement]) ?? [])
                        .map { ($0, depth + 1) })
                }
            }
            if !out.isEmpty { break }
        }
        return out
    }
}
