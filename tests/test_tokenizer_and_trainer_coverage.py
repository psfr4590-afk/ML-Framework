from __future__ import annotations

import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline.tokenizer import train_tokenizer
from pipeline.trainer import train


def test_tokenizer_doc_stream_full_and_reservoir_paths(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    rows = [
        {"text": "alpha beta gamma"},
        {"text": ""},
        {"text": "delta epsilon"},
        "not-an-object",
        {"text": "zeta eta theta"},
        {"other": "missing text"},
    ]
    corpus.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
    assert list(train_tokenizer._doc_stream(corpus, None)) == [
        "alpha beta gamma", "delta epsilon", "zeta eta theta"
    ]
    sampled = list(train_tokenizer._doc_stream(corpus, 2, seed=7))
    assert len(sampled) == 2
    assert set(sampled).issubset({"alpha beta gamma", "delta epsilon", "zeta eta theta"})
    assert list(train_tokenizer._doc_stream(corpus, 0)) == []


def test_tokenizer_init_encode_load_and_dependency_guards(tmp_path, monkeypatch):
    cfg = {
        "vocab_size": 32,
        "min_frequency": 1,
        "special_tokens": ["<|unk|>"],
        "output_path": str(tmp_path / "tok"),
        "train_on_sample": True,
        "sample_size": 2,
    }
    trainer = train_tokenizer.BPETokenizerTrainer(cfg)
    assert trainer._vocab_size == 32 and trainer._sample_size == 2
    with pytest.raises(ValueError, match="trained tokenizer"):
        trainer.encode("x")
    monkeypatch.setattr(train_tokenizer, "HF_TOKENIZERS_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="not installed"):
        trainer.train(tmp_path / "missing.jsonl")
    with pytest.raises(RuntimeError, match="not installed"):
        trainer.load()


def test_tokenizer_real_train_and_load(tmp_path):
    # The tokenizer owns vocabulary construction.  Do not predict BPE output
    # with a second training path or hard-code a version-sensitive vocabulary.
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps({"text": "alpha bravo charlie delta echo"}) + "\n",
        encoding="utf-8",
    )

    trainer = train_tokenizer.BPETokenizerTrainer({
        "vocab_size": None,
        "min_frequency": 1,
        "special_tokens": ["<|unk|>"],
        "output_path": str(tmp_path / "tokenizer"),
    })
    tok = trainer.train(corpus)
    actual_vocab = tok.get_vocab_size()

    assert actual_vocab > 1
    assert trainer.load().get_vocab_size() == actual_vocab
    assert trainer.encode("alpha", tok)

    output = tmp_path / "tokenizer"
    config = json.loads((output / "tokenizer_config.json").read_text(encoding="utf-8"))
    assert config["vocab_size"] == actual_vocab
    assert config["provenance"]["vocab_size_requested"] is None
    assert config["provenance"]["corpus_sha256"]
    assert json.loads((output / "special_tokens_map.json").read_text(encoding="utf-8"))["unk_token"] == "<|unk|>"


def test_tokenizer_empty_corpus_and_contract_failures(tmp_path, monkeypatch):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("{}\n", encoding="utf-8")
    trainer = train_tokenizer.BPETokenizerTrainer({"vocab_size": 32, "output_path": str(tmp_path / "tok")})
    with pytest.raises(RuntimeError, match="no usable"):
        trainer.train(empty)

    trainer = train_tokenizer.BPETokenizerTrainer({"vocab_size": 32, "output_path": str(tmp_path / "tok2")})
    corpus = tmp_path / "one.jsonl"
    corpus.write_text(json.dumps({"text": "a small corpus with enough words"}) + "\n", encoding="utf-8")
    real = train_tokenizer.Tokenizer

    class FakeTokenizer:
        def __init__(self, *args, **kwargs):
            self.saved = False
        def train(self, *args, **kwargs):
            return None
        def get_vocab_size(self):
            return 1
        def token_to_id(self, token):
            return 0
        def save(self, path):
            Path(path).write_text("{}", encoding="utf-8")

    monkeypatch.setattr(train_tokenizer, "Tokenizer", FakeTokenizer)
    with pytest.raises(RuntimeError, match="vocabulary contract"):
        trainer.train(corpus)
    monkeypatch.setattr(train_tokenizer, "Tokenizer", real)


def test_tokenizer_load_missing_artifact(tmp_path):
    trainer = train_tokenizer.BPETokenizerTrainer({"output_path": str(tmp_path / "missing")})
    with pytest.raises(FileNotFoundError, match="No tokenizer"):
        trainer.load()


def test_trainer_helper_branches(tmp_path, monkeypatch):
    assert train.cosine_lr(0, 10, 1.0, 0.1, 100) == 0.0
    assert train.cosine_lr(100, 10, 1.0, 0.1, 100) == 0.1
    assert train.cosine_lr(50, 10, 1.0, 0.1, 100) < 1.0
    assert train._shard_manifest_hash(tmp_path) is None
    cfg = {"pipeline": {"output_dir": str(tmp_path)}, "_pipeline_config_sha256": "x", "train": {"seed": 9}}
    with pytest.raises(RuntimeError, match="shard manifest"):
        train._provenance(cfg, SimpleNamespace(to_dict=lambda: {}), tmp_path)
    with pytest.raises(RuntimeError, match="canonical"):
        train._provenance({"train": {}}, SimpleNamespace(to_dict=lambda: {}), tmp_path)
    assert train._source_manifest_hash({"pipeline": {"output_dir": str(tmp_path)}}) is None

    train._seed_everything(7)
    state = train._rng_state()
    random.random()
    train._restore_rng_state(state)
    assert train._rng_state()["python"] == state["python"]
    with pytest.raises(RuntimeError, match="invalid"):
        train._restore_rng_state(None)


def test_trainer_checkpoint_prune_and_eval(tmp_path):
    trainer = train.Trainer({"pipeline": {"output_dir": str(tmp_path)}, "train": {"allow_cpu_training": True}})
    ckpt = trainer.ckpt_dir
    ckpt.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (ckpt / f"ckpt_{i:07d}.pt").write_bytes(b"x")
    for i in range(4):
        (ckpt / f"ckpt_{i:07d}.pt.manifest.json").write_text("{}", encoding="utf-8")
    trainer._prune_checkpoints(ckpt, keep=2)
    assert not (ckpt / "ckpt_0000000.pt").exists()
    assert not (ckpt / "ckpt_0000001.pt").exists()
    assert (ckpt / "ckpt_0000002.pt").exists()
    assert (ckpt / "ckpt_0000003.pt").exists()

    class Loader:
        def next_batch(self, batch_size):
            return torch.ones((batch_size, 2), dtype=torch.long), torch.ones((batch_size, 2), dtype=torch.long)

    class Model:
        def eval(self): return self
        def train(self): return self
        def __call__(self, x, y): return x, torch.tensor(2.0)

    trainer.amp_dtype = torch.float16
    value = trainer._eval(Model(), Loader(), torch.device("cpu"), 2, 1)
    assert value == 2.0


def test_trainer_restore_rng_and_prune_missing_manifest(tmp_path):
    trainer = train.Trainer({"pipeline": {"output_dir": str(tmp_path)}, "train": {}})
    ckpt = trainer.ckpt_dir
    ckpt.mkdir(parents=True, exist_ok=True)
    (ckpt / "ckpt_0000001.pt").write_bytes(b"x")
    assert train.latest_checkpoint(ckpt) is None
    state = {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state()}
    train._restore_rng_state(state)
    with pytest.raises(KeyError):
        train._restore_rng_state({"python": state["python"], "numpy": state["numpy"]})


def test_tokenizer_provenance_and_artifact_contract_branches(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"text": "a b c"}) + "\n", encoding="utf-8")
    trainer = train_tokenizer.BPETokenizerTrainer({
        "vocab_size": 16, "min_frequency": 1,
        "special_tokens": ["<|unk|>", "<|bos|>"],
        "output_path": str(tmp_path / "tok"),
    })

    class MissingSpecialTokenizer:
        def __init__(self, *args, **kwargs): pass
        def train(self, *args, **kwargs): pass
        def get_vocab_size(self): return 16
        def token_to_id(self, token): return None
        def save(self, path): Path(path).write_text("{}", encoding="utf-8")

    monkeypatch.setattr(train_tokenizer, "Tokenizer", MissingSpecialTokenizer)
    with pytest.raises(RuntimeError, match="special-token contract"):
        trainer.train(corpus)

    class MissingArtifactTokenizer(MissingSpecialTokenizer):
        def token_to_id(self, token): return 0
        def save(self, path): pass

    monkeypatch.setattr(train_tokenizer, "Tokenizer", MissingArtifactTokenizer)
    with pytest.raises(RuntimeError, match="artifact contract"):
        trainer.train(corpus)


def test_tokenizer_stream_sampling_is_deterministic(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text("\n".join(json.dumps({"text": f"doc-{i}"}) for i in range(20)) + "\n", encoding="utf-8")
    first = list(train_tokenizer._doc_stream(corpus, 5, seed=99))
    second = list(train_tokenizer._doc_stream(corpus, 5, seed=99))
    assert first == second and len(first) == 5
