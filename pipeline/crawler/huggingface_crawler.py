"""Hugging Face Hub dataset metadata crawler."""
from __future__ import annotations

import logging
import os
from typing import Iterator

import requests

from pipeline.crawler.base import BaseCrawler
from pipeline.types import Document

log = logging.getLogger("crawler.huggingface")


class HuggingFaceCrawler(BaseCrawler):
    def __init__(self, cfg: dict, weight_lookup, signal_tracker):
        super().__init__(cfg, weight_lookup, signal_tracker)
        self.cfg_hf = cfg.get("huggingface", {})
        self.timeout = int(cfg.get("timeout", 20))
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "ML-Framework/1.3"
        token = os.getenv(self.cfg_hf.get("token_env", "HF_TOKEN"), "")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def crawl(self) -> Iterator[Document]:
        datasets = self.cfg_hf.get("datasets", [])
        if isinstance(datasets, str):
            datasets = [datasets]
        for dataset_id in datasets:
            url = f"https://huggingface.co/api/datasets/{dataset_id}"
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                item = resp.json()
                self.stats["fetched"] += 1
            except (requests.RequestException, ValueError) as exc:
                self.stats["errors"] += 1
                log.warning("Hugging Face dataset query failed for %s: %s", dataset_id, exc)
                continue
            tags = item.get("tags") or []
            text = "\n".join(filter(None, [item.get("id", dataset_id), item.get("description", ""), "Tags: " + ", ".join(tags) if tags else ""]))
            doc = Document(
                doc_id=f"hf:{item.get('id', dataset_id)}", url=f"https://huggingface.co/datasets/{dataset_id}",
                source="huggingface", text=text, title=item.get("id", dataset_id),
                language="en", content_type="dataset", domain="huggingface.co",
                meta={"downloads": item.get("downloads", 0), "likes": item.get("likes", 0), "tags": tags},
            )
            if self.weight_lookup:
                doc = self._apply_weights(doc)
            yield doc


__all__ = ["HuggingFaceCrawler"]
