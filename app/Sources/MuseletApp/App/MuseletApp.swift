import AppKit
import SwiftUI

@main
struct MuseletApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @ObservedObject private var model = AppModel.shared

    var body: some Scene {
        MenuBarExtra {
            PanelView(model: model)
        } label: {
            Image(nsImage: MenuBarIcon.make(recording: model.isRecording))
                .accessibilityLabel("muselet")
        }
        .menuBarExtraStyle(.window)
    }
}
