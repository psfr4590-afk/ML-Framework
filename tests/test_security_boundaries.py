from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.crawler.content_parser import ContentParseError, parse_content
from ui.services.log_service import LogService


def test_xml_parser_rejects_external_entities():
    payload = b'''<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>'''
    with pytest.raises(Exception):
        parse_content("payload.xml", "application/xml", payload)


def test_log_service_rejects_arbitrary_file(tmp_path: Path):
    secret = tmp_path / "secret.log"
    secret.write_text("not a command-center log", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        LogService().tail(secret, 10)


def test_log_service_rejects_symlink(tmp_path: Path):
    allowed = Path("datasets")
    target = tmp_path / "target.log"
    target.write_text("secret", encoding="utf-8")
    link = allowed / "security-test.log"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    try:
        with pytest.raises(ValueError):
            LogService().tail(link, 10)
    finally:
        link.unlink(missing_ok=True)
