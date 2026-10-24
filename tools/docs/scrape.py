"""Scrape product docs into an offline Q&A corpus (ANSWER intent).

Output: data/docs/docs_corpus.jsonl  records {"id","product","url","title","section","text"}
        tools/docs/stats.json         pages / chunks / tokens per product (committed)
The corpus is copyrighted vendor documentation: never commit it. Upload only to a PRIVATE HF dataset.

Usage:
  python tools/docs/scrape.py [--products numbers,macos,premiere] [--upload ardahk/muselet-docs]
Deps: requests, beautifulsoup4, (optional) tokenizers, huggingface_hub (upload only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "docs" / "cache"
CORPUS = ROOT / "data" / "docs" / "docs_corpus.jsonl"
STATS = Path(__file__).resolve().parent / "stats.json"

UA = "muselet-docs-scraper/0.1 (offline help corpus for a personal on-device assistant; contact hoke@berkeley.edu)"
DELAY_S = 1.0
MAX_WORDS = 350
PREMIERE_CAP = 400

SOURCES = {
    "premiere": {
        "product": "Adobe Premiere Pro",
        "index": "https://helpx.adobe.com/premiere-pro/user-guide.html",
        "extra": ["https://helpx.adobe.com/premiere-pro/using/default-keyboard-shortcuts.html"],
        "link_re": re.compile(r"^https://helpx\.adobe\.com/premiere-pro/(using|how-to)/[^?#]+\.html$"),
        "cap": PREMIERE_CAP,
    },
    "numbers": {
        "product": "Apple Numbers for Mac",
        "index": "https://support.apple.com/guide/numbers/welcome/mac",
        "extra": [],
        "link_re": re.compile(r"^https://support\.apple\.com/guide/numbers/[a-z0-9-]+/mac$"),
        "cap": 10_000,
    },
    "macos": {
        "product": "macOS",
        "index": None,
        "extra": ["https://support.apple.com/en-us/102650"],
        "link_re": None,
        "cap": 1,
    },
}

CHROME_SELECTORS = [
    "script", "style", "noscript", "svg", "header", "nav", "footer", "aside", "form", "button",
    "#globalnav", "#ac-globalnav", ".globalnav", "#ac-gn-placeholder", "#ac-globalfooter", ".ac-gf-content",
    "#toc-container", "#toc-section-wrapper", "#modal-toc-container", ".as-search", "#feedback-state",
    "#rating-done", ".localnav", ".breadcrumbs", ".feedback", "[role=navigation]", "[aria-hidden=true]",
]


class Fetcher:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.last = 0.0
        self.requests = 0

    def allowed(self, url: str) -> bool:
        host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if host not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._get(host + "/robots.txt")
                if r.status_code in (401, 403):
                    rp.disallow_all = True  # same policy as urllib.robotparser.read()
                elif r.status_code >= 400:
                    rp.allow_all = True
                else:
                    rp.parse(r.text.splitlines())
            except requests.RequestException:
                rp.disallow_all = True
            self.robots[host] = rp
        return self.robots[host].can_fetch(UA, url)

    def _get(self, url: str) -> requests.Response:
        wait = DELAY_S - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        self.requests += 1
        return self.s.get(url, timeout=30)

    def html(self, url: str) -> str | None:
        key = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")
        if key.exists():
            return key.read_text()
        if not self.allowed(url):
            print(f"  robots.txt disallows (or blocks) {url}", file=sys.stderr)
            return None
        for attempt in range(3):
            try:
                r = self._get(url)
            except requests.RequestException as e:
                print(f"  error {url}: {e}", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                CACHE.mkdir(parents=True, exist_ok=True)
                key.write_text(r.text)
                return r.text
            if r.status_code in (429, 503):
                time.sleep(int(r.headers.get("Retry-After", 5 * (attempt + 1))))
                continue
            print(f"  HTTP {r.status_code} {url}", file=sys.stderr)
            return None
        return None


def norm(url: str) -> str:
    return urldefrag(url)[0].split("?")[0]


def discover(f: Fetcher, src: dict) -> list[str]:
    urls = []
    if src["index"]:
        page = f.html(src["index"])
        if page:
            soup = BeautifulSoup(page, "html.parser")
            for a in soup.find_all("a", href=True):
                u = norm(urljoin(src["index"], a["href"]))
                if src["link_re"].match(u) and u not in urls:
                    urls.append(u)
    urls = urls[: src["cap"]]
    for u in src["extra"]:
        if u not in urls:
            urls.append(u)
    return urls


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def content_root(soup: BeautifulSoup) -> Tag:
    for sel in CHROME_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    body = soup.body or soup
    total = len(body.find_all(["p", "li", "tr"])) or 1
    h1 = body.find("h1")
    node = h1
    while node is not None and node is not body:
        if len(node.find_all(["p", "li", "tr"])) >= 0.8 * total:
            return node
        node = node.parent
    return body


def table_rows(table: Tag) -> list[str]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append(" | ".join(cells))
    return rows


BLOCK_TAGS = {"p", "li", "pre", "dt", "dd", "figcaption", "blockquote"}
HEAD_TAGS = {"h1", "h2", "h3", "h4"}


def blocks(root: Tag):
    """Yield ("h", level, text) | ("p", text) | ("table", [rows]) in document order."""
    def walk(node: Tag):
        for child in node.children:
            if isinstance(child, NavigableString) or not isinstance(child, Tag):
                continue
            name = child.name
            if name in HEAD_TAGS:
                t = clean(child.get_text(" "))
                if t:
                    yield ("h", int(name[1]), t)
            elif name == "table":
                rows = table_rows(child)
                if rows:
                    yield ("table", rows)
            elif name in BLOCK_TAGS and not child.find(list(BLOCK_TAGS | HEAD_TAGS | {"table"})):
                t = clean(child.get_text(" "))
                if t:
                    yield ("p", ("- " + t) if name == "li" else t)
            else:
                yield from walk(child)
    yield from walk(root)


def words(t: str) -> int:
    return len(t.split())


def split_long(text: str) -> list[str]:
    out, cur = [], []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if cur and words(" ".join(cur + [sent])) > MAX_WORDS:
            out.append(" ".join(cur))
            cur = []
        cur.append(sent)
    if cur:
        out.append(" ".join(cur))
    return [o if words(o) <= MAX_WORDS else " ".join(o.split()[:MAX_WORDS]) for o in out]


def chunk_page(url: str, html: str, product: str, key: str) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    page_title = clean(soup.title.get_text()) if soup.title else url
    page_title = re.sub(r"\s*[-|]\s*(Apple Support|Adobe Inc\.?|Adobe Help Center).*$", "", page_title)
    root = content_root(soup)
    title = page_title
    sections: list[tuple[str, list[str]]] = []
    heads: dict[int, str] = {}
    cur_section, cur = None, []
    for b in blocks(root):
        if b[0] == "h":
            _, lvl, t = b
            if lvl == 1:
                title = t
                continue
            if cur:
                sections.append((cur_section or title, cur))
            heads = {k: v for k, v in heads.items() if k < lvl}
            heads[lvl] = t
            cur_section, cur = " > ".join(heads[k] for k in sorted(heads)), []
        elif b[0] == "p":
            cur.append(b[1])
        else:
            rows = b[1]
            if words("\n".join(rows)) <= MAX_WORDS:
                cur.append("\n".join(rows))
            else:  # keep rows intact; repeat the header row on every piece
                header, piece = rows[0], [rows[0]]
                for r in rows[1:]:
                    if len(piece) > 1 and words("\n".join(piece + [r])) > MAX_WORDS:
                        cur.append("\n".join(piece))
                        piece = [header]
                    piece.append(r)
                if len(piece) > 1:
                    cur.append("\n".join(piece))
    if cur:
        sections.append((cur_section or title, cur))

    chunks = []
    for section, paras in sections:
        buf: list[str] = []
        pieces: list[str] = []
        for p in paras:
            for q in ([p] if words(p) <= MAX_WORDS else split_long(p)):
                if buf and words("\n".join(buf + [q])) > MAX_WORDS:
                    pieces.append("\n".join(buf))
                    buf = []
                buf.append(q)
        if buf:
            pieces.append("\n".join(buf))
        for text in pieces:
            cid = f"{key}-{hashlib.sha1((url + section + text).encode()).hexdigest()[:12]}"
            chunks.append({"id": cid, "product": product, "url": url, "title": title, "section": section, "text": text})
    return title, chunks


def token_counter():
    try:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_pretrained("Qwen/Qwen3-0.6B")
        return "Qwen/Qwen3-0.6B", lambda t: len(tok.encode(t, add_special_tokens=False).ids)
    except Exception:
        return "words*1.33 (estimate)", lambda t: round(words(t) * 1.33)


def upload(repo: str) -> None:
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    info = api.repo_info(repo, repo_type="dataset")
    if not info.private:
        raise SystemExit(f"{repo} exists and is PUBLIC; refusing to upload copyrighted docs")
    api.upload_file(path_or_fileobj=str(CORPUS), path_in_repo="docs_corpus.jsonl", repo_id=repo, repo_type="dataset")
    api.upload_file(path_or_fileobj=str(STATS), path_in_repo="stats.json", repo_id=repo, repo_type="dataset")
    print(f"uploaded to https://huggingface.co/datasets/{repo} (private)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", default="premiere,numbers,macos")
    ap.add_argument("--upload", metavar="REPO", help="private HF dataset repo id, e.g. ardahk/muselet-docs")
    args = ap.parse_args()

    f = Fetcher()
    tok_name, ntok = token_counter()
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    stats = {"tokenizer": tok_name, "max_words": MAX_WORDS, "products": {}}
    seen_ids = set()
    with CORPUS.open("w") as out:
        for key in args.products.split(","):
            src = SOURCES[key]
            urls = discover(f, src)
            print(f"[{key}] {len(urls)} candidate pages", file=sys.stderr)
            pages = chunks = tokens = 0
            failed = []
            for u in urls:
                html = f.html(u)
                if not html:
                    failed.append(u)
                    continue
                _, cs = chunk_page(u, html, src["product"], key)
                cs = [c for c in cs if c["id"] not in seen_ids]
                if not cs:
                    continue
                pages += 1
                for c in cs:
                    seen_ids.add(c["id"])
                    out.write(json.dumps(c, ensure_ascii=False) + "\n")
                    chunks += 1
                    tokens += ntok(c["text"])
            stats["products"][src["product"]] = {
                "pages": pages, "chunks": chunks, "tokens": tokens, "failed_pages": len(failed),
                "sources": [src["index"]] + src["extra"] if src["index"] else src["extra"],
            }
            print(f"[{key}] pages={pages} chunks={chunks} tokens={tokens} failed={len(failed)}", file=sys.stderr)
    STATS.write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))
    if args.upload:
        upload(args.upload)


if __name__ == "__main__":
    main()
