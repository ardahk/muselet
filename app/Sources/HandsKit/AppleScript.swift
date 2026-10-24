import CoreServices
import Foundation

// MARK: - Skill scripts (fixed source, parameterized handlers)

/// A fixed-source AppleScript whose handlers take parameters. It is
/// compiled once per process (at warm-up, without running it) and then
/// called with different arguments through a subroutine Apple event, so a
/// new argument never means a new compile and argument text is never
/// spliced into source (no escaping, no injection).
public struct SkillScript: Hashable {
    public let name: String
    public let source: String
    public init(name: String, source: String) {
        self.name = name
        self.source = source
    }
}

public enum SkillScripts {
    /// set_level(n) / set_muted(bool) return "<volume>,<muted>" read back.
    public static let volume = SkillScript(name: "volume", source: """
        on set_level(lvl)
            set volume output volume lvl
            return my volume_state()
        end set_level
        on set_muted(m)
            set volume output muted m
            return my volume_state()
        end set_muted
        on volume_state()
            set s to get volume settings
            return ((output volume of s) as text) & "," & ((output muted of s) as text)
        end volume_state
        """)

    /// set_dark(bool) returns the dark mode read back ("true"/"false").
    public static let appearance = SkillScript(name: "appearance", source: """
        on set_dark(onOff)
            tell application "System Events" to tell appearance preferences to set dark mode to onOff
            return my get_dark()
        end set_dark
        on get_dark()
            tell application "System Events" to tell appearance preferences to return (dark mode as text)
        end get_dark
        """)

    /// new_note(name, htmlBody); note_count() is a harmless read (probe).
    public static let notes = SkillScript(name: "notes", source: """
        on new_note(theTitle, theBody)
            tell application "Notes"
                make new note at folder "Notes" with properties {name:theTitle, body:theBody}
            end tell
            return theTitle
        end new_note
        on note_count()
            tell application "Notes" to return (count notes) as text
        end note_count
        """)

    public static let music = SkillScript(name: "music", source: """
        on play_query(q)
            tell application "Music"
                activate
                if (count (every track of library playlist 1 whose name contains q)) > 0 then
                    play (first track of library playlist 1 whose name contains q)
                else if (count (every playlist whose name contains q)) > 0 then
                    play (first playlist whose name contains q)
                else
                    play (first track of library playlist 1 whose artist contains q)
                end if
            end tell
            return q
        end play_query
        """)

    public static let messages = SkillScript(name: "messages", source: """
        on send_text(toWho, msg)
            tell application "Messages"
                send msg to participant toWho of first account
            end tell
            return toWho
        end send_text
        """)

    public static let all: [SkillScript] = [volume, appearance, notes, music, messages]

    /// Argument-free skill sources run with `run(_:)` (cached by source).
    public static let fixedSources: [String] = [
        "output volume of (get volume settings)",
        Skills.volumeStateScript,
        "tell application \"System Events\" to tell appearance preferences to get dark mode",
        "tell application \"Finder\" to empty trash",
    ]
}

// MARK: - Runner

public protocol ScriptRunning {
    /// Compile (cached by source) and run an ad-hoc script (planner
    /// `script applescript`, argument-free skill scripts).
    func run(_ source: String) throws -> String
    /// Call `handler` of the compiled `script` with `args` (String, Int,
    /// Double, Bool). The script is compiled once per process.
    func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String
}

/// One compiled script: NSAppleScript in production, mocks in tests.
public protocol CompiledAppleScript: AnyObject {
    func execute() throws -> String
    func callHandler(_ name: String, args: [Any]) throws -> String
}

/// NSAppleScript-backed compiled script.
public final class NSAppleScriptCompiled: CompiledAppleScript {
    private let script: NSAppleScript

    public init(source: String) throws {
        guard let s = NSAppleScript(source: source) else {
            throw HandsError.skillFailed("applescript init failed")
        }
        var err: NSDictionary?
        guard s.compileAndReturnError(&err) else {
            throw HandsError.skillFailed("applescript compile: \(Self.message(err))")
        }
        script = s
    }

    static func message(_ e: NSDictionary?) -> String {
        (e?["NSAppleScriptErrorMessage"] as? String) ?? e.map { "\($0)" } ?? "unknown error"
    }

    public func execute() throws -> String {
        var err: NSDictionary?
        let out = script.executeAndReturnError(&err)
        if let e = err { throw HandsError.skillFailed("applescript: \(Self.message(e))") }
        return out.stringValue ?? ""
    }

