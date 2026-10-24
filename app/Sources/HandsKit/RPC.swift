import AppKit
import ApplicationServices
import Foundation

/// Dispatches brain -> app RPC methods per AGENTS.md.
public final class RPCHandler {
    public let hands = Hands()
    public let skills: Skills
    public var ownBundleId: String? = Bundle.main.bundleIdentifier
    public weak var delegate: HandsDelegate? {
        didSet {
            hands.delegate = delegate
            skills.delegate = delegate
        }
    }

    static let focusChangingSkills: Set<String> = [
        "open_app", "quit_app", "hide_app", "open_url", "web_search", "open_folder",
        "open_file", "play_music", "compose_email", "premiere_command",
    ]

    /// App whose windows a screenshot targets: frontmost, unless that is
    /// this process (then the last observed app).
    private func screenshotTargetPid() -> pid_t? {
        let front = hands.apps.frontmostPid()
        if front != 0 && front != getpid() { return front }
        return hands.lastPid != 0 ? hands.lastPid : nil
    }

    /// `skills`: injectable for tests; `warmUp: false` skips the AppleScript
    /// precompile (tests must not touch System Events).
    public init(skills: Skills? = nil, warmUp: Bool = true) {
        self.skills = skills ?? Skills()
        guard warmUp else { return }
        // Warm the AppleScript runner off the hot path (first compile ~9 s).
        DispatchQueue.global(qos: .utility).async { [skills = self.skills] in
            skills.warmUp()
        }
        // Vision's first accurate OCR in a new binary takes ~25 s; pay it now.
        DispatchQueue.global(qos: .background).async { OCR.warmUp() }
    }

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
                if obs.truncated { r["truncated"] = true }
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
                // App-switching skills change focus without an observation:
                // the next input act binds to whatever is frontmost then.
                if Self.focusChangingSkills.contains(name) { hands.noteExternalFocusChange() }
                delegate?.handsDidAct(op: name, frame: nil, ok: ok)
                delegate?.handsDidRunSkill(name: name, args: args, result: r)
                return (ok, r, r["error"] as? String)

            case "screenshot":
                let region = rectParam(params, "region")
                if params["region"] != nil && region == nil {
                    return (false, nil, ScreenshotError.badRegion.description)
                }
                let r = try Screenshot.captureSync(
                    windowOnly: params["window"] as? Bool ?? false,
                    region: region,
                    maxPixels: intParam(params, "max_pixels") ?? 1_000_000,
                    excludeBundleId: ownBundleId,
                    targetPid: screenshotTargetPid(),
                    outDir: URL(fileURLWithPath: NSTemporaryDirectory()))
                return (true, ["path": r.path, "width": r.width, "height": r.height,
                               "origin": r.origin, "scale": r.scale], nil)

            case "ocr":
                let region = rectParam(params, "region")
                let path = params["path"] as? String
                if path == nil && region == nil {
                    return (false, nil, "ocr needs path or region:[x,y,w,h]")
                }
                let r = try OCR.run(path: path, region: path == nil ? region : nil,
                                    excludeBundleId: ownBundleId)
                return (true, r, nil)

            case "verify":
                guard let exp = params["expect"] else {
                    return (false, nil, "verify needs expect")
                }
                let pred = try Expect.parse(json: exp)
                let obs = try hands.observe(scope: "focused_window", diff: false)
                let (ok, observed) = hands.evalExpect(pred, obs)
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
