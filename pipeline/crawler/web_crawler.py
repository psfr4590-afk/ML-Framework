"""General-purpose web crawler used by Model Lab.

The crawler is deliberately polite and bounded: it honors robots.txt when configured,
uses request timeouts/retries, stays within configured depth/page budgets, applies
source-quality gating, and emits canonical :class:`pipeline.types.Document` records.
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import socket
import time
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from pipeline.crawler.base import BaseCrawler
from pipeline.crawler.content_parser import ContentParseError, parse_content
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
