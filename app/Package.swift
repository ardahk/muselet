// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "hands",
    platforms: [.macOS(.v26)],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser", exact: "1.8.2"),
        // MuseletApp STT (Parakeet TDT on the ANE). v0.17.7 = newest release >= 7 days old
        // (published 2026-10-08). traits: [] drops the NeMo text-normalization engine.
        .package(url: "https://github.com/FluidInference/FluidAudio.git", exact: "0.17.7", traits: []),
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
        // Menu-bar app: mascot, ghost cursor overlay, push-to-talk STT, brain client.
        // Bundle with app/scripts/build_app.sh (bundle id ai.muselet.app).
        .executableTarget(
            name: "MuseletApp",
            dependencies: [
                "HandsKit",
                .product(name: "FluidAudio", package: "FluidAudio"),
            ]
        ),
        .testTarget(name: "HandsKitTests", dependencies: ["HandsKit"]),
    ],
    swiftLanguageModes: [.v5]
)
