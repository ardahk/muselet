import Contacts
import XCTest
@testable import HandsKit

/// Pure comms logic: handles, compose-field and recipient checks, the
/// send gate, contact labels. No Messages/Contacts access anywhere here.
final class MessageHandleTests: XCTestCase {
    func testEmails() {
        XCTAssertEqual(MessageHandles.parse("Arda@Gmail.com")?.value,
                       "arda@gmail.com")
        XCTAssertEqual(MessageHandles.parse("a.b-c@sub.domain.co")?.kind,
                       .email)
        XCTAssertEqual(MessageHandles.parse("  x@y.io  ")?.value, "x@y.io")
    }

    func testPhones() {
        XCTAssertEqual(MessageHandles.parse("+1 (555) 123-4567")?.value,
                       "+15551234567")
        XCTAssertEqual(MessageHandles.parse("555 123 4567")?.value,
                       "5551234567")
        XCTAssertEqual(MessageHandles.parse("555-1234")?.value, "5551234")
    }

    func testRejects() {
        XCTAssertNil(MessageHandles.parse("mom"))
        XCTAssertNil(MessageHandles.parse("Arda Kilic"))
        XCTAssertNil(MessageHandles.parse("12345"))           // < 7 digits
        XCTAssertNil(MessageHandles.parse("call 555-1234!"))  // letters
        XCTAssertNil(MessageHandles.parse(""))
        XCTAssertNil(MessageHandles.parse("arda@localhost"))  // no dot
    }

    func testURLs() {
        let phone = MessageHandles.parse("+15551234567")!
        XCTAssertEqual(MessageHandles.imessageURL(phone)?.absoluteString,
                       "imessage:+15551234567")
        XCTAssertEqual(MessageHandles.smsURL(phone)?.absoluteString,
                       "sms:+15551234567")
        let email = MessageHandles.parse("arda@x.io")!
        // `@` is legal unencoded in a URI path.
        XCTAssertEqual(MessageHandles.imessageURL(email)?.absoluteString,
                       "imessage:arda@x.io")
    }
}

final class ComposeFieldTests: XCTestCase {
    /// (role, placeholder, title, desc) triples as Messages exposes them.
    private func pick(_ els: [(String?, String?, String?, String?)])
        -> Int? {
        els.firstIndex {
            MessageHandles.isComposeField(
                role: $0.0, placeholder: $0.1, title: $0.2, desc: $0.3)
        }
    }

    func testSelectsCompose() {
        let els: [(String?, String?, String?, String?)] = [
            ("AXStaticText", nil, "Arda", nil),
            ("AXSearchField", "Search", nil, nil),
            ("AXTextArea", "iMessage", nil, nil),
        ]
        XCTAssertEqual(pick(els), 2)
    }

    func testLabels() {
        for label in ["iMessage", "Text Message", "RCS Message", "Message"] {
            XCTAssertTrue(MessageHandles.isComposeField(
                role: "AXTextArea", placeholder: label,
                title: nil, desc: nil), label)
            // Also via description/title, and on an AXTextField.
            XCTAssertTrue(MessageHandles.isComposeField(
                role: "AXTextField", placeholder: nil,
                title: label, desc: nil), label)
        }
    }

    func testRejects() {
        let els: [(String?, String?, String?, String?)] = [
            ("AXTextArea", "iMessage drafts are here", nil, nil), // not exact
            ("AXTextField", "Search", nil, nil),
            ("AXStaticText", "iMessage", nil, nil),               // wrong role
            ("AXTextArea", nil, nil, nil),                        // no label
            ("AXButton", "Send", nil, nil),
        ]
        XCTAssertNil(pick(els))
    }
}

final class RecipientTests: XCTestCase {
    let phone = MessageHandles.parse("+1 (555) 123-4567")!
    let email = MessageHandles.parse("arda@x.io")!

    func testRightNumber() {
        XCTAssertTrue(MessageHandles.recipientMatches(
            texts: ["Arda Kilic", "+1 (555) 123-4567"],
            handle: phone, contactName: nil))
    }

    func testWrongConversation() {
        XCTAssertFalse(MessageHandles.recipientMatches(
            texts: ["Mom", "+1 (444) 999-0000"],
            handle: phone, contactName: nil))
    }

    func testNameMatch() {
        XCTAssertTrue(MessageHandles.recipientMatches(
            texts: ["Arda Kilic"],
            handle: phone, contactName: "Arda Kilic"))
        // A wrong title does not save a non-matching name.
        XCTAssertFalse(MessageHandles.recipientMatches(
            texts: ["Bob"],
            handle: phone, contactName: "Arda Kilic"))
    }

    func testEmailCasefold() {
        XCTAssertTrue(MessageHandles.recipientMatches(
            texts: ["ARDA@X.IO — Messages"],
            handle: email, contactName: nil))
    }

    func testShortDigitRunIgnored() {
        // A run under 7 digits can never identify a recipient.
        XCTAssertFalse(MessageHandles.recipientMatches(
            texts: ["ext 1234 today"],
            handle: phone, contactName: nil))
        // 7+ digits that don't overlap the handle's tail: no match.
        XCTAssertFalse(MessageHandles.recipientMatches(
            texts: ["order 7654321 shipped"],
            handle: phone, contactName: nil))
    }
}

