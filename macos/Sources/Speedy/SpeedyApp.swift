import SwiftUI

@main
struct SpeedyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 320, minHeight: 200)
        }
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
