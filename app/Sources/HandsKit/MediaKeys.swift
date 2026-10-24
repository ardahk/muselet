import AppKit
import CoreGraphics
import Foundation

/// Media keys for the `act` `keys` op (`keys volume_up`, `keys brightness_down`, ...),
/// posted like the hardware keys: a system-defined event (NX_SYSDEFINED,
/// subtype 8 = NX_SUBTYPE_AUX_CONTROL_BUTTONS) with
/// `data1 = (NX_KEYTYPE << 16) | (state << 8)`, state 0xA = down, 0xB = up;
/// a down then an up. Every event is tagged as Muselet input
/// (`SyntheticEvent`), so push-to-talk ignores it. Media keys are global:
/// they don't need (or move) the keyboard focus.
public struct MediaKey: Equatable {
    /// Canonical combo name (`volume_up`, ...).
    public let name: String
    /// NX_KEYTYPE_* code (IOKit/hidsystem/ev_keymap.h).
    public let code: Int32

    /// What a key changes (for the read-back in the act result).
    public enum Kind: Equatable { case volume, brightness, playback }

    /// Combo name -> NX_KEYTYPE: SOUND_UP 0, SOUND_DOWN 1, BRIGHTNESS_UP 2,
    /// BRIGHTNESS_DOWN 3, MUTE 7, PLAY 16, NEXT 17, PREVIOUS 18.
    public static let codes: [String: Int32] = [
        "volume_up": 0, "volume_down": 1, "brightness_up": 2, "brightness_down": 3,
        "mute": 7, "play_pause": 16, "next_track": 17, "previous_track": 18,
    ]

    public var kind: Kind {
        switch code {
        case 0, 1, 7: return .volume
        case 2, 3: return .brightness
        default: return .playback
        }
    }

    /// `combo` as a media key, or nil (an ordinary key combo). Case-insensitive;
    /// `-` or a space may stand for `_` (`volume-up`).
    public static func parse(_ combo: String) -> MediaKey? {
        let n = combo.trimmingCharacters(in: .whitespaces).lowercased()
            .replacingOccurrences(of: "-", with: "_")
            .replacingOccurrences(of: " ", with: "_")
        guard let c = codes[n] else { return nil }
        return MediaKey(name: n, code: c)
    }

    /// `media_control` actions -> keys.
    public static func forMediaAction(_ action: String) -> MediaKey? {
        switch action.lowercased() {
        case "play", "pause", "toggle", "play_pause": return parse("play_pause")
        case "next", "next_track": return parse("next_track")
        case "previous", "prev", "previous_track": return parse("previous_track")
        default: return nil
        }
    }

    /// `data1` of the system-defined event: key << 16 | state << 8.
    public static func data1(code: Int32, down: Bool) -> Int {
        (Int(code) << 16) | ((down ? 0xA : 0xB) << 8)
    }

    /// The tagged CGEvent for one half of a press (not posted).
    public static func event(code: Int32, down: Bool) -> CGEvent? {
        let flags = NSEvent.ModifierFlags(rawValue: UInt(down ? 0xA00 : 0xB00))
        guard let e = NSEvent.otherEvent(
            with: .systemDefined, location: .zero, modifierFlags: flags,
            timestamp: 0, windowNumber: 0, context: nil,
            subtype: 8, data1: data1(code: code, down: down), data2: -1)?.cgEvent else { return nil }
        SyntheticEvent.tag(e)
        return e
    }

    /// Down, then up, at the HID tap (tagged).
    public static func post(code: Int32) {
        for down in [true, false] {
            if let e = event(code: code, down: down) { SyntheticEvent.post(e) }
        }
    }

    public func post() { Self.post(code: code) }
}
