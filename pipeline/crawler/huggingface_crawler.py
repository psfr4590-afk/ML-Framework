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

    @classmethod
    def _row_text_fields(cls, row: dict, text_fields: list[str]) -> str:
        parts: list[str] = []
        for field in text_fields:
            value = cls._row_text(row, field)
            if value:
                parts.append(f"{field}: {value}")
        return "\n\n".join(parts)

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
            revision = str(definition.get("revision", "")).strip()
            if not dataset_id or not revision:
                self.stats["skipped"] += 1
                log.warning("Hugging Face dataset definition requires repo and revision")
                continue

            split = str(definition.get("split", "train"))
            config = definition.get("config")
            text_field = str(definition.get("text_field", "text"))
            raw_text_fields = definition.get("text_fields", [])
            if isinstance(raw_text_fields, str):
                raw_text_fields = [raw_text_fields]
            text_fields = [str(field).strip() for field in raw_text_fields if str(field).strip()]
            if text_fields:
                effective_text_field = "+".join(text_fields)
            else:
                text_fields = [text_field]
                effective_text_field = text_field
            max_docs = max(0, int(definition.get("max_docs", 0)))
            if max_docs == 0:
                continue

            kwargs = {"split": split, "streaming": True, "revision": revision}
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
                    text = self._row_text_fields(row, text_fields)
                    if not text:
                        self.stats["skipped"] += 1
                        continue
                    self.stats["fetched"] += 1
                    doc = Document(
                        doc_id=f"hf:{dataset_id}:{revision}:{split}:{index}",
                        url=f"https://huggingface.co/datasets/{dataset_id}",
                        source="huggingface",
                        text=text,
                        title=f"{dataset_id} [{split}] #{index}",
                        language="en",
                        content_type="dataset",
                        domain="huggingface.co",
                        meta={
                            "dataset": dataset_id,
                            "revision": revision,
                            "config": config,
                            "split": split,
                            "text_field": effective_text_field,
                            "text_fields": text_fields,
                            "row_index": index,
                            "source_identity": {
                                "type": "huggingface_dataset_row",
                                "repo": dataset_id,
                                "revision": revision,
                                "config": config,
                                "split": split,
                                "row_index": index,
                            },
                            "rights_status": "review_required",
                            "license_status": "unknown",
                        },
                    )
                    if self.weight_lookup:
                        doc = self._apply_weights(doc)
                    if doc is not None:
                        yield doc
            except Exception as exc:  # dataset backends raise varied provider-specific exceptions
                self.stats["errors"] += 1
                log.warning("Hugging Face dataset crawl failed for %s@%s: %s", dataset_id, revision, exc)


__all__ = ["HuggingFaceCrawler"]
