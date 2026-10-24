import CoreGraphics
import Foundation

public struct KeyCombo: Equatable {
    public var flags: CGEventFlags
    public var keyCode: CGKeyCode
    public var keyName: String
}

public enum ComboError: Error, CustomStringConvertible {
    case empty, unknownKey(String), missingKey
    public var description: String {
        switch self {
        case .empty: return "empty combo"
        case .unknownKey(let k): return "unknown key: \(k)"
        case .missingKey: return "combo has no non-modifier key"
        }
    }
}

public enum Combo {
    static let keyCodes: [String: CGKeyCode] = [
        "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51,
        "esc": 53, "escape": 53, "forwarddelete": 117, "home": 115, "end": 119,
        "pageup": 116, "pagedown": 121, "left": 123, "right": 124, "down": 125, "up": 126,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
        "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
        "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
        "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
        "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28,
        "9": 25, "0": 29, "=": 24, "-": 27, "[": 33, "]": 30, "\\": 42,
        ";": 41, "'": 39, ",": 43, ".": 47, "/": 44, "`": 50,
    ]

    static let modifiers: [String: CGEventFlags] = [
        "cmd": .maskCommand, "command": .maskCommand, "⌘": .maskCommand,
        "shift": .maskShift, "⇧": .maskShift,
        "opt": .maskAlternate, "option": .maskAlternate, "alt": .maskAlternate, "⌥": .maskAlternate,
        "ctrl": .maskControl, "control": .maskControl, "⌃": .maskControl,
        "fn": .maskSecondaryFn,
    ]

    /// Parse "cmd+shift+n", "return", "esc" into flags + virtual key code.
    public static func parse(_ s: String) throws -> KeyCombo {
        let parts = s.lowercased().split(separator: "+").map { $0.trimmingCharacters(in: .whitespaces) }
        guard !parts.isEmpty else { throw ComboError.empty }
        var flags = CGEventFlags()
        var key: String? = nil
        for p in parts {
            if let f = modifiers[p] {
                flags.insert(f)
            } else if keyCodes[p] != nil {
                if key != nil { throw ComboError.unknownKey(p) }
                key = p
            } else if p.count == 1, let c = keyCodes[p] {
                if key != nil { throw ComboError.unknownKey(p) }
                key = p; _ = c
            } else {
                throw ComboError.unknownKey(p)
            }
        }
        guard let k = key, let code = keyCodes[k] else { throw ComboError.missingKey }
        return KeyCombo(flags: flags, keyCode: code, keyName: k)
    }

    /// Post key down + up, tagged as synthetic (see `SyntheticEvent`).
    public static func post(_ combo: KeyCombo) {
        let src = CGEventSource(stateID: .hidSystemState)
        if let down = CGEvent(keyboardEventSource: src, virtualKey: combo.keyCode, keyDown: true) {
            down.flags = combo.flags
            SyntheticEvent.post(down)
        }
        if let up = CGEvent(keyboardEventSource: src, virtualKey: combo.keyCode, keyDown: false) {
            up.flags = combo.flags
            SyntheticEvent.post(up)
        }
    }

    /// Canonical spelling for logs/results ("cmd+shift+n").
    public static func describe(_ c: KeyCombo) -> String {
        var parts: [String] = []
        if c.flags.contains(.maskControl) { parts.append("ctrl") }
        if c.flags.contains(.maskAlternate) { parts.append("opt") }
        if c.flags.contains(.maskShift) { parts.append("shift") }
        if c.flags.contains(.maskCommand) { parts.append("cmd") }
        if c.flags.contains(.maskSecondaryFn) { parts.append("fn") }
        parts.append(c.keyName)
        return parts.joined(separator: "+")
    }
}
