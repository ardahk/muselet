import AppKit
import ApplicationServices
import Contacts
import Foundation

/// A normalized message recipient (verbatim phone or email, never a name).
public struct MessageHandle: Equatable {
    public enum Kind: String { case phone, email }
    public var kind: Kind
    /// email casefolded; phone digits with a leading "+" kept.
    public var value: String
}

/// Pure comms helpers: handle validation, URL building, compose-field and
/// recipient checks. No Messages/Contacts access, so tests can drive them.
public enum MessageHandles {
    private static let emailRe = try! NSRegularExpression(
        pattern: #"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$"#,
        options: [.caseInsensitive])
    /// A phone-number-looking span: digits plus the separators people
    /// write numbers with ("+1 (555) 123-4567" is ONE span).
    private static let phoneSpan = try! NSRegularExpression(
        pattern: #"[0-9+][0-9 ()+\-.]*"#)

    /// Email, or a phone number with >= 7 digits (a leading "+" survives).
    /// Bare names and junk -> nil (`bad_handle` / `unresolved_recipient`).
    public static func parse(_ raw: String) -> MessageHandle? {
        let s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if emailRe.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil {
            return MessageHandle(kind: .email, value: s.lowercased())
        }
        var digits = s.filter(\.isNumber)
        guard digits.count >= 7,
              s.allSatisfy({ $0.isNumber || "+()-. /".contains($0) })
        else { return nil }
        if s.hasPrefix("+") { digits = "+" + digits }
        return MessageHandle(kind: .phone, value: digits)
    }

    private static func pct(_ s: String) -> String {
        s.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? s
    }
    public static func imessageURL(_ h: MessageHandle) -> URL? {
        URL(string: "imessage:\(pct(h.value))")
    }
    public static func smsURL(_ h: MessageHandle) -> URL? {
        URL(string: "sms:\(pct(h.value))")
    }

    /// Placeholder/description/title strings Messages uses on its compose
    /// field (iMessage / Text Message / RCS Message / Message).
    public static let composeLabels: Set<String> = [
        "imessage", "text message", "rcs message", "message",
    ]

    /// The Messages compose box: an AXTextArea/AXTextField whose
    /// placeholder, description or title is a compose label (exact match,
    /// case-insensitive). Anything else (Search fields, transcript texts)
    /// is never a target.
    public static func isComposeField(role: String?, placeholder: String?,
                                      title: String?, desc: String?) -> Bool {
        guard role == "AXTextArea" || role == "AXTextField" else { return false }
        return [placeholder, title, desc]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines)
                .lowercased() }
            .contains { composeLabels.contains($0) }
    }

    /// Phone-shaped spans in `s`, collapsed to their digits (each >= 7).
    static func digitRuns(_ s: String) -> [String] {
        phoneSpan.matches(in: s, range: NSRange(s.startIndex..., in: s))
            .compactMap { m -> String? in
                guard let r = Range(m.range, in: s) else { return nil }
                let d = s[r].filter(\.isNumber)
                return d.count >= 7 ? String(d) : nil
            }
    }

    /// `texts` (window title + header/To tokens) identify the conversation:
    /// a phone matches on the last 7+ digits of any digit run, an email
    /// casefolded, or either may match the owning contact's full name.
    public static func recipientMatches(texts: [String],
                                        handle: MessageHandle,
                                        contactName: String?) -> Bool {
        switch handle.kind {
        case .email:
            let needle = handle.value
            if texts.contains(where: { $0.lowercased().contains(needle) }) {
                return true
            }
        case .phone:
            let handleDigits = handle.value.filter(\.isNumber)
            for t in texts {
                for run in digitRuns(t) {
                    let k = min(run.count, handleDigits.count)
                    if run.suffix(k) == handleDigits.suffix(k) {
                        return true
                    }
                }
            }
        }
        if let name = contactName?.trimmingCharacters(in: .whitespaces),
           name.count >= 3 {
            let needle = name.lowercased()
            if texts.contains(where: { $0.lowercased().contains(needle) }) {
                return true
            }
        }
        return false
    }
}

/// `messages_compose` / `messages_send` RPCs. Compose opens Messages on a
/// conversation, fills the draft field and verifies the recipient before
/// reporting; send re-checks window + draft and posts one Return.
public final class MessagesComposer {
    public static let messagesBundle = "com.apple.MobileSMS"

