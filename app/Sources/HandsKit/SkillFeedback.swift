import Foundation

/// What the app's feedback HUD should show after a skill ran, derived from
/// the skill response `{ok, result:{...}}` (read-back values).
public enum SkillFeedback: Equatable {
    /// Level bar 0...100 (volume, brightness); `muted` only for volume.
    case level(kind: Kind, level: Int, muted: Bool)
    /// On/Off toggle (dark mode, Wi-Fi, Bluetooth).
    case toggle(kind: Kind, on: Bool)

    public enum Kind: String, Equatable {
        case volume, brightness, darkMode, wifi, bluetooth
    }

    public static func from(name: String, response: [String: Any]) -> SkillFeedback? {
        guard response["ok"] as? Bool == true,
              let r = response["result"] as? [String: Any] else { return nil }
        func int(_ k: String) -> Int? {
            if let i = r[k] as? Int { return i }
            if let n = r[k] as? NSNumber { return n.intValue }
            return nil
        }
        func bool(_ k: String) -> Bool? {
            if let b = r[k] as? Bool { return b }
            if let n = r[k] as? NSNumber { return n.boolValue }
            return nil
        }
        switch name {
        case "set_volume", "change_volume", "mute":
            let muted = bool("muted") ?? false
            guard let level = int("level") ?? (muted ? 0 : nil) else { return nil }
            return .level(kind: .volume, level: max(0, min(100, level)), muted: muted)
        case "set_brightness":
            guard let level = int("level") else { return nil }
            return .level(kind: .brightness, level: max(0, min(100, level)), muted: false)
        case "dark_mode":
            return bool("on").map { .toggle(kind: .darkMode, on: $0) }
        case "wifi":
            return bool("on").map { .toggle(kind: .wifi, on: $0) }
        case "bluetooth":
            return bool("on").map { .toggle(kind: .bluetooth, on: $0) }
        default:
            return nil
        }
    }
}
