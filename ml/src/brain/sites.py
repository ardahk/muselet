"""Spoken website names and URL normalization."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit


def normalize_name(value: str) -> str:
    """Normalize a spoken site/app name for table lookup."""
    s = str(value or "").strip().casefold()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"\s+(?:website|site)\s*$", "", s)
    s = re.sub(r"\s*(?:\.com|dot\s+com)\s*$", "", s)
    return re.sub(r"[\s\-]+", "", s)


# Keep aliases in normalized form.  This intentionally includes common web
# apps that do not have a native Mac application.
SITES: dict[str, str] = {
    "gmail": "mail.google.com", "google": "google.com",
    "googledocs": "docs.google.com", "googlesheets": "sheets.google.com",
    "googleslides": "slides.google.com", "googlecalendar": "calendar.google.com",
    "googledrive": "drive.google.com", "googlemaps": "maps.google.com",
    "googlemeet": "meet.google.com", "youtube": "youtube.com",
    "wikipedia": "wikipedia.org", "reddit": "reddit.com",
    "github": "github.com", "gitlab": "gitlab.com", "bitbucket": "bitbucket.org",
    "linkedin": "linkedin.com", "facebook": "facebook.com",
    "instagram": "instagram.com", "threads": "threads.net",
    "tiktok": "tiktok.com", "snapchat": "snapchat.com",
    "pinterest": "pinterest.com", "x": "x.com", "twitter": "x.com",
    "mastodon": "mastodon.social", "bluesky": "bsky.app",
    "amazon": "amazon.com", "ebay": "ebay.com", "walmart": "walmart.com",
    "target": "target.com", "etsy": "etsy.com", "bestbuy": "bestbuy.com",
    "costco": "costco.com", "homedepot": "homedepot.com",
    "lowes": "lowes.com", "wayfair": "wayfair.com",
    "netflix": "netflix.com", "hulu": "hulu.com", "disneyplus": "disneyplus.com",
    "max": "max.com", "hbomax": "max.com", "primevideo": "primevideo.com",
    "peacock": "peacocktv.com", "paramountplus": "paramountplus.com",
    "spotify": "spotify.com", "soundcloud": "soundcloud.com",
    "twitch": "twitch.tv", "vimeo": "vimeo.com", "crunchyroll": "crunchyroll.com",
    "chatgpt": "chatgpt.com", "claude": "claude.ai", "gemini": "gemini.google.com",
    "copilot": "copilot.microsoft.com", "perplexity": "perplexity.ai",
    "notion": "notion.so", "figma": "figma.com", "canva": "canva.com",
    "miro": "miro.com", "trello": "trello.com", "asana": "asana.com",
    "monday": "monday.com", "airtable": "airtable.com", "slack": "slack.com",
    "discord": "discord.com", "zoom": "zoom.us", "teams": "teams.microsoft.com",
    "microsoftteams": "teams.microsoft.com", "telegram": "web.telegram.org",
    "whatsapp": "web.whatsapp.com", "messenger": "messenger.com",
    "signal": "signal.org", "wechat": "web.wechat.com",
    "canvas": "bcourses.berkeley.edu", "bcourses": "bcourses.berkeley.edu",
    "berkeley": "berkeley.edu", "coursera": "coursera.org",
    "udemy": "udemy.com", "edx": "edx.org", "khanacademy": "khanacademy.org",
    "duolingo": "duolingo.com", "quizlet": "quizlet.com",
    "nytimes": "nytimes.com", "washingtonpost": "washingtonpost.com",
    "theguardian": "theguardian.com", "bbc": "bbc.com",
    "cnn": "cnn.com", "foxnews": "foxnews.com", "npr": "npr.org",
    "reuters": "reuters.com", "apnews": "apnews.com",
    "bloomberg": "bloomberg.com", "wsj": "wsj.com",
    "forbes": "forbes.com", "usatoday": "usatoday.com",
    "yahoo": "yahoo.com", "bing": "bing.com", "duckduckgo": "duckduckgo.com",
    "weather": "weather.com", "accuweather": "accuweather.com",
    "imdb": "imdb.com", "rottentomatoes": "rottentomatoes.com",
    "goodreads": "goodreads.com", "yelp": "yelp.com",
    "tripadvisor": "tripadvisor.com", "airbnb": "airbnb.com",
    "expedia": "expedia.com", "booking": "booking.com",
    "paypal": "paypal.com", "venmo": "venmo.com", "chase": "chase.com",
    "bankofamerica": "bankofamerica.com", "wellsfargo": "wellsfargo.com",
    "stripe": "stripe.com", "dropbox": "dropbox.com",
    "box": "box.com", "icloud": "icloud.com", "outlook": "outlook.live.com",
    "hotmail": "outlook.live.com", "office": "office.com",
    "microsoft365": "microsoft365.com", "apple": "apple.com",
    "developer.apple": "developer.apple.com", "stackoverflow": "stackoverflow.com",
    "npm": "npmjs.com", "pypi": "pypi.org", "dockerhub": "hub.docker.com",
    "vercel": "vercel.com", "netlify": "netlify.com", "heroku": "heroku.com",
    "digitalocean": "digitalocean.com", "aws": "aws.amazon.com",
    "azure": "azure.microsoft.com", "rust": "rust-lang.org",
    "python": "python.org", "mdn": "developer.mozilla.org",
    "producthunt": "producthunt.com", "hackernews": "news.ycombinator.com",
    "craigslist": "craigslist.org", "indeed": "indeed.com",
    "glassdoor": "glassdoor.com", "ziprecruiter": "ziprecruiter.com",
    "dribbble": "dribbble.com", "behance": "behance.net",
    "unsplash": "unsplash.com", "deviantart": "deviantart.com",
    "webmd": "webmd.com", "mayoclinic": "mayoclinic.org",
    "espn": "espn.com", "nfl": "nfl.com", "nba": "nba.com",
}


def _host_key(host: str) -> str:
    return normalize_name(host.split(":", 1)[0].rstrip("."))


def match_name(text: str) -> tuple[str, str] | None:
    """Find the longest whole spoken site name in text."""
    words = re.findall(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", str(text or ""))
    for start in range(len(words)):
        joined = ""
        for end in range(start, len(words)):
            joined += normalize_name(words[end])
            if joined in SITES:
                best = (joined, SITES[joined])
            else:
                best = None
            if best and (end == len(words) - 1 or
                         normalize_name("".join(words[start:end + 2])) not in SITES):
                # Continue extending to prefer a longer alias such as
                # "google docs" over "google".
                longer = False
                for stop in range(end + 1, len(words)):
                    if normalize_name("".join(words[start:stop + 1])) in SITES:
                        longer = True
                        break
                if not longer:
                    return best
    return None


def fix_url(value: str) -> str:
    """Return an HTTPS URL, expanding bare spoken hosts through ``SITES``."""
    raw = str(value or "").strip()
    if not raw:
        return "https://"
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = parsed.hostname or ""
    if not host:
        # urlsplit treats a bare value with spaces as a path in some cases.
        host = raw.split("/", 1)[0].split("?", 1)[0]
        path = "/" + raw[len(raw.split("/", 1)[0]):].lstrip("/") \
            if "/" in raw else ""
        parsed = urlsplit(f"https://{host}{path}")
        host = parsed.hostname or host
    host = host.rstrip(".").casefold()
    try:
        address = ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        address = None
        is_ip = False
    if "." not in host and host.casefold() not in {"localhost"} and not is_ip:
        host = SITES.get(_host_key(host), f"{_host_key(host)}.com")
    port = f":{parsed.port}" if parsed.port else ""
    if isinstance(address, ipaddress.IPv6Address):
        host = f"[{host}]"
    return urlunsplit(("https", f"{host}{port}", parsed.path,
                       parsed.query, parsed.fragment))
