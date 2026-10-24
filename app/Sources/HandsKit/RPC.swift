import AppKit
import ApplicationServices
import Foundation

/// Dispatches brain -> app RPC methods per AGENTS.md:
///  - `observe`, `act`, `skill`, `screenshot`, `ocr`, `verify`, `apps`.
///  - `act` `keys` takes media keys too: `volume_up`, `volume_down`, `mute`,
///    `brightness_up`, `brightness_down`, `play_pause`, `next_track`,
///    `previous_track` (system-defined events like the hardware keys,
///    tagged as Muselet input; read-back `level_before` / `level` /
///    `changed` for volume and brightness). See `Hands.act`.
///  - `skill set_brightness {delta}`: relative brightness (current + delta,
///    clamped 0...100, read back); `open_folder {view}`; `type_text` /
///    `type` into a keystroke app (Calculator, `via: "keystroke_app"`);
///    truthful launches (`not_frontmost`). See `Skills`.
///  - `timers {}` -> Muselet timers plus optional `clock_ax` observations and
///    Clock shortcut merge status; `timer_backend` reports AX/shortcut readiness.
///  - `timers_cancel {id?}` -> `{cancelled: [timer...], timers: [remaining...]}`:
///    one timer, or every Muselet/Clock timer without `id`; an unknown id is
///    ok=false `unknown_timer` (with the pending list). Clock AX cancel falls
///    back to the optional Cancel shortcut.
///    (Timers are RPCs, not skills, so the catalog is unchanged.)
///  - Comms (`brain.comms` contract):
///    `contacts_search {query, limit=5}` -> `{matches, ms}` (`contacts_denied`);
///    `messages_compose {handle, body}` -> `{frontmost, window_title,
///    body_visible, recipient_ok}`, never sends (`bad_handle`,
///    `screen_locked`, `not_frontmost`, `no_text_target`,
///    `recipient_unverified`);
///    `messages_send {}` -> `{sent}` after one Return in the stored
///    compose only (`no_compose`, `screen_locked`, `not_frontmost`,
///    `draft_changed`).
public final class RPCHandler {
    public let hands = Hands()
    public let skills: Skills
    /// Messages compose/send state (the draft a `messages_send` may release).
    public let composer = MessagesComposer()
    /// Dock / menu-extra frames for the ghost cursor before skills.
    public let skillTargets: SkillTargets
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
    public init(skills: Skills? = nil, skillTargets: SkillTargets? = nil, warmUp: Bool = true) {
        self.skills = skills ?? Skills()
        self.skillTargets = skillTargets ?? SkillTargets()
        guard warmUp else { return }
        // Precompile the skill AppleScripts off the hot path (compile only:
        // nothing runs, so no app is launched and no Automation prompt shows).
        DispatchQueue.global(qos: .utility).async { [skills = self.skills, hands = self.hands] in
            skills.warmUp()
            // The volume read-back of `keys volume_up/down/mute` (Hands' own runner).
            (hands.scripts as? AppleScriptRunner)?.precompile([Skills.volumeStateScript])
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
                // focused | main | windows | app | none | menubar | all_windows
                r["window_source"] = obs.windowSource
                if let d = obs.diffText { r["diff_text"] = d }
                if obs.full { r["full"] = true }
                if obs.truncated { r["truncated"] = true }
                // Chrome is still building its web tree (2 s debounce after
                // the switch): re-observe shortly instead of screenshotting.
                if obs.webAXPending { r["web_ax_pending"] = true }
                return (true, r, nil)

            case "act":
                let r = hands.act(params)
                return (r["ok"] as? Bool ?? false, r, r["error"] as? String)

            case "skill":
                guard let name = params["name"] as? String else {
                    return (false, nil, "missing skill name")
                }
                let args = params["args"] as? [String: Any] ?? [:]
                // ux-4: fly the ghost cursor to the skill's natural target
                // (Dock icon, menu extra) first, within cursor_lead_ms
                // (<= 120 ms, lookup time included). Headless: no delegate,
                // no lookup, no delay.
                if let delegate {
                    let t0 = Date()
                    let leadMs = min(Double(intParam(params, "cursor_lead_ms") ?? 120), 120)
                    let target = SkillTargets.hasTarget(name)
                        ? skillTargets.target(skill: name, args: args) : nil
                    let wait = delegate.handsWillAct(op: name, frame: target?.frame,
                                                     label: target?.label)
                    let left = min(wait, leadMs / 1000) - Date().timeIntervalSince(t0)
                    if wait > 0, left > 0 { usleep(UInt32(left * 1_000_000)) }
                }
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

            case "timers":
                return (true, skills.timersReport(askClock: params["clock_status"] as? Bool ?? false), nil)

            case "timer_backend":
                // {clock_ready, clock_ax_ready, shortcuts, enabled, backend, cancel_ready, status_ready}
                return (true, skills.timerBackendInfo(refresh: params["refresh"] as? Bool ?? false), nil)

            case "timers_cancel":
                // No id: every Muselet timer. An id must name a pending timer.
                var id: String?
                if let v = params["id"] ?? params["timer_id"], !(v is NSNull) {
                    guard let s = v as? String, !s.isEmpty else {
                        return (false, nil, HandsError.invalidParams("timers_cancel: id must be a timer id").description)
                    }
                    id = s
                }
                let c = skills.cancelTimersDetailed(id: id)
                var r: [String: Any] = ["cancelled": c.cancelled, "timers": skills.timerList()]
                if let id, c.unknown { return (false, r, "unknown_timer: \(id)") }
                if !c.axReasons.isEmpty { r["clock_ax_reasons"] = c.axReasons }
                if !c.unsupported.isEmpty {
                    r["unsupported"] = c.unsupported
                    return (false, r,
                            "unsupported: Clock timer cancel control not found (no \(ClockShortcut.cancel) shortcut)")
                }
                if !c.failed.isEmpty {
                    r["failed"] = c.failed
                    return (false, r, "clock_cancel_failed: \(c.failed.first?["reason"] as? String ?? "?")")
                }
                return (true, r, nil)

            case "contacts_search":
                return ContactsSearch.rpc(
                    query: params["query"] as? String ?? "",
                    limit: intParam(params, "limit") ?? 5,
                    fuzzy: params["fuzzy"] as? Bool ?? false)

            case "messages_people":
                return MessagesPeople.rpc(
                    query: params["query"] as? String ?? "",
                    limit: intParam(params, "limit") ?? 5)

            case "messages_compose":
                guard let handle = params["handle"] as? String,
                      let body = params["body"] as? String else {
                    return (false, nil,
                            "messages_compose needs handle + body")
                }
                return composer.compose(
                    handle: handle, body: body,
                    name: params["name"] as? String)

            case "messages_send":
                return composer.send()

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
