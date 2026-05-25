#!/usr/bin/env python3

import base64
import hashlib
import os
import secrets


def deterministic_value(seed: str, key: str) -> str:
	"""Generate deterministic placeholder values from a stable seed."""
	digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()
	return f"ci_{digest[:40]}"


def random_value(_: str) -> str:
	"""Generate random placeholder values for one-off deploy environments."""
	return secrets.token_hex(24)


def fernet_key_random() -> str:
	"""Generate a random Fernet-compatible key."""
	return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def fernet_key_deterministic(seed: str, key: str) -> str:
	"""Generate deterministic Fernet-compatible key material for CI/integration mode."""
	raw = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
	return base64.urlsafe_b64encode(raw).decode("ascii")
