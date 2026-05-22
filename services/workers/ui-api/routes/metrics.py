"""GET /ui/metrics/* — consumer-group lag and pipeline analytics.

Consumer lag endpoint calls the Redpanda Admin HTTP API (port 9644) to get
live consumer group offset data. Pipeline analytics are derived from the
event-store read model (same read-only DB role used by ui_query).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings
from db import get_query_db

router = APIRouter(prefix="/ui/metrics", tags=["ui-metrics"])

_KNOWN_GROUPS = [
    "excel-scanner-v1",
    "excel-trigger-v1",
    "excel-bronze-writer-v1",
    "cdc-fraud-worker-v1",
    "cdc-bronze-writer-v1",
    "salesforce-bronze-writer-v1",
    "airflow-curated-silver-v1",
    "airflow-curated-gold-v1",
]


class ConsumerLagItem(BaseModel):
    group: str
    topic: str
    partition: int
    current_offset: int
    log_end_offset: int
    lag: int


class PipelineAnalyticsItem(BaseModel):
    pipeline_name: str
    completed: int
    failed: int
    quarantined: int
    scan_failed: int
    avg_duration_seconds: float | None
    alerts_high: int
    alerts_medium: int


def _fetch_redpanda_groups() -> list[dict[str, Any]]:
    url = f"http://{settings.redpanda_admin_host}:{settings.redpanda_admin_port}/v1/groups"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redpanda admin API unavailable: {exc}",
        ) from exc


@router.get(
    "/consumer-lag",
    response_model=list[ConsumerLagItem],
    status_code=status.HTTP_200_OK,
)
def get_consumer_lag() -> list[ConsumerLagItem]:
    """Return per-partition consumer lag for all known platform consumer groups."""
    groups_data = _fetch_redpanda_groups()

    lag_items: list[ConsumerLagItem] = []
    known = set(_KNOWN_GROUPS)

    for group in groups_data:
        group_id = group.get("group_id", "")
        if group_id not in known:
            continue
        for member in group.get("members", []):
            for assignment in member.get("client_host", []):
                pass
        # Redpanda /v1/groups returns partition assignment; lag is in committed
        # vs high-watermark. Flatten all partition entries.
        for partition_offset in group.get("members", []):
            for pa in partition_offset.get("member_assignment", {}).get("topic_partitions", []):
                topic = pa.get("topic", "")
                for p in pa.get("partitions", []):
                    partition = p.get("partition_index", 0)
                    committed = p.get("committed_offset", 0)
                    hw = p.get("high_watermark", committed)
                    lag_items.append(
                        ConsumerLagItem(
                            group=group_id,
                            topic=topic,
                            partition=partition,
                            current_offset=committed,
                            log_end_offset=hw,
                            lag=max(0, hw - committed),
                        )
                    )

    return lag_items


@router.get(
    "/pipeline-analytics",
    response_model=list[PipelineAnalyticsItem],
    status_code=status.HTTP_200_OK,
)
def get_pipeline_analytics(
    db: Session = Depends(get_query_db),
) -> list[PipelineAnalyticsItem]:
    """Return 30-day run counts, avg duration, and alert summary per pipeline."""
    rows = db.execute(
        text(
            """
            SELECT
                pr.pipeline_name,
                COUNT(*) FILTER (WHERE pr.status = 'completed')   AS completed,
                COUNT(*) FILTER (WHERE pr.status = 'failed')       AS failed,
                COUNT(*) FILTER (WHERE pr.status = 'quarantined')  AS quarantined,
                COUNT(*) FILTER (WHERE pr.status = 'scan_failed')  AS scan_failed,
                AVG(
                    EXTRACT(EPOCH FROM (pr.completed_at - pr.started_at))
                ) FILTER (WHERE pr.status = 'completed' AND pr.completed_at IS NOT NULL)
                    AS avg_duration_seconds
            FROM event_store.pipeline_run pr
            WHERE pr.started_at >= now() - INTERVAL '30 days'
            GROUP BY pr.pipeline_name
            ORDER BY pr.pipeline_name
            """
        )
    ).mappings()

    run_data = {row["pipeline_name"]: dict(row) for row in rows}

    alert_rows = db.execute(
        text(
            """
            SELECT
                pr.pipeline_name,
                COUNT(*) FILTER (WHERE ae.severity = 'high')   AS alerts_high,
                COUNT(*) FILTER (WHERE ae.severity = 'medium') AS alerts_medium
            FROM event_store.alert_event ae
            JOIN event_store.pipeline_run pr ON pr.run_id = ae.run_id
            WHERE ae.occurred_at >= now() - INTERVAL '30 days'
            GROUP BY pr.pipeline_name
            """
        )
    ).mappings()

    alert_data: dict[str, dict] = {}
    for row in alert_rows:
        alert_data[row["pipeline_name"]] = dict(row)

    all_pipelines = sorted(set(run_data) | set(alert_data))
    result = []
    for name in all_pipelines:
        rd = run_data.get(name, {})
        ad = alert_data.get(name, {})
        result.append(
            PipelineAnalyticsItem(
                pipeline_name=name,
                completed=rd.get("completed", 0) or 0,
                failed=rd.get("failed", 0) or 0,
                quarantined=rd.get("quarantined", 0) or 0,
                scan_failed=rd.get("scan_failed", 0) or 0,
                avg_duration_seconds=rd.get("avg_duration_seconds"),
                alerts_high=ad.get("alerts_high", 0) or 0,
                alerts_medium=ad.get("alerts_medium", 0) or 0,
            )
        )
    return result
