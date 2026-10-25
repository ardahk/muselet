import AppKit
import HandsKit
import SwiftUI

/// Settings page (behind the gear): Permissions, Models, Memory, Voice, Timers, Debug.
struct SettingsView: View {
    @ObservedObject var model: AppModel
    private let actions = AppActions.shared
    @State private var showTimerSetup = false
    @State private var memoryQuery = ""
    @State private var confirmForgetAll = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                permissions
                if PlannerSettings.supported { models }
                memory
                voice
                timers
                debug
            }
            .padding(.bottom, 2)
        }
        .scrollIndicators(.automatic)
        .frame(height: 470)
    }

    // MARK: sections

    private var permissions: some View {
        Card(title: "Permissions") {
            VStack(spacing: 6) {
                ForEach(PermissionKind.allCases) { k in
                    PermissionRow(kind: k, state: model.permissions[k]) { actions.requestPermission(k) }
                }
                AutomationRow(statuses: model.automation) { actions.requestAutomation($0) }
            }
        }
    }

    private var models: some View {
        Card(title: "Models") {
            VStack(alignment: .leading, spacing: 6) {
                Toggle(isOn: Binding(get: { model.escalatePlanner },
                                     set: { actions.setEscalatePlanner($0) })) {
                    Text("Use 35B planner fallback (needs ≥ 48 GB RAM)").font(.system(size: 12.5))
                }
                .toggleStyle(.switch)
                .controlSize(.small)
                HStack(spacing: 6) {
                    Image(systemName: ackSymbol).foregroundStyle(ackColor).font(.system(size: 11))
                    Text(ackText).font(.system(size: 11)).foregroundStyle(.secondary).lineLimit(2)
                    Spacer()
                    Text("\(PlannerSettings.memoryGB) GB").font(.system(size: 10.5)).foregroundStyle(.tertiary)
                        .monospacedDigit()
                }
            }
        }
    }

    private var memory: some View {
        Card(title: "Memory") {
            VStack(alignment: .leading, spacing: 7) {
                Toggle(isOn: Binding(
                    get: { model.longtermMemoryEnabled },
                    set: { actions.setLongtermMemory($0) })) {
                        Text("Remember things").font(.system(size: 12.5))
                    }
                    .toggleStyle(.switch)
                    .controlSize(.small)
                HStack(spacing: 6) {
                    TextField("Search memory", text: $memoryQuery)
                        .textFieldStyle(.roundedBorder)
                        .onSubmit { searchMemory() }
                    Button("Search") { searchMemory() }.controlSize(.small)
                    Button("List") { actions.listMemory() }.controlSize(.small)
                }
                if model.memoryItems.isEmpty {
                    Text("No saved memories.")
                        .font(.system(size: 11)).foregroundStyle(.secondary)
                } else {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 5) {
                            ForEach(model.memoryItems) { item in
                                HStack(alignment: .top, spacing: 7) {
                                    Text("\(item.type) · \(item.key) = \(item.value)")
                                        .font(.system(size: 11))
                                        .textSelection(.enabled)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Button {
                                        actions.deleteMemory(item.id)
                                    } label: {
                                        Image(systemName: "trash")
                                    }
                                    .buttonStyle(.plain)
                                    .help("Forget this memory")
                                }
                            }
                        }
                    }
                    .frame(maxHeight: 100)
                }
                Button("Forget everything", role: .destructive) {
                    confirmForgetAll = true
                }
                .controlSize(.small)
                .confirmationDialog("Forget everything?", isPresented: $confirmForgetAll,
                                    titleVisibility: .visible) {
                    Button("Forget everything", role: .destructive) {
                        actions.clearMemory()
                    }
                    Button("Cancel", role: .cancel) {}
                }
                .onAppear { actions.listMemory() }
            }
        }
    }

    private func searchMemory() {
        let query = memoryQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        if query.isEmpty { actions.listMemory() }
        else { actions.searchMemory(query) }
    }

    private var ackText: String {
        if let a = model.configAck { return "Brain: \(a.summary)" }
        return model.brainStatus == .connected ? "Brain: waiting for reply…" : "Sent when the brain connects"
    }

    private var ackSymbol: String {
        guard let a = model.configAck else { return "clock" }
        return a.ok ? "checkmark.circle.fill" : "exclamationmark.circle.fill"
    }

    private var ackColor: Color {
        guard let a = model.configAck else { return .secondary }
        return a.ok ? .green : .orange
    }

    private var voice: some View {
        Card(title: "Voice") {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "cpu").foregroundStyle(.secondary).frame(width: 18)
                    Text(model.sttEngine).font(.system(size: 12)).lineLimit(1)
                    Spacer()
                    sttBadge
                }
                HStack(spacing: 8) {
                    Image(systemName: "keyboard").foregroundStyle(.secondary).frame(width: 18)
                    Text(model.pushToTalkActive ? "Right ⌥ hotkey active" : "Hotkey needs Input Monitoring")
                        .font(.system(size: 12))
                        .foregroundStyle(model.pushToTalkActive ? Color.primary : Color.orange)
                    Spacer()
                }
                if case .downloading(let f, let phase) = model.sttState {
                    VStack(alignment: .leading, spacing: 3) {
                        ProgressView(value: f).progressViewStyle(.linear).tint(Brand.tintColor)
                        Text("\(phase) · \(Int(f * 100))%").font(.system(size: 10.5))
                            .foregroundStyle(.secondary).monospacedDigit()
                    }
                } else if case .loading(let phase) = model.sttState {
                    HStack(spacing: 6) {
                        ProgressView().controlSize(.mini)
                        Text(phase).font(.system(size: 10.5)).foregroundStyle(.secondary)
                    }
                } else if case .failed(let e) = model.sttState {
                    Text(e).font(.system(size: 10.5)).foregroundStyle(.red).lineLimit(2)
                }
                if let ms = model.lastSTTms {
                    HStack(spacing: 8) {
                        Image(systemName: "stopwatch").foregroundStyle(.secondary).frame(width: 18)
                        Text("Last release → text").font(.system(size: 12)).foregroundStyle(.secondary)
                        Spacer()
                        Text("\(Int(ms.rounded())) ms").font(.system(size: 12, weight: .medium)).monospacedDigit()
                    }
                }
            }
        }
    }

    @ViewBuilder private var sttBadge: some View {
        switch model.sttState {
        case .ready: Badge(text: "ready", color: .green)
        case .failed: Badge(text: "failed", color: .red)
        case .downloading: Badge(text: "downloading", color: .orange)
        case .loading: Badge(text: "loading", color: .orange)
        case .idle: Badge(text: "idle", color: .secondary)
        }
    }

    private var timers: some View {
        Card(title: "Timers") {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "timer").foregroundStyle(.secondary).frame(width: 18)
                    Text(timerStatusText).font(.system(size: 12)).lineLimit(1)
                    Spacer()
                    timerBadge
                    Button(showTimerSetup ? "Done" : "Set up") {
                        showTimerSetup.toggle()
                        if showTimerSetup { actions.refreshTimerBackend(true) }
                    }
                    .controlSize(.small)
                }
                Toggle(isOn: Binding(get: { model.useClockTimers },
                                     set: { actions.setUseClockTimers($0) })) {
                    Text("Use the Clock app for timers").font(.system(size: 12.5))
                }
                .toggleStyle(.switch)
                .controlSize(.small)
                if showTimerSetup { timerSetup }
            }
        }
    }

    private var timerSetup: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(Array(TimerSettings.setupSteps.enumerated()), id: \.offset) { i, step in
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text("\(i + 1).").font(.system(size: 11)).foregroundStyle(.secondary).monospacedDigit()
                    Text(step).font(.system(size: 11)).fixedSize(horizontal: false, vertical: true)
                }
            }
            HStack(spacing: 8) {
                Button("Open Shortcuts") { actions.openShortcuts() }.controlSize(.small)
                Button("Check again") { actions.refreshTimerBackend(true) }.controlSize(.small)
            }
            .padding(.top, 2)
        }
    }

    private var timerStatusText: String {
        guard let s = model.clockTimers else { return "Checking Shortcuts…" }
        if !s.ready { return "Muselet timers (shortcut missing)" }
        return model.useClockTimers ? "Timers go to the Clock app" : "Muselet timers"
    }

    @ViewBuilder private var timerBadge: some View {
        switch model.clockTimers?.ready {
        case true?: Badge(text: "Clock ready", color: .green)
        case false?: Badge(text: "Shortcut missing", color: .orange)
        case nil: Badge(text: "checking", color: .secondary)
        }
    }

    private var debug: some View {
        Card(title: "Debug", accessory: {
            if !model.activity.isEmpty {
                Button("Clear") { model.activity.removeAll() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
        }) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Text(model.brainStatus.title).font(.system(size: 11, weight: .medium))
                    Text(model.brainStatus.detail).font(.system(size: 11)).foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                if model.activity.isEmpty {
                    Text("No activity yet.")
                        .font(.system(size: 11.5))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 50)
                } else {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 5) {
                            ForEach(model.activity) { e in ActivityRow(entry: e) }
                        }
                        .padding(.vertical, 2)
                    }
                    .frame(height: 160)
                }
                HStack(spacing: 6) {
                    Button { actions.reconnect() } label: { Label("Reconnect", systemImage: "arrow.clockwise") }
                    Button { actions.resetMascot() } label: { Label("Reset mascot", systemImage: "figure.wave") }
                    Spacer()
                    Button { NSApp.terminate(nil) } label: { Label("Quit", systemImage: "power") }
                        .keyboardShortcut("q")
                }
                .buttonStyle(.glass)
                .controlSize(.small)
                .labelStyle(.titleAndIcon)
            }
        }
    }
}