    /// Subroutine event ('ascr'/'psbr'): handler name (lowercased) in
    /// 'snam', positional parameters as a list in the direct object.
    public func callHandler(_ name: String, args: [Any]) throws -> String {
        let event = NSAppleEventDescriptor(
            eventClass: fourCC("ascr"), eventID: fourCC("psbr"),
            targetDescriptor: NSAppleEventDescriptor.currentProcess(),
            returnID: AEReturnID(kAutoGenerateReturnID),
            transactionID: AETransactionID(kAnyTransactionID))
        event.setParam(NSAppleEventDescriptor(string: name.lowercased()), forKeyword: fourCC("snam"))
        let list = NSAppleEventDescriptor.list()
        for (i, a) in args.enumerated() { list.insert(Self.descriptor(a), at: i + 1) }
        event.setParam(list, forKeyword: fourCC("----"))
        var err: NSDictionary?
        let out = script.executeAppleEvent(event, error: &err)
        if let e = err { throw HandsError.skillFailed("applescript: \(Self.message(e))") }
        return out.stringValue ?? ""
    }

    static func descriptor(_ v: Any) -> NSAppleEventDescriptor {
        switch v {
        case let b as Bool: return NSAppleEventDescriptor(boolean: b)
        case let i as Int: return NSAppleEventDescriptor(int32: Int32(clamping: i))
        case let d as Double: return NSAppleEventDescriptor(double: d)
        case let s as String: return NSAppleEventDescriptor(string: s)
        default: return NSAppleEventDescriptor(string: "\(v)")
        }
    }
}

func fourCC(_ s: String) -> FourCharCode {
    s.utf8.reduce(0) { ($0 << 8) | FourCharCode($1) }
}

/// Compiles each source once and caches it. Skill scripts and fixed skill
/// sources are pinned (never evicted); ad-hoc planner scripts live in a
/// 64-entry LRU. One lock serializes compile and execution (OSA is not
/// re-entrant), held per operation only: warm-up compiles one script at a
/// time, so a skill call waits for at most one compile.
public final class AppleScriptRunner: ScriptRunning {
    public typealias Compiler = (String) throws -> CompiledAppleScript
    private static let capacity = 64
    private let compiler: Compiler
    private var pinned: [String: CompiledAppleScript] = [:]
    private var cache: [String: CompiledAppleScript] = [:]
    private var lru: [String] = []          // oldest first
    private let lock = NSLock()
    /// Number of compiles so far (tests / probes).
    public private(set) var compileCount = 0

    public init(compiler: @escaping Compiler = { try NSAppleScriptCompiled(source: $0) }) {
        self.compiler = compiler
    }

    static let pinnedSources: Set<String> =
        Set(SkillScripts.all.map(\.source) + SkillScripts.fixedSources)

    /// Compiled script for `source` (caller holds `lock`).
    private func compiled(_ source: String) throws -> CompiledAppleScript {
        if let s = pinned[source] { return s }
        if let s = cache[source] {
            lru.removeAll { $0 == source }
            lru.append(source)
            return s
        }
        let s = try compiler(source)
        compileCount += 1
        if Self.pinnedSources.contains(source) {
            pinned[source] = s
        } else {
            cache[source] = s
            lru.append(source)
            if lru.count > Self.capacity { cache.removeValue(forKey: lru.removeFirst()) }
        }
        return s
    }

    public func run(_ source: String) throws -> String {
        lock.lock(); defer { lock.unlock() }
        return try compiled(source).execute()
    }

    public func call(_ script: SkillScript, _ handler: String, _ args: [Any]) throws -> String {
        lock.lock(); defer { lock.unlock() }
        return try compiled(script.source).callHandler(handler, args: args)
    }

    /// Is `source` compiled already?
    public func isCompiled(_ source: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return pinned[source] != nil || cache[source] != nil
    }

    /// Compile without running (one lock hold per script). Returns the
    /// compile ms per source; failures are skipped (retried on first use).
    @discardableResult
    public func precompile(_ sources: [String]) -> [(source: String, ms: Double, ok: Bool)] {
        var out: [(String, Double, Bool)] = []
        for src in sources {
            let t0 = Date()
            lock.lock()
            let ok = (try? compiled(src)) != nil
            lock.unlock()
            out.append((src, Date().timeIntervalSince(t0) * 1000, ok))
        }
        return out
    }

    /// Warm-up at startup: compile every skill script (handlers + fixed
    /// sources) WITHOUT running any of them, so no app is launched and no
    /// Automation prompt appears at Muselet start. (The old warm-up ran
    /// the System Events dark-mode read: it launched System Events, could
    /// raise a consent prompt, and held the runner lock meanwhile, which
    /// is how the first set_volume took 9.6 s.)
    public func warmUp() {
        precompile(SkillScripts.all.map(\.source) + SkillScripts.fixedSources)
    }
}
