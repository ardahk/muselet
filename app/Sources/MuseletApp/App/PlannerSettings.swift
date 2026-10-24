import Foundation

/// "Use 35B planner fallback" setting: persisted in UserDefaults, offered
/// only on Macs with >= 48 GB, sent to the brain as a `config` frame.
enum PlannerSettings {
    static let key = "muselet.escalatePlanner"
    static let minMemoryGB: UInt64 = 48

    /// hw.memsize (bytes) via sysctlbyname.
    static var memoryBytes: UInt64 {
        var size: UInt64 = 0
        var len = MemoryLayout<UInt64>.size
        guard sysctlbyname("hw.memsize", &size, &len, nil, 0) == 0 else { return 0 }
        return size
    }

    static var memoryGB: Int { Int(memoryBytes / 1_073_741_824) }
    static var supported: Bool { memoryBytes >= minMemoryGB * 1_073_741_824 }

    /// Stored choice; always false on Macs that can't hold the 35B.
    static var escalate: Bool {
        get { supported && UserDefaults.standard.bool(forKey: key) }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static var frame: [String: Any] { ["t": "config", "escalate_planner": escalate] }
}

/// Brain reply to `config`: `{"t":"config_ack","escalate_planner":true,"loaded":true,"reason":"..."}`.
struct ConfigAck: Equatable {
    var ok: Bool
    var escalatePlanner: Bool?
    var reason: String?

    static func parse(_ text: String) -> ConfigAck? {
        guard let data = text.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              obj["t"] as? String == "config_ack" else { return nil }
        let enabled = obj["escalate_planner"] as? Bool ?? false
        let loaded = obj["loaded"] as? Bool ?? (obj["ok"] as? Bool ?? false)
        // Turning it off succeeds unless the brain gave a reason.
        let ok = enabled ? loaded : (obj["reason"] == nil || loaded)
        return ConfigAck(ok: ok,
                         escalatePlanner: obj["escalate_planner"] as? Bool,
                         reason: obj["reason"] as? String)
    }

    /// Settings row text: "Loaded", "Off", or the brain's reason.
    var summary: String {
        if ok && escalatePlanner == true { return "Loaded" }
        if ok && escalatePlanner == false { return "Off" }
        return (reason?.isEmpty == false ? reason! : "Not available")
    }
}
