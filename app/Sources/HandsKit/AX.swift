import ApplicationServices
import Foundation

/// Batched attribute snapshot of one AX element.
public struct ElAttrs {
    public var role: String?
    public var subrole: String?
    public var title: String?
    public var desc: String?
    public var value: Any?
    public var placeholder: String?
    public var help: String?
    public var enabled: Bool = true
    public var focused: Bool = false
    public var selected: Bool?
    public var position: CGPoint = .zero
    public var size: CGSize = .zero
    public var children: [Element] = []
    public var frame: CGRect { CGRect(origin: position, size: size) }
    public init() {}
}

/// Abstraction over AXUIElement so tests can drive a mock tree.
public protocol Element: AnyObject {
    /// Fetch the full attribute batch (role, subrole, title, description,
    /// value, placeholder, help, enabled, focused, selected, position, size, children).
    func copyAttrs() -> ElAttrs
    func setMessagingTimeout(_ seconds: Float)
    func performAction(_ name: String) -> Bool
    func setAttr(_ name: String, _ value: Any?) -> Bool
    func isSettable(_ name: String) -> Bool
    /// Fetch a single attribute on demand (used sparingly, e.g. menu bar).
    func copySingleAttr(_ name: String) -> Any?
    /// Identity token for session bookkeeping (CFHash for AXUIElement).
    var stableId: Int { get }
    /// False once the underlying UI element is destroyed
    /// (kAXErrorInvalidUIElement). Used by `gone #ref`.
    func isAlive() -> Bool
}

public extension Element {
    func setMessagingTimeout(_ seconds: Float) {}
    func copySingleAttr(_ name: String) -> Any? { nil }
    var stableId: Int { ObjectIdentifier(self).hashValue }
    func isAlive() -> Bool { true }
}

private let kAttrNames: [String] = [
    kAXRoleAttribute, kAXSubroleAttribute, kAXTitleAttribute, kAXDescriptionAttribute,
    kAXValueAttribute, kAXPlaceholderValueAttribute, kAXHelpAttribute, kAXEnabledAttribute,
    kAXFocusedAttribute, kAXSelectedAttribute, kAXPositionAttribute, kAXSizeAttribute,
    kAXChildrenAttribute,
]

public final class AXNode: Element {
    public let el: AXUIElement
    private var timeoutSet = false
    public init(_ el: AXUIElement) { self.el = el }

    /// AXUIElement identity: stable for the same underlying element across
    /// calls; used as the window-session key (survives title changes).
    public var stableId: Int { Int(CFHash(el)) }

    public func setMessagingTimeout(_ seconds: Float) {
        AXUIElementSetMessagingTimeout(el, seconds)
        timeoutSet = true
    }

    public func copyAttrs() -> ElAttrs {
        if !timeoutSet { setMessagingTimeout(0.25) }
        var out = ElAttrs()
        var values: CFArray?
        let err = AXUIElementCopyMultipleAttributeValues(
            el, kAttrNames as CFArray, [], &values)
        guard err == .success, let arr = values as? [Any] else { return out }
        func val<T>(_ i: Int) -> T? {
            guard i < arr.count else { return nil }
            if arr[i] is NSNull { return nil }
            return arr[i] as? T
        }
        out.role = val(0)
        out.subrole = val(1)
        out.title = val(2)
        out.desc = val(3)
        out.value = val(4)
        out.placeholder = val(5)
        out.help = val(6)
        if let e: Bool = val(7) { out.enabled = e }
        if let f: Bool = val(8) { out.focused = f }
        out.selected = val(9)
        if let p: AXValue = val(10) {
            var pt = CGPoint.zero
            if AXValueGetValue(p, .cgPoint, &pt) { out.position = pt }
        }
        if let s: AXValue = val(11) {
            var sz = CGSize.zero
            if AXValueGetValue(s, .cgSize, &sz) { out.size = sz }
        }
        if let kids = val(12) as [AXUIElement]? {
            out.children = kids.map { AXNode($0) }
        } else if let raw = val(12) as [Any]? {
            out.children = raw.map { AXNode($0 as! AXUIElement) }
        }
        return out
    }

    public func performAction(_ name: String) -> Bool {
        if !timeoutSet { setMessagingTimeout(0.25) }
        return AXUIElementPerformAction(el, name as CFString) == .success
    }

    public func setAttr(_ name: String, _ value: Any?) -> Bool {
        if !timeoutSet { setMessagingTimeout(0.25) }
        return AXUIElementSetAttributeValue(el, name as CFString, value as CFTypeRef) == .success
    }

    public func isSettable(_ name: String) -> Bool {
        if !timeoutSet { setMessagingTimeout(0.25) }
        var settable: DarwinBoolean = false
        AXUIElementIsAttributeSettable(el, name as CFString, &settable)
        return settable.boolValue
    }

    public func copySingleAttr(_ name: String) -> Any? {
        if !timeoutSet { setMessagingTimeout(0.25) }
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(el, name as CFString, &v) == .success else { return nil }
        return v
    }

    public func isAlive() -> Bool {
        if !timeoutSet { setMessagingTimeout(0.25) }
        var v: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(el, kAXRoleAttribute as CFString, &v)
        // Timeouts / cannot-complete mean "busy", not destroyed.
        return err != .invalidUIElement
    }
}

/// Identity comparison for CF-based elements.
public func sameElement(_ a: Element, _ b: Element) -> Bool {
    if let x = a as? AXNode, let y = b as? AXNode { return CFEqual(x.el, y.el) }
    return a === b
}
