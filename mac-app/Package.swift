// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Tandem",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(name: "Tandem", path: "Sources/Tandem")
    ]
)
