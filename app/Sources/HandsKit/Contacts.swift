import Contacts
import Foundation

/// `contacts_search` RPC: people search over CNContactStore for the comms
/// skill. Authorization: authorized search; notDetermined asks and
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
    private static let appleLabel = try! NSRegularExpression(
        pattern: #"^_\$!<(.*?)>!\$_$"#)

    public static func localizedLabel(_ raw: String?) -> String {
        guard let raw else { return "" }
        // Custom labels ("_$!<Cabin>!$_") unwrap to their inner text; the
        // framework only maps the known constants.
        if let m = appleLabel.firstMatch(
            in: raw, range: NSRange(raw.startIndex..., in: raw)),
           let r = Range(m.range(at: 1), in: raw) {
            return String(raw[r]).lowercased()
        }
        return CNLabeledValue<NSString>.localizedString(forLabel: raw)
            .lowercased()
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
        case .authorized:
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

    /// Classic Levenshtein distance (small strings; contact names).
    public static func levenshtein(_ a: String, _ b: String) -> Int {
        let x = Array(a.lowercased()), y = Array(b.lowercased())
        var prev = Array(0...y.count)
        for (i, cx) in x.enumerated() {
            var cur = [i + 1] + Array(repeating: 0, count: y.count)
            for (j, cy) in y.enumerated() {
                cur[j + 1] = cx == cy
                    ? prev[j]
                    : 1 + min(prev[j], prev[j + 1], cur[j])
            }
            prev = cur
        }
        return prev[y.count]
    }

    /// Normalized similarity in 0...1 (1 = identical).
    public static func similarity(_ a: String, _ b: String) -> Double {
        let m = max(a.count, b.count)
        guard m > 0 else { return 1 }
        return 1 - Double(levenshtein(a, b)) / Double(m)
    }

    /// Best fuzzy score of `query` against a contact's name fields
    /// (full / given / family / nickname). Pure for tests.
    public static func fuzzyScore(query: String, full: String,
                                  given: String, family: String,
                                  nickname: String) -> Double {
        [full, given, family, nickname]
            .filter { !$0.isEmpty }
            .map { similarity(query.lowercased(), $0.lowercased()) }
            .max() ?? 0
    }

    /// fuzzy:true — enumerate every contact and keep the top `limit`
    /// with score >= 0.75, each carrying `score`.
    static func fuzzySearch(store: CNContactStore, query: String,
                            limit: Int) -> ([[String: Any]]?, String?) {
        switch CNContactStore.authorizationStatus(for: .contacts) {
        case .authorized:
            break
        case .notDetermined:
            var granted = false
            let sem = DispatchSemaphore(value: 0)
            store.requestAccess(for: .contacts) { g, _ in
                granted = g; sem.signal() }
            _ = sem.wait(timeout: .now() + 60)
            guard granted else { return (nil, "contacts_denied") }
        case .denied, .restricted:
            return (nil, "contacts_denied")
        @unknown default:
            return (nil, "contacts_denied")
        }
        let keys: [CNKeyDescriptor] = fetchKeys + [
            CNContactGivenNameKey as CNKeyDescriptor,
            CNContactFamilyNameKey as CNKeyDescriptor,
        ]
        var scored: [(Double, [String: Any])] = []
        let req = CNContactFetchRequest(keysToFetch: keys)
        do {
            try store.enumerateContacts(with: req) { c, _ in
                let s = fuzzyScore(
                    query: query,
                    full: CNContactFormatter.string(from: c, style: .fullName) ?? "",
                    given: c.givenName, family: c.familyName,
                    nickname: c.nickname)
                if s >= 0.75 {
                    var d = matchDict(c)
                    d["score"] = (s * 1000).rounded() / 1000
                    scored.append((s, d))
                }
            }
        } catch {
            return (nil, "contacts_search failed: \(error.localizedDescription)")
        }
        scored.sort { $0.0 > $1.0 }
        return (scored.prefix(max(1, limit)).map(\.1), nil)
    }

    /// `(ok, result, error)` in the RPC handler's shape.
    public static func rpc(query: String, limit: Int, fuzzy: Bool = false)
        -> (Bool, Any?, String?) {
        let t0 = Date()
        let store = CNContactStore()
        let (matches, error) = fuzzy
            ? fuzzySearch(store: store, query: query, limit: limit)
            : search(store: store, query: query, limit: limit)
        if let error { return (false, nil, error) }
        return (true, [
            "matches": matches ?? [],
            "ms": (Date().timeIntervalSince(t0) * 1000).rounded(to: 2),
        ], nil)
    }
}