final class SendGateTests: XCTestCase {
    private func compose(body: String = "hi") -> MessagesComposer.Compose {
        MessagesComposer.Compose(
            pid: 0, window: MockElement(role: "AXWindow"),
            field: MockElement(role: "AXTextArea"), body: body,
            handle: MessageHandles.parse("+15551234567")!)
    }

    func testNoCompose() {
        XCTAssertEqual(
            MessagesComposer.sendCheck(
                compose: nil, locked: false, messagesFrontmost: true,
                sameWindow: true, currentBody: "hi"),
            "no_compose")
    }

    func testDraftChanged() {
        XCTAssertEqual(
            MessagesComposer.sendCheck(
                compose: compose(body: "hi"), locked: false,
                messagesFrontmost: true, sameWindow: true,
                currentBody: "hi mom"),
            "draft_changed")
    }

    func testRefusalOrderAndGo() {
        // Lock beats frontmost; frontmost beats draft.
        XCTAssertEqual(
            MessagesComposer.sendCheck(
                compose: compose(), locked: true, messagesFrontmost: false,
                sameWindow: false, currentBody: "x"),
            "screen_locked")
        XCTAssertEqual(
            MessagesComposer.sendCheck(
                compose: compose(), locked: false, messagesFrontmost: false,
                sameWindow: true, currentBody: "hi"),
            "not_frontmost")
        XCTAssertEqual(
            MessagesComposer.sendCheck(
                compose: compose(), locked: false, messagesFrontmost: true,
                sameWindow: false, currentBody: "hi"),
            "not_frontmost")
        XCTAssertNil(
            MessagesComposer.sendCheck(
                compose: compose(), locked: false, messagesFrontmost: true,
                sameWindow: true, currentBody: "hi"))
    }
}

final class ContactLabelTests: XCTestCase {
    func testLabels() {
        XCTAssertEqual(
            ContactsSearch.localizedLabel(CNLabelPhoneNumberMobile), "mobile")
        XCTAssertEqual(
            ContactsSearch.localizedLabel(CNLabelPhoneNumberiPhone), "iphone")
        XCTAssertEqual(ContactsSearch.localizedLabel(CNLabelHome), "home")
        XCTAssertEqual(ContactsSearch.localizedLabel(CNLabelWork), "work")
        // Custom Apple labels unwrap to their inner text.
        XCTAssertEqual(ContactsSearch.localizedLabel("_$!<Cabin>!$_"),
                       "cabin")
    }
}

final class SendMessageGuardTests: XCTestCase {
    func skills() -> Skills {
        Skills(catalog: (try! Catalog.load()), scripts: SpyRunner(),
               events: MockPoster(), apps: MockApps(), hooks: .inert)
    }

    func testBareNameRefused() {
        let r = skills().execute(
            name: "send_message",
            args: ["to": "mom", "body": "hi", "confirmed": true])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "unresolved_recipient")
    }

    func testVerbatimAllowed() {
        let r = skills().execute(
            name: "send_message",
            args: ["to": "+1 555 123 4567", "body": "hi", "confirmed": true])
        XCTAssertEqual(r["ok"] as? Bool, true, "\(r)")
        let e = skills().execute(
            name: "send_message",
            args: ["to": "arda@x.io", "body": "hi", "confirmed": true])
        XCTAssertEqual(e["ok"] as? Bool, true, "\(e)")
    }
}

final class RelativePathTests: XCTestCase {
    func skills() -> Skills {
        Skills(catalog: (try! Catalog.load()), scripts: SpyRunner(),
               events: MockPoster(), apps: MockApps(), hooks: .inert)
    }

    func testChecked() {
        XCTAssertNoThrow(try PathAlias.checked("downloads"))
        XCTAssertNoThrow(try PathAlias.checked("~/Documents"))
        XCTAssertNoThrow(try PathAlias.checked("/tmp"))
        XCTAssertThrowsError(try PathAlias.checked("my desktop")) {
            XCTAssertEqual(($0 as? HandsError)?.code, "relative_path")
        }
        XCTAssertThrowsError(try PathAlias.checked("rel/dir"))
        XCTAssertThrowsError(try PathAlias.checked(".."))
    }

    func testNewFolder() {
        let r = skills().execute(name: "new_folder", args: [
            "parent": "my desktop", "name": "muselet invoices"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "relative_path")
        XCTAssertEqual(r["observed"] as? String, "my desktop")
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: "my desktop/muselet invoices"))
    }

    func testOpenFolder() {
        let r = skills().execute(
            name: "open_folder", args: ["path": "docs/inbox"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "relative_path")
        XCTAssertEqual(r["observed"] as? String, "docs/inbox")
    }

    func testOpenFile() {
        let r = skills().execute(
            name: "open_file", args: ["path": "report.pdf"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "relative_path")
    }

    func testMoveToTrash() {
        // confirmed skips the confirm gate so the path check is reached.
        let r = skills().execute(name: "move_to_trash", args: [
            "path": "old folder", "confirmed": true])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["error"] as? String, "relative_path")
        XCTAssertEqual(r["observed"] as? String, "old folder")
    }
}
