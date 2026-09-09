"""General-purpose web crawler used by Model Lab.

The crawler is deliberately polite and bounded: it honors robots.txt when configured,
uses request timeouts/retries, stays within configured depth/page budgets, applies
source-quality gating, and emits canonical :class:`pipeline.types.Document` records.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from pipeline.crawler.base import BaseCrawler
from pipeline.crawler.source_scorer import classify_text, classify_url, detect_code_language, score_document
from pipeline.types import Document

log = logging.getLogger("crawler.web")


class WebCrawler(BaseCrawler):
    def __init__(self, cfg: dict, weight_lookup, signal_tracker):
        super().__init__(cfg, weight_lookup, signal_tracker)
        self.web = cfg.get("web", {})
        self.max_depth = int(self.web.get("max_depth", 2))
        self.max_pages_per_domain = int(self.web.get("max_pages_per_domain", 500))
        self.timeout = float(cfg.get("request_timeout", self.web.get("request_timeout", 15)))
        self.retries = int(cfg.get("retry_attempts", 3))
        self.backoff = float(cfg.get("retry_backoff", 2.0))
        self.delay = float(cfg.get("politeness_delay", 1.0))
        self.follow_links = bool(self.web.get("follow_links", True))
        self.stay_on_domain = bool(self.web.get("stay_on_domain", False))
        self.respect_robots = bool(self.web.get("respect_robots_txt", True))
        self.allow = [re.compile(p) for p in self.web.get("url_allowlist_patterns", []) if p]
        self.block = [re.compile(p) for p in self.web.get("url_blocklist_patterns", []) if p]
        self.user_agent = str(cfg.get("user_agent", "ModelLab/1.3 (+local research dataset builder)"))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"})
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}
        self._seen_urls: set[str] = set()
        self._domain_pages: dict[str, int] = {}

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        if self.block and any(p.search(url) for p in self.block):
            return False
        return not self.allow or any(p.search(url) for p in self.allow)

    def _robots_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._robots.get(root)
        if rp is None:
            rp = RobotFileParser(urljoin(root, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                self._robots[root] = RobotFileParser()
                return True
            self._robots[root] = rp
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _polite_wait(self, domain: str) -> None:
        now = time.monotonic()
        delta = now - self._last_request.get(domain, 0.0)
        if delta < self.delay:
            time.sleep(self.delay - delta)
        self._last_request[domain] = time.monotonic()

    def _fetch(self, url: str):
        domain = urlparse(url).netloc.lower()
        self._polite_wait(domain)
        last = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else self.backoff * (attempt + 1)
                    time.sleep(min(wait, 60.0))
                    continue
                response.raise_for_status()
                self.stats["fetched"] += 1
                return response
            except requests.RequestException as exc:
                last = exc
                self.stats["errors"] += 1
                if attempt < self.retries:
                    time.sleep(self.backoff * (attempt + 1))
        if last:
            log.warning("fetch failed %s: %s", url, last)
        return None

    def _extract(self, url: str, html: str) -> tuple[str, str, list[str]]:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for tag in soup(["script", "style", "noscript", "nav", "footer", "aside", "form", "iframe"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        links = [urljoin(url, a.get("href")) for a in soup.find_all("a", href=True)]
        return title, text, links

    def _document(self, url: str, title: str, text: str, depth: int) -> Document:
        parsed = urlparse(url)
        doc = Document(
            doc_id=hashlib.sha256(url.encode("utf-8")).hexdigest(),
            url=url,
            source="web",
            text=text,
            title=title,
            content_type=classify_url(url),
            code_language=detect_code_language(url),
            domain=parsed.netloc.lower(),
            crawl_depth=depth,
        )
        if doc.content_type == "unknown":
            doc.content_type = classify_text(text)
        doc.meta.update({"quality_signal": score_document(url, text)})
        self.signal_tracker.record(doc.domain, doc.meta["quality_signal"])
        return self._apply_weights(doc)

    def crawl(self):
        seeds = list(self.web.get("seed_urls", []))
        queue = deque((u, 0, u) for u in seeds if self._allowed(u))
        while queue:
            url, depth, origin = queue.popleft()
            normalized = url.split("#", 1)[0]
            if normalized in self._seen_urls or not self._allowed(normalized):
                continue
            domain = urlparse(normalized).netloc.lower()
            if self._domain_pages.get(domain, 0) >= self.max_pages_per_domain:
                self.stats["skipped"] += 1
                continue
            if self.signal_tracker.should_abandon(domain):
                self.stats["abandoned_domains"] += 1
                continue
            if not self._robots_allowed(normalized):
                self.stats["skipped"] += 1
                continue
            self._seen_urls.add(normalized)
            response = self._fetch(normalized)
            if response is None:
                continue
            final_url = response.url.split("#", 1)[0]
            ctype = response.headers.get("Content-Type", "").lower()
            if "html" not in ctype and "xhtml" not in ctype:
                self.stats["skipped"] += 1
                continue
            self._domain_pages[domain] = self._domain_pages.get(domain, 0) + 1
            max_bytes = int(self.web.get("max_content_bytes", 5_000_000))
            if len(response.content) > max_bytes:
                self.stats["skipped"] += 1
                continue
            title, text, links = self._extract(final_url, response.text)
            if not text:
                self.stats["skipped"] += 1
                continue
            doc = self._document(final_url, title, text, depth)
            yield doc
            if not self.follow_links or depth >= self.max_depth:
                continue
            for link in links:
                link = link.split("#", 1)[0]
                if not self._allowed(link):
                    continue
                if self.stay_on_domain and urlparse(link).netloc.lower() != urlparse(origin).netloc.lower():
                    continue
                if link not in self._seen_urls:
                    queue.append((link, depth + 1, origin))
