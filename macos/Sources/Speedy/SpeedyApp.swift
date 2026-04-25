import SwiftUI

@main
struct SpeedyApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup("Speedy") {
            ContentView()
                .frame(minWidth: 360, minHeight: 220)
        }
        .windowResizability(.contentSize)
    }
}

struct ContentView: View {
    var body: some View {
        VStack(spacing: 12) {
            Text("Speedy")
                .font(.system(size: 28, weight: .semibold))
            Text("Trade where you read.")
                .foregroundStyle(.secondary)
        }
        .padding(32)
    }
}
