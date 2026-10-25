import ApplicationServices
import CoreGraphics
import Foundation
import XCTest
@testable import HandsKit

// Truthful launches: open_app / open_url / web_search / open_folder (+ view)
// / open_file report success only once the target is frontmost, with the
// window title read back. Hermetic: MockLauncher stands in for
// LaunchServices; no launches, no AppleScript, no files outside temp dirs.

// MARK: - truthful launches + open_folder view

/// LaunchServices stand-in: records opens; tests move the "frontmost" app.
final class MockLauncher: Launching {
    var apps: [String: (pid: pid_t, launched: Bool)] = [:]
    /// URL scheme, file extension, or "folder" -> default app.
    var defaults: [String: LaunchTarget] = [:]
    var named: [String: LaunchTarget] = [:]
    var opened: [(url: URL, app: LaunchTarget?)] = []
    var openPid: pid_t = 0
    var onOpen: ((URL, LaunchTarget?) -> Void)?
    var onOpenApp: ((String) -> Void)?

    func openApp(named name: String) throws -> (pid: pid_t, launched: Bool) {
        guard let a = apps[name.lowercased()] else { throw HandsError.skillFailed("app not found: \(name)") }
        onOpenApp?(name)
        return a
    }

    func defaultApp(for url: URL) -> LaunchTarget? {
        if url.isFileURL { return defaults[url.pathExtension.isEmpty ? "folder" : url.pathExtension] }
        return defaults[url.scheme ?? ""]
    }

    func app(named name: String) -> LaunchTarget? {
        named[name.lowercased()]
    }

    func open(_ url: URL, with app: LaunchTarget?) throws -> pid_t {
        opened.append((url, app))
        onOpen?(url, app)
        return openPid
    }
}

/// App whose front window title comes from a closure (changes over time);
/// nil = no window.
final class TitledApp: Element {
    final class Window: Element {
        let title: () -> String?
        init(_ title: @escaping () -> String?) { self.title = title }
        func copyAttrs() -> ElAttrs {
            var a = ElAttrs()
            a.role = "AXWindow"
            a.title = title()
            a.size = CGSize(width: 800, height: 600)
            return a
        }
        func performAction(_ name: String) -> Bool { false }
        func setAttr(_ name: String, _ value: Any?) -> Bool { false }
        func isSettable(_ name: String) -> Bool { false }
        func copySingleAttr(_ name: String) -> Any? { name == kAXTitleAttribute as String ? title() : nil }
    }

    let window: Window
    init(_ title: @escaping () -> String?) { window = Window(title) }
    func copyAttrs() -> ElAttrs { var a = ElAttrs(); a.role = "AXApplication"; return a }
    func performAction(_ name: String) -> Bool { false }
    func setAttr(_ name: String, _ value: Any?) -> Bool { false }
    func isSettable(_ name: String) -> Bool { false }
    func copySingleAttr(_ name: String) -> Any? {
        name == kAXFocusedWindowAttribute as String && window.title() != nil ? window : nil
    }
}

final class TruthfulLaunchTests: XCTestCase {
    private let term = RunningAppInfo(pid: 1, name: "Terminal", bundleId: "com.apple.Terminal")
    private let safari = RunningAppInfo(pid: 600, name: "Safari", bundleId: "com.apple.Safari")
    private let zen = RunningAppInfo(pid: 700, name: "Zen", bundleId: "app.zen-browser.zen")
    private let finder = RunningAppInfo(pid: 800, name: "Finder", bundleId: "com.apple.finder")
    private let preview = RunningAppInfo(pid: 900, name: "Preview", bundleId: "com.apple.Preview")
    private var zenTarget: LaunchTarget {
        LaunchTarget(name: "Zen", bundleId: zen.bundleId, url: URL(fileURLWithPath: "/Applications/Zen.app"))
    }
    private var safariTarget: LaunchTarget {
        LaunchTarget(name: "Safari", bundleId: safari.bundleId,
                     url: URL(fileURLWithPath: "/Applications/Safari.app"))
    }
    private var cleanup: [String] = []

    override func tearDown() {
        for p in cleanup { try? FileManager.default.removeItem(atPath: p) }
        cleanup = []
        super.tearDown()
    }

    private func tempDir(_ name: String) throws -> String {
        let root = NSTemporaryDirectory() + "hands-launch-\(UUID().uuidString)"
        let p = root + "/" + name
        try FileManager.default.createDirectory(atPath: p, withIntermediateDirectories: true)
        cleanup.append(root)
        return p
    }

