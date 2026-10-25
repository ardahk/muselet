import AppKit
import Foundation

/// An app that opens something (default browser, the file's app, Finder).
public struct LaunchTarget: Equatable {
    public var name: String
    public var bundleId: String
    public var url: URL?
    public init(name: String, bundleId: String, url: URL?) {
        self.name = name; self.bundleId = bundleId; self.url = url
    }
}

/// LaunchServices calls behind the launch skills (`open_app`, `open_url`,
/// `web_search`, `open_folder`, `open_file`); mocked in tests.
public protocol Launching: AnyObject {
    /// Launch or activate the app named `name` (running apps first, then
    /// /Applications, /System/Applications, ~/Applications). Returns its
    /// pid (0 if unknown) and whether it had to be launched.
    func openApp(named name: String) throws -> (pid: pid_t, launched: Bool)
    /// An installed app resolved by its user-visible name.
    func app(named name: String) -> LaunchTarget?
    /// The app that opens `url` by default: the browser for http(s), the
    /// file's app for a file URL (Finder for a folder).
    func defaultApp(for url: URL) -> LaunchTarget?
    /// Open `url` with `app` (or the default handler), asking it to
    /// activate. Returns the opening app's pid when LaunchServices reports it (else 0).
    func open(_ url: URL, with app: LaunchTarget?) throws -> pid_t
}

/// Live LaunchServices (NSWorkspace).
public final class WorkspaceLauncher: Launching {
    public init() {}

    public func openApp(named name: String) throws -> (pid: pid_t, launched: Bool) {
        let before = Set(NSWorkspace.shared.runningApplications.map(\.processIdentifier))
        let pid = try openAppNamed(name)
        return (pid, pid > 0 && !before.contains(pid))
    }

    public func app(named name: String) -> LaunchTarget? {
        guard let path = SkillTargets.liveAppPath(name) else { return nil }
        return Self.target(appURL: URL(fileURLWithPath: path))
    }

    public func defaultApp(for url: URL) -> LaunchTarget? {
        guard let appURL = NSWorkspace.shared.urlForApplication(toOpen: url) else { return nil }
        return Self.target(appURL: appURL)
    }

    static func target(appURL: URL) -> LaunchTarget {
        let bundle = Bundle(url: appURL)
        let bid = bundle?.bundleIdentifier ?? ""
        let running = bid.isEmpty ? nil
            : NSRunningApplication.runningApplications(withBundleIdentifier: bid).first
        let name = running?.localizedName
            ?? (bundle?.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String)
            ?? (bundle?.object(forInfoDictionaryKey: "CFBundleName") as? String)
            ?? appURL.deletingPathExtension().lastPathComponent
        return LaunchTarget(name: name, bundleId: bid, url: appURL)
    }

    public func open(_ url: URL, with app: LaunchTarget?) throws -> pid_t {
        let cfg = NSWorkspace.OpenConfiguration()
        cfg.activates = true
        let sem = DispatchSemaphore(value: 0)
        var pid: pid_t = 0
        var openErr: Error?
        let done: (NSRunningApplication?, Error?) -> Void = { ra, err in
            pid = ra?.processIdentifier ?? 0
            openErr = err
            sem.signal()
        }
        if let appURL = app?.url {
            NSWorkspace.shared.open([url], withApplicationAt: appURL, configuration: cfg,
                                    completionHandler: done)
        } else {
            NSWorkspace.shared.open(url, configuration: cfg, completionHandler: done)
        }
        // The completion runs on a background queue once the app has the
        // request (a cold launch can take a few seconds).
        if sem.wait(timeout: .now() + 5) == .timedOut { return 0 }
        if let e = openErr { throw HandsError.skillFailed("open failed: \(e.localizedDescription)") }
        return pid
    }
}

/// Finder window views for `open_folder view=`: the View menu shortcuts
/// (cmd+1 icons, cmd+2 list, cmd+3 columns, cmd+4 gallery) and the
/// `current view of front Finder window` read-back.
public enum FinderView: String, CaseIterable {
    case icons, list, columns, gallery

