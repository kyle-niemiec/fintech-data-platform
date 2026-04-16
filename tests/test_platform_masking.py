"""Unit tests for libs.platform_masking.

The masking library must be deterministic: reruns with the same salt
must produce identical outputs so silver SCD2 identity is stable across
replays. All functions must take their salt from PLATFORM_MASKING_SALT;
missing salt is a fatal configuration error, not a fallback.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _salt(monkeypatch):
    monkeypatch.setenv("PLATFORM_MASKING_SALT", "test-salt-v1")


def test_mask_email_preserves_domain_and_hashes_local():
    from libs.platform_masking import mask_email

    masked = mask_email("jane.doe@acme.co")

    assert masked.endswith("@acme.co")
    assert masked != "jane.doe@acme.co"
    assert mask_email("jane.doe@acme.co") == masked


def test_mask_email_passes_none_through():
    from libs.platform_masking import mask_email

    assert mask_email(None) is None


def test_mask_email_raises_on_malformed():
    from libs.platform_masking import mask_email

    with pytest.raises(ValueError):
        mask_email("not-an-email")


def test_tokenize_is_deterministic_and_scoped():
    from libs.platform_masking import tokenize

    same_scope_a = tokenize("12345", scope="account_id")
    same_scope_b = tokenize("12345", scope="account_id")
    other_scope = tokenize("12345", scope="opportunity_id")

    assert same_scope_a == same_scope_b
    assert same_scope_a != other_scope
    assert len(same_scope_a) == 32
    assert all(ch in "0123456789abcdef" for ch in same_scope_a)


def test_tokenize_requires_non_empty_scope():
    from libs.platform_masking import tokenize

    with pytest.raises(ValueError):
        tokenize("12345", scope="")


def test_hash_pii_returns_64_char_hex():
    from libs.platform_masking import hash_pii

    digest = hash_pii("SSN:123-45-6789")

    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)
    assert hash_pii("SSN:123-45-6789") == digest


def test_redact_masks_middle_third():
    from libs.platform_masking import redact

    assert redact("555-867-5309") == "555-****5309"
    assert redact("abcdef") == "ab**ef"
    assert redact("") == ""
    assert redact("abc") == "a*c"


def test_missing_salt_raises():
    import importlib

    import libs.platform_masking.masking as masking

    importlib.reload(masking)

    import os

    os.environ.pop("PLATFORM_MASKING_SALT", None)

    with pytest.raises(RuntimeError):
        masking.hash_pii("anything")
