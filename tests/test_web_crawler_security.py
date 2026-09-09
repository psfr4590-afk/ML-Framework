from __future__ import annotations

import io

import requests

from pipeline.crawler.web_crawler import WebCrawler


class _DummyLookup:
    def domain_weight(self, domain):
        return 1.0, "general"

    def content_type_weight(self, content_type):
        return 1.0

    def quality_score(self, text):
        return 1.0

    def code_language_weight(self, language):
        return 1.0


class _DummySignals:
    def should_abandon(self, domain):
        return False

    def record(self, domain, score):
        pass


def _crawler(monkeypatch):
    monkeypatch.setattr("pipeline.crawler.web_crawler.time.sleep", lambda _: None)
    crawler = WebCrawler(
        {"web": {"respect_robots_txt": False, "max_redirects": 3}},
        _DummyLookup(),
        _DummySignals(),
    )
    return crawler


def test_private_ip_targets_are_rejected_without_network(monkeypatch):
    crawler = _crawler(monkeypatch)
    assert not crawler._allowed("http://127.0.0.1:8080/admin")
    assert not crawler._allowed("http://169.254.169.254/latest/meta-data/")
    assert not crawler._allowed("http://10.0.0.7/internal")


def test_hostname_with_private_resolution_is_rejected(monkeypatch):
    crawler = _crawler(monkeypatch)
    monkeypatch.setattr(
        "pipeline.crawler.web_crawler.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("192.168.1.20", 0))],
    )
    assert not crawler._allowed("https://example.test/")


def test_redirect_to_private_address_is_blocked(monkeypatch):
    crawler = _crawler(monkeypatch)
    monkeypatch.setattr(
        "pipeline.crawler.web_crawler.WebCrawler._host_is_public",
        staticmethod(lambda host: host not in {"127.0.0.1", "localhost"}),
    )

    redirect = requests.Response()
    redirect.status_code = 302
    redirect.headers["Location"] = "http://127.0.0.1:8080/internal"
    redirect.url = "https://public.example/"
    redirect._content = b""
    redirect.raw = io.BytesIO()

    calls = []

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return redirect

    crawler.session = FakeSession()
    assert crawler._fetch("https://public.example/") is None
    assert calls == [("https://public.example/", {"timeout": 15.0, "allow_redirects": False})]


def test_public_redirect_is_followed_manually(monkeypatch):
    crawler = _crawler(monkeypatch)
    monkeypatch.setattr(
        "pipeline.crawler.web_crawler.WebCrawler._host_is_public",
        staticmethod(lambda host: True),
    )

    first = requests.Response()
    first.status_code = 302
    first.headers["Location"] = "/next"
    first.url = "https://public.example/"
    first._content = b""
    first.raw = io.BytesIO()

    second = requests.Response()
    second.status_code = 200
    second.url = "https://public.example/next"
    second._content = b"<html><title>ok</title>body</html>"

    responses = iter([first, second])
    calls = []

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return next(responses)

    crawler.session = FakeSession()
    result = crawler._fetch("https://public.example/")
    assert result is second
    assert [url for url, _ in calls] == ["https://public.example/", "https://public.example/next"]
    assert all(kwargs["allow_redirects"] is False for _, kwargs in calls)


def test_oversized_response_is_not_materialized(monkeypatch):
    crawler = _crawler(monkeypatch)
    crawler.web["seed_urls"] = ["https://public.example/"]
    monkeypatch.setattr(
        "pipeline.crawler.web_crawler.WebCrawler._host_is_public",
        staticmethod(lambda host: True),
    )

    response = requests.Response()
    response.status_code = 200
    response.url = "https://public.example/"
    response.headers["Content-Type"] = "text/html"
    response.iter_content = lambda chunk_size: iter([b"a" * 8, b"b" * 8])
    response.raw = io.BytesIO()

    class FakeSession:
        def get(self, url, **kwargs):
            return response

    crawler.session = FakeSession()
    crawler.web["max_content_bytes"] = 10
    assert list(crawler.crawl()) == []
    assert crawler.stats["skipped"] == 1
    assert crawler.stats["fetched"] == 1
