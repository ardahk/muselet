// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "hands",
    platforms: [.macOS(.v26)],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser", exact: "1.8.2")
    ],
    targets: [
        .target(name: "HandsKit"),
        .executableTarget(
            name: "hands",
            dependencies: [
                "HandsKit",
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
            ]
        ),
        .testTarget(name: "HandsKitTests", dependencies: ["HandsKit"]),
    ],
    swiftLanguageModes: [.v5]
)
