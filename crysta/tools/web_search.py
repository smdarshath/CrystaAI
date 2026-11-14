"""Free, key-less web research: DuckDuckGo HTML + Wikipedia API + polite page fetching."""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

from ..errors import NetworkError

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0 CrystaAI/1.0"
_robots_cache = {}


def http_get(url, timeout=10, max_bytes=600_000, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept-Language": "en", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(max_bytes + 1)
            charset = r.headers.get_content_charset() or "utf-8"
            return {"status": r.status, "text": raw[:max_bytes].decode(charset, "replace"),
                    "content_type": r.headers.get("Content-Type", ""), "url": r.geturl(), "truncated": len(raw) > max_bytes}
    except urllib.error.HTTPError as e:
        raise NetworkError(f"HTTP {e.code}")
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        raise NetworkError(str(getattr(e, "reason", e)) or "network error")


def get_with_retry(url, retries=1, **kw):
    last = None
    for _ in range(retries + 1):
        try:
            return http_get(url, **kw)
        except NetworkError as e:
            last = e
            if str(e).startswith("HTTP 4"):
                break
    raise last


def is_public_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        for info in socket.getaddrinfo(p.hostname, p.port or 443):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


class _DDG(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results, self._mode, self._buf = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        a = dict(attrs)
        cls = a.get("class") or ""
        if "result__a" in cls:
            self._mode, self._buf = "title", []
            self.results.append({"title": "", "url": self._clean(a.get("href", "")), "snippet": ""})
        elif "result__snippet" in cls and self.results:
            self._mode, self._buf = "snippet", []

    def handle_data(self, data):
        if self._mode:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._mode and self.results:
            self.results[-1][self._mode] = " ".join("".join(self._buf).split())
            self._mode = None

    @staticmethod
    def _clean(href):
        if href.startswith("//"):
            href = "https:" + href
        q = urllib.parse.urlparse(href)
        if "uddg" in q.query:
            return urllib.parse.parse_qs(q.query)["uddg"][0]
        return href


def ddg_search(query, n=8):
    r = get_with_retry("https://html.duckduckgo.com/html/", data=urllib.parse.urlencode({"q": query}).encode(),
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    p = _DDG()
    p.feed(r["text"])
    out = [x for x in p.results if x["url"].startswith("http") and "duckduckgo.com/y.js" not in x["url"] and x["title"]]
    return out[:n]


def wiki_search(query, n=3):
    url = ("https://en.wikipedia.org/w/api.php?action=query&format=json&redirects=1&generator=search"
           f"&gsrlimit={n}&prop=extracts&exintro=1&explaintext=1&exlimit={n}&exsentences=6&gsrsearch="
           + urllib.parse.quote(query))
    data = json.loads(get_with_retry(url)["text"])
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    return [{"title": p["title"], "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
             "text": p.get("extract", "")} for p in pages if p.get("extract")]


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts, self.title, self._skip, self._in_title = [], "", 0, False
        self.links, self._href, self._atext = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and not self._skip:
            self._href, self._atext = dict(attrs).get("href"), []
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((" ".join("".join(self._atext).split())[:120], self._href))
            self._href = None
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)
            if self._href is not None:
                self._atext.append(data)


def html_to_text(html, with_links=False):
    p = _Text()
    p.feed(html)
    text = re.sub(r"[ \t]+", " ", "".join(p.parts))
    out = (" ".join(p.title.split()), re.sub(r"\n\s*\n+", "\n", text).strip())
    return out + (p.links,) if with_links else out


def robots_allows(url):
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    rp = _robots_cache.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            txt = http_get(base + "/robots.txt", timeout=5, max_bytes=100_000)["text"]
            rp.parse(txt.splitlines())
        except NetworkError:
            rp = False  # robots unreachable -> allowed
        _robots_cache[base] = rp
    return True if rp is False else rp.can_fetch(UA, url)


def fetch_page(url, max_chars=20000):
    if not is_public_url(url):
        raise NetworkError("That address is not a public web page, so I won't fetch it.")
    if not robots_allows(url):
        raise NetworkError("The site's robots.txt asks automated tools not to read this page.")
    r = get_with_retry(url)
    if "html" not in r["content_type"] and "text" not in r["content_type"]:
        raise NetworkError(f"Not a readable web page ({r['content_type'] or 'unknown type'}).")
    title, text, raw_links = html_to_text(r["text"], with_links=True)
    links = []
    for label, href in raw_links[:400]:
        full = urllib.parse.urljoin(r["url"], href)
        if full.startswith(("http://", "https://")):
            links.append({"text": label, "href": full})
    return {"url": r["url"], "title": title or url, "text": text[:max_chars], "links": links, "untrusted": True}