    public static func parse(_ s: String) -> FinderView? {
        switch s.trimmingCharacters(in: .whitespaces).lowercased() {
        case "icons", "icon", "icon view": return .icons
        case "list", "list view": return .list
        case "columns", "column", "column view": return .columns
        case "gallery", "gallery view", "cover flow", "flow": return .gallery
        default: return nil
        }
    }

    public var combo: String {
        switch self {
        case .icons: return "cmd+1"
        case .list: return "cmd+2"
        case .columns: return "cmd+3"
        case .gallery: return "cmd+4"
        }
    }

    /// Read-back source (fixed, precompiled at warm-up).
    public static let readScript =
        "tell application \"Finder\" to return (current view of front Finder window) as text"

    /// `current view ... as text` -> view: "icon view" | "list view" |
    /// "column view" | "flow view" (gallery; older name) | "gallery view",
    /// or the raw constant («constant ****lsvw»).
    public static func fromAppleScript(_ s: String) -> FinderView? {
        let t = s.lowercased()
        if t.contains("icon") || t.contains("icnv") { return .icons }
        if t.contains("list") || t.contains("lsvw") { return .list }
        if t.contains("column") || t.contains("clvw") { return .columns }
        if t.contains("flow") || t.contains("gallery") || t.contains("flvw") || t.contains("glvw") { return .gallery }
        return nil
    }
}

extension Skills {
    /// Outcome of waiting for an opened app to come forward.
    struct ForegroundWait {
        var front: Bool
        var pid: pid_t
        var title: String?
        var done: Bool
    }

    /// Poll (<= `timeout`) until the app (`pid`, else the running app with
    /// `bundleId`) is frontmost and its front window title satisfies `done`
    /// (nil when it has no window). Re-activates it every
    /// `launchReactivateInterval` while another app is frontmost
    /// (cooperative activation may ignore the launch's own request).
    func waitForeground(pid inPid: pid_t, bundleId: String?, timeout: TimeInterval,
                        done: (String?) -> Bool) -> ForegroundWait {
        let reactivate = launchReactivateInterval
        let start = Date()
        let end = start.addingTimeInterval(timeout)
        var nextActivate = start.addingTimeInterval(reactivate)
        var w = ForegroundWait(front: false, pid: inPid, title: nil, done: false)
        while true {
            if w.pid <= 0, let b = bundleId, !b.isEmpty, let ra = apps.runningApp(bundlePrefix: b) {
                w.pid = ra.pid
            }
            w.front = w.pid > 0 && apps.frontmostPid() == w.pid
            if w.front {
                w.title = frontWindowTitle(pid: w.pid)
                w.done = done(w.title)
                if w.done { return w }
            } else if w.pid > 0, Date() >= nextActivate {
                apps.activate(pid: w.pid)
                nextActivate = Date().addingTimeInterval(reactivate)
            }
            if Date() >= end { return w }
            Hands.pollWait(min(launchPollInterval, max(0.001, end.timeIntervalSinceNow)))
        }
    }

    /// Title of `pid`'s front window (focused, main, else first visible), nil without one.
    func frontWindowTitle(pid: pid_t) -> String? {
        Hands.pickWindow(app: axApp(pid)).map { Hands.windowTitle($0.window) }
    }

    /// Placeholder titles a browser shows before the page has one.
    static func isPlaceholderTitle(_ t: String, browser: String) -> Bool {
        let s = t.trimmingCharacters(in: .whitespaces).lowercased()
        if s.isEmpty || s == browser.lowercased() { return true }
        for p in ["new tab", "loading", "untitled", "about:blank", "start page"] where s.hasPrefix(p) {
            return true
        }
        return false
    }

