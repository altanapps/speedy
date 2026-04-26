// swift-tools-version: 5.9
import PackageDescription

// SPM `swift build` is used in this repo for compile-only smoke tests on
// CI; the runnable .app is generated via xcodegen from project.yml. Custom
// fonts (Inter / JetBrains Mono) live under macos/Resources/Fonts and are
// bundled by xcodegen into the .app. We don't bundle them via SPM because
// SPM resource paths can't ascend out of the target source tree.
let package = Package(
    name: "Speedy",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Speedy",
            path: "Sources/Speedy"
        ),
        .testTarget(
            name: "SpeedyTests",
            dependencies: ["Speedy"],
            path: "Tests/SpeedyTests"
        ),
    ]
)
