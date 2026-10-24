import AppKit
import ApplicationServices
import AVFoundation
import CoreGraphics
import HandsKit

enum PermissionKind: String, CaseIterable, Identifiable {
    case accessibility, screenRecording, microphone, inputMonitoring
    var id: String { rawValue }

    var title: String {
        switch self {
        case .accessibility: return "Accessibility"
        case .screenRecording: return "Screen Recording"
        case .microphone: return "Microphone"
        case .inputMonitoring: return "Input Monitoring"
        }
    }

    var symbol: String {
        switch self {
        case .accessibility: return "accessibility"
        case .screenRecording: return "rectangle.dashed.badge.record"
        case .microphone: return "mic.fill"
        case .inputMonitoring: return "keyboard"
        }
    }

    var purpose: String {
        switch self {
        case .accessibility: return "read and act on app UI"
        case .screenRecording: return "screenshots when the AX tree is blind"
        case .microphone: return "push-to-talk voice input"
        case .inputMonitoring: return "right ⌥ hold-to-talk hotkey"
        }
    }

    var settingsURL: URL {
        let anchor: String
        switch self {
        case .accessibility: anchor = "Privacy_Accessibility"
        case .screenRecording: anchor = "Privacy_ScreenCapture"
        case .microphone: anchor = "Privacy_Microphone"
        case .inputMonitoring: anchor = "Privacy_ListenEvent"
        }
        return URL(string: "x-apple.systempreferences:com.apple.preference.security?\(anchor)")!
    }
}

enum PermissionState: Equatable {
    case granted, denied, notDetermined
}

struct PermissionSnapshot: Equatable {
    var accessibility: PermissionState = .notDetermined
    var screenRecording: PermissionState = .notDetermined
    var microphone: PermissionState = .notDetermined
    var inputMonitoring: PermissionState = .notDetermined

    subscript(_ k: PermissionKind) -> PermissionState {
        switch k {
        case .accessibility: return accessibility
        case .screenRecording: return screenRecording
        case .microphone: return microphone
        case .inputMonitoring: return inputMonitoring
        }
    }

    var allGranted: Bool { PermissionKind.allCases.allSatisfy { self[$0] == .granted } }
}

enum Permissions {
    static func snapshot() -> PermissionSnapshot {
        var s = PermissionSnapshot()
        s.accessibility = AXIsProcessTrusted() ? .granted : .denied
        s.screenRecording = CGPreflightScreenCaptureAccess() ? .granted : .denied
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: s.microphone = .granted
        case .notDetermined: s.microphone = .notDetermined
        default: s.microphone = .denied
        }
        s.inputMonitoring = CGPreflightListenEventAccess() ? .granted : .denied
        return s
    }

    /// Trigger the system prompt where one exists, then open the pane.
    static func request(_ k: PermissionKind, completion: @escaping () -> Void = {}) {
        switch k {
        case .accessibility:
            let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
            if !AXIsProcessTrustedWithOptions(opts) { NSWorkspace.shared.open(k.settingsURL) }
            completion()
        case .screenRecording:
            if !CGRequestScreenCaptureAccess() { NSWorkspace.shared.open(k.settingsURL) }
            completion()
        case .microphone:
            switch AVCaptureDevice.authorizationStatus(for: .audio) {
            case .notDetermined:
                AVCaptureDevice.requestAccess(for: .audio) { _ in
                    DispatchQueue.main.async { completion() }
                }
            case .authorized:
                completion()
            default:
                NSWorkspace.shared.open(k.settingsURL)
                completion()
            }
        case .inputMonitoring:
            if !CGRequestListenEventAccess() { NSWorkspace.shared.open(k.settingsURL) }
            completion()
        }
    }
}

/// Automation (Apple Events) consent per target app: bundle id -> status.
/// Optional (not part of `allGranted`): skills ask on first use otherwise,
/// and that first call blocks behind the system prompt.
enum AutomationPermissions {
    /// Read statuses (never prompts, never launches anything).
    static func snapshot() -> [String: Automation.Status] {
        var d: [String: Automation.Status] = [:]
        for (t, s) in Automation.statuses() { d[t.bundleId] = s }
        return d
    }

    /// Grant: denied -> open System Settings > Automation (the prompt never
    /// shows again); else ask (launches the target hidden if needed).
    static func request(_ t: Automation.Target, current: Automation.Status?,
                        completion: @escaping (Automation.Status?) -> Void) {
        if current == .denied {
            NSWorkspace.shared.open(Automation.settingsURL)
            completion(nil)
            return
        }
        Automation.request(t) { completion($0) }
    }
}

/// Polls permission state only while someone is looking (panel open or a
/// grant is in flight) — never an always-on timer.
final class PermissionWatcher {
    private var timer: Timer?
    private var deadline = Date.distantPast
    private var automationInFlight = false
    private let automationQueue = DispatchQueue(label: "ai.muselet.automation-status", qos: .utility)
    var onChange: ((PermissionSnapshot) -> Void)?

    func refreshNow() {
        let s = Permissions.snapshot()
        if AppModel.shared.permissions != s {
            AppModel.shared.permissions = s
            onChange?(s)
        }
        refreshAutomation()
    }

    /// Automation statuses off the main thread (AE/TCC queries), published
    /// on main when they change.
    func refreshAutomation() {
        guard !automationInFlight else { return }
        automationInFlight = true
        automationQueue.async { [weak self] in
            let snap = AutomationPermissions.snapshot()
            DispatchQueue.main.async {
                self?.automationInFlight = false
                if AppModel.shared.automation != snap { AppModel.shared.automation = snap }
            }
        }
    }

    /// Poll at 1 Hz for `seconds` (extends an active window).
    func watch(for seconds: TimeInterval) {
        refreshNow()
        deadline = max(deadline, Date().addingTimeInterval(seconds))
        guard timer == nil else { return }
        let t = Timer(timeInterval: 1.0, repeats: true) { [weak self] t in
            guard let self else { t.invalidate(); return }
            self.refreshNow()
            if Date() > self.deadline { t.invalidate(); self.timer = nil }
        }
        t.tolerance = 0.3
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func stop() {
        deadline = .distantPast
    }
}
