"""Hugging Face Hub dataset record crawler."""
from __future__ import annotations

import json
import logging
import os
from typing import Iterator

from datasets import load_dataset

from pipeline.crawler.base import BaseCrawler
from pipeline.types import Document

log = logging.getLogger("crawler.huggingface")


class HuggingFaceCrawler(BaseCrawler):
    def __init__(self, cfg: dict, weight_lookup, signal_tracker):
        super().__init__(cfg, weight_lookup, signal_tracker)
        self.cfg_hf = cfg.get("huggingface", {})
        self.timeout = int(cfg.get("timeout", 20))
        token_env = self.cfg_hf.get("token_env", "HF_TOKEN")
        self.token = os.getenv(token_env, "")

    @staticmethod
    def _row_text(row: dict, text_field: str) -> str:
        value = row.get(text_field)
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def crawl(self) -> Iterator[Document]:
        datasets = self.cfg_hf.get("datasets", [])
        if isinstance(datasets, str):
            datasets = [datasets]

        for definition in datasets:
            if isinstance(definition, str):
                definition = {"repo": definition}
            if not isinstance(definition, dict):
                self.stats["skipped"] += 1
                log.warning("Invalid Hugging Face dataset definition: %r", definition)
                continue

            dataset_id = str(definition.get("repo", "")).strip()
            if not dataset_id:
                self.stats["skipped"] += 1
                log.warning("Hugging Face dataset definition is missing repo")
                continue

            split = str(definition.get("split", "train"))
            config = definition.get("config")
            text_field = str(definition.get("text_field", "text"))
            max_docs = max(0, int(definition.get("max_docs", 0)))
            if max_docs == 0:
                continue

            kwargs = {"split": split, "streaming": True}
            if config:
                kwargs["name"] = str(config)
            if self.token:
                kwargs["token"] = self.token

            try:
                stream = load_dataset(dataset_id, **kwargs)
                for index, row in enumerate(stream):
                    if index >= max_docs:
                        break
                    if not isinstance(row, dict):
                        self.stats["skipped"] += 1
                        continue
                    text = self._row_text(row, text_field)
                    if not text:
                        self.stats["skipped"] += 1
                        continue
                    self.stats["fetched"] += 1
                    doc = Document(
                        doc_id=f"hf:{dataset_id}:{split}:{index}",
                        url=f"https://huggingface.co/datasets/{dataset_id}",
                        source="huggingface",
                        text=text,
                        title=f"{dataset_id} [{split}] #{index}",
                        language="en",
                        content_type="dataset",
                        domain="huggingface.co",
                        meta={
                            "dataset": dataset_id,
                            "config": config,
                            "split": split,
                            "text_field": text_field,
                            "row_index": index,
                        },
                    )
                    if self.weight_lookup:
                        doc = self._apply_weights(doc)
                    yield doc
            except Exception as exc:  # dataset backends raise varied provider-specific exceptions
                self.stats["errors"] += 1
                log.warning("Hugging Face dataset crawl failed for %s: %s", dataset_id, exc)


__all__ = ["HuggingFaceCrawler"]
