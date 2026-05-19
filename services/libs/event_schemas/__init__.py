"""Excel schema contract assets."""

from __future__ import annotations

from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent


def contract_path(contract_id: str) -> Path:
    return SCHEMAS_DIR / f"{contract_id}.json"


__all__ = ["SCHEMAS_DIR", "contract_path"]
