import Foundation

/// Spoken yes/no for CONFIRM (send/delete/buy/post). Biased to safety:
///  - any negator anywhere -> false ("not right now", "okay cancel that",
///    "that's not correct");
///  - an explicit yes plus a negator -> nil (ambiguous: re-ask), e.g.
///    "yes no wait";
///  - a yes word negated by the 1-2 preceding words ("not sure", "don't do
///    it") does not count as yes;
///  - "ok"/"okay"/"alright" are fillers: yes only when nothing negates.
/// Returns nil when nothing decisive was said.
public enum YesNo {
    static let negators: Set<String> = [
        "no", "not", "nope", "nah", "never", "cancel", "cancelled", "canceled", "stop",
        "wait", "abort", "negative", "don't", "dont", "nevermind",
    ]
    static let negatorPhrases: [[String]] = [["hold", "on"], ["never", "mind"], ["not", "now"]]
    static let yesWords: Set<String> = [
        "yes", "yeah", "yep", "yup", "ya", "yah", "sure", "confirm", "confirmed",
        "affirmative", "absolutely", "definitely",
    ]
    static let yesPhrases: [[String]] = [
        ["go", "ahead"], ["do", "it"], ["send", "it"], ["please", "do"], ["sounds", "good"],
        ["of", "course"], ["go", "for", "it"],
    ]
    static let fillerYes: Set<String> = ["ok", "okay", "alright"]
    /// Affirmative phrases that contain "no"; removed before the negator scan.
    static let affirmativeNoPhrases: [[String]] = [["no", "problem"], ["no", "worries"]]

    static func tokens(_ text: String) -> [String] {
        let t = text.lowercased()
            .replacingOccurrences(of: "\u{2019}", with: "'")
            .replacingOccurrences(of: "[^a-z' ]", with: " ", options: .regularExpression)
        return t.split(separator: " ").map { String($0).trimmingCharacters(in: CharacterSet(charactersIn: "'")) }
            .filter { !$0.isEmpty }
    }

    static func isNegator(_ w: String) -> Bool {
        negators.contains(w) || w.hasSuffix("n't")
    }

    public static func parse(_ text: String) -> Bool? {
        var w = tokens(text)
        guard !w.isEmpty else { return nil }

        // "no problem" / "no worries" are agreement, not refusal.
        var filler = false
        for p in affirmativeNoPhrases {
            var i = 0
            while i + p.count <= w.count {
                if Array(w[i..<i + p.count]) == p {
                    w.removeSubrange(i..<i + p.count)
                    filler = true
                } else { i += 1 }
            }
        }

        var negIdx = Set<Int>()
        for (i, t) in w.enumerated() where isNegator(t) { negIdx.insert(i) }
        for p in negatorPhrases {
            for i in 0...(max(0, w.count - p.count)) where i + p.count <= w.count {
                if Array(w[i..<i + p.count]) == p { negIdx.formUnion(i..<i + p.count) }
            }
        }
        // A yes at index i is negated by a negator in the two words before it.
        func negated(_ i: Int) -> Bool { negIdx.contains(i - 1) || negIdx.contains(i - 2) }

        var strongYes = false
        for (i, t) in w.enumerated() where yesWords.contains(t) && !negIdx.contains(i) {
            if !negated(i) { strongYes = true }
        }
        for p in yesPhrases where p.count <= w.count {
            for i in 0...(w.count - p.count) where Array(w[i..<i + p.count]) == p {
                if !negated(i) && !negIdx.contains(i) { strongYes = true }
            }
        }
        for (i, t) in w.enumerated() where fillerYes.contains(t) && !negated(i) { filler = true }

        if !negIdx.isEmpty { return strongYes ? nil : false }
        if strongYes || filler { return true }
        return nil
    }
}