    /// What a successful compose stores for a later send.
    struct Compose {
        var pid: pid_t
        var window: Element
        var field: Element
        var body: String
        var handle: MessageHandle
    }
    private(set) var lastCompose: Compose?

    public var apps: AppControlling
    /// The send Return key: injectable so tests can count posts.
    public var postReturn: () -> Void = {
        if let c = try? Combo.parse("return") { Combo.post(c) }
    }

    public init(apps: AppControlling = WorkspaceApps()) { self.apps = apps }

    // MARK: send gate (pure)

    /// Ordered refusals for messages_send; nil means go.
    static func sendCheck(compose: Compose?, locked: Bool,
                          messagesFrontmost: Bool, sameWindow: Bool,
                          currentBody: String?) -> String? {
        guard compose != nil else { return "no_compose" }
        if locked { return "screen_locked" }
        if !messagesFrontmost || !sameWindow { return "not_frontmost" }
        if currentBody != compose?.body { return "draft_changed" }
        return nil
    }

    // MARK: AX helpers

    /// Messages' front window element (focused, else main, else first).
    private func frontWindow(appEl: Element) -> Element? {
        for attr in [kAXFocusedWindowAttribute, kAXMainWindowAttribute] {
            if let w = axElement(appEl.copySingleAttr(attr)) { return w }
        }
        return axElements(appEl.copySingleAttr(kAXWindowsAttribute)).first
    }

    /// BFS the window for the editable compose field (<= 500 nodes).
    private func composeField(in window: Element) -> Element? {
        var queue: [Element] = [window]
        var seen = 0
        while !queue.isEmpty, seen < 500 {
            let el = queue.removeFirst()
            seen += 1
            let a = el.copyAttrs()
            if MessageHandles.isComposeField(
                role: a.role, placeholder: a.placeholder,
                title: a.title, desc: a.desc),
               a.enabled, el.isSettable(kAXValueAttribute) {
                return el
            }
            queue.append(contentsOf: a.children)
        }
        return nil
    }

    /// Text the recipient may appear in: window title plus every short
    /// string exposed by elements in the window (header, To: chips).
    private func windowTexts(_ window: Element, title: String) -> [String] {
        var texts: [String] = title.isEmpty ? [] : [title]
        var queue: [Element] = [window]
        var seen = 0
        while !queue.isEmpty, seen < 300, texts.count < 60 {
            let el = queue.removeFirst()
            seen += 1
            let a = el.copyAttrs()
            for v in [a.title, a.value as? String, a.desc] {
                if let s = v?.trimmingCharacters(in: .whitespacesAndNewlines),
                   !s.isEmpty, s.count <= 200 { texts.append(s) }
            }
            queue.append(contentsOf: a.children)
        }
        return texts
    }

    /// Full name of the contact owning `handle`, when Contacts access is
    /// authorized (never prompts here — the compose RPC isn't the place).
    private func contactName(for handle: MessageHandle) -> String? {
        guard CNContactStore.authorizationStatus(for: .contacts) == .authorized
        else { return nil }
        let pred: NSPredicate = handle.kind == .email
            ? CNContact.predicateForContacts(matchingEmailAddress: handle.value)
            : CNContact.predicateForContacts(
                matching: CNPhoneNumber(stringValue: handle.value))
        let keys: [CNKeyDescriptor] = [
            CNContactFormatter.descriptorForRequiredKeys(for: .fullName)]
        guard let c = try? CNContactStore().unifiedContacts(
            matching: pred, keysToFetch: keys).first else { return nil }
        return CNContactFormatter.string(from: c, style: .fullName)
    }

    // MARK: messages_compose

