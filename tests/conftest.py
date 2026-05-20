"""Shared pytest fixtures.

Adds service roots to sys.path so tests can import `workers` and `libs`
without requiring editable installs. Integration-tier fixtures (redpanda,
minio, event-store) are added in later slices under the `integration` marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYTHONPATH_ROOTS = (
    _REPO_ROOT / "services" / "pipeline",
    _REPO_ROOT / "services" / "workers" / "salesforce-mock-api",
    _REPO_ROOT / "services",
    _REPO_ROOT / "services" / "workers" / "ui-api",
)

for path in _PYTHONPATH_ROOTS:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
