import AppKit
import HandsKit
import SwiftUI

// MARK: - components

struct Card<Content: View, Accessory: View>: View {
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

/// Header status: a dot plus "Connected" / "Offline".
struct StatusDot: View {
    let status: BrainStatus

    private var color: Color {
        switch status {
        case .connected: return .green
        case .connecting: return .yellow
        case .busy: return .orange
        case .offline: return .secondary
        }
    }

    private var title: String {
        switch status {
        case .connected: return "Connected"
        case .connecting: return "Connecting…"
        case .busy: return "Busy"
        case .offline: return "Offline"
        }
    }

    var body: some View {
        HStack(spacing: 5) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(title).font(.system(size: 11, weight: .medium)).foregroundStyle(.secondary)
        }
        .help(status.detail)
        .accessibilityElement(children: .combine)
    }
}

struct Badge: View {
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

struct PermissionRow: View {
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
struct AutomationRow: View {
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

struct AutomationChip: View {
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

struct ActivityRow: View {
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
