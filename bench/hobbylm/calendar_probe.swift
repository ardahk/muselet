import Dispatch
import EventKit
import Foundation

final class AccessState: @unchecked Sendable {
    private let lock = NSLock()
    private var result = false

    func set(_ value: Bool) {
        lock.lock()
        result = value
        lock.unlock()
    }

    func get() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return result
    }
}

func sourceTypeName(_ type: EKSourceType) -> String {
    switch type {
    case .local: return "local"
    case .calDAV: return "caldav"
    case .exchange: return "exchange"
    case .mobileMe: return "mobileme"
    case .subscribed: return "subscribed"
    case .birthdays: return "birthdays"
    @unknown default: return "other"
    }
}

func output(_ value: [String: Any], status: Int32 = 0) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
    exit(status)
}

let mode = CommandLine.arguments.dropFirst().first ?? "probe"
let title = "Muselet Bench"
let store = EKEventStore()
let access = AccessState()
let semaphore = DispatchSemaphore(value: 0)
store.requestFullAccessToEvents { granted, _ in
    access.set(granted)
    semaphore.signal()
}
if semaphore.wait(timeout: .now() + 30) == .timedOut || !access.get() {
    output(["exists": false, "source_type": NSNull(), "source_title": NSNull(),
            "is_default_for_new_events": false, "error": "Calendar access was not granted."], status: 2)
}

let calendars = store.calendars(for: .event).filter { $0.title == title }
func describe(_ calendar: EKCalendar?) -> [String: Any] {
    guard let calendar else {
        return ["exists": false, "source_type": NSNull(), "source_title": NSNull(),
                "is_default_for_new_events": false]
    }
    let source = calendar.source
    return [
        "exists": true,
        "source_type": source.map { sourceTypeName($0.sourceType) } ?? NSNull(),
        "source_title": source?.title ?? NSNull(),
        "is_default_for_new_events": store.defaultCalendarForNewEvents?.calendarIdentifier
            == calendar.calendarIdentifier
    ]
}

if mode == "setup" {
    if let local = calendars.first(where: { $0.source.sourceType == .local }) {
        output(describe(local))
    }
    guard let source = store.sources.first(where: { $0.sourceType == .local }) else {
        output(["exists": false, "source_type": NSNull(), "source_title": NSNull(),
                "is_default_for_new_events": false,
                "error": "No local Calendar source (On My Mac) is available; no calendar was created."],
               status: 3)
    }
    let calendar = EKCalendar(for: .event, eventStore: store)
    calendar.title = title
    calendar.source = source
    do {
        try store.saveCalendar(calendar, commit: true)
    } catch {
        output(["exists": false, "source_type": "local", "source_title": source.title,
                "is_default_for_new_events": false, "error": String(describing: error)], status: 4)
    }
    output(describe(calendar))
}

let selected = calendars.first(where: { $0.source.sourceType == .local }) ?? calendars.first
if mode == "events" || mode == "delete" {
    guard let localCalendar = calendars.first(where: { $0.source.sourceType == .local }) else {
        output(["exists": false, "events": [], "error": "Muselet Bench is not local."], status: 5)
    }
    let start = Calendar.current.date(byAdding: .day, value: -365, to: Date())!
    let end = Calendar.current.date(byAdding: .day, value: 365, to: Date())!
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: [localCalendar])
    let events = store.events(matching: predicate)
    if mode == "events" {
        let rows = events.map { event in
            [
                "id": event.eventIdentifier ?? "",
                "title": event.title ?? "",
                "start": ISO8601DateFormatter().string(from: event.startDate),
                "notes": event.notes ?? ""
            ]
        }
        output(["exists": true, "events": rows])
    }
    let ids = Set(CommandLine.arguments.dropFirst(2))
    var deleted: [String] = []
    for event in events where ids.contains(event.eventIdentifier ?? "") {
        do {
            try store.remove(event, span: .thisEvent, commit: true)
            deleted.append(event.eventIdentifier ?? "")
        } catch {
            output(["exists": true, "deleted": deleted, "error": String(describing: error)], status: 6)
        }
    }
    output(["exists": true, "deleted": deleted])
}
output(describe(selected))
