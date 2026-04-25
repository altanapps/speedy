// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Speedy",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Speedy",
            path: "Sources/Speedy"
        )
    ]
)
