import AppKit
import HandsKit
import SwiftUI

/// Actions the panel can trigger; wired up by the AppDelegate.
final class AppActions {
    static let shared = AppActions()
    var requestPermission: (PermissionKind) -> Void = { _ in }
    /// Ask Automation consent for one target app (or open Settings if denied).
    var requestAutomation: (Automation.Target) -> Void = { _ in }
    var panelVisible: (Bool) -> Void = { _ in }
    var setEscalatePlanner: (Bool) -> Void = { _ in }
    var setLongtermMemory: (Bool) -> Void = { _ in }
    var listMemory: () -> Void = {}
    var searchMemory: (String) -> Void = { _ in }
    var deleteMemory: (Int) -> Void = { _ in }
    var clearMemory: () -> Void = {}
    /// Settings › Timers.
    var setUseClockTimers: (Bool) -> Void = { _ in }
    /// Re-run `timer_backend` (`refresh`: re-list shortcuts now).
    var refreshTimerBackend: (Bool) -> Void = { _ in }
    var openShortcuts: () -> Void = {}
}

/// Menu-bar panel = Settings, in the System Settings style: grouped Form, system
/// materials, fonts and controls. Sections: missing permissions (hidden when all are
/// granted), Models (>= 48 GB Macs), Memory, Quit. A warning row only when the brain is down.
struct PanelView: View {
    @ObservedObject var model: AppModel
    @State private var memoryQuery = ""
    @State private var confirmForgetAll = false
    @State private var contentHeight: CGFloat = 360
    private let actions = AppActions.shared
    static let width: CGFloat = 340
    static let maxHeight: CGFloat = 560

    var body: some View {
        Form {
            if let warning = Self.brainWarning(model.brainStatus) {
                Label(warning, systemImage: "exclamationmark.triangle.fill")
                    .symbolRenderingMode(.multicolor)
                    .foregroundStyle(.secondary)
            }
            let missing = Self.missingPermissions(model.permissions)
            let automation = Self.missingAutomation(model.automation)
            if !missing.isEmpty || !automation.isEmpty {
                Section("Permissions") {
                    ForEach(missing) { k in
                        PermissionRow(title: k.title, detail: k.purpose, symbol: k.symbol) {
                            actions.requestPermission(k)
                        }
                    }
                    ForEach(automation) { t in
                        PermissionRow(title: "Automation: \(t.name)", detail: "let skills script \(t.name)",
                                      symbol: "applescript") { actions.requestAutomation(t) }
                    }
                }
            }
            if PlannerSettings.supported { models }
            memory
            Section {
                Button("Quit Muselet") { NSApp.terminate(nil) }
                    .keyboardShortcut("q")
            }
        }
        .formStyle(.grouped)
        .onScrollGeometryChange(for: CGFloat.self) { $0.contentSize.height } action: { _, h in
            if h > 1 { contentHeight = h }
        }
        .frame(width: Self.width, height: min(contentHeight, Self.maxHeight))
        .onAppear {
            actions.panelVisible(true)
            actions.listMemory()
        }
        .onDisappear { actions.panelVisible(false) }
    }

    // MARK: sections

    private var models: some View {
        Section {
            Toggle("35B planner fallback", isOn: Binding(get: { model.escalatePlanner },
                                                         set: { actions.setEscalatePlanner($0) }))
        } header: {
            Text("Models")
        } footer: {
            Text(ackText).foregroundStyle(.secondary)
        }
    }

    private var memory: some View {
        Section("Memory") {
            Toggle("Remember things", isOn: Binding(get: { model.longtermMemoryEnabled },
                                                    set: { actions.setLongtermMemory($0) }))
            TextField("Search", text: $memoryQuery, prompt: Text("Search memories"))
                .labelsHidden()
                .onSubmit { searchMemory() }
            if model.memoryItems.isEmpty {
                Text("No saved memories").foregroundStyle(.secondary)
            } else {
                ForEach(model.memoryItems) { item in
                    HStack(alignment: .firstTextBaseline) {
                        VStack(alignment: .leading, spacing: 1) {
                            Text(item.value).lineLimit(2).textSelection(.enabled)
                            Text("\(item.type) · \(item.key)").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button { actions.deleteMemory(item.id) } label: { Image(systemName: "trash") }
                            .buttonStyle(.borderless)
                            .help("Forget this memory")
                            .accessibilityLabel("Forget \(item.key)")
                    }
                }
                Button("Forget Everything…", role: .destructive) { confirmForgetAll = true }
                    .confirmationDialog("Forget everything Muselet remembers?", isPresented: $confirmForgetAll) {
                        Button("Forget Everything", role: .destructive) { actions.clearMemory() }
                        Button("Cancel", role: .cancel) {}
                    }
            }
        }
    }

    private func searchMemory() {
        let query = memoryQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        if query.isEmpty { actions.listMemory() } else { actions.searchMemory(query) }
    }

    private var ackText: String {
        if let a = model.configAck { return "\(a.summary) · \(PlannerSettings.memoryGB) GB memory" }
        return "Used when the 4B planner is unsure · \(PlannerSettings.memoryGB) GB memory"
    }

    // MARK: pure helpers (unit-testable)

    /// Only shown when something is wrong; nothing while connecting or connected.
    static func brainWarning(_ s: BrainStatus) -> String? {
        switch s {
        case .offline: return "Muselet's brain isn't running"
        case .busy: return "Another app is using Muselet's brain"
        case .connecting, .connected: return nil
        }
    }

    static func missingPermissions(_ p: PermissionSnapshot) -> [PermissionKind] {
        PermissionKind.allCases.filter { p[$0] != .granted }
    }

    /// Automation targets that still need consent (unknown / not running / not installed stay hidden).
    static func missingAutomation(_ s: [String: Automation.Status]) -> [Automation.Target] {
        Automation.targets.filter {
            switch s[$0.bundleId] {
            case .denied?, .notDetermined?: return true
            default: return false
            }
        }
    }
}

private struct PermissionRow: View {
    let title: String
    let detail: String
    let symbol: String
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label {
                VStack(alignment: .leading, spacing: 1) {
                    Text(title)
                    Text(detail).font(.caption).foregroundStyle(.secondary)
                }
            } icon: {
                Image(systemName: symbol).foregroundStyle(.secondary)
            }
            HStack {
                Spacer()
                Button("Open System Settings", action: action)
            }
        }
    }
}
