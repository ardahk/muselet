// Read or step the built-in display brightness via DisplayServices (private framework used by brightness utilities).
// Usage: brightness get | down | up | set <0..1>   (one step = 1/16, like the keyboard)
import Foundation
import CoreGraphics
let h = dlopen("/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices", RTLD_NOW)
typealias Get = @convention(c) (UInt32, UnsafeMutablePointer<Float>) -> Int32
typealias Set = @convention(c) (UInt32, Float) -> Int32
guard let h, let g = dlsym(h, "DisplayServicesGetBrightness"), let s = dlsym(h, "DisplayServicesSetBrightness") else { print("{\"error\": \"DisplayServices unavailable\"}"); exit(1) }
let get = unsafeBitCast(g, to: Get.self), set = unsafeBitCast(s, to: Set.self)
let d = CGMainDisplayID()
var b: Float = 0
guard get(d, &b) == 0 else { print("{\"error\": \"read failed\"}"); exit(1) }
let cmd = CommandLine.arguments.dropFirst().first ?? "get"
if cmd == "set", CommandLine.arguments.count == 3, let v = Float(CommandLine.arguments[2]) {
    _ = set(d, max(0.0625, min(1.0, v))); usleep(300000); _ = get(d, &b)
}
if cmd == "down" || cmd == "up" {
    let nb = max(0.0625, min(1.0, b + (cmd == "up" ? 0.0625 : -0.0625)))  // never fully black
    _ = set(d, nb); usleep(300000); _ = get(d, &b)
}
print("{\"brightness\": \(String(format: "%.4f", b))}")
