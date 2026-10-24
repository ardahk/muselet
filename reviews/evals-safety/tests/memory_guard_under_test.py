"""Safety guard against follow-up rewrites adding irreversible actions."""

import re


IRREVERSIBLE = re.compile(
    r"\b(send|text|message|email|mail|delete|trash|remove|erase|empty|buy|"
    r"purchase|order|pay|post|tweet|publish|submit|quit|shut ?down|restart|"
    r"lock|sign out|log out|format|uninstall)\b", re.IGNORECASE)


def allowed(before: str, after: str) -> bool:
    original = {match.group(0).casefold()
                for match in IRREVERSIBLE.finditer(before)}
    return all(match.group(0).casefold() in original
               for match in IRREVERSIBLE.finditer(after))
