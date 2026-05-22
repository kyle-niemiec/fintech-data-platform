"""GET /ui/metrics/* — consumer-group lag and pipeline analytics.

Consumer lag is read over the Kafka protocol (see `services/consumer_lag.py`),
matching `make consumer-lag`. Pipeline analytics are derived from the
event-store read model (same read-only DB role used by ui_query).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_query_db
from services.consumer_lag import ConsumerLagUnavailable, fetch_consumer_lag

router = APIRouter(prefix="/ui/metrics", tags=["ui-metrics"])


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


@router.get(
    "/consumer-lag",
    response_model=list[ConsumerLagItem],
    status_code=status.HTTP_200_OK,
)
def get_consumer_lag() -> list[ConsumerLagItem]:
    """Return per-partition consumer lag for all known platform consumer groups."""
    try:
        rows = fetch_consumer_lag()
    except ConsumerLagUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redpanda unavailable: {exc}",
        ) from exc
    return [ConsumerLagItem(**row) for row in rows]


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