    private func tempFile(_ name: String) throws -> String {
        let p = try tempDir("files") + "/" + name
        try "x".write(toFile: p, atomically: true, encoding: .utf8)
        return p
    }

    private func skills(_ apps: MockApps, _ launcher: MockLauncher, scripts: ScriptRunning = SpyRunner(),
                        poster: MockPoster = MockPoster(),
                        title: @escaping (pid_t) -> String?) -> Skills {
        let s = Skills(catalog: catalog(), scripts: scripts, events: poster, apps: apps, hooks: .inert,
                       launcher: launcher)
        s.axApp = { pid in TitledApp { title(pid) } }
        s.openAppTimeout = 0.3
        s.openTimeout = 0.4
        s.sameTabKeyDelay = 0
        s.launchPollInterval = 0.01
        s.launchReactivateInterval = 0.05
        s.viewPollInterval = 0.01
        s.displayNameOverride = { ($0 as NSString).lastPathComponent }
        return s
    }

    // open_app

    func testOpenAppReturnsOnceFrontmost() {
        let apps = MockApps(frontmost: 1, running: [term, safari])
        let launcher = MockLauncher()
        launcher.apps["safari"] = (600, true)
        launcher.onOpenApp = { _ in apps.frontmost = 600 }       // the launch brought it forward
        let s = skills(apps, launcher) { _ in "Start Page" }
        let r = s.execute(name: "open_app", args: ["app": "Safari"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["app"] as? String, "Safari")
        XCTAssertEqual(res?["frontmost"] as? String, "Safari")
        XCTAssertEqual(res?["launched"] as? Bool, true)
        XCTAssertEqual(res?["window_title"] as? String, "Start Page")
        XCTAssertTrue(apps.activated.isEmpty)
    }

    func testOpenAppReactivatesWhenTheLaunchDidNotComeForward() {
        let apps = MockApps(frontmost: 1, running: [term, safari])
        let launcher = MockLauncher()
        launcher.apps["safari"] = (600, false)
        let s = skills(apps, launcher) { _ in nil }
        let r = s.execute(name: "open_app", args: ["app": "safari"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(apps.activated.first, 600)
        XCTAssertEqual((r["result"] as? [String: Any])?["app"] as? String, "Safari")   // resolved name
        XCTAssertEqual((r["result"] as? [String: Any])?["launched"] as? Bool, false)
    }

    func testOpenAppNeverFrontmostIsNotFrontmostWithTheReadBack() {
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [term, safari])
        let launcher = MockLauncher()
        launcher.apps["safari"] = (600, true)
        let s = skills(apps, launcher) { _ in nil }
        let t0 = Date()
        let r = s.execute(name: "open_app", args: ["app": "Safari"])
        let dt = Date().timeIntervalSince(t0)
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "not_frontmost")
        XCTAssertTrue((r["observed"] as? String ?? "").contains("Terminal"), "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["frontmost"] as? String, "Terminal")
        XCTAssertGreaterThanOrEqual(dt, 0.28)                    // waited the whole bound
        XCTAssertLessThan(dt, 1.0)
        XCTAssertFalse(apps.activated.isEmpty)                   // and retried activation
        // Unknown app: the launcher's error, no wait.
        XCTAssertEqual(s.execute(name: "open_app", args: ["app": "Nope"])["error"] as? String,
                       "app not found: Nope")
    }

    // open_url / web_search

    func testOpenURLWaitsForTheBrowserAndANewTitle() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var openedAt: Date?
        launcher.onOpen = { _, _ in apps.frontmost = 700; openedAt = Date() }
        let s = skills(apps, launcher) { pid in
            guard pid == 700 else { return nil }
            // The old tab's title until the new page loads ~60 ms after the open.
            guard let t = openedAt, Date().timeIntervalSince(t) > 0.06 else { return "GitHub" }
            return "Example Domain — Zen Browser"
        }
        let r = s.execute(name: "open_url", args: ["url": "example.com"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["url"] as? String, "https://example.com")
        XCTAssertEqual(res?["browser"] as? String, "Zen")
        XCTAssertEqual(res?["frontmost"] as? String, "Zen")
        XCTAssertEqual(res?["window_title"] as? String, "Example Domain — Zen Browser")
        XCTAssertEqual(res?["title_changed"] as? Bool, true)
        XCTAssertEqual(launcher.opened.first?.url.absoluteString, "https://example.com")
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "app.zen-browser.zen")   // the default browser
    }

    func testOpenURLUsesAnInstalledNamedBrowser() {
        let apps = MockApps(frontmost: 1, running: [term, safari, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.named["safari"] = safariTarget
        launcher.openPid = 600
        var opened = false
        launcher.onOpen = { _, app in
            XCTAssertEqual(app?.bundleId, "com.apple.Safari")
            apps.frontmost = 600
            opened = true
        }
        let s = skills(apps, launcher) { pid in
            pid == 600 ? (opened ? "Example Domain — Safari" : "Start Page") : nil
        }
        let r = s.execute(name: "open_url", args: [
            "url": "https://example.com", "browser": "Safari"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["browser"] as? String, "Safari")
        XCTAssertEqual(res?["browser_requested"] as? String, "Safari")
        XCTAssertNil(res?["browser_fallback"])
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "com.apple.Safari")
    }

    func testWebSearchFallsBackWhenTheRequestedBrowserIsUnavailable() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var opened = false
        launcher.onOpen = { _, _ in apps.frontmost = 700; opened = true }
        let s = skills(apps, launcher) { pid in
            pid == 700 ? (opened ? "Example Domain — Zen Browser" : "Start Page") : nil
        }
        let r = s.execute(name: "web_search", args: [
            "query": "example", "browser": "Arc"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["browser"] as? String, "Zen")
        XCTAssertEqual(res?["browser_requested"] as? String, "Arc")
        XCTAssertEqual(res?["browser_fallback"] as? Bool, true)
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "app.zen-browser.zen")
    }

    func testOpenURLUnchangedTitleIsReported() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        launcher.onOpen = { _, _ in apps.frontmost = 700 }
        let s = skills(apps, launcher) { pid in pid == 700 ? "Example Domain" : nil }
        let r = s.execute(name: "open_url", args: ["url": "https://example.com"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")              // frontmost: it did open
        XCTAssertEqual((r["result"] as? [String: Any])?["title_changed"] as? Bool, false)
    }

    func testFreshBrowserLaunchWaitsPastPlaceholderTitles() {
        let apps = MockApps(frontmost: 1, running: [term])           // Zen not running yet
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var openedAt: Date?
        let zen = self.zen
        launcher.onOpen = { _, _ in apps.running.append(zen); apps.frontmost = 700; openedAt = Date() }
        let s = skills(apps, launcher) { pid in
            guard pid == 700, let t = openedAt else { return nil }
            return Date().timeIntervalSince(t) > 0.06 ? "Example Domain" : "New Tab"
        }
        let r = s.execute(name: "open_url", args: ["url": "https://example.com"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual((r["result"] as? [String: Any])?["window_title"] as? String, "Example Domain")
        XCTAssertEqual((r["result"] as? [String: Any])?["title_changed"] as? Bool, true)
    }

    func testOpenURLNeverFrontmostIsNotFrontmost() {
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        let s = skills(apps, launcher) { _ in "GitHub" }
        let r = s.execute(name: "open_url", args: ["url": "example.com"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "not_frontmost")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["browser"] as? String, "Zen")
        XCTAssertEqual(res?["frontmost"] as? String, "Terminal")
        XCTAssertEqual(res?["url"] as? String, "https://example.com")
    }

    func testWebSearchOpensTheEncodedQueryInTheBrowser() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        var openedAt: Date?
        launcher.onOpen = { _, _ in apps.frontmost = 700; openedAt = Date() }
        let s = skills(apps, launcher) { _ in openedAt == nil ? "GitHub" : "AT&T c++ a=b - Google Search" }
        let r = s.execute(name: "web_search", args: ["query": "AT&T c++ a=b"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(launcher.opened.first?.url.absoluteString,
                       "https://www.google.com/search?q=AT%26T%20c%2B%2B%20a%3Db")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["query"] as? String, "AT&T c++ a=b")
        XCTAssertEqual(res?["window_title"] as? String, "AT&T c++ a=b - Google Search")
    }

    func testSameTabOpenURLNavigatesCurrentFrontmostBrowser() {
        let apps = MockApps(frontmost: 700, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        let poster = MockPoster()
        let url = "https://en.wikipedia.org/wiki/History"
        let s = skills(apps, launcher, poster: poster) { pid in
            guard pid == 700 else { return nil }
            return poster.typed.isEmpty ? "Wikipedia" : "history - Search results - Wikipedia"
        }
        let r = s.execute(name: "open_url", args: ["url": url, "same_tab": true])

        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let result = r["result"] as? [String: Any]
        XCTAssertTrue(launcher.opened.isEmpty)
        XCTAssertEqual(poster.typed, [url])
        XCTAssertEqual(poster.posted, ["cmd+l", "forwarddelete", "return"])
        XCTAssertEqual(result?["same_tab_used"] as? Bool, true)
        XCTAssertEqual(result?["title_changed"] as? Bool, true)
    }

    func testSameTabOpenURLFallsBackWhenBrowserIsNotFrontmost() {
        let apps = MockApps(frontmost: 1, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        launcher.openPid = 700
        launcher.onOpen = { _, _ in apps.frontmost = 700 }
        let s = skills(apps, launcher) { pid in pid == 700 ? "History" : nil }

        let r = s.execute(name: "open_url", args: [
            "url": "https://en.wikipedia.org/wiki/History", "same_tab": true])

        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(launcher.opened.count, 1)
        XCTAssertEqual((r["result"] as? [String: Any])?["same_tab_used"] as? Bool, false)
    }

    func testSameTabOpenURLFallsBackToExplicitlyRequestedBrowser() {
        let apps = MockApps(frontmost: 700, running: [term, safari, zen])
        let launcher = MockLauncher()
        launcher.named["safari"] = safariTarget
        launcher.openPid = 600
        launcher.onOpen = { _, _ in apps.frontmost = 600 }
        let s = skills(apps, launcher) { pid in
            pid == 600 ? "History - Safari" : "Wikipedia"
        }

        let r = s.execute(name: "open_url", args: [
            "url": "https://en.wikipedia.org/wiki/History",
            "browser": "Safari", "same_tab": true])

        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertEqual(launcher.opened.count, 1)
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "com.apple.Safari")
        XCTAssertEqual((r["result"] as? [String: Any])?["same_tab_used"] as? Bool, false)
    }

    func testSameTabWebSearchNavigatesCurrentFrontmostBrowser() {
        let apps = MockApps(frontmost: 700, running: [term, zen])
        let launcher = MockLauncher()
        launcher.defaults["https"] = zenTarget
        let poster = MockPoster()
        let s = skills(apps, launcher, poster: poster) { pid in
            guard pid == 700 else { return nil }
            return poster.typed.isEmpty ? "Wikipedia" : "history - Google Search"
        }

        let r = s.execute(name: "web_search", args: [
            "query": "history", "same_tab": true])

        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        XCTAssertTrue(launcher.opened.isEmpty)
        XCTAssertEqual(poster.typed, ["https://www.google.com/search?q=history"])
        XCTAssertEqual((r["result"] as? [String: Any])?["same_tab_used"] as? Bool, true)
    }

    // open_folder (+ view) / open_file

    func testOpenFolderReadsTheWindowTitleAndAppliesTheView() throws {
        let dir = try tempDir("Reports")
        let apps = MockApps(frontmost: 1, running: [term, finder])
        let launcher = MockLauncher()
        launcher.openPid = 800
        launcher.onOpen = { _, _ in apps.frontmost = 800 }
        let spy = SpyRunner()
        spy.respond = "list view"
        let poster = MockPoster()
        let s = skills(apps, launcher, scripts: spy, poster: poster) { pid in pid == 800 ? "Reports" : nil }
        let r = s.execute(name: "open_folder", args: ["path": dir, "view": "list"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["app"] as? String, "Finder")
        XCTAssertEqual(res?["frontmost"] as? String, "Finder")
        XCTAssertEqual(res?["window_title"] as? String, "Reports")
        XCTAssertEqual(res?["title_matches"] as? Bool, true)
        XCTAssertEqual(poster.posted, ["cmd+2"])
        XCTAssertEqual(spy.ran, [FinderView.readScript])
        XCTAssertEqual(res?["view"] as? String, "list")
        XCTAssertEqual(res?["view_applied"] as? Bool, true)
        XCTAssertEqual(launcher.opened.first?.app?.bundleId, "com.apple.finder")
        XCTAssertEqual(launcher.opened.first?.url.path, dir)
    }

    func testOpenFolderViewValidatedFirstAndOnlyForTheVerifiedWindow() throws {
        let dir = try tempDir("Taxes")
        let apps = MockApps(frontmost: 1, running: [term, finder])
        let launcher = MockLauncher()
        launcher.openPid = 800
        launcher.onOpen = { _, _ in apps.frontmost = 800 }
        let spy = SpyRunner()
        let poster = MockPoster()
        let s = skills(apps, launcher, scripts: spy, poster: poster) { pid in pid == 800 ? "Downloads" : nil }
        let bad = s.execute(name: "open_folder", args: ["path": dir, "view": "huge"])
        XCTAssertEqual(bad["ok"] as? Bool, false)
        XCTAssertTrue((bad["error"] as? String ?? "").contains("view must be"), "\(bad)")
        XCTAssertTrue(launcher.opened.isEmpty)                   // nothing opened
        // Finder came forward but another folder's window is in front: no keys.
        let r = s.execute(name: "open_folder", args: ["path": dir, "view": "icons"])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["title_matches"] as? Bool, false)
        XCTAssertEqual(res?["view_applied"] as? Bool, false)
        XCTAssertNotNil(res?["view_error"])
        XCTAssertTrue(poster.posted.isEmpty)
        XCTAssertTrue(spy.ran.isEmpty)
        // Missing folder: nothing opened.
        XCTAssertEqual(s.execute(name: "open_folder", args: ["path": dir + "/nope"])["ok"] as? Bool, false)
        XCTAssertEqual(launcher.opened.count, 1)
    }

    func testOpenFolderNotFrontmost() throws {
        let dir = try tempDir("Inbox")
        let apps = MockApps(frontmost: 1, activateSucceeds: false, running: [term, finder])
        let launcher = MockLauncher()
        launcher.openPid = 800
        let s = skills(apps, launcher) { _ in "Inbox" }
        let r = s.execute(name: "open_folder", args: ["path": dir])
        XCTAssertEqual(r["error"] as? String, "not_frontmost")
        XCTAssertEqual((r["result"] as? [String: Any])?["path"] as? String, dir)
    }

    func testFinderViewMapping() {
        XCTAssertEqual(FinderView.parse("Columns"), .columns)
        XCTAssertEqual(FinderView.parse("icon"), .icons)
        XCTAssertEqual(FinderView.parse("gallery"), .gallery)
        XCTAssertNil(FinderView.parse("tiles"))
        XCTAssertEqual(FinderView.icons.combo, "cmd+1")
        XCTAssertEqual(FinderView.list.combo, "cmd+2")
        XCTAssertEqual(FinderView.columns.combo, "cmd+3")
        XCTAssertEqual(FinderView.gallery.combo, "cmd+4")
        XCTAssertEqual(FinderView.fromAppleScript("column view"), .columns)
        XCTAssertEqual(FinderView.fromAppleScript("flow view"), .gallery)
        XCTAssertEqual(FinderView.fromAppleScript("«constant ****lsvw»"), .list)
        XCTAssertEqual(FinderView.fromAppleScript("icon view"), .icons)
        XCTAssertNil(FinderView.fromAppleScript("group view"))
        XCTAssertTrue(SkillScripts.fixedSources.contains(FinderView.readScript))   // precompiled at warm-up
    }

    func testOpenFileWaitsForItsAppAndTitle() throws {
        let file = try tempFile("report.pdf")
        let apps = MockApps(frontmost: 1, running: [term, preview])
        let launcher = MockLauncher()
        launcher.defaults["pdf"] = LaunchTarget(name: "Preview", bundleId: preview.bundleId, url: nil)
        launcher.openPid = 900
        launcher.onOpen = { _, _ in apps.frontmost = 900 }
        let s = skills(apps, launcher) { pid in pid == 900 ? "report" : nil }   // extension hidden
        let r = s.execute(name: "open_file", args: ["path": file])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let res = r["result"] as? [String: Any]
        XCTAssertEqual(res?["app"] as? String, "Preview")
        XCTAssertEqual(res?["frontmost"] as? String, "Preview")
        XCTAssertEqual(res?["window_title"] as? String, "report")
        XCTAssertEqual(res?["title_matches"] as? Bool, true)
        let odd = try tempFile("data.xyz")
        XCTAssertEqual(s.execute(name: "open_file", args: ["path": odd])["error"] as? String,
                       "no app opens data.xyz")
    }
}
