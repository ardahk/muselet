import AppKit
import HandsKit
import SwiftUI

/// Actions the panel can trigger; wired up by the AppDelegate.
final class AppActions {
    static let shared = AppActions()
    var requestPermission: (PermissionKind) -> Void = { _ in }
    /// Ask Automation consent for one target app (or open Settings if denied).
    var requestAutomation: (Automation.Target) -> Void = { _ in }
    var reconnect: () -> Void = {}
    var resetMascot: () -> Void = {}
    var panelVisible: (Bool) -> Void = { _ in }
    var testGhost: () -> Void = {}
}

struct PanelView: View {
    @ObservedObject var model: AppModel
    private let actions = AppActions.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            header
            voiceCard
            permissionsCard
            activityCard
            footer
        }
        .padding(14)
        .frame(width: 360)
        .onAppear { actions.panelVisible(true) }
        .onDisappear { actions.panelVisible(false) }
    }

    // MARK: header

    private var header: some View {
        HStack(spacing: 10) {
            Image(nsImage: MenuBarIcon.make(recording: model.isRecording))
                .renderingMode(.template)
                .resizable()
                .frame(width: 26, height: 26)
                .foregroundStyle(Brand.tintColor)
                .padding(6)
                .background(Brand.tintColor.opacity(0.14), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 1) {
                Text("muselet").font(.system(size: 15, weight: .semibold))
                Text("on-device voice agent").font(.system(size: 11)).foregroundStyle(.secondary)
            }
            Spacer()
            StatusPill(status: model.brainStatus)
        }
    }

    // MARK: voice

    private var voiceCard: some View {
        Card(title: "Voice") {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: model.isRecording ? "waveform" : "mic.fill")
                        .symbolEffect(.variableColor.iterative, isActive: model.isRecording)
                        .foregroundStyle(model.isRecording ? Brand.tintColor : .secondary)
                        .frame(width: 18)
                    if model.pushToTalkActive {
                        Text("Hold \(Text("right ⌥").fontWeight(.semibold)) to talk · \(Text("esc").fontWeight(.semibold)) cancels")
                            .font(.system(size: 12.5))
                    } else {
                        Text("Hotkey needs Input Monitoring").font(.system(size: 12.5))
                            .foregroundStyle(.orange)
                    }
                    Spacer()
                }
                HStack(spacing: 8) {
                    Image(systemName: "cpu").foregroundStyle(.secondary).frame(width: 18)
                    Text(model.sttEngine).font(.system(size: 11.5)).foregroundStyle(.secondary)
                        .lineLimit(1)
                    Spacer()
                    sttBadge
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
                }
                if let ms = model.lastSTTms {
                    HStack(spacing: 8) {
                        Image(systemName: "stopwatch").foregroundStyle(.secondary).frame(width: 18)
                        Text("Last release → text").font(.system(size: 11.5)).foregroundStyle(.secondary)
                        Spacer()
                        Text("\(Int(ms.rounded())) ms").font(.system(size: 11.5, weight: .medium)).monospacedDigit()
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

    // MARK: permissions

    private var permissionsCard: some View {
        Card(title: "Permissions") {
            VStack(spacing: 6) {
                ForEach(PermissionKind.allCases) { k in
                    PermissionRow(kind: k, state: model.permissions[k]) { actions.requestPermission(k) }
                }
                AutomationRow(statuses: model.automation) { actions.requestAutomation($0) }
            }
        }
    }

    // MARK: activity

    private var activityCard: some View {
        Card(title: "Activity", accessory: {
            if !model.activity.isEmpty {
                Button("Clear") { model.activity.removeAll() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
        }) {
            if model.activity.isEmpty {
                Text("Nothing yet. Hold right ⌥ and say “set volume to 30”.")
                    .font(.system(size: 11.5))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 60, alignment: .center)
                    .multilineTextAlignment(.center)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 5) {
                        ForEach(model.activity) { e in ActivityRow(entry: e) }
                    }
                    .padding(.vertical, 2)
                }
                .frame(height: 190)
                .scrollIndicators(.automatic)
            }
        }
    }

    // MARK: footer

    private var footer: some View {
        HStack(spacing: 6) {
            Button { actions.reconnect() } label: {
                Label("Reconnect", systemImage: "arrow.clockwise")
            }
            Button { actions.resetMascot() } label: {
                Label("Reset mascot", systemImage: "figure.wave")
            }
            Spacer()
            Button { NSApp.terminate(nil) } label: {
                Label("Quit", systemImage: "power")
            }
            .keyboardShortcut("q")
        }
        .buttonStyle(.glass)
        .controlSize(.small)
        .labelStyle(.titleAndIcon)
    }
}

// MARK: - components

private struct Card<Content: View, Accessory: View>: View {
    let title: String
    @ViewBuilder var accessory: () -> Accessory
    @ViewBuilder var content: () -> Content

    init(title: String, @ViewBuilder accessory: @escaping () -> Accessory = { EmptyView() },
         @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.accessory = accessory
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title.uppercased())
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .tracking(0.6)
                Spacer()
                accessory()
            }
            content()
        }
        .padding(11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.045), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous)
            .strokeBorder(Color.primary.opacity(0.06), lineWidth: 0.5))
    }
}

private struct StatusPill: View {
    let status: BrainStatus

