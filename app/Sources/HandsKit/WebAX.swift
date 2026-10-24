import AppKit
import ApplicationServices
import Foundation

/// How an app's web content is exposed to accessibility clients.
public enum WebAXMode: String {
    /// Chromium / Electron: `AXManualAccessibility = true` on the app element.
    case manual
    /// WebKit (Safari) and Gecko (Firefox, Zen) browsers:
    /// `AXEnhancedUserInterface = true`. Restricted to browser bundle ids:
    /// some apps animate/glitch window moves while it is set.
    case enhanced
}

/// Turning on the web accessibility tree of browsers / Electron apps, so
/// web pages are observable through AX instead of screenshots.
public enum WebAX {
    public static let manualAttribute = "AXManualAccessibility"
    public static let enhancedAttribute = "AXEnhancedUserInterface"
    /// Max time the first observe of a newly enabled app waits for the web
    /// area to populate.
    public static let populateTimeout: TimeInterval = 0.3

    static let chromiumIds: Set<String> = [
        "com.google.Chrome", "com.google.Chrome.beta", "com.google.Chrome.dev",
        "com.google.Chrome.canary", "org.chromium.Chromium",
        "com.microsoft.edgemac", "com.microsoft.edgemac.Beta", "com.microsoft.edgemac.Dev",
        "com.brave.Browser", "com.brave.Browser.beta", "com.vivaldi.Vivaldi",
        "com.operasoftware.Opera", "com.operasoftware.OperaGX",
        "company.thebrowser.Browser", "company.thebrowser.dia",   // Arc, Dia
        "com.tinyspeck.slackmacgap", "com.hnc.Discord", "com.microsoft.VSCode",
        "com.visualstudio.code.oss", "com.figma.Desktop", "notion.id",
        "com.spotify.client", "com.todoist.mac.Todoist", "com.microsoft.teams2",
    ]

    /// WebKit / Gecko browsers that need AXEnhancedUserInterface.
    static let enhancedIds: Set<String> = [
        "com.apple.Safari", "com.apple.SafariTechnologyPreview",
        "org.mozilla.firefox", "org.mozilla.firefoxdeveloperedition", "org.mozilla.nightly",
        "app.zen-browser.zen", "io.gitlab.librewolf-community", "net.waterfox.waterfox",
        "org.torproject.torbrowser", "net.mullvad.mullvadbrowser", "one.ablaze.floorp",
        "com.kagi.kagimacOS",                                       // Orion (WebKit)
    ]

    /// Which attribute (if any) enables web content AX for this app.
    public static func mode(bundleId: String?, bundleURL: URL?) -> WebAXMode? {
        if let b = bundleId, enhancedIds.contains(b) { return .enhanced }
        if isChromiumFamily(bundleId: bundleId, bundleURL: bundleURL) { return .manual }
        return nil
    }

    /// Set the mode's attribute on the app element. Returns the AX result.
    @discardableResult
    public static func enable(_ mode: WebAXMode, app: Element) -> Bool {
        switch mode {
        case .manual: return app.setAttr(manualAttribute, true)
        case .enhanced: return app.setAttr(enhancedAttribute, true)
        }
    }

    /// Breadth-first search for the first AXWebArea under `root`
    /// (bounded by node count and deadline).
    public static func findWebArea(in root: Element, deadline: Date,
                                   maxNodes: Int = 400, maxDepth: Int = 16) -> Element? {
        var queue: [(Element, Int)] = [(root, 0)]
        var qi = 0
        while qi < queue.count && qi < maxNodes && Date() < deadline {
            let (el, depth) = queue[qi]; qi += 1
            let a = el.copyAttrs()
            if a.role == "AXWebArea" { return el }
            if depth >= maxDepth { continue }
            // Leaves never contain a web area: skip their children.
            if let r = a.role, kLeafRoles.contains(r) { continue }
            for c in a.children { queue.append((c, depth + 1)) }
        }
        return nil
    }

    private static let kLeafRoles: Set<String> = [
        "AXButton", "AXStaticText", "AXImage", "AXTextField", "AXCheckBox",
        "AXRadioButton", "AXMenuButton", "AXPopUpButton", "AXSlider", "AXLink",
        "AXMenuBar", "AXMenuBarItem", "AXIncrementor", "AXDisclosureTriangle",
    ]

    public struct WaitResult {
        public var populated: Bool
        public var foundWebArea: Bool
        public var ms: Double
        public var polls: Int
    }

    /// Poll (every ~25 ms) until an AXWebArea under `root` has children,
    /// bounded by `timeout` (<= 300 ms by default).
    public static func waitForWebArea(root: Element,
                                      timeout: TimeInterval = populateTimeout) -> WaitResult {
        let t0 = Date()
        let end = t0.addingTimeInterval(timeout)
        var area: Element?
        var polls = 0
        while true {
            polls += 1
            if area == nil { area = findWebArea(in: root, deadline: end) }
            if let a = area {
                if !a.isAlive() { area = nil }
                else if !a.copyAttrs().children.isEmpty {
                    return WaitResult(populated: true, foundWebArea: true,
                                      ms: Date().timeIntervalSince(t0) * 1000, polls: polls)
                }
            }
            let left = end.timeIntervalSinceNow
            if left <= 0 { break }
            usleep(UInt32(min(0.025, left) * 1_000_000))
        }
        return WaitResult(populated: false, foundWebArea: area != nil,
                          ms: Date().timeIntervalSince(t0) * 1000, polls: polls)
    }
}
