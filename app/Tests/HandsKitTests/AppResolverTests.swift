import Foundation
import XCTest
@testable import HandsKit

final class AppResolverTests: XCTestCase {
    private var roots: [URL] = []

    override func tearDown() {
        for r in roots { try? FileManager.default.removeItem(at: r) }
        roots = []
        super.tearDown()
    }

    private func tree(_ name: String) throws -> URL {
        let repoRuns = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("runs")
        let root = repoRuns.appendingPathComponent(
            "appresolver-\(name)-\(UUID().uuidString)")
        try FileManager.default.createDirectory(
            at: root, withIntermediateDirectories: true)
        roots.append(root)
        return root
    }

    private func app(_ name: String, in dir: URL) throws -> URL {
        let url = dir.appendingPathComponent(name)
        try FileManager.default.createDirectory(
            at: url.appendingPathComponent("Contents/MacOS"),
            withIntermediateDirectories: true)
        return url
    }

    func testNestedVendorBundleResolves() throws {
        let root = try tree("nested")
        let bundle = try app("Adobe Premiere Pro 2026.app",
                             in: root.appendingPathComponent(
                                "Adobe Premiere Pro 2026"))
        let url = AppResolver.url(forAppNamed: "Adobe Premiere Pro 2026",
                                  directories: [root])
        XCTAssertEqual(url?.path, bundle.path)
    }

    func testUtilitiesSubdirectoryResolves() throws {
        let root = try tree("utilities")
        let bundle = try app("SomeTool.app",
                             in: root.appendingPathComponent("Utilities"))
        let url = AppResolver.url(forAppNamed: "SomeTool",
                                  directories: [root])
        XCTAssertEqual(url?.path, bundle.path)
    }

    func testInjectedHomeApplicationsRootResolves() throws {
        let system = try tree("system")
        let home = try tree("home")
        _ = try app("Present.app", in: system)
        let homeBundle = try app("HomeOnly.app", in: home)
        XCTAssertEqual(
            AppResolver.url(forAppNamed: "HomeOnly",
                            directories: [system, home])?.path,
            homeBundle.path)
    }

    func testAppPackageContentsAreNotEnumerated() throws {
        let root = try tree("pkg")
        let outer = try app("Outer.app", in: root)
        _ = try app("InnerHelper.app",
                    in: outer.appendingPathComponent("Contents/MacOS"))
        let names = AppResolver.installedAppURLs(in: [root])
            .map { $0.deletingPathExtension().lastPathComponent }
        XCTAssertEqual(names, ["Outer"])
        XCTAssertNil(AppResolver.url(forAppNamed: "InnerHelper",
                                     directories: [root]))
    }

    func testHiddenAppsAreExcluded() throws {
        let root = try tree("hidden")
        _ = try app(".Secret.app", in: root)
        _ = try app("InsideHidden.app",
                    in: root.appendingPathComponent(".hiddendir"))
        _ = try app("Visible.app", in: root)
        let names = AppResolver.installedAppURLs(in: [root])
            .map { $0.deletingPathExtension().lastPathComponent }
        XCTAssertEqual(names, ["Visible"])
    }

    func testRootAppSymlinkIsIncluded() throws {
        let root = try tree("links")
        let real = try app("RealBrowser.app",
                           in: root.appendingPathComponent("Vendor"))
        let link = root.appendingPathComponent("LinkedBrowser.app")
        try FileManager.default.createSymbolicLink(
            at: link, withDestinationURL: real)
        let names = AppResolver.installedAppURLs(in: [root])
            .map(\.lastPathComponent)
        XCTAssertTrue(names.contains("LinkedBrowser.app"), "\(names)")
        XCTAssertEqual(AppResolver.url(forAppNamed: "LinkedBrowser",
                                       directories: [root])?.path,
                       link.path)
    }

    func testExactRootAppWinsOverSubstring() throws {
        let root = try tree("exact")
        _ = try app("DeepZenHelper.app",
                    in: root.appendingPathComponent("Sub"))
        let exact = try app("Zen.app", in: root)
        XCTAssertEqual(AppResolver.url(forAppNamed: "zen",
                                       directories: [root])?.path,
                       exact.path)
    }

    func testSubstringFallsBackWhenNoExact() throws {
        let root = try tree("substr")
        let helper = try app("DeepZenHelper.app",
                             in: root.appendingPathComponent("Sub"))
        _ = try app("Apples.app", in: root)
        XCTAssertEqual(AppResolver.url(forAppNamed: "zen",
                                       directories: [root])?.path,
                       helper.path)
    }

    func testEmptyNameDoesNotResolve() throws {
        let root = try tree("empty")
        _ = try app("Zen.app", in: root)
        XCTAssertNil(AppResolver.url(forAppNamed: "", directories: [root]))
        XCTAssertNil(AppResolver.url(forAppNamed: "   ",
                                     directories: [root]))
        XCTAssertNil(AppResolver.url(forAppNamed: ".app",
                                     directories: [root]))
    }

    func testInstalledAppURLsSortWithinRootAndPreserveRootOrder() throws {
        let first = try tree("first")
        let second = try tree("second")
        _ = try app("Zed.app", in: first)
        _ = try app("Alpha.app", in: first)
        _ = try app("Mid.app", in: second)
        let urls = AppResolver.installedAppURLs(in: [first, second])
        XCTAssertEqual(urls.map { $0.deletingPathExtension().lastPathComponent },
                       ["Alpha", "Zed", "Mid"])
    }

    func testInstalledAppNamesSortedAndDeduplicated() throws {
        let first = try tree("n1")
        let second = try tree("n2")
        _ = try app("Notes.app", in: first)
        _ = try app("Zed.app", in: second)
        _ = try app("Notes.app", in: second)
        XCTAssertEqual(installedAppNames(in: [first, second]),
                       ["Notes", "Zed"])
    }

    func testTrimsWhitespaceAndAppSuffix() throws {
        let root = try tree("trim")
        let bundle = try app("Zen.app", in: root)
        XCTAssertEqual(AppResolver.url(forAppNamed: "  Zen.app  ",
                                       directories: [root])?.path,
                       bundle.path)
    }
}
