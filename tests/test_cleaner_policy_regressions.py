import os

import pytest

from pipeline.cleaner.cleaner import Cleaner


@pytest.mark.parametrize("spans, expected", [
    ([(2, 7), (5, 9)], "ab[REMOVED]j"),
    ([(2, 9), (3, 5)], "ab[REMOVED]j"),
    ([(2, 5), (2, 5)], "ab[REMOVED]fghij"),
    ([(1, 3), (6, 8)], "a[REMOVED]def[REMOVED]ij"),
    ([(2, 5), (5, 8)], "ab[REMOVED]ij"),
    ([], "abcdefghij"),
    ([(2, 2)], "abcdefghij"),
])
def test_redaction_uses_union_of_original_spans(spans, expected):
    cleaner = Cleaner.__new__(Cleaner)
    hits = [{"span": span} for span in spans]
    assert cleaner._redact("abcdefghij", hits) == expected
    assert cleaner._redact("abcdefghij", list(reversed(hits))) == expected


def test_redaction_rejects_out_of_range_span():
    with pytest.raises(ValueError):
        Cleaner.__new__(Cleaner)._redact("abc", [{"span": (0, 4)}])


def write_config(path, minimum=1, redact=False):
    text = (
        "general:\n"
        f"  min_doc_length: {minimum}\n"
        "  action: redact\n"
        "  score_threshold: 0.01\n"
        "html:\n  enabled: false\n"
        "unicode:\n  enabled: false\n"
        "dedup:\n  enabled: false\n"
        f"refusal_filter:\n  enabled: {str(redact).lower()}\n"
    )
    if redact:
        text += (
            "  instant_drop_patterns:\n    enabled: false\n"
            "  pattern_groups:\n    overlapping:\n"
            "      patterns: ['cdefg', 'fghi']\n"
        )
    path.write_text(text, encoding="utf-8")


def change_policy(path):
    old = path.stat().st_mtime
    write_config(path, minimum=20)
    os.utime(path, (old + 10, old + 10))


def test_default_policy_stays_fixed_after_file_edit(tmp_path):
    path = tmp_path / "cleaner.yaml"
    write_config(path)
    cleaner = Cleaner(path)
    change_policy(path)
    assert cleaner.clean("abc").kept


def test_auto_reload_requires_explicit_opt_in(tmp_path):
    path = tmp_path / "cleaner.yaml"
    write_config(path)
    cleaner = Cleaner(path, auto_reload=True)
    change_policy(path)
    assert cleaner.clean("abc").action == "too_short"


def test_manual_reload_remains_available(tmp_path):
    path = tmp_path / "cleaner.yaml"
    write_config(path)
    cleaner = Cleaner(path)
    change_policy(path)
    cleaner.reload()
    assert cleaner.clean("abc").action == "too_short"


def test_clean_redacts_overlapping_pattern_matches(tmp_path):
    path = tmp_path / "cleaner.yaml"
    write_config(path, redact=True)
    cleaner = Cleaner(path)
    result = cleaner.clean("abcdefghij", doc_id="overlap-fixture")
    assert result.kept
    assert result.action == "redacted"
    assert result.text == "ab[REMOVED]j"
    assert result.doc_id == "overlap-fixture"
