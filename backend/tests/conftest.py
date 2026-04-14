"""Shared pytest fixtures.

Adds `backend/` to sys.path so tests can `from libs.platform_events import ...`
without requiring an editable install. Integration-tier fixtures (redpanda,
minio, event-store) are added in later slices under the `integration` marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
