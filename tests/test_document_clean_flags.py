import json

import pytest

from pipeline.types import Document


def test_flagged_action_at_construction_sets_flag():
    assert Document(doc_id="a", clean_action="flagged").flagged is True


def test_clean_action_assigned_after_construction_is_serialized_as_flagged():
    document = Document(doc_id="a", text="some training text")
    document.clean_action = "flagged"
    assert document.to_jsonl()["flagged"] is True


def test_flag_survives_jsonl_round_trip():
    document = Document(doc_id="a")
    document.clean_action = "flagged"
    restored = Document.from_dict(json.loads(json.dumps(document.to_jsonl())))
    assert restored.flagged is True
    assert restored.clean_action == "flagged"


def test_old_flagged_record_is_normalized_on_read():
    document = Document.from_dict({"doc_id": "a", "flagged": False, "clean_action": "flagged"})
    assert document.flagged is True


@pytest.mark.parametrize("action", ["", "kept", "redacted"])
def test_existing_independent_flags_are_not_cleared(action):
    assert Document(doc_id="a", flagged=True, clean_action=action).to_jsonl()["flagged"] is True


@pytest.mark.parametrize("action", ["", "kept", "redacted"])
def test_unflagged_actions_remain_unflagged(action):
    assert Document(doc_id="a", clean_action=action).to_jsonl()["flagged"] is False


def test_serialization_does_not_mutate_original_document():
    document = Document(doc_id="a", embedding=[1.0])
    document.clean_action = "flagged"
    before = document.__dict__.copy()
    output = document.to_jsonl()
    assert output["flagged"] is True
    assert "embedding" not in output
    assert document.__dict__ == before
