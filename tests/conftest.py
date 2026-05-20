"""Shared pytest fixtures.

Adds service roots to sys.path so tests can import worker and pipeline modules
(`workers.*`, pipeline DAG modules) without an editable install.

Shared libraries are imported through the `meridian.libs.*` namespace, matching
the runtime images (worker Dockerfiles `COPY services/libs -> /app/meridian/libs`;
the orchestrator uses `/opt/airflow/meridian/libs`). That namespace is provided
by the environment, not fabricated here: run the suite inside the container image,
or locally with the libraries available as `meridian` (for example a `PYTHONPATH`
entry whose `meridian/libs` resolves to `services/libs`). Integration-tier fixtures
(redpanda, minio, event-store) are added in later slices under the `integration`
marker.
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
