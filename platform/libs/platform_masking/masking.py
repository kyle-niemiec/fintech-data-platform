"""Deterministic PII masking for curated-layer transforms.

Callers must provide the salt via the ``PLATFORM_MASKING_SALT`` env var.
A missing salt is a fatal configuration error; this module never falls
back to a default because silver SCD2 identity depends on the salt
being stable across reruns.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Optional

_EMAIL_RE = re.compile(r"^([^@\s]+)@([^@\s]+)$")


def _salt() -> bytes:
    value = os.environ.get("PLATFORM_MASKING_SALT")
    if not value:
        raise RuntimeError("PLATFORM_MASKING_SALT is not set")
    return value.encode("utf-8")


def hash_pii(value: str) -> str:
    """Hex-encoded HMAC-SHA256(salt, value)."""
    return hmac.new(_salt(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def tokenize(value: str, *, scope: str) -> str:
    """Scoped 32-hex-char token. Same (value, scope) yields the same token.

    The scope prefix prevents cross-domain token correlation — tokens for
    the same raw value under different scopes must not collide.
    """
    if not scope:
        raise ValueError("scope must be non-empty")
    keyed = hmac.new(_salt(), f"{scope}:{value}".encode("utf-8"), hashlib.sha256)
    return keyed.hexdigest()[:32]


def mask_email(value: Optional[str]) -> Optional[str]:
    """Hash the local-part, preserve the domain. ``None`` passes through."""
    if value is None:
        return None
    match = _EMAIL_RE.match(value)
    if not match:
        raise ValueError(f"not an email: {value!r}")
    local, domain = match.group(1), match.group(2)
    return f"{tokenize(local, scope='email_local')}@{domain}"


def redact(value: str) -> str:
    """Mask the middle third of a string with ``*``. Empty passes through."""
    if not value:
        return value
    n = len(value)
    a = n // 3
    b = n - a
    return value[:a] + "*" * (b - a) + value[b:]
