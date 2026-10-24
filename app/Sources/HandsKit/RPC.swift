import AppKit
import ApplicationServices
import Foundation

/// Dispatches brain -> app RPC methods per AGENTS.md.
public final class RPCHandler {
    public let hands = Hands()
    public let skills = Skills()
    public var ownBundleId: String? = Bundle.main.bundleIdentifier
    public weak var delegate: HandsDelegate? {
        didSet { hands.delegate = delegate }
    }

    public init() {}

    /// Returns (ok, result-dict-or-nil, error-string-or-nil).
    public func handle(method: String, params: [String: Any]) -> (Bool, Any?, String?) {
        do {
            switch method {
            case "observe":
                let obs = try hands.observe(
                    scope: params["scope"] as? String ?? "focused_window",
                    app: params["app"] as? String,
                    maxNodes: intParam(params, "max_nodes") ?? 150,
                    diff: params["diff"] as? Bool ?? true)
                var elements: [[String: Any]] = []
                for e in obs.elements {
                    var d: [String: Any] = [
                        "ref": e.ref, "role": e.role, "label": e.label,
                        "enabled": e.enabled,
                        "frame": [e.frame.minX, e.frame.minY,
                                  e.frame.width, e.frame.height],
                    ]
                    if let v = e.value as? String { d["value"] = v }
                    else if let n = e.value as? NSNumber { d["value"] = n }
                    if e.selected { d["selected"] = true }
                    if let c = e.checked { d["checked"] = c }
                    elements.append(d)
                }
                var r: [String: Any] = [
                    "epoch": obs.epoch, "app": obs.app, "window": obs.window,
                    "elements": elements, "text": obs.text, "ax_ms": obs.axMs.rounded(to: 2),
                ]
                if let f = obs.focusedRef { r["focused_ref"] = f }
                if let d = obs.diffText { r["diff_text"] = d }
                if obs.full { r["full"] = true }
                return (true, r, nil)

            case "act":
                let r = hands.act(params)
                return (r["ok"] as? Bool ?? false, r, r["error"] as? String)

            case "skill":
                guard let name = params["name"] as? String else {
                    return (false, nil, "missing skill name")
                }
                let args = params["args"] as? [String: Any] ?? [:]
                let wait = delegate?.handsWillAct(op: name, frame: nil,
                                                  label: nil) ?? 0
                if wait > 0 { usleep(UInt32(min(wait, 5.0) * 1_000_000)) }
                let r = skills.execute(name: name, args: args)
                let ok = r["ok"] as? Bool ?? false
                delegate?.handsDidAct(op: name, frame: nil, ok: ok)
                return (ok, r, r["error"] as? String)

            case "screenshot":
                let r = try Screenshot.captureSync(
                    windowOnly: params["window"] as? Bool ?? false,
                    maxPixels: intParam(params, "max_pixels") ?? 1_000_000,
                    excludeBundleId: ownBundleId,
                    outDir: URL(fileURLWithPath: NSTemporaryDirectory()))
                return (true, ["path": r.path, "width": r.width, "height": r.height,
                               "origin": r.origin, "scale": r.scale], nil)

            case "verify":
                guard let exp = params["expect"] else {
                    return (false, nil, "verify needs expect")
                }
                let pred = try Expect.parse(json: exp)
                let obs = try hands.observe(scope: "focused_window", diff: false)
                let (ok, observed) = Expect.eval(pred, obs)
                return (true, ["ok": ok, "observed": observed], nil)

            case "apps":
                let running = NSWorkspace.shared.runningApplications.compactMap { a -> [String: Any]? in
                    guard let n = a.localizedName else { return nil }
                    return ["name": n, "bundle_id": a.bundleIdentifier ?? "",
                            "pid": a.processIdentifier,
                            "active": a.isActive]
                }
                var installed: [String] = []
                let fm = FileManager.default
                for d in ["/Applications", "/System/Applications"] {
                    for i in (try? fm.contentsOfDirectory(atPath: d)) ?? []
                    where i.hasSuffix(".app") {
                        installed.append(String(i.dropLast(4)))
                    }
                }
                return (true, ["running": running, "installed": installed.sorted()], nil)

            default:
                return (false, nil, "unknown method \(method)")
            }
        } catch let e as HandsError {
            return (false, nil, e.description)
        } catch {
            return (false, nil, "\(error)")
        }
    }
}