    /// Open `url` in the requested or default browser, waiting for the same
    /// frontmost and title verification. Returns the browser actually used.
    func openInBrowser(_ url: URL, extra: [String: Any],
                       browser: String? = nil,
                       sameTab: Bool = false) throws -> [String: Any] {
        let requested = browser?.trimmingCharacters(in: .whitespacesAndNewlines)
        let requestedName = requested?.isEmpty == false ? requested : nil
        let requestedApp = requestedName.flatMap { launcher.app(named: $0) }
        let target = requestedApp ?? launcher.defaultApp(for: url)
        let bid = target?.bundleId ?? ""
        let running = bid.isEmpty ? nil : apps.runningApp(bundlePrefix: bid)
        let before = running.flatMap { frontWindowTitle(pid: $0.pid) }
        let name = target?.name ?? "browser"

        func checkedResult(_ w: ForegroundWait, sameTabUsed: Bool = false,
                           beforeURL: String? = nil,
                           afterURL: String? = nil) throws -> [String: Any] {
            var r = extra
            r["browser"] = name
            if let requestedName {
                r["browser_requested"] = requestedName
                if requestedApp == nil { r["browser_fallback"] = true }
            }
            r["frontmost"] = apps.name(pid: apps.frontmostPid())
            r["window_title"] = w.title ?? ""
            r["title_changed"] = w.done
            r["same_tab_used"] = sameTabUsed
            if sameTabUsed, let beforeURL, let afterURL {
                r["url_changed"] = !afterURL.isEmpty && afterURL != beforeURL
                if !afterURL.isEmpty { r["page_url"] = afterURL }
            }
            guard w.front else {
                throw HandsError.verifyFailed(
                    code: "not_frontmost",
                    observed: "frontmost \"\(r["frontmost"]!)\", not \(name)",
                    result: r)
            }
            return r
        }

        if sameTab, let running, apps.frontmostPid() == running.pid,
           before != nil {
            let beforeURL = UtteranceCtx.pageInfo(
                app: axApp(running.pid), browser: true).url
            if let combo = try? Combo.parse("cmd+l") { events.post(combo) }
            Hands.pollWait(sameTabKeyDelay)
            events.typeText(url.absoluteString)
            if let combo = try? Combo.parse("forwarddelete") { events.post(combo) }
            if let combo = try? Combo.parse("return") { events.post(combo) }
            let w = waitForeground(pid: running.pid, bundleId: bid,
                                   timeout: openTimeout) { title in
                guard let t = title, t != before else { return false }
                return !Self.isPlaceholderTitle(t, browser: name)
            }
            let afterURL = UtteranceCtx.pageInfo(
                app: axApp(running.pid), browser: true).url
            return try checkedResult(w, sameTabUsed: true,
                                     beforeURL: beforeURL, afterURL: afterURL)
        }

        let opened = try launcher.open(url, with: target)
        let w = waitForeground(pid: opened > 0 ? opened : (running?.pid ?? 0), bundleId: bid,
                               timeout: openTimeout) { title in
            guard let t = title, t != before else { return false }
            return !Self.isPlaceholderTitle(t, browser: name)
        }
        return try checkedResult(w)
    }

    /// Open a folder in Finder and wait (<= `openTimeout`) for a frontmost
    /// Finder window titled with the folder's name; then apply `view`.
    func openFolder(path p: String, view: FinderView?) throws -> [String: Any] {
        let url = URL(fileURLWithPath: p)
        let finder = LaunchTarget(name: "Finder", bundleId: Self.finderBundleId,
                                  url: URL(fileURLWithPath: SkillTargets.finderPath))
        let want = displayName(p)
        let opened = try launcher.open(url, with: finder)
        let w = waitForeground(pid: opened, bundleId: Self.finderBundleId, timeout: openTimeout) { title in
            guard let t = title else { return false }
            return t.localizedCaseInsensitiveCompare(want) == .orderedSame
        }
        var r: [String: Any] = ["path": p, "app": "Finder",
                                "frontmost": apps.name(pid: apps.frontmostPid()),
                                "window_title": w.title ?? "", "title_matches": w.done]
        guard w.front else {
            throw HandsError.verifyFailed(code: "not_frontmost",
                                          observed: "frontmost \"\(r["frontmost"]!)\", not Finder", result: r)
        }
        if let view {
            for (k, v) in applyFinderView(view, windowVerified: w.done, pid: w.pid) { r[k] = v }
        }
        return r
    }

