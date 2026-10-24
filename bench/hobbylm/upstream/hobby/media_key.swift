// Sends one hardware-style media key press (the same system-defined event the physical F-row key sends).
// Usage: media_key brightness_down|brightness_up|volume_down|volume_up|mute
import AppKit
let codes: [String: Int32] = ["volume_up": 0, "volume_down": 1, "brightness_up": 2, "brightness_down": 3, "mute": 7]
guard CommandLine.arguments.count == 2, let key = codes[CommandLine.arguments[1]] else { print("usage: media_key <key>"); exit(2) }
func post(down: Bool) {
    let flags = NSEvent.ModifierFlags(rawValue: down ? 0xa00 : 0xb00)
    let data1 = Int((key << 16) | ((down ? 0xa : 0xb) << 8))
    let ev = NSEvent.otherEvent(with: .systemDefined, location: .zero, modifierFlags: flags, timestamp: 0,
                                windowNumber: 0, context: nil, subtype: 8, data1: data1, data2: -1)
    ev?.cgEvent?.post(tap: .cghidEventTap)
}
post(down: true); usleep(20000); post(down: false)
print("sent \(CommandLine.arguments[1])")
