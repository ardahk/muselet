import Contacts
import Foundation

/// `contacts_search` RPC: people search over CNContactStore for the comms
/// skill. Authorization: authorized/limited search; notDetermined asks and
/// awaits (<= 60 s); denied/restricted/refused -> `contacts_denied`.
/// Pure helpers (query kind, label mapping, match packing) take plain
/// values so tests never touch the store.
public enum ContactsSearch {

    public enum QueryKind { case email, phone, name }

    private static let emailRe = try! NSRegularExpression(
        pattern: #"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$"#,
        options: [.caseInsensitive])

    /// Predicate selection: email-looking -> email predicate; >= 7 digits
    /// -> phone predicate; anything else -> name.
    public static func queryKind(_ query: String) -> QueryKind {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if emailRe.firstMatch(in: q, range: NSRange(q.startIndex..., in: q)) != nil {
            return .email
        }
        if q.filter(\.isNumber).count >= 7 { return .phone }
        return .name
    }

    /// `CNLabeledValue.localizedString(forLabel:)` lowercased
    /// ("mobile", "iphone", "home", "work", custom labels unwrapped).
    public static func localizedLabel(_ raw: String?) -> String {
        CNLabeledValue<NSString>.localizedString(forLabel: raw).lowercased()
    }

    static let fetchKeys: [CNKeyDescriptor] = [
        CNContactFormatter.descriptorForRequiredKeys(for: .fullName),
        CNContactIdentifierKey as CNKeyDescriptor,
        CNContactOrganizationNameKey as CNKeyDescriptor,
        CNContactNicknameKey as CNKeyDescriptor,
        CNContactPhoneNumbersKey as CNKeyDescriptor,
        CNContactEmailAddressesKey as CNKeyDescriptor,
    ]

    /// One contact -> the wire match dict.
    public static func matchDict(_ c: CNContact) -> [String: Any] {
        var handles: [[String: Any]] = []
        for lv in c.phoneNumbers {
            handles.append(["kind": "phone", "value": lv.value.stringValue,
                            "label": localizedLabel(lv.label)])
        }
        for lv in c.emailAddresses {
            handles.append(["kind": "email", "value": lv.value as String,
                            "label": localizedLabel(lv.label)])
        }
        var d: [String: Any] = [
            "id": c.identifier,
            "name": CNContactFormatter.string(from: c, style: .fullName)
                ?? c.organizationName,
            "handles": handles,
        ]
        if !c.nickname.isEmpty { d["nickname"] = c.nickname }
        return d
    }

    /// The search itself. Returns `(matches, error)`.
    public static func search(store: CNContactStore, query: String,
                              limit: Int) -> ([[String: Any]]?, String?) {
        switch CNContactStore.authorizationStatus(for: .contacts) {
        case .authorized, .limited:
            break
        case .notDetermined:
            var granted = false
            let sem = DispatchSemaphore(value: 0)
            store.requestAccess(for: .contacts) { g, _ in
                granted = g
                sem.signal()
            }
            _ = sem.wait(timeout: .now() + 60)
            guard granted,
                  CNContactStore.authorizationStatus(for: .contacts) != .denied
            else { return (nil, "contacts_denied") }
        case .denied, .restricted:
            return (nil, "contacts_denied")
        @unknown default:
            return (nil, "contacts_denied")
        }

        let predicate: NSPredicate
        switch queryKind(query) {
        case .email:
            predicate = CNContact.predicateForContacts(matchingEmailAddress: query)
        case .phone:
            predicate = CNContact.predicateForContacts(
                matching: CNPhoneNumber(stringValue: query))
        case .name:
            predicate = CNContact.predicateForContacts(matchingName: query)
        }
        do {
            var found = try store.unifiedContacts(
                matching: predicate, keysToFetch: fetchKeys)
            // A multi-word name that matched nothing retries on its first
            // word (Contacts' name predicate needs all words to match).
            if found.isEmpty, case .name = queryKind(query),
               let first = query.split(whereSeparator: \.isWhitespace).first,
               query.contains(" ") {
                found = try store.unifiedContacts(
                    matching: CNContact.predicateForContacts(
                        matchingName: String(first)),
                    keysToFetch: fetchKeys)
            }
            return (found.prefix(max(1, limit)).map(matchDict), nil)
        } catch {
            return (nil, "contacts_search failed: \(error.localizedDescription)")
        }
    }

    /// `(ok, result, error)` in the RPC handler's shape.
    public static func rpc(query: String, limit: Int)
        -> (Bool, Any?, String?) {
        let t0 = Date()
        let (matches, error) = search(
            store: CNContactStore(), query: query, limit: limit)
        if let error { return (false, nil, error) }
        return (true, [
            "matches": matches ?? [],
            "ms": (Date().timeIntervalSince(t0) * 1000).rounded(to: 2),
        ], nil)
    }
}