    var color: Color {
        switch status {
        case .connected: return .green
        case .connecting: return .yellow
        case .busy: return .orange
        case .offline: return .red
        }
    }

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 7, height: 7)
                .shadow(color: color.opacity(0.7), radius: 3)
            VStack(alignment: .trailing, spacing: 0) {
                Text(status.title).font(.system(size: 11.5, weight: .medium))
                Text(status.detail).font(.system(size: 9.5)).foregroundStyle(.secondary).lineLimit(1)
                    .frame(maxWidth: 150, alignment: .trailing)
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .glassEffect(.regular, in: Capsule())
        .help(status.detail)
    }
}

private struct Badge: View {
    let text: String
    let color: Color
    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.14), in: Capsule())
    }
}

private struct PermissionRow: View {
    let kind: PermissionKind
    let state: PermissionState
    let action: () -> Void

    var body: some View {
        HStack(spacing: 9) {
            Image(systemName: kind.symbol)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(state == .granted ? Brand.tintColor : .secondary)
                .frame(width: 20)
            VStack(alignment: .leading, spacing: 0) {
                Text(kind.title).font(.system(size: 12.5, weight: .medium))
                Text(kind.purpose).font(.system(size: 10.5)).foregroundStyle(.secondary)
            }
            Spacer()
            if state == .granted {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 15))
                    .foregroundStyle(.green)
                    .help("Granted")
            } else {
                Button(state == .notDetermined ? "Allow" : "Grant…", action: action)
                    .buttonStyle(.glassProminent)
                    .tint(Brand.tintColor)
                    .controlSize(.small)
            }
        }
    }
}

/// Automation (Apple Events) consent for the apps skills script. Status is
/// read without prompting; "Grant" asks once (the target is launched hidden
/// if it isn't running). A target that isn't running reads as unknown.
private struct AutomationRow: View {
    let statuses: [String: Automation.Status]
    let request: (Automation.Target) -> Void

    private var installed: [Automation.Target] {
        Automation.targets.filter { statuses[$0.bundleId] != .notInstalled }
    }
    private var granted: Int { installed.filter { statuses[$0.bundleId] == .granted }.count }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 9) {
                Image(systemName: "applescript")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(granted == installed.count && granted > 0 ? Brand.tintColor : .secondary)
                    .frame(width: 20)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Automation").font(.system(size: 12.5, weight: .medium))
                    Text("let skills script these apps").font(.system(size: 10.5)).foregroundStyle(.secondary)
                }
                Spacer()
                if granted == installed.count && granted > 0 {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 15))
                        .foregroundStyle(.green)
                        .help("Granted")
                } else {
                    Text("\(granted)/\(installed.count)")
                        .font(.system(size: 11, weight: .medium))
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                }
            }
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 6), GridItem(.flexible(), spacing: 6)],
                      alignment: .leading, spacing: 4) {
                ForEach(Automation.targets) { t in
                    AutomationChip(target: t, status: statuses[t.bundleId]) { request(t) }
                }
            }
            .padding(.leading, 29)
        }
    }
}

private struct AutomationChip: View {
    let target: Automation.Target
    let status: Automation.Status?
    let action: () -> Void

    private var hint: String {
        switch status {
        case .granted: return "\(target.name): allowed"
        case .denied: return "\(target.name): denied — change it in System Settings › Privacy & Security › Automation"
        case .notDetermined: return "\(target.name): not asked yet"
        case .notRunning: return "\(target.name): unknown until it runs; Grant launches it hidden and asks"
        case .notInstalled: return "\(target.name) is not installed"
        case .unknown(let s): return "\(target.name): status \(s)"
        case nil: return "\(target.name): checking…"
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            Text(target.name).font(.system(size: 11)).lineLimit(1)
            Spacer(minLength: 2)
            switch status {
            case .granted:
                Image(systemName: "checkmark.circle.fill").font(.system(size: 11)).foregroundStyle(.green)
            case .notInstalled:
                Text("n/a").font(.system(size: 9.5)).foregroundStyle(.tertiary)
            case nil:
                ProgressView().controlSize(.mini)
            default:
                Button(status == .denied ? "Settings…" : "Grant", action: action)
                    .buttonStyle(.glassProminent)
                    .tint(status == .denied ? .orange : Brand.tintColor)
                    .controlSize(.mini)
            }
        }
        .padding(.horizontal, 7)
        .padding(.vertical, 3)
        .background(Color.primary.opacity(0.04), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
        .help(hint)
    }
}

private struct ActivityRow: View {
    let entry: ActivityEntry
    private static let time: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f
    }()

    var tint: Color {
        if entry.ok == false || entry.kind == .error { return .red }
        switch entry.kind {
        case .say: return Brand.tintColor
        case .utterance, .stt: return .blue
        case .rpc: return .purple
        case .confirm: return .orange
        default: return .secondary
        }
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 7) {
            Image(systemName: entry.kind.symbol)
                .font(.system(size: 10.5, weight: .semibold))
                .foregroundStyle(tint)
                .frame(width: 16)
            Text(entry.text)
                .font(.system(size: 11.5))
                .lineLimit(2)
                .truncationMode(.tail)
                .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: .trailing, spacing: 0) {
                if let ms = entry.ms {
                    Text(ms < 10 ? String(format: "%.1f ms", ms) : "\(Int(ms.rounded())) ms")
                        .font(.system(size: 10.5, weight: .medium))
                        .monospacedDigit()
                        .foregroundStyle(entry.ok == false ? .red : .primary)
                }
                Text(Self.time.string(from: entry.date))
                    .font(.system(size: 9.5))
                    .monospacedDigit()
                    .foregroundStyle(.tertiary)
            }
        }
    }
}
