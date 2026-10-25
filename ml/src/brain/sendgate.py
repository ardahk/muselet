"""Pure predicates for detecting message composers and send actions."""

import re


_COMPOSER_NAMES = (
    "Discord", "WhatsApp", "Microsoft Teams", "Teams", "Telegram", "Signal",
    "Messenger", "WeChat", "Zoom", "Skype", "Google Chat", "Messages", "Mail",
    "Slack", "Outlook",
)
_BUNDLE_IDS = {
    "com.hnc.discord", "net.whatsapp.whatsapp", "com.microsoft.teams2",
    "com.microsoft.teams", "ru.keepcoder.telegram", "org.telegram.desktop",
    "org.whispersystems.signal-desktop", "com.facebook.archon",
    "com.tencent.xinwechat", "us.zoom.xos", "com.skype.skype",
    "com.apple.mobilesms", "com.apple.mail", "com.tinyspeck.slackmacgap",
}
_BROWSER_NAMES = (
    "Safari", "Google Chrome", "Chrome", "Arc", "Firefox", "Microsoft Edge",
    "Brave Browser", "Zen", "Zen Browser", "Vivaldi", "Opera", "Orion",
)
_COMPOSER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(name) for name in _COMPOSER_NAMES) + r")\b",
    re.IGNORECASE,
)
_BROWSER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(name) for name in _BROWSER_NAMES) + r")\b",
    re.IGNORECASE,
)
_BROWSER_TITLE_RE = re.compile(
    r"\b(?:" + "|".join(
        re.escape(name) for name in (*_COMPOSER_NAMES, "Gmail")) + r")\b",
    re.IGNORECASE,
)
_COMPOSER_FIELD_RE = re.compile(
    r"\b(message|reply|chat|comment|post|tweet|compose|send)\b|\bwrite a\b",
    re.IGNORECASE,
)
_PAYMENT_CONTEXT_RE = re.compile(
    r"\b(checkout|check out|payments?|pay|billing|banking?)\b",
    re.IGNORECASE,
)
_CLICK_DANGEROUS_RE = re.compile(
    r"\b(send|pay|buy|purchase|delete|remove|post|submit|transfer|"
    r"confirm order|place order)\b", re.IGNORECASE)
_COMPOSER_SIGNAL_RE = re.compile(
    r"\b(inbox|messages?|messaging|reply|compose|send|recipient|subject)\b"
    r"|^\s*(?:to|cc|bcc)\s*(?::|$)", re.IGNORECASE)
_MESSAGE_INTENT_RE = re.compile(
    r"\b(send(?:ing)?|reply(?:ing)?|messag(?:e|es|ing))\b", re.IGNORECASE)


def has_composer_signals(window_title, elements, goal) -> bool:
    if _MESSAGE_INTENT_RE.search(str(goal or "")):
        return True
    labels = [window_title, *(element.get("label") for element in elements or [])]
    return any(_COMPOSER_SIGNAL_RE.search(str(label or "")) for label in labels)


def is_composer_app(app: str | None, window_title: str | None = None) -> bool:
    """Whether an app, or a browser's window title, identifies a composer."""
    app = str(app or "")
    if app.casefold().strip() in _BUNDLE_IDS or _COMPOSER_RE.search(app):
        return True
    return bool(_BROWSER_RE.search(app) and
                _BROWSER_TITLE_RE.search(str(window_title or "")))


def is_browser(app: str | None) -> bool:
    """Whether an app name identifies a supported browser."""
    return bool(_BROWSER_RE.search(str(app or "")))


_SEARCH_FIELD_RE = re.compile(r"\b(search|find)\b", re.IGNORECASE)


def enter_sends(app, window_title, focused_role, focused_label) -> bool:
    """Whether Enter in the current app/focused element could send a message."""
    if _SEARCH_FIELD_RE.search(str(focused_label or "")):
        return False   # a find/search field can't send anything
    if is_composer_app(app, window_title):
        return True
    role = str(focused_role or "").strip().casefold()
    return role in {"textarea", "textfield", "combobox"} and bool(
        _COMPOSER_FIELD_RE.search(str(focused_label or "")))


def is_payment_context(value) -> bool:
    return bool(_PAYMENT_CONTEXT_RE.search(str(value or "")))


def click_ocr_hit(text) -> str | None:
    """Return the matched dangerous OCR phrase, if any."""
    match = _CLICK_DANGEROUS_RE.search(str(text or ""))
    return match.group(0) if match else None