    /// cmd+1..4 on the Finder window we opened (only when it is verified
    /// frontmost), then read `current view of front Finder window` back
    /// (polled <= ~0.5 s: Finder takes the key and the Apple event separately).
    func applyFinderView(_ view: FinderView, windowVerified: Bool, pid: pid_t) -> [String: Any] {
        var r: [String: Any] = ["view_requested": view.rawValue]
        guard windowVerified, apps.frontmostPid() == pid else {
            r["view_applied"] = false
            r["view_error"] = "the opened Finder window is not frontmost"
            return r
        }
        guard let combo = try? Combo.parse(view.combo) else { return r }
        events.post(combo)
        var got: FinderView?
        var lastErr: String?
        for i in 0..<6 {
            if i > 0 { Hands.pollWait(viewPollInterval) }
            do {
                got = FinderView.fromAppleScript(try scripts.run(FinderView.readScript))
                lastErr = nil
                if got == view { break }
            } catch {
                lastErr = "\(error)"
            }
        }
        if let got { r["view"] = got.rawValue }
        if let lastErr, got == nil { r["view_error"] = String(lastErr.prefix(200)) }
        r["view_applied"] = got == view
        return r
    }

    /// Open a file with its default app and wait (<= `openTimeout`) for that
    /// app frontmost with a window titled with the file name (or its stem).
    func openFile(path p: String) throws -> [String: Any] {
        let url = URL(fileURLWithPath: p)
        guard let app = launcher.defaultApp(for: url) else {
            throw HandsError.skillFailed("no app opens \((p as NSString).lastPathComponent)")
        }
        let file = (p as NSString).lastPathComponent
        let stem = (file as NSString).deletingPathExtension
        let opened = try launcher.open(url, with: app)
        let w = waitForeground(pid: opened, bundleId: app.bundleId, timeout: openTimeout) { title in
            guard let t = title, !t.isEmpty else { return false }
            return t.localizedCaseInsensitiveContains(file)
                || (!stem.isEmpty && t.localizedCaseInsensitiveContains(stem))
        }
        let r: [String: Any] = ["path": p, "app": app.name,
                                "frontmost": apps.name(pid: apps.frontmostPid()),
                                "window_title": w.title ?? "", "title_matches": w.done]
        guard w.front else {
            throw HandsError.verifyFailed(code: "not_frontmost",
                                          observed: "frontmost \"\(r["frontmost"]!)\", not \(app.name)", result: r)
        }
        return r
    }

    /// Launch / activate an app and wait (<= `openAppTimeout`) until it is
    /// frontmost: {app, frontmost, launched, window_title?}; else not_frontmost.
    func openApp(named name: String) throws -> [String: Any] {
        let (pid, launched) = try launcher.openApp(named: name)
        let w = waitForeground(pid: pid, bundleId: nil, timeout: openAppTimeout) { _ in true }
        let appName = pid > 0 ? (apps.app(pid: pid)?.name ?? name) : name
        var r: [String: Any] = ["app": appName, "frontmost": apps.name(pid: apps.frontmostPid()),
                                "launched": launched]
        if let t = w.title, !t.isEmpty { r["window_title"] = t }
        guard w.front else {
            throw HandsError.verifyFailed(code: "not_frontmost",
                                          observed: "frontmost \"\(r["frontmost"]!)\", not \(appName)", result: r)
        }
        return r
    }

    static let finderBundleId = "com.apple.finder"

    /// Finder's window title for a folder (localized display name; "/" ->
    /// the volume name). Tests override via `displayNameOverride`.
    func displayName(_ path: String) -> String {
        if let o = displayNameOverride { return o(path) }
        return FileManager.default.displayName(atPath: path)
    }
}