    /// `(ok, result, error)` in the RPC handler's shape. Never sends.
    public func compose(handle rawHandle: String, body: String)
        -> (Bool, Any?, String?) {
        guard let handle = MessageHandles.parse(rawHandle) else {
            return (false, nil, "bad_handle")
        }
        if apps.screenLocked() {
            return (false, nil, "screen_locked")
        }
        // imessage: opens the conversation directly; sms: as a fallback.
        var scheme = "imessage"
        if let u = MessageHandles.imessageURL(handle),
           !NSWorkspace.shared.open(u),
           let s = MessageHandles.smsURL(handle) {
            scheme = "sms"
            _ = NSWorkspace.shared.open(s)
        }
        // Wait <= 3 s for Messages to take the front.
        let deadline = Date().addingTimeInterval(3)
        var pid: pid_t = 0
        while Date() < deadline {
            let front = apps.frontmostPid()
            if apps.app(pid: front)?.bundleId == Self.messagesBundle {
                pid = front
                break
            }
            usleep(50_000)
        }
        guard pid != 0 else {
            return (false, ["frontmost": false], "not_frontmost")
        }
        let appEl = AXNode(AXUIElementCreateApplication(pid))
        appEl.setMessagingTimeout(0.5)
        guard let window = frontWindow(appEl: appEl) else {
            return (false, ["frontmost": true], "no_text_target")
        }
        let title = window.copySingleAttr(kAXTitleAttribute) as? String ?? ""
        guard let field = composeField(in: window) else {
            return (false, ["frontmost": true, "window_title": title],
                    "no_text_target")
        }

        // Collect the recipient-identifying text BEFORE the draft lands —
        // the body itself must never satisfy the recipient check.
        let texts = windowTexts(window, title: title)

        // Fill the draft: AXValue first, pasteboard+cmd+v as the fallback
        // (never keystrokes: Return in Messages sends).
        _ = field.setAttr(kAXFocusedAttribute, true)
        usleep(30_000)
        let previous = field.copySingleAttr(kAXValueAttribute) as? String ?? ""
        if !field.setAttr(kAXValueAttribute, body) {
            let pb = NSPasteboard.general
            let old = pb.string(forType: .string)
            pb.clearContents()
            pb.setString(body, forType: .string)
            if let c = try? Combo.parse("cmd+v") { Combo.post(c) }
            usleep(150_000)
            pb.clearContents()
            if let old { pb.setString(old, forType: .string) }
        }
        let read = field.copySingleAttr(kAXValueAttribute) as? String ?? ""
        let visible = read.trimmingCharacters(in: .whitespacesAndNewlines)
            == body.trimmingCharacters(in: .whitespacesAndNewlines)

        // Safety-critical: a draft in the wrong conversation must not stand.
        let recipientOK = MessageHandles.recipientMatches(
            texts: texts, handle: handle,
            contactName: contactName(for: handle))
        if !recipientOK {
            _ = field.setAttr(kAXValueAttribute, previous)
            return (false, [
                "frontmost": true, "window_title": title,
                "body_visible": visible,
                "observed": ["window_title": title,
                             "header": texts.prefix(10)],
            ], "recipient_unverified")
        }
        lastCompose = Compose(pid: pid, window: window, field: field,
                              body: body, handle: handle)
        return (true, [
            "frontmost": true, "window_title": title,
            "body_visible": visible, "recipient_ok": true,
            "scheme": scheme,
        ], nil)
    }

    // MARK: messages_send

    /// `(ok, result, error)`. Posts one Return only when the stored
    /// compose is still exactly on screen.
    public func send() -> (Bool, Any?, String?) {
        let c = lastCompose
        let messagesFront = apps.app(pid: apps.frontmostPid())?
            .bundleId == Self.messagesBundle
        var sameWindow = false
        var currentBody: String?
        if messagesFront, let c {
            let appEl = AXNode(AXUIElementCreateApplication(apps.frontmostPid()))
            appEl.setMessagingTimeout(0.5)
            if let w = frontWindow(appEl: appEl) {
                sameWindow = sameElement(w, c.window)
                    || (w as? AXNode)?.stableId == (c.window as? AXNode)?.stableId
            }
            currentBody = c.field.isAlive()
                ? c.field.copySingleAttr(kAXValueAttribute) as? String
                : nil
        }
        if let err = Self.sendCheck(
            compose: c, locked: apps.screenLocked(),
            messagesFrontmost: messagesFront, sameWindow: sameWindow,
            currentBody: currentBody) {
            return (false, nil, err)
        }
        guard let c else { return (false, nil, "no_compose") }

        _ = c.field.setAttr(kAXFocusedAttribute, true)
        usleep(30_000)
        postReturn()
        lastCompose = nil  // cleared after any attempt

        // The field empties when the message goes out.
        let deadline = Date().addingTimeInterval(2)
        var sent = false
        while Date() < deadline {
            let v = c.field.isAlive()
                ? c.field.copySingleAttr(kAXValueAttribute) as? String : nil
            if (v ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                .isEmpty {
                sent = true
                break
            }
            usleep(100_000)
        }
        return (true, ["sent": sent], nil)
    }
}
