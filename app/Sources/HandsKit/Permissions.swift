import AppKit
import ApplicationServices
import CoreGraphics
import Darwin
import Foundation

public enum Permissions {
    /// The app a human must grant the permission to: nearest ancestor
    /// process with a bundle (Terminal, Devin, iTerm...), else ourselves.
    public static func hostAppName() -> String {
        var pid = getppid()
        var hops = 0
        while pid > 1 && hops < 8 {
            if let app = NSRunningApplication(processIdentifier: pid),
               app.bundleIdentifier != nil, let name = app.localizedName {
                return name
            }
            var kpid = pid_t(0)
            var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
            var info = kinfo_proc()
            var size = MemoryLayout<kinfo_proc>.size
            sysctl(&mib, u_int(mib.count), &info, &size, nil, 0)
            kpid = info.kp_eproc.e_ppid
            if kpid == pid { break }
            pid = kpid
            hops += 1
        }
        return ProcessInfo.processInfo.processName
    }

    /// Exit(3) with an exact grant message when a permission is missing.
    public static func requireAX() {
        if !AXIsProcessTrusted() {
            FileHandle.standardError.write("""
                Accessibility permission required.
                Grant it to the app running this process: \(hostAppName())
                (System Settings -> Privacy & Security -> Accessibility), then re-run.
                """.data(using: .utf8)!)
            exit(3)
        }
    }

    public static func requireScreen() {
        if !CGPreflightScreenCaptureAccess() {
            FileHandle.standardError.write("""
                Screen Recording permission required.
                Grant it to the app running this process: \(hostAppName())
                (System Settings -> Privacy & Security -> Screen Recording), then re-run.
                """.data(using: .utf8)!)
            exit(3)
        }
    }
}
